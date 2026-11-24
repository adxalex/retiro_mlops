# Spec 007 — Front Streamlit como cliente HTTP del agente

> Estado: Aprobada · Fecha: 2026-11-22

## Contexto y objetivo
Hoy el agente del Retiro solo se maneja desde la CLI y desde una app Streamlit que lo ejecuta dentro del mismo proceso. La spec 006 lo expone como un servicio HTTP con un contrato estable. Queremos un front que lo use únicamente a través de ese contrato: una persona conversa con el agente, ve la propuesta de visita, la aprueba o la rechaza y consulta el historial, sin que el front contenga el agente, el RAG ni la base de datos. Así el front se puede desplegar y probar por separado y la decisión humana sobre cada plan queda siempre en manos de la persona.

La spec 006 es el contrato: rutas, campos, códigos de error y mensajes. Si ese contrato cambia, esta spec se revisa.

## Usuarios / actores
- **Persona que planifica una visita**: conversa con el agente, decide sobre los planes y revisa conversaciones anteriores.
- **Equipo y evaluadores en la demo**: comprueban el flujo completo contra el servicio desplegado.

## Historias de usuario
- H1: Como persona que planifica quiero escribir una pregunta y ver la respuesta del agente para organizar mi visita al Retiro.
- H2: Como persona que planifica quiero ver la propuesta y decidir con Aprobar o Rechazar, con un comentario opcional, para que ningún plan se cierre sin mi decisión.
- H3: Como persona que planifica quiero ver el historial de mi conversación y poder retomar una anterior con su `thread_id` para no perder lo hablado.
- H4: Como persona que planifica quiero empezar una conversación nueva cuando lo necesite.
- H5: Como persona que planifica quiero ver el texto del error que devuelve el servicio, sin que la app se rompa, para saber qué hacer.
- H6: Como equipo en la demo quiero ver el estado del servicio al abrir la app para saber si está activo antes de empezar.

## Requisitos funcionales (criterios de aceptación en EARS)

**Prioridades.** *Núcleo*: estado del servicio, chat, aprobación, historial y gestión de errores. *Extra*: aviso de base de datos caída (RF-8), retomar un `thread_id` (RF-28), confirmación al cambiar de conversación (RF-29, RF-30), validación previa (RF-31 a RF-33) y aviso de estado no garantizado (RF-38). Las tareas se ordenan con el núcleo primero. Los números no siguen el orden de lectura porque RF-39 a RF-46 se añadieron al aclarar la spec sin renumerar.

### Configuración y aislamiento
- RF-1 [Núcleo]: EL FRONT se comunica con el servicio del agente exclusivamente por HTTP, sin ejecutar el agente ni el RAG en su proceso y sin acceder a la base de datos.
- RF-2 [Núcleo]: EL FRONT toma la URL base del servicio y la `api_key` de la configuración de su entorno, nunca del código ni del repositorio.
- RF-3 [Núcleo]: SI falta la URL base o la `api_key` en la configuración, ENTONCES EL FRONT muestra un mensaje en español que indica cuál falta y no llama al servicio.
- RF-4 [Núcleo]: EL FRONT no muestra la `api_key` en pantalla ni en ningún mensaje de error.
- RF-5 [Núcleo]: EL FRONT muestra todos los textos de la interfaz en español.
- RF-43 [Núcleo]: EL FRONT no escribe la `api_key` en ningún log ni traza, tampoco en los de las librerías que utiliza.
- RF-46 [Núcleo]: EL FRONT muestra en sus mensajes de error únicamente el texto de `detail` que devuelve el servicio o textos fijos en español.

### Estado del servicio
- RF-6 [Núcleo]: CUANDO se abre la app, EL FRONT consulta `GET /health` sin `api_key` y muestra si el servicio está activo.
- RF-7 [Núcleo]: CUANDO `GET /health` responde, EL FRONT muestra el estado de la base de datos del servicio (`ok` o `error`).
- RF-8 [Extra]: SI `GET /health` indica `"db": "error"`, ENTONCES EL FRONT avisa de que la base de datos del servicio no responde y de que el historial puede no estar disponible.
- RF-9 [Núcleo]: EL FRONT permite usar el chat aunque `GET /health` indique `"db": "error"` o no responda.
- RF-39 [Núcleo]: SI `GET /health` no responde en 30 segundos o no se puede establecer la conexión, ENTONCES EL FRONT muestra el mensaje "El servicio está arrancando o no responde".
- RF-40 [Núcleo]: JUNTO a ese mensaje, EL FRONT muestra un botón Reintentar.
- RF-41 [Núcleo]: CUANDO la persona pulsa Reintentar, EL FRONT vuelve a consultar `GET /health`.

### Conversación
- RF-10 [Núcleo]: CUANDO la persona envía una pregunta válida, EL FRONT llama a `POST /ask` con la `pregunta` y el `thread_id` de la conversación, enviando la `api_key` como parámetro de consulta.
- RF-11 [Núcleo]: EL FRONT envía siempre `auto_aprobar=false` en `POST /ask`.
- RF-12 [Núcleo]: CUANDO se abre la app, EL FRONT crea una conversación con un `thread_id` nuevo (UUID) generado por él, antes de enviar ninguna pregunta.
- RF-13 [Núcleo]: EL FRONT muestra el `thread_id` de la conversación actual.
- RF-14 [Núcleo]: CUANDO `POST /ask` responde 200, EL FRONT muestra la `respuesta` del agente en el chat.
- RF-15 [Núcleo]: MIENTRAS espera la respuesta del servicio, EL FRONT muestra un indicador de espera y no permite enviar otra petición.

### Aprobación del plan
- RF-16 [Núcleo]: CUANDO `POST /ask` responde con `pendiente_hitl=true`, EL FRONT muestra la propuesta (la `respuesta` del agente), un campo de comentario opcional y los botones Aprobar y Rechazar.
- RF-17 [Núcleo]: MIENTRAS hay un plan pendiente de decisión, EL FRONT no permite enviar una nueva pregunta.
- RF-18 [Núcleo]: CUANDO la persona pulsa Aprobar, EL FRONT llama a `POST /approve` con el `thread_id` y `aprobado=true`.
- RF-19 [Núcleo]: CUANDO la persona pulsa Rechazar, EL FRONT llama a `POST /approve` con el `thread_id` y `aprobado=false`.
- RF-20 [Núcleo]: DONDE la persona ha escrito un comentario, EL FRONT lo envía en `POST /approve`.
- RF-21 [Núcleo]: CUANDO `POST /approve` responde 200 tras Aprobar, EL FRONT muestra la confirmación "Plan aprobado.", sin repetir la `respuesta` del agente, y retira los botones.
- RF-22 [Núcleo]: CUANDO `POST /approve` responde 200 tras Rechazar, EL FRONT muestra la confirmación "Plan rechazado.", retira los botones y permite enviar una nueva pregunta en la misma conversación.

### Historial
- RF-23 [Núcleo]: CUANDO un turno se cierra (`POST /ask` responde 200 con `pendiente_hitl=false` o `POST /approve` responde 200), EL FRONT recarga el historial con `GET /threads/{thread_id}/messages`.
- RF-24 [Núcleo]: EL FRONT muestra de cada mensaje del historial su `role`, su `content` y su `created_at`.
- RF-25 [Núcleo]: EN los mensajes del asistente, EL FRONT muestra la etiqueta "Aprobado" o "Rechazado" según su `decision`, cuando no es `null`.
- RF-45 [Núcleo]: EN los mensajes del asistente cuyo `comentario` no es `null`, EL FRONT muestra el comentario.
- RF-26 [Núcleo]: SI `GET /threads/{thread_id}/messages` responde 404, ENTONCES EL FRONT muestra el historial vacío, sin mensaje de error.

### Cambio de conversación
- RF-27 [Núcleo]: CUANDO la persona pulsa "Conversación nueva", EL FRONT limpia el chat y el historial mostrados y crea una conversación con un `thread_id` nuevo (UUID) generado por él.
- RF-28 [Extra]: CUANDO la persona confirma un `thread_id` escrito en el campo para retomar una conversación, EL FRONT lo establece como conversación actual y carga su historial.
- RF-29 [Extra]: SI hay un plan pendiente de decisión y la persona pide una conversación nueva o retomar otro `thread_id`, ENTONCES EL FRONT avisa de que el plan quedará sin decidir y sin guardarse en el historial, y solo cambia de conversación si la persona confirma.
- RF-30 [Extra]: SI la persona cancela esa confirmación, ENTONCES EL FRONT mantiene la conversación actual y su plan pendiente.

### Validación previa
- RF-31 [Extra]: SI la pregunta, tras quitar los espacios de los extremos, está vacía o supera los 2000 caracteres, ENTONCES EL FRONT avisa en español y no llama al servicio.
- RF-32 [Extra]: SI el comentario supera los 500 caracteres, ENTONCES EL FRONT avisa en español y no llama al servicio.
- RF-33 [Extra]: SI el `thread_id` escrito para retomar una conversación está vacío, supera los 64 caracteres o contiene espacios, ENTONCES EL FRONT avisa en español y no llama al servicio.

### Errores
- RF-34 [Núcleo]: SI el servicio responde con un error HTTP que incluye `detail` (por ejemplo 401, 409, 422, 429, 500, 503 o 504), ENTONCES EL FRONT muestra el texto de `detail` en un mensaje de error.
- RF-35 [Núcleo]: SI se produce cualquier error, ENTONCES EL FRONT mantiene la conversación mostrada y sigue funcionando.
- RF-36 [Núcleo]: SI el servicio responde con un error HTTP sin `detail`, ENTONCES EL FRONT muestra un mensaje genérico en español con el código de estado.
- RF-37 [Núcleo]: SI una petición distinta de `GET /health` no obtiene respuesta dentro del tiempo de espera configurado o no se puede establecer la conexión, ENTONCES EL FRONT muestra el mensaje "No se pudo contactar con el servicio".
- RF-38 [Extra]: SI `POST /ask` o `POST /approve` responde 504 o agota el tiempo de espera del front, ENTONCES EL FRONT, además del mensaje de error, avisa de que el estado de la conversación no está garantizado y propone empezar una conversación nueva.
- RF-42 [Núcleo]: SI el tiempo de espera configurado no es un número o es menor o igual que 0, ENTONCES EL FRONT usa 70 segundos.
- RF-44 [Núcleo]: SI se produce un error que no es una respuesta HTTP, un fallo de conexión ni un tiempo de espera agotado, ENTONCES EL FRONT muestra el mensaje "Se ha producido un error inesperado en la aplicación", sin mostrar la traza.

## Requisitos no funcionales
- **Seguridad**: la `api_key` y la URL base solo viven en la configuración del entorno del front; la `api_key` no aparece en pantalla, mensajes de error, logs ni trazas (RF-4, RF-43, RF-46). La URL de las peticiones lleva la `api_key` en la cadena de consulta, por lo que ningún error ni registro puede reproducir esa URL.
- **Configuración**: el front lee `FRONT_API_URL`, `FRONT_API_KEY` y `FRONT_TIMEOUT_SECONDS` del entorno. Sin `FRONT_TIMEOUT_SECONDS` se usa el valor por defecto (RF-42). El front declara sus propias dependencias, separadas de las del servicio.
- **Tiempo de espera**: el front espera la respuesta de `POST /ask`, `POST /approve` y `GET /threads/{thread_id}/messages` el tiempo configurado, 70 segundos por defecto, sin mínimo forzado. El valor por defecto supera los 60 segundos tras los que el servicio responde 504 (spec 006, RF-11), y la documentación del front lo indica. `GET /health` usa un tiempo de espera propio y fijo de 30 segundos (RF-39).
- **Límites de entrada**: pregunta de 1 a 2000 caracteres, comentario de hasta 500 y `thread_id` de 1 a 64 caracteres sin espacios, los mismos que el contrato 006.
- **Idioma**: textos de la interfaz en español; los errores del servicio se muestran tal como los devuelve (constitución §14).
- **Pruebas**: toda la verificación se hace contra un servidor simulado, sin red ni servicio real (constitución §9). Al menos un test comprueba que se envía `auto_aprobar=false`.

## Casos límite
- Reinicio del servicio con un plan pendiente: el plan se pierde en el servicio; `POST /approve` da 409, el front muestra su `detail` y los botones siguen visibles hasta que la persona empiece una conversación nueva (RF-34, RF-35).
- Retomar un `thread_id` que tiene un plan pendiente: el front no puede saberlo, porque el contrato 006 no tiene ruta para consultarlo; la siguiente pregunta da 409 y se muestra su `detail` (RF-28, RF-34).
- `thread_id` desconocido al retomar: el historial se muestra vacío y ese `thread_id` pasa a ser la conversación actual (RF-26, RF-28).
- Tiempo agotado o 504 en cualquier pregunta, incluida la primera: el front conoce el `thread_id` desde que crea la conversación, pero el servicio puede seguir ejecutando y dejar un plan pendiente; el front avisa de que el estado no está garantizado y propone una conversación nueva (RF-12, RF-38).
- Doble clic mientras espera la respuesta: no se envía una segunda petición, así que no aparece un 409 por petición en curso (RF-15).
- Rechazo: el servicio devuelve `done=false` (spec 006, RF-27); el front muestra el rechazo por el botón pulsado y no depende del contenido de `respuesta` (RF-22).
- Error en `POST /approve` distinto de 504 (por ejemplo 429 o 503): los botones se mantienen y la persona puede reintentar (RF-35).
- Arranque en frío del servicio: `GET /health` puede tardar hasta 30 segundos; después muestra "El servicio está arrancando o no responde" con Reintentar, y el chat sigue siendo usable (RF-9, RF-39, RF-40, RF-41).
- Tiempo de espera configurado con un valor no numérico o menor o igual que 0: se usan 70 segundos (RF-42).
- Excepción inesperada del propio front: se muestra un texto fijo y ninguna traza, de modo que la `api_key` de la URL no llega a pantalla (RF-44, RF-46).
- Aprobar: la respuesta del servicio termina diciendo que la propuesta sigue pendiente de aprobación; por eso el front muestra una confirmación fija y no la repite (RF-21).
- Pregunta de exactamente 2000 caracteres: se envía; de 2001: no (RF-31).
- Recarga de la página: se crea una conversación nueva con otro `thread_id` y se pierden el chat y el plan pendiente mostrados; la conversación anterior se recupera retomando su `thread_id` (RF-12, RF-28).

## Fuera de alcance
- Autenticación de usuarios: solo la `api_key` compartida del servicio.
- Subida de imágenes: el contrato 006 solo admite texto en `/ask`.
- Base de datos propia del front.
- Despliegue del front.
- Mover o modificar las apps Streamlit heredadas.
- Consultar si un hilo tiene un plan pendiente (el contrato 006 no lo ofrece).
- Reintentos automáticos de peticiones.
- Paginación y borrado del historial.
- Mostrar la traza de ejecución del agente.
- Conservar el `thread_id` entre recargas de la página.

## Criterios de finalización
- Todos los RF con test en verde (`pytest`) contra un servidor simulado, sin red ni servicio real, incluido el test de `auto_aprobar=false`.
- El README del front indica que el tiempo de espera configurado debe superar el del servicio.
- Demo manual contra el servicio desplegado: estado del servicio al abrir, pregunta con plan pendiente, Aprobar con comentario, otra pregunta con Rechazar, historial con decisión y comentario, conversación nueva, retomar un `thread_id` y un error visible (por ejemplo, una `api_key` incorrecta que muestre el 401) sin que la clave aparezca en pantalla.

## Dudas abiertas
Ninguna.
