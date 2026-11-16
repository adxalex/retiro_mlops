# Constitución — Retiro MLOps

Principios innegociables para toda spec, plan, tarea y línea de código. Si una petición choca con alguno, el agente se detiene y lo dice.

1. **Manda el enunciado del PB3.** Ninguna spec puede contradecirlo; si choca, se avisa antes de seguir. El agente del PB2 se reutiliza, no se rehace.
2. **La spec manda sobre el código.** El contrato HTTP (rutas, bodies y códigos) se escribe y aprueba antes de implementarlo; si cambia el comportamiento, primero se cambia la spec.
3. **Anclado al corpus.** El RAG responde solo con lo recuperado y se abstiene sin evidencia; el agente no inventa datos que deba aportar una tool.
4. **El modelo propone, Python decide.** La allowlist de tools, la validación de argumentos, los límites y el cierre del plan (`done`) se deciden en código, nunca solo por el LLM.
5. **HITL obligatorio.** Un plan solo se cierra con una decisión humana. Única excepción: que el cliente pida `auto_aprobar=true` de forma explícita (pruebas en Swagger); el front siempre decide con Aprobar o Rechazar.
6. **Capas separadas.** API, agente, datos y front van en capas distintas: la API solo llama a `procesar_turno` y `aprobar_plan`; el front es un cliente HTTP y no importa el grafo.
7. **Tools predecibles.** Toda tool devuelve `ok`, `error` o `blocked`, nunca lanza excepciones y deja traza; una API externa siempre tiene fallback local.
8. **Trazabilidad sin secretos.** Cada petición protegida deja un log con método, ruta, `thread_id`, `duration_ms` y status; nunca claves ni la connection string.
9. **Tests sin API ni red.** El LLM, los embeddings, AEMET y Postgres se sustituyen por dobles o una BD de prueba; prohibido avanzar con tests en rojo.
10. **Configuración y secretos.** Los valores configurables y las variables de entorno (`DATABASE_URL`, `API_KEY`, límites) se leen en `config.py`; las claves viven solo en `.env` local y en el panel de Render, nunca en el repo, la imagen ni los logs.
11. **Stack cerrado.** Python 3.10+, LangChain/LangGraph, Gemini, ChromaDB, FastAPI, Pydantic, SQLModel, PostgreSQL, Docker, Render, Streamlit y pytest. Fuera: Kubernetes, JWT/OAuth, Redis, Alembic, varias réplicas, checkpoint en Postgres. Dependencias nuevas, solo con spec y plan.
12. **Estado.** El historial de producto vive en Postgres; el checkpoint del grafo sigue en memoria, así que el servicio corre con un solo proceso.
13. **Git.** `main` es lo que despliega Render y nadie trabaja ahí; una rama por bloque hacia `develop`, PR revisada por otra persona, mínimo una por miembro y commits pequeños.
14. **Idioma** *(pendiente de acordar con el equipo)*. Identificadores nuevos en inglés técnico neutro; mensajes y documentación en español; el código heredado no se renombra.