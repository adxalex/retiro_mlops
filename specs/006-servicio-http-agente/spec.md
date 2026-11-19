# Spec 006 — Servicio HTTP del agente del Retiro

> Estado: Borrador · Fecha: 2026-11-19

## Contexto y objetivo
El agente del Retiro (consulta → plan → decisión humana → respuesta final) solo se puede usar hoy desde la CLI y desde Streamlit, y nada de lo que ocurre en una conversación sobrevive a un reinicio. Queremos exponerlo como un servicio HTTP con un contrato estable para que cualquier cliente (el futuro front, Swagger, pruebas) lo use sin conocer su interior. El servicio protege las rutas con una clave, limita su uso, deja una traza por petición sin secretos y conserva en PostgreSQL el historial de los turnos cerrados de cada conversación.

## Usuarios / actores
- **Cliente HTTP** (el front Streamlit previsto, Swagger u otro programa): envía consultas, decide sobre planes y lee el historial.
- **Persona que opera el servicio**: configura la clave y los límites y lee los logs para diagnosticar.

## Historias de usuario
- H1: Como cliente quiero enviar una pregunta, con o sin `thread_id`, para recibir la respuesta o el plan que espera mi decisión.
- H2: Como cliente quiero aprobar o rechazar el plan pendiente (con comentario opcional) para cerrar el turno.
- H3: Como cliente quiero consultar los turnos cerrados de una conversación para mostrar su historial aunque el servicio se haya reiniciado.
- H4: Como persona que opera el servicio quiero que solo se pueda usar con una clave, con límite de uso y con un log por petición, para controlar el acceso y diagnosticar sin exponer secretos.
- H5: Como cliente quiero un `/health` y un `/docs` abiertos para comprobar que el servicio y su base de datos están vivos y conocer el contrato.

## Requisitos funcionales (criterios de aceptación en EARS)

**Definición.** Un *turno cerrado* es un turno sin plan pendiente de decisión y sin error. Incluye las consultas informativas sin plan, los planes aprobados y los planes rechazados.

### Rutas y acceso
- RF-1: EL SISTEMA expone las rutas `GET /health`, `GET /docs`, `POST /ask`, `POST /approve` y `GET /threads/{thread_id}/messages`.
- RF-2: CUANDO se pide `GET /health` sin `api_key`, EL SISTEMA responde 200 con `{"status": "ok", "storage": "postgres", "db": "ok"}`.
- RF-3: SI la base de datos no responde, ENTONCES `GET /health` sigue respondiendo 200 con `"db": "error"`.
- RF-4: CUANDO se pide `GET /docs` sin `api_key`, EL SISTEMA muestra la documentación interactiva de todas las rutas, con un campo `api_key` en cada ruta protegida.
- RF-5: EL SISTEMA exige una `api_key`, enviada como parámetro de consulta `api_key`, en `POST /ask`, `POST /approve` y `GET /threads/{thread_id}/messages`.
- RF-6: SI el servicio no tiene ninguna `api_key` configurada, ENTONCES EL SISTEMA responde 503 en las rutas protegidas.
- RF-7: SI en una ruta protegida la `api_key` falta o no coincide con la configurada, ENTONCES EL SISTEMA responde 401 sin ejecutar el agente ni tocar la base de datos.
- RF-8: SI una misma `api_key` válida supera el número de peticiones por minuto configurado (30 por defecto) en una ventana fija de un minuto, ENTONCES EL SISTEMA responde 429 a las siguientes hasta que empiece la ventana siguiente.
- RF-9: EL SISTEMA cuenta para el límite de RF-8 toda petición a una ruta protegida con `api_key` válida, sea cual sea su resultado, y no cuenta las rutas públicas ni las que terminan en 401 o 503.
- RF-10: EL SISTEMA comprueba en las rutas protegidas, en este orden: 503, 401, 429, validación de la entrada (422) y lógica de la ruta.
- RF-11: SI el agente tarda más de 60 segundos en atender una petición, ENTONCES EL SISTEMA responde 504 sin guardar nada en el historial.
- RF-12: SI la base de datos no responde al guardar o leer el historial, ENTONCES EL SISTEMA responde 503, el cliente no recibe la respuesta del agente y el turno no queda en el historial.
- RF-13: SI el agente devuelve un error distinto de plan pendiente o de falta de plan pendiente, ENTONCES EL SISTEMA responde 500 con un mensaje genérico en español, sin detalles internos y sin guardar nada.
- RF-14: EL SISTEMA devuelve todos los errores HTTP con el cuerpo `{"detail": "<mensaje en español>"}`.

### Consulta (`/ask`)
- RF-15: CUANDO llega `POST /ask` con `pregunta` válida, EL SISTEMA ejecuta un turno del agente y responde 200 con `respuesta`, `plan`, `thread_id`, `done`, `pendiente_hitl` y `error`.
- RF-16: EL SISTEMA devuelve `error` con valor `null` en toda respuesta 200 de `/ask` y `/approve`.
- RF-17: SI `POST /ask` no incluye `thread_id`, ENTONCES EL SISTEMA genera uno y lo devuelve en la respuesta.
- RF-18: SI `pregunta` está vacía, solo contiene espacios o supera los 2000 caracteres, ENTONCES EL SISTEMA responde 422 y no ejecuta el agente.
- RF-19: SI `thread_id` está vacío, supera los 64 caracteres o contiene espacios, ENTONCES EL SISTEMA responde 422 en `POST /ask`, `POST /approve` y `GET /threads/{thread_id}/messages`.
- RF-20: CUANDO el turno produce un plan que requiere decisión humana, EL SISTEMA responde con `pendiente_hitl=true` y `done=false`.
- RF-21: SI el `thread_id` ya tiene un plan pendiente de decisión, ENTONCES EL SISTEMA responde 409 a un nuevo `POST /ask` y no ejecuta el agente.
- RF-22: SI llega una petición para un `thread_id` que ya tiene otra petición en curso, ENTONCES EL SISTEMA responde 409 a la segunda.
- RF-23: SI la petición no incluye `auto_aprobar`, ENTONCES EL SISTEMA lo trata como [NECESITA ACLARACIÓN: ¿`true` (decisión del equipo) o `false`? La constitución §5 exige que `auto_aprobar=true` lo pida el cliente de forma explícita].
- RF-24: DONDE la petición incluye `auto_aprobar=true` y el turno genera un plan, EL SISTEMA lo aprueba sin decisión humana, lo guarda con decisión "aprobado" y comentario vacío, y responde con `done=true`.
- RF-25: SI `auto_aprobar` es `true` y el turno no genera ningún plan, ENTONCES `auto_aprobar` no tiene efecto.

### Decisión (`/approve`)
- RF-26: CUANDO llega `POST /approve` con `thread_id` y `aprobado=true` para un plan pendiente, EL SISTEMA aplica el plan y responde 200 con la misma forma que `/ask` y `done=true`.
- RF-27: CUANDO llega `POST /approve` con `thread_id` y `aprobado=false` para un plan pendiente, EL SISTEMA no aplica el plan y responde 200 con la misma forma que `/ask`, `done=false` y `pendiente_hitl=false`.
- RF-28: SI el `thread_id` no tiene un plan pendiente, ENTONCES EL SISTEMA responde 409 a `POST /approve`.
- RF-29: SI `comentario` supera los 500 caracteres, ENTONCES EL SISTEMA responde 422 y no ejecuta el agente.
- RF-30: DONDE `POST /approve` incluye `comentario`, EL SISTEMA lo guarda con el turno.

### Historial
- RF-31: CUANDO un turno se cierra, EL SISTEMA guarda en PostgreSQL su `thread_id`, la pregunta, la respuesta, el plan, la decisión ("aprobado", "rechazado" o ninguna), el comentario y la fecha.
- RF-32: CUANDO se rechaza un plan, EL SISTEMA guarda el turno con la pregunta y con la respuesta y el plan que devolvió `/ask`, marcado como "rechazado" y con el comentario.
- RF-33: EL SISTEMA no guarda en el historial los turnos con plan pendiente de decisión ni los que terminan en error.
- RF-34: CUANDO llega `GET /threads/{thread_id}/messages` para un `thread_id` con turnos cerrados, EL SISTEMA responde 200 con una lista cronológica, del más antiguo al más reciente y sin paginación, cuyos elementos tienen `role` ("user" o "assistant"), `content` y `created_at`.
- RF-35: EN los elementos con `role` "assistant", EL SISTEMA incluye además `decision` ("aprobado", "rechazado" o `null`) y `comentario` (o `null`).
- RF-36: SI el `thread_id` no tiene ningún turno cerrado, ENTONCES EL SISTEMA responde 404 a `GET /threads/{thread_id}/messages`.
- RF-37: CUANDO el servicio se reinicia, EL SISTEMA sigue devolviendo en `GET /threads/{thread_id}/messages` los turnos cerrados antes del reinicio.

### Trazabilidad
- RF-38: CUANDO atiende una petición a una ruta protegida, sea cual sea su resultado, EL SISTEMA escribe un log con método, ruta sin la cadena de consulta, `thread_id`, `duration_ms` y código de estado.
- RF-39: EL SISTEMA no incluye la `api_key` ni la cadena de conexión a la base de datos en ningún log del servicio, en las respuestas ni en los mensajes de error.

## Requisitos no funcionales
- **Seguridad**: la `api_key`, la cadena de conexión y los límites (peticiones por minuto, 60 s de espera) se leen de la configuración; ninguno se escribe en el repositorio. Como la `api_key` viaja en la cadena de consulta, RF-39 abarca también los logs de acceso del propio servidor.
- **Límites de entrada**: `pregunta` de 1 a 2000 caracteres, `comentario` de hasta 500 y `thread_id` de 1 a 64 caracteres sin espacios.
- **Idioma**: mensajes de error en español (constitución §14).
- **Despliegue**: un único proceso del servicio, porque el estado de los planes pendientes vive en memoria (constitución §12).
- **Pruebas**: toda la verificación se hace sin API externa ni red, con dobles del agente y una base de datos de prueba (constitución §9).

## Casos límite
- Petición protegida sin `api_key` válida o con `thread_id` inválido: el log registra `thread_id` vacío (RF-7, RF-19, RF-38).
- Reinicio con un plan pendiente: el plan se pierde, porque vive en memoria; el historial de turnos cerrados se conserva (RF-33, RF-37).
- `POST /approve` sobre un `thread_id` desconocido: se trata como sin plan pendiente (RF-28).
- Hilo con un plan pendiente y ningún turno cerrado: `GET .../messages` da 404 (RF-33, RF-36).
- Consulta informativa sin plan: es un turno cerrado, se guarda con decisión `null` y `GET .../messages` ya la devuelve (RF-31, RF-35).
- Rechazo: `/approve` devuelve `done=false` porque el núcleo del agente no cambia (spec 003), pero el turno se guarda como cerrado (RF-27, RF-32).
- Tras un 504 no se guarda nada y el estado del hilo no está garantizado; el cliente debe empezar con otro `thread_id` (RF-11).
- Fallo de guardado en `/approve`: el plan ya se aplicó en el agente, pero el cliente recibe 503 y el turno no queda en el historial. Es un límite conocido y se documenta en el informe (RF-12).
- Dos peticiones simultáneas para el mismo `thread_id`: la segunda recibe 409 (RF-22).
- Petición con `api_key` válida y cuerpo no válido: cuenta para el límite aunque acabe en 422 (RF-9).
- Orden de comprobaciones: 503, 401, 429, 422 y lógica de la ruta (RF-10).

## Fuera de alcance
- Docker, despliegue en Render y el front Streamlit.
- Imagen en `/ask`: solo texto.
- Autenticación por usuario, JWT u OAuth: solo una `api_key` compartida.
- Paginación del historial y borrado de conversaciones.
- Persistir los planes pendientes o el checkpoint del grafo en PostgreSQL.
- Varias réplicas del servicio.
- Reintento o recuperación del hilo tras un 504 o un fallo de guardado.

## Criterios de finalización
- Todos los RF con test en verde (`pytest`), sin API ni red.
- Demo manual en Swagger: `/ask` → plan pendiente → `/approve` → `/threads/{thread_id}/messages` con el turno guardado.
- Comprobación manual de 401, 429 y de que ningún log contiene la `api_key`.
- El límite de RF-12 para `/approve` queda documentado en el informe.

## Dudas abiertas
- [NECESITA ACLARACIÓN: constitución §5. El equipo quiere `auto_aprobar=true` por defecto, pero la constitución dice que solo se aprueba sin humano si el cliente lo pide de forma explícita y que el front siempre decide. ¿Se cambia el valor por defecto a `false` o se modifica la constitución?]
- [NECESITA ACLARACIÓN: constitución §14. Los campos que fija la guía (`role`, `content`, `created_at`, `status`, `storage`, `db`, `detail`) están en inglés y §14 pide los campos del contrato en español. ¿Prevalece el enunciado (§1) y se añade la excepción a §14?]
- [NECESITA ACLARACIÓN: los elementos del historial solo tienen `content`; el plan de un turno se guarda (RF-31, RF-32) pero ¿cómo se devuelve? ¿Dentro de `content` o se queda sin exponer?]
