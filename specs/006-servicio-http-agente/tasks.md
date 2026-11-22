# Tareas — Spec 006

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero (en rojo y luego en verde). Marca `[x]` al terminar.
> **Una rama y un PR por bloque** (constitución §13), hacia `develop`. Dentro de cada PR, las tareas van en orden y con commits pequeños.
> Antes de abrir un PR: `pytest -m "not corpus"` en verde y sin secretos en `git diff --staged`.
> Las ramas que dependen de T0 parten de `feature/api-config` sin esperar su merge; las demás parten de la rama indicada en "Parte de".

## Contrato fijado entre Mihaela y Guillermo
Ambos programan contra esto y no se esperan. No hay clase de error compartida: **la API trata cualquier excepción del repositorio como 503** (RF-12).

```python
# src/db.py (Guillermo)
class TurnRepository:
    def __init__(self, engine) -> None: ...
    def save(self, thread_id: str, question: str, answer: str,
             decision: str | None, comment: str | None) -> None
    def list(self, thread_id: str) -> list      # más antiguo primero; [] si no hay turnos
    def ping(self) -> bool                      # nunca lanza; False si no hay conexión

def normalize_database_url(url: str) -> str     # postgres:// y postgresql:// → postgresql+psycopg://
def make_engine(url: str | None = None)         # url por defecto: config.DATABASE_URL
def make_repository(url: str | None = None) -> TurnRepository
```

- `decision` es `"aprobado"`, `"rechazado"` o `None`. `comment` es texto, `""` (auto-aprobación) o `None`.
- Cada elemento de `list` tiene los atributos `thread_id`, `question`, `answer`, `decision`, `comment` y `created_at` (fecha con zona UTC). Es la tabla `Turn` de `src/models.py`.
- `save` y `list` **lanzan** la excepción del motor si falla la base de datos.
- Mihaela usa un `InMemoryTurnRepository` en `tests/conftest.py` con exactamente esos métodos y atributos, y un interruptor para forzar fallos.
- `create_app(repo=None, agent=None)`: si `repo` es `None`, usa `make_repository()` (se conecta en M16). `agent` tiene `procesar_turno(texto, thread_id, imagen=None)` y `aprobar_plan(thread_id, aprobado, comentario="")` con las mismas claves de respuesta que el agente real.

## Reparto de PR
| PR | Tareas | Rama | Responsable | Parte de | Revisa |
|---|---|---|---|---|---|
| PR-1 | T0 | `feature/api-config` | Alex | `develop` | Mihaela |
| PR-2 | G1, G2 | `feature/api-db-models-engine` | Guillermo | `feature/api-config` | Alex |
| PR-3 | G3, G4 | `feature/api-db-repository` | Guillermo | `feature/api-db-models-engine` | Alex |
| PR-4 | I1 | `feature/api-repo-contract` | Guillermo | `develop` con PR-3 y PR-6 fusionadas | Alex |
| PR-5 | M1 a M4 | `feature/api-schemas-security` | Mihaela | `feature/api-config` | Guillermo |
| PR-6 | M5 a M8 | `feature/api-app-core` | Mihaela | `feature/api-schemas-security` | Guillermo |
| PR-7 | M9 a M11 | `feature/api-ask` | Mihaela | `feature/api-app-core` | Guillermo |
| PR-8 | M12 | `feature/api-timeout` | Mihaela | `feature/api-ask` | Guillermo |
| PR-9 | M13, M14 | `feature/api-approve-messages` | Mihaela | `feature/api-timeout` | Guillermo |
| PR-10 | M15, M16 | `feature/api-integration` | Mihaela | `feature/api-approve-messages` con PR-3 fusionada | Guillermo |
| PR-11 | A1 a A3 | `docs/api-closure` | Alex | `develop` con todo fusionado | Mihaela |

Orden de fusión en `develop`: PR-1 → (PR-2 → PR-3) y (PR-5 → PR-6 → PR-7 → PR-8 → PR-9) en paralelo → PR-4 y PR-10 → PR-11. Al fusionar una rama previa, las siguientes hacen `git merge develop`.

---

## PR-1 · Configuración previa (Alex) — `feature/api-config`
- [x] **T0.** Configuración y dependencias. (RF-6, 8, 11, 39, 40)
      Tests primero: `tests/test_config_api.py` (valores por defecto 30, 60 y `CORS_ORIGINS` vacío; lectura del entorno con `monkeypatch`; parseo de `CORS_ORIGINS` separado por comas con espacios recortados). Después: `config.py` con `API_KEY`, `DATABASE_URL`, `RATE_LIMIT_PER_MINUTE`, `ASK_TIMEOUT_SECONDS`, `CORS_ORIGINS` y las constantes fijas (2000/500/64, timeout de conexión, rutas protegidas); `requirements.txt` (fastapi, uvicorn, sqlmodel, psycopg[binary]); `requirements-dev.txt` (httpx); `.env.example` solo con los nombres.
      Hecho cuando: `pytest tests/test_config_api.py -q` en verde, `pip install -r requirements-dev.txt` sin errores y `.env.example` sin valores.

## PR-2 · Modelo y motor (Guillermo) — `feature/api-db-models-engine`
- [ ] **G1.** Tabla `Turn`. Depende de: T0. (RF-31)
      Tests primero: `tests/test_models.py` (la tabla se crea en SQLite en memoria con los campos del contrato; `created_at` por defecto en UTC; `decision` y `comment` admiten `None`). Después: `src/models.py`.
      Hecho cuando: `pytest tests/test_models.py -q` en verde.
- [ ] **G2.** Normalización de URL y motor. Depende de: G1. (RF-12, 31)
      Tests primero: `tests/test_db_url.py` (`postgres://` y `postgresql://` pasan a `postgresql+psycopg://`; `sqlite://` no cambia; sin URL se usa `config.DATABASE_URL`; el timeout de conexión solo se aplica a Postgres). Después: `normalize_database_url` y `make_engine` en `src/db.py`.
      Hecho cuando: `pytest tests/test_db_url.py -q` en verde.

## PR-3 · Repositorio (Guillermo) — `feature/api-db-repository`
- [ ] **G3.** `save` y `list`. Depende de: G2. (RF-31, 32, 34, 35, 36, 37)
      Tests primero: `tests/test_db_repository.py` sobre SQLite en memoria (guardar y listar en orden cronológico; turno rechazado con comentario; turno informativo con `decision=None`; `list` de un hilo sin turnos devuelve `[]`; dos repositorios sobre el mismo motor ven los mismos datos, que simula el reinicio). Después: `save` y `list` de `TurnRepository`.
      Hecho cuando: `pytest tests/test_db_repository.py -q` en verde.
- [ ] **G4.** `ping`, tablas perezosas y `make_repository`. Depende de: G3. (RF-2, 3, 12)
      Tests primero: en el mismo archivo (`ping` devuelve `True` con motor sano y `False` con motor roto sin lanzar; `save` y `list` lanzan con motor roto; las tablas se crean al primer uso aunque la base de datos no estuviera disponible al arrancar). Después: `ping`, creación perezosa de tablas y `make_repository`.
      Hecho cuando: `pytest tests/test_db_repository.py -q` en verde con los casos nuevos.

## PR-5 · Esquemas y seguridad (Mihaela) — `feature/api-schemas-security`
- [ ] **M1.** `schemas.py`. Depende de: T0. (RF-15, 16, 18, 19, 23, 29, 34, 35)
      Tests primero: `tests/test_api_schemas.py` (`pregunta` recortada de 1 a 2000; `thread_id` de 1 a 64 sin espacios; `comentario` hasta 500; `auto_aprobar` por defecto `true`; salida con `error=None`; elemento de historial con `role`, `content`, `created_at` y, en el asistente, `decision` y `comentario`). Después: `schemas.py`.
      Hecho cuando: `pytest tests/test_api_schemas.py -q` en verde.
- [ ] **M2.** Limitador de ventana fija. Depende de: T0. (RF-8, 9)
      Tests primero: `tests/test_api_limiter.py` (con reloj inyectado: la petición 31 del minuto da 429 y el minuto siguiente se reinicia; el contador es por clave). Después: limitador en `security.py`.
      Hecho cuando: `pytest tests/test_api_limiter.py -q` en verde.
- [ ] **M3.** Compuerta de acceso. Depende de: M2. (RF-5, 6, 7, 8, 9, 10)
      Tests primero: `tests/test_api_gate.py` con una app mínima de prueba (sin `API_KEY` configurada da 503; clave ausente o incorrecta da 401 sin llamar a la ruta; sobre el límite da 429; el orden es 503, 401, 429; las rutas públicas y los 401/503 no cuentan para el límite; el parámetro es `api_key` en la query). Después: middleware de compuerta en `security.py`.
      Hecho cuando: `pytest tests/test_api_gate.py -q` en verde.
- [ ] **M4.** Log por petición y filtro de enmascarado. Depende de: M3. (RF-38, 39)
      Tests primero: `tests/test_api_logs.py` (con `caplog`: un log por petición protegida con método, ruta sin query, `thread_id`, `duration_ms` y status; ningún registro contiene la clave; el filtro enmascara `api_key=…` en los mensajes de acceso de uvicorn). Después: log y filtro en `security.py`.
      Hecho cuando: `pytest tests/test_api_logs.py -q` en verde.

## PR-6 · Núcleo de la app (Mihaela) — `feature/api-app-core`
- [ ] **M5.** Esqueleto de `create_app` y fixtures. Depende de: T0. (RF-1, 2, 3, 4)
      Tests primero: `tests/test_api_app.py` (`/health` con repositorio sano da `{"status":"ok","storage":"postgres","db":"ok"}` y con repositorio roto da 200 y `"db":"error"`; `/docs` y `/openapi.json` responden sin clave; `/redoc` no existe). Después: `create_app(repo, agent)` en `api.py` y, en `tests/conftest.py`, el agente falso, `InMemoryTurnRepository` y el cliente de pruebas.
      Hecho cuando: `pytest tests/test_api_app.py -q` en verde y `tests/conftest.py` documenta las fixtures.
- [ ] **M6.** Manejadores de error. Depende de: M5. (RF-14)
      Tests primero: en `tests/test_api_app.py` (422, 404 y 405 devuelven `{"detail": "<texto en español>"}` sin valores de entrada; un error no previsto devuelve 500 genérico). Después: manejadores de error en `api.py`.
      Hecho cuando: `pytest tests/test_api_app.py -q` en verde.
- [ ] **M7.** Cablear compuerta y log. Depende de: M4, M5. (RF-5 a 10, 38, 39)
      Tests primero: en `tests/test_api_gate.py` (con la app real: 503, 401 y 429 en `/ask`, `/approve` y `/threads/...` antes de cualquier lógica; hay log por petición). Después: cablear compuerta y log en `create_app`.
      Hecho cuando: `pytest tests/test_api_gate.py tests/test_api_logs.py -q` en verde.
- [ ] **M8.** CORS. Depende de: M7. (RF-40)
      Tests primero: `test_cors_solo_origenes_listados` en `tests/test_api_gate.py` (un origen listado recibe la cabecera de permiso; uno no listado no la recibe; OPTIONS a `/ask` sin `api_key` no da 401 ni cuenta para el límite). Después: `CORSMiddleware` como capa más externa.
      Hecho cuando: ese test en verde.

## PR-7 · `/ask` (Mihaela) — `feature/api-ask`
- [ ] **M9.** `POST /ask` básico. Depende de: M1, M6, M7. (RF-13, 15, 16, 17, 18, 19, 31, 33)
      Tests primero: `tests/test_api_ask.py` (200 con la forma completa y `error=null`; `thread_id` generado si falta; `pregunta` vacía, en blanco o de 2001 caracteres da 422 y el agente no se llama; `thread_id` inválido da 422; error del agente da 500 genérico sin guardar; consulta sin plan se guarda con `decision=None`; el contrato del agente falso coincide con el del real). Después: `POST /ask`.
      Hecho cuando: `pytest tests/test_api_ask.py -q` en verde.
- [ ] **M10.** Plan pendiente. Depende de: M9. (RF-20, 21, 33)
      Tests primero: en `tests/test_api_ask.py` (con `auto_aprobar=false` y plan: `pendiente_hitl=true`, `done=false` y no se guarda; un segundo `/ask` del mismo hilo da 409 sin llamar al agente). Después: registro de planes pendientes.
      Hecho cuando: esos tests en verde.
- [ ] **M11.** Auto-aprobación. Depende de: M10. (RF-23, 24, 25)
      Tests primero: en `tests/test_api_ask.py` (sin `auto_aprobar` se trata como `true`; con plan se aprueba, `done=true` y se guarda con `decision="aprobado"` y `comment=""`; sin plan no tiene efecto). Después: auto-aprobación en `/ask`.
      Hecho cuando: esos tests en verde.

## PR-8 · Tiempo límite y peticiones en curso (Mihaela) — `feature/api-timeout`
- [ ] **M12.** Límite de tiempo y reserva por hilo. Depende de: M10. (RF-11, 22) *(puede rozar los 30 min)*
      Tests primero: en `tests/test_api_ask.py` (con `ASK_TIMEOUT_SECONDS` mínimo y agente bloqueado con `Event`: 504 y nada guardado; una segunda petición al mismo hilo mientras la primera sigue da 409; la reserva se libera cuando el hilo termina de verdad). Después: tarea en hilo con `asyncio.shield` y reserva por hilo.
      Hecho cuando: esos tests en verde.

## PR-9 · `/approve` y mensajes (Mihaela) — `feature/api-approve-messages`
- [ ] **M13.** `POST /approve`. Depende de: M10, M12. (RF-19, 22, 26 a 30, 32)
      Tests primero: `tests/test_api_approve.py` (aprobar da `done=true`; rechazar da `done=false` y `pendiente_hitl=false`; sin plan pendiente o hilo desconocido da 409; `comentario` de 501 caracteres da 422; el comentario se guarda; el turno rechazado guarda la respuesta que devolvió `/ask`; petición en curso en el mismo hilo da 409). Después: `POST /approve`.
      Hecho cuando: `pytest tests/test_api_approve.py -q` en verde.
- [ ] **M14.** `GET /threads/{thread_id}/messages`. Depende de: M5, M9. (RF-19, 34, 35, 36)
      Tests primero: `tests/test_api_historial.py` (lista cronológica con pares `user`/`assistant`; `decision` y `comentario` solo en el asistente; hilo sin turnos da 404; hilo con plan pendiente y sin turnos cerrados da 404; `thread_id` inválido da 422). Después: `GET /threads/{thread_id}/messages`.
      Hecho cuando: `pytest tests/test_api_historial.py -q` en verde.

## PR-4 · Contrato del repositorio (Guillermo) — `feature/api-repo-contract`
- [ ] **I1.** Mismas aserciones contra las dos implementaciones. Depende de: G4, M5. (RF-31 a 37)
      Tests primero: `tests/test_repository_contract.py`, parametrizado contra `InMemoryTurnRepository` y `TurnRepository` (SQLite). Evita que los dos diverjan.
      Hecho cuando: `pytest tests/test_repository_contract.py -q` en verde con las dos implementaciones.

## PR-10 · Integración (Mihaela) — `feature/api-integration`
- [ ] **M15.** Tests transversales. Depende de: M7, M11, M13, M14. (RF-1, 4, 9, 10, 12, 13, 38)
      Tests primero: en `tests/test_api_gate.py` y `tests/test_api_app.py` (orden 503→401→429→422 incluso con JSON roto; cuentan para el límite las peticiones que acaban en 404, 409 o 422; con repositorio roto `/ask`, `/approve` y `GET` dan 503 sin respuesta del agente; `openapi.json` declara `api_key` en las tres rutas protegidas; las rutas expuestas son exactamente las de RF-1; el log lleva `thread_id`). Sin código nuevo salvo correcciones.
      Hecho cuando: `pytest tests/test_api_*.py -q` en verde.
- [ ] **M16.** Repositorio real por defecto. Depende de: G4, M15. (RF-31 a 37)
      Tests primero: `tests/test_api_integration.py` con `DATABASE_URL` en SQLite en memoria y `create_app()` sin `repo`: `/ask` → `/approve` → `GET messages` devuelve el turno, y otra `create_app()` sobre el mismo motor lo sigue devolviendo. Después: usar `make_repository()` por defecto.
      Hecho cuando: `pytest -m "not corpus" -q` entero en verde.

## PR-11 · Cierre (Alex) — `docs/api-closure`
- [ ] **A1.** Actualizar `AGENTS.md`. Depende de: M16. (RF-39)
      Quita los `[COMPLETAR]` de los archivos ya creados en el mapa y fija el arranque `uvicorn api:app --no-access-log` con un solo worker.
      Hecho cuando: `AGENTS.md` no tiene `[COMPLETAR]` salvo Dockerfile y `front/`, y su mapa coincide con los archivos reales.
- [ ] **A2.** Demo manual con Postgres real. Depende de: M16, I1. (RF-4, 12, 37, 39)
      Swagger (campo `api_key` en cada ruta protegida; `/ask` con `auto_aprobar=false` → `/approve` → `GET messages`), 401 y 429 reales, reinicio del servicio con el historial intacto, caída de Postgres con 503 y salida de uvicorn sin la clave. El límite de RF-12 para `/approve` se anota en el informe.
      Hecho cuando: `validacion.md` recoge cada comprobación con comando y resultado.
- [ ] **A3.** Validación final RF por RF (`/sdd-validar`). (Todos)
      Hecho cuando: `validacion.md` con veredicto "Sí" y `pytest` completo en verde.

---

## Cobertura RF → tareas
| RF | Tareas |
|---|---|
| 1 a 4 | M5, M15, A2 |
| 5 a 10 | M3, M7, M15 |
| 11 | T0, M12 |
| 12 | G2, G4, M15, A2 |
| 13, 14 | M9, M6 |
| 15 a 25 | M1, M9, M10, M11 |
| 26 a 30 | M13 |
| 31 a 37 | G1, G3, G4, M14, I1, M16 |
| 38, 39 | M4, M7 |
| 40 | T0, M8 |
