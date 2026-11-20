# Plan técnico — Spec 006

> Basado en `spec.md` (estado: Aclarada). No añade comportamiento que no esté en la spec. `src/agent.py`, `src/graph.py` y `src/state.py` no cambian (spec 003).

## Archivos afectados
| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `requirements.txt` | Modificar | Añade `fastapi`, `uvicorn`, `sqlmodel`, `psycopg[binary]` (versiones compatibles con Python 3.10+, se fijan al instalar) | RF-1, 31 |
| `requirements-dev.txt` | Modificar | Añade `httpx` (cliente de pruebas de FastAPI) | tests |
| `config.py` | Modificar | Lee del entorno: `API_KEY`, `DATABASE_URL`, `RATE_LIMIT_PER_MINUTE` (30), `ASK_TIMEOUT_SECONDS` (60), `CORS_ORIGINS` (lista separada por comas, vacío por defecto). Constantes fijas: `PREGUNTA_MAX_CHARS=2000`, `COMENTARIO_MAX_CHARS=500`, `THREAD_ID_MAX_CHARS=64`, `DB_CONNECT_TIMEOUT_SECONDS`, rutas protegidas | RF-6, 8, 11, 18, 19, 29, 40 |
| `.env.example` | Modificar | Solo los nombres: `API_KEY`, `DATABASE_URL`, `RATE_LIMIT_PER_MINUTE`, `ASK_TIMEOUT_SECONDS`, `CORS_ORIGINS` | RF-6, 8, 11, 39, 40 |
| `schemas.py` | Crear | Modelos Pydantic de entrada y salida con sus validaciones | RF-15 a 20, 26 a 29, 34, 35 |
| `security.py` | Crear | Compuerta de acceso (503→401→429), limitador de ventana fija, log por petición, filtro que enmascara la clave | RF-5 a 10, 38, 39 |
| `src/models.py` | Crear | Tabla de turnos cerrados (`Turn`) | RF-31, 32 |
| `src/db.py` | Crear | Normalización de URL, motor, repositorio (`save`, `list`, `ping`), creación perezosa de tablas | RF-2, 3, 12, 31 a 37 |
| `api.py` | Crear | `create_app(repo, agent)`, rutas, manejadores de error, registro de planes pendientes, reserva de peticiones en curso, límite de tiempo y `CORSMiddleware` | RF-1 a 4, 11 a 37, 40 |
| `tests/conftest.py` | Modificar | Fixtures de la API: agente falso, repositorio en memoria, cliente | todos |
| `tests/test_config_api.py`, `test_models.py`, `test_db_url.py`, `test_db_repository.py`, `test_repository_contract.py`, `test_api_schemas.py`, `test_api_limiter.py`, `test_api_gate.py`, `test_api_logs.py`, `test_api_app.py`, `test_api_ask.py`, `test_api_approve.py`, `test_api_historial.py`, `test_api_integration.py` | Crear | Tests por RF (sección Estrategia de tests) | todos |
| `AGENTS.md` | Modificar | Quita los `[COMPLETAR]` de lo ya creado; arranque `uvicorn api:app --no-access-log` con un solo worker | RF-39 |

## Contrato
Toda ruta protegida lleva `?api_key=...`. Los errores siempre devuelven `{"detail": "<mensaje en español>"}`.

```text
POST /ask?api_key=K
{"pregunta": "Organiza una visita de dos horas al Retiro",
 "thread_id": "visita-1", "auto_aprobar": false}
→ 200 {"respuesta": "...**Propuesta de visita**...", "plan": ["...", "..."],
       "thread_id": "visita-1", "done": false, "pendiente_hitl": true, "error": null}

POST /approve?api_key=K
{"thread_id": "visita-1", "aprobado": true, "comentario": "Perfecto"}
→ 200 {..., "done": true, "pendiente_hitl": false, "error": null}
(con aprobado=false: 200, done=false, pendiente_hitl=false)

GET /threads/visita-1/messages?api_key=K
→ 200 [{"role": "user", "content": "Organiza una visita...", "created_at": "2026-11-19T10:15:00Z"},
       {"role": "assistant", "content": "...", "created_at": "...",
        "decision": "aprobado", "comentario": "Perfecto"}]

GET /health → 200 {"status": "ok", "storage": "postgres", "db": "ok"}
```

| Situación | Código |
|---|---|
| `API_KEY` sin configurar / clave ausente o incorrecta / más de 30 peticiones por minuto | 503 / 401 / 429 |
| Entrada no válida (`pregunta`, `comentario`, `thread_id`) | 422 |
| Plan pendiente al hacer `/ask`; sin plan pendiente al hacer `/approve`; petición en curso en el mismo hilo | 409 |
| Hilo sin turnos cerrados | 404 |
| El agente tarda más de 60 s | 504 |
| Error interno del agente | 500 |
| Postgres no responde al guardar o leer | 503 |

| Concepto | Valor |
|---|---|
| Rutas públicas (sin `api_key`) | `/health`, `/docs`, `/openapi.json` |
| Rutas protegidas | `/ask`, `/approve`, `/threads/{thread_id}/messages` |
| Cabeceras CORS | Solo para orígenes de `CORS_ORIGINS`; la petición de comprobación previa (OPTIONS) no exige `api_key` |

### Contrato del repositorio (entre `api.py` y `src/db.py`)
```python
class TurnRepository:
    def __init__(self, engine) -> None: ...
    def save(self, thread_id: str, question: str, answer: str,
             decision: str | None, comment: str | None) -> None
    def list(self, thread_id: str) -> list      # más antiguo primero; [] si no hay turnos
    def ping(self) -> bool                      # nunca lanza

def normalize_database_url(url: str) -> str     # postgres:// y postgresql:// → postgresql+psycopg://
def make_engine(url: str | None = None)         # por defecto config.DATABASE_URL
def make_repository(url: str | None = None) -> TurnRepository
```
`decision` es `"aprobado"`, `"rechazado"` o `None`. `comment` es texto, `""` (auto-aprobación) o `None`. Cada elemento de `list` tiene `thread_id`, `question`, `answer`, `decision`, `comment` y `created_at` (UTC con zona). `save` y `list` lanzan la excepción del motor si falla; la API trata cualquier excepción del repositorio como 503.

## Lógica clave
```text
create_app(repo=None, agent=None):
  lee RATE_LIMIT_PER_MINUTE, ASK_TIMEOUT_SECONDS y CORS_ORIGINS de config
  repo por defecto: make_repository() ; agent por defecto: src.agent
  middleware, de fuera a dentro: CORS → compuerta (503→401→429, log) → rutas

compuerta, ruta protegida y método distinto de OPTIONS:
  API_KEY vacía → 503 ; api_key ausente o incorrecta → 401 ; limitador > límite → 429
  al terminar: log(método, ruta sin query, thread_id, duration_ms, status)

POST /ask:
  tid = body.thread_id o uuid4().hex ; request.state.thread_id = tid
  si tid en pendientes → 409
  si no se puede reservar tid en en_curso → 409
  # una sola tarea en un hilo, con límite ASK_TIMEOUT_SECONDS (shield: el hilo no se cancela)
  tarea: r = procesar_turno(pregunta, tid)
         si r.pendiente y auto_aprobar: r = aprobar_plan(tid, True, "")
  si timeout → 504 (no se guarda nada)
  si r.error → 500 genérico
  si r.pendiente: pendientes[tid] = (pregunta, r.respuesta) ; devolver pendiente_hitl=true
  si no: guardar(tid, pregunta, r.respuesta, "aprobado" si hubo plan auto, si no None, "" o None)
  la reserva en_curso se libera cuando el hilo termina de verdad

POST /approve:
  si tid no en pendientes → 409 ; reservar tid o 409
  r = aprobar_plan(tid, aprobado, comentario or "")   # mismo límite de tiempo
  si r.error → 500 (el pendiente se conserva)
  p = pendientes.pop(tid)
  guardar(tid, p.pregunta, p.respuesta, "aprobado"/"rechazado", comentario)
  devolver r (rechazo: done=false)

GET messages: validar tid → turnos = repo.list(tid) → vacío: 404 → aplanar en pares user/assistant
```

## Decisiones técnicas
| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Compuerta como **middleware** | `Depends` de FastAPI | Con `Depends`, un JSON mal formado da 422 antes que 401 y se rompe el orden de RF-10. |
| Campo `api_key` declarado en cada ruta solo para Swagger | Esquema de seguridad con botón "Authorize" | RF-4 pide un campo en cada ruta. |
| **Registro propio** de planes pendientes (en memoria) | Leer el estado del grafo | Constitución §6: la API solo llama a `procesar_turno` y `aprobar_plan`. El agente borra la propuesta al rechazar y RF-32 exige guardarla. Cuadra con §12 (un solo proceso). |
| Todo `error` del agente → 500; los 409 salen del registro propio | Interpretar el texto del error | No depende de la redacción de los mensajes. |
| Límite de tiempo con hilo + `asyncio.shield` | Matar el hilo o lanzar un proceso hijo | Un hilo no se puede matar y un proceso hijo perdería el checkpoint en memoria (§12). La reserva se libera al terminar la tarea real. |
| Auto-aprobación en la API (`procesar_turno` y luego `aprobar_plan(True)`) | Cambiar el agente | Spec 003 y AGENTS.md prohíben cambiar su contrato. |
| `create_app(repo=None, agent=None)` con inyección | Globales y `monkeypatch` | Aísla el estado entre tests y permite simular un reinicio. |
| Cualquier excepción del repositorio → 503 | Clase de error compartida | Desacopla `api.py` de `src/db.py` y permite trabajar en paralelo. |
| Tests con **SQLite en memoria** | Postgres con Docker | Constitución §9 (sin red); Docker está fuera de esta spec. |
| `create_all` al arrancar con reintento perezoso | Alembic | Prohibido por §11. `/health` debe responder aunque Postgres caiga (RF-3). |
| Limitador de ventana fija en memoria | `slowapi` o Redis | Redis prohibido (§11) y `slowapi` sería una dependencia más. |
| Log con `logging` estándar a stdout, en JSON | Reutilizar `logging_utils` | Ese módulo escribe consultas del RAG en un fichero; Render lee stdout. |
| Desactivar el log de acceso de uvicorn y filtro que enmascara `api_key=` | Dejarlo | La clave viaja en la query y saldría en el log de acceso (RF-39). |
| Manejadores propios para 422 y 404/405 | Respuestas por defecto de FastAPI | RF-14 exige `{"detail": "<texto en español>"}`. |
| `pregunta` recortada con `strip` antes de medir 1 a 2000 | Medir sin recortar | Coincide con el agente, que ya recorta. |
| `CORSMiddleware` como capa **más externa** | Colocarlo dentro de la compuerta | Si no, OPTIONS sin `api_key` recibiría 401 y las respuestas 401/429 saldrían sin cabeceras CORS. |
| `CORS_ORIGINS` vacío por defecto, sin credenciales | Comodín `*` | La API usa `api_key` en la query, no cookies; un comodín la abriría a cualquier navegador. |
| Desactivar `/redoc` (`redoc_url=None`) | Dejarlo público | RF-1 lista exactamente las rutas; no se añade otra pública. |
| `create_app()` lee la configuración al crearse y los tests la parchean antes | Leerla en cada petición | Necesario para CORS; no cambia el comportamiento de los demás ajustes. |
| RF-22 aplicado a `/ask` y `/approve` (no a `GET messages`) | Bloquear también las lecturas | Interpretación aprobada: solo esas rutas ejecutan el agente. |
| Dependencias nuevas: fastapi, uvicorn, sqlmodel, psycopg[binary], httpx (dev) | — | Aprobadas; el stack ya las contempla (§11). |

## Estrategia de tests
**Dobles**:
- Agente falso con las mismas claves que la respuesta pública del agente real, con contador de llamadas y bloqueo por `Event` para simular lentitud.
- `InMemoryTurnRepository` en `tests/conftest.py`, con un interruptor para forzar fallos. Y `TurnRepository` sobre SQLite en memoria.
- Reloj inyectable en el limitador.
- `caplog` para los logs.
- Un test de contrato llama a la función real `procesar_turno("")`, que devuelve el error de consulta vacía sin tocar el grafo, y comprueba que las claves coinciden con las del falso.
- `tests/test_repository_contract.py` ejecuta las mismas aserciones contra las dos implementaciones del repositorio.

**Solo a mano**:
- Que Swagger muestre el campo `api_key` en cada ruta protegida (RF-4; el `openapi.json` sí se comprueba en test).
- Reinicio real del servicio con Postgres (RF-37).
- Caída real de Postgres (RF-12).
- Que la salida de uvicorn no contenga la clave (RF-39): arrancar con `uvicorn api:app --no-access-log`, hacer peticiones e inspeccionar la consola.
- La demo de Swagger de los criterios de finalización.

## Riesgos
- **Tras un 504 el hilo sigue ejecutándose**: consume recursos y el `thread_id` queda bloqueado con 409 hasta que termine. Por eso la spec pide empezar otro hilo.
- **`api_key` en la URL**: puede quedar en historiales del navegador y en logs del proxy de Render, que no controlamos.
- **`auto_aprobar=true` por defecto**: si el front olvida enviar `false`, los planes se aprueban sin humano. Conviene un test en la spec del front.
- **Fallo de Postgres tras ejecutar el agente**: el plan ya se aplicó y el cliente ve 503 (límite conocido, RF-12). Aplica igual a `/ask` con auto-aprobación.
- **Divergencia entre el registro de pendientes y el grafo**: se evita porque ambos viven en el mismo proceso y se reinician juntos.
- **SQLite frente a Postgres**: diferencias de zona horaria en fechas. Se normaliza a UTC al leer.
- **Render entrega `postgres://`**: SQLAlchemy necesita `postgresql+psycopg://`; se normaliza en `src/db.py`.
- **`request.state.thread_id` compartido entre ruta y middleware**: se verifica con el test del log.
- **Importar `api` importa `src.agent`**, que construye el grafo; ya ocurre en los tests actuales y no llama a ninguna API.
- **Orden de los middlewares**: si alguien reordena el CORS por dentro de la compuerta, se rompe la comprobación previa del navegador. Lo cubre el test de RF-40.
- **Variables de Render mal escritas**: un `CORS_ORIGINS` con espacios o sin esquema (`https://`) no coincide con el origen real. Se recortan espacios al parsear; la validación del esquema queda para quien configure Render.
- **Un origen de CORS no protege la API**: la autenticación sigue siendo la `api_key`.
- **Los dos repositorios pueden divergir**: lo mitiga `test_repository_contract.py`.

## Notas para la spec de Docker y Render (fuera de esta spec)
- **Arranque**: `uvicorn api:app --no-access-log`, **un solo worker** (sin `--workers`, constitución §12), `--host 0.0.0.0` y el puerto que asigne Render.
- **Variables en el panel de Render**: `API_KEY`, `DATABASE_URL`, `RATE_LIMIT_PER_MINUTE`, `ASK_TIMEOUT_SECONDS`, `CORS_ORIGINS`. Ninguna va en la imagen ni en el repositorio.
- **`DATABASE_URL`**: Render entrega `postgres://`, que `src/db.py` normaliza.

## Trazabilidad
| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | `api.py`, rutas | `tests/test_api_app.py::test_rutas_expuestas` |
| RF-2 | `/health`, `ping` | `tests/test_api_app.py::test_health_ok`, `tests/test_db_repository.py::test_ping_sano` |
| RF-3 | `ping`, Riesgos | `tests/test_api_app.py::test_health_db_error_sigue_200` |
| RF-4 | campo `api_key` por ruta, `/docs` | `tests/test_api_app.py::test_openapi_declara_api_key` + manual Swagger |
| RF-5 | compuerta | `tests/test_api_gate.py::test_api_key_va_en_query` |
| RF-6 | compuerta, `config.py` | `tests/test_api_gate.py::test_sin_clave_configurada_503` |
| RF-7 | compuerta | `tests/test_api_gate.py::test_clave_ausente_o_mala_401_sin_agente_ni_bd` |
| RF-8 | limitador, `config.py` | `tests/test_api_limiter.py::test_ventana_fija`, `tests/test_api_gate.py::test_429_sobre_el_limite` |
| RF-9 | limitador | `tests/test_api_gate.py::test_cuentan_404_409_422_y_no_401_503_publicas` |
| RF-10 | middleware | `tests/test_api_gate.py::test_orden_503_401_429_422_con_json_roto` |
| RF-11 | tarea con límite | `tests/test_api_ask.py::test_timeout_504_no_guarda` |
| RF-12 | repositorio | `tests/test_api_app.py::test_bd_caida_503_sin_respuesta`, `tests/test_db_repository.py::test_save_y_list_lanzan_con_motor_roto` + manual Postgres |
| RF-13 | mapeo de errores | `tests/test_api_ask.py::test_error_agente_500_generico_sin_guardar` |
| RF-14 | manejadores | `tests/test_api_app.py::test_detail_en_espanol_en_todos_los_errores` |
| RF-15 | Contrato `/ask` | `tests/test_api_ask.py::test_ask_200_forma`, `test_contrato_claves_agente_real` |
| RF-16 | `schemas.py` | `tests/test_api_ask.py::test_error_null_en_200` |
| RF-17 | lógica `/ask` | `tests/test_api_ask.py::test_thread_id_generado` |
| RF-18 | `schemas.py` | `tests/test_api_ask.py::test_pregunta_invalida_422` |
| RF-19 | `schemas.py` | `tests/test_api_ask.py::test_thread_id_invalido_422`, `test_api_approve.py`, `test_api_historial.py` (mismo caso) |
| RF-20 | registro de pendientes | `tests/test_api_ask.py::test_plan_con_auto_false_queda_pendiente` |
| RF-21 | registro de pendientes | `tests/test_api_ask.py::test_ask_con_plan_pendiente_409` |
| RF-22 | `en_curso` | `tests/test_api_ask.py::test_peticion_en_curso_409`, `tests/test_api_approve.py::test_approve_en_curso_409` |
| RF-23 | `schemas.py` | `tests/test_api_ask.py::test_auto_aprobar_por_defecto_true` |
| RF-24 | auto-aprobación | `tests/test_api_ask.py::test_auto_true_con_plan_aprueba_y_guarda` |
| RF-25 | auto-aprobación | `tests/test_api_ask.py::test_auto_true_sin_plan_sin_efecto` |
| RF-26 | lógica `/approve` | `tests/test_api_approve.py::test_aprobar_done_true` |
| RF-27 | lógica `/approve` | `tests/test_api_approve.py::test_rechazar_done_false` |
| RF-28 | registro de pendientes | `tests/test_api_approve.py::test_sin_plan_pendiente_409` |
| RF-29 | `schemas.py` | `tests/test_api_approve.py::test_comentario_largo_422` |
| RF-30 | repositorio | `tests/test_api_approve.py::test_comentario_se_guarda` |
| RF-31 | `models.py`, `db.py` | `tests/test_db_repository.py::test_guardar_y_listar`, `tests/test_api_ask.py::test_consulta_sin_plan_se_guarda` |
| RF-32 | registro de pendientes | `tests/test_api_approve.py::test_rechazado_guarda_respuesta_de_ask` |
| RF-33 | lógica `/ask` | `tests/test_api_ask.py::test_pendiente_y_error_no_se_guardan` |
| RF-34 | Contrato `GET messages` | `tests/test_api_historial.py::test_messages_orden_y_forma` |
| RF-35 | `schemas.py` | `tests/test_api_historial.py::test_assistant_incluye_decision_y_comentario` |
| RF-36 | lógica `GET` | `tests/test_api_historial.py::test_thread_sin_turnos_404` |
| RF-37 | repositorio | `tests/test_db_repository.py::test_persiste_entre_repositorios`, `tests/test_api_integration.py::test_historial_tras_reinicio` + manual Postgres |
| RF-38 | log de la compuerta | `tests/test_api_logs.py::test_log_por_peticion_protegida_sin_query` |
| RF-39 | filtro de enmascarado | `tests/test_api_logs.py::test_ningun_log_contiene_la_clave` + manual uvicorn |
| RF-40 | `CORS_ORIGINS`, `CORSMiddleware` (capa externa) | `tests/test_api_gate.py::test_cors_solo_origenes_listados` |
