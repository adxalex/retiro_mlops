# AGENTS.md — Retiro MLOps

## Proyecto
Este repositorio es el Project Break 3 (MLOps). Parte del agente multiagente del PB2 (importado de `retiro_agents`, commit `7abee56`, que a su vez incluye el RAG del PB1) y lo publica como API FastAPI + PostgreSQL + Docker + Render, con un front Streamlit que solo es cliente HTTP. El agente se reutiliza, no se rehace. El enunciado oficial del PB3 manda sobre cualquier spec.

Base actual: asistente RAG en español sobre el Parque de El Retiro (Madrid) con agente LangGraph (supervisor, especialistas, HITL, tools con allowlist). El corpus curado está en `data/processed/`. Pipeline offline: `load` → `chunk` → `embed` (Gemini `gemini-embedding-001`) → `index` (ChromaDB, coseno); pipeline online: pregunta → `embed_query` → `retrieve` → `build_prompt` → LLM Gemini → `responder()` con fuentes o abstención. Interfaces actuales: CLI (`main.py`, `main_agent.py`) y Streamlit (`app.py`, `app_agent.py`). La API, la capa de datos y el front del PB3 están previstos y aún no existen (`[COMPLETAR]` en el mapa).

## Mapa del código
| Archivo | Responsabilidad |
|---|---|
| `config.py` | Constantes centralizadas: rutas, modelos, chunking, lotes y reintentos de embeddings, `TOP_K`, umbral de abstención, AEMET/horario del parque e índice preconstruido |
| `main.py` | CLI: `--index` (`--recreate-index`, `--dry-run`), `--query` (solo retrieval), `--ask` (RAG completo; `--top-k`, `--category`, `--score-minimo`, `--contexto`, `--json`) y `--saludo` |
| `app.py` | App Streamlit del RAG (PB1): banner del tiempo, chat, contexto recuperado y tabla de métricas. No es la API: esa vive en `api.py` |
| `app_agent.py` | App Streamlit del agente: chat con imagen opcional, Aprobar/Rechazar con comentario en la sidebar, expander de depuración y nueva conversación; solo llama a `procesar_turno` y `aprobar_plan` |
| `src/load.py` | Carga PDF, Markdown y CSV desde `DATA_DIR` y asigna `category`/`corpus_group` según el manifiesto del contrato |
| `src/chunk.py` | Fragmentación en chunks trazables, con limpieza de líneas repetidas y validación de configuración |
| `src/embed.py` | Embeddings Gemini por lotes con reintentos ante 429, `embed_query` y `limitar_chunks` |
| `src/embedding_cache.py` | Checkpoint persistente (`EmbeddingCheckpoint`) para reanudar embeddings interrumpidos |
| `src/index.py` | Cliente y colección ChromaDB, validación de chunks y upsert por lotes |
| `src/pipeline.py` | Orquestación offline: `prepare_corpus`, `summarize_corpus`, `build_index` |
| `src/retrieve.py` | Retrieval con `top_k`, filtros de metadata y conversión distancia → score |
| `src/generate.py` | Prompt anclado al contexto, llamada al LLM, citas y abstención; funciones principales `responder()` y `rag_ask()` |
| `src/gemini_auth.py` | Carga de la API key y cliente Gemini compartido |
| `src/fuentes.py` | Nombres legibles y organismo de cada fuente para las citas |
| `src/contexto_visita.py` | Saludo contextual: hora de Madrid, horario del parque y viento AEMET frente a los umbrales del protocolo |
| `src/logging_utils.py` | Registro JSONL de consultas, cronómetro y resumen de métricas |
| `main_agent.py` | CLI del agente: demo y modo interactivo con traza y HITL; usa `procesar_turno` y `aprobar_plan` |
| `src/agent.py` | Interfaz pública del agente: `procesar_turno` y `aprobar_plan` (única entrada para API y front) |
| `src/graph.py` | Grafo LangGraph: supervisor, especialistas, HITL y checkpoint en memoria |
| `src/state.py` | Estado del grafo (`EstadoGrafo`) y eventos de traza |
| `src/tools/` | Tools con allowlist (`TOOL_REGISTRY`, validación de argumentos): `rag_ask`, `api_dominio` (AEMET con fallback local), `hora_actual`, `describir_imagen` |
| `src/ui_agente.py` | Lógica pura de la app del agente, sin Streamlit ni grafo: sesión, validación de imagen, envío de turnos y decisiones, ocultación de secretos y datos de depuración |
| `api.py` | [COMPLETAR] (previsto) Punto de entrada FastAPI (`uvicorn api:app`); solo llama a `procesar_turno` y `aprobar_plan` |
| `schemas.py` | [COMPLETAR] (previsto) Modelos Pydantic del contrato HTTP |
| `security.py` | [COMPLETAR] (previsto) Autenticación por `API_KEY` y log de peticiones sin secretos |
| `src/db.py` | [COMPLETAR] (previsto) Conexión a PostgreSQL (`DATABASE_URL` desde `config.py`) |
| `src/models.py` | [COMPLETAR] (previsto) Modelos SQLModel del historial de producto |
| `Dockerfile` | [COMPLETAR] (previsto) Imagen de la API para Render |
| `front/` | [COMPLETAR] (previsto) Front Streamlit, cliente HTTP que no importa el grafo |
| `scripts/index_corpus.py` | CLI alternativa de indexación (`--dry-run`, `--keep-existing`, `--json`) |
| `scripts/download_index.py` | Descarga e instala el índice Chroma preconstruido (verifica SHA-256) |
| `scripts/validation/` | Validación de corpus, contrato PDF, modelos Gemini, smoke test de embeddings, evaluación de preguntas y calibración del umbral |
| `scripts/experiments/`, `scripts/etl/`, `scripts/corpus/` | Comparación de chunking, filtrado del inventario de arbolado y generación de PDF del corpus |
| `tests/` | Tests con pytest (incluye agente, grafo, tools y UI del agente) y dobles de prueba (sin API); el marcador `corpus` indexa el corpus real en una Chroma temporal con embeddings deterministas |

## Comandos
- Instalar: `pip install -r requirements.txt` (desarrollo: `pip install -r requirements-dev.txt`)
- Tests: `pytest` (no necesita API key); sin los tests lentos del corpus: `pytest -m "not corpus"`
- Descargar índice preconstruido: `python -m scripts.download_index` (no gasta API; `--force` borra `CHROMA_DIR`)
- Validar carga y chunking sin API: `python main.py --index --dry-run`
- Preparar e indexar: `python main.py --index` (`--recreate-index` para reconstruir) o `python -m scripts.index_corpus` (reconstruye la colección por defecto; `--keep-existing` la conserva) ⚠️ gasta API
- Solo retrieval: `python main.py --query "..."` ⚠️ gasta API (embedding de la consulta)
- Preguntar: `python main.py --ask "..."` ⚠️ gasta API
- Saludo con el tiempo del Retiro: `python main.py --saludo` (consulta AEMET con `AEMET_API_KEY`, no usa Gemini)
- Web: `streamlit run app.py` ⚠️ gasta API
- Web del agente: `streamlit run app_agent.py` ⚠️ gasta API
- CLI del agente: `python main_agent.py` ⚠️ gasta API
- API local: `uvicorn api:app` ⚠️ gasta API (aún no existe `api.py`; previsto). Docker y front del PB3: `[COMPLETAR]`

## Flujo SDD de este repositorio
- Constitución: `docs/constitution.md` (Retiro MLOps, 14 principios). Léela siempre.
- Specs: `specs/NNN-nombre/` con `spec.md`, `plan.md`, `tasks.md` y `validacion.md`. La spec activa es la de número más alto, salvo que se indique otra.
- Plantillas: `docs/plantillas/`. Chuleta de EARS: `docs/chuleta_ears.md`. Cómo testear sin API: `docs/tests_sin_api.md`.
- Comandos por fase: `.claude/commands/` (`/sdd-contexto`, `/sdd-constitucion`, `/sdd-spec`, `/sdd-clarificar`, `/sdd-plan`, `/sdd-tareas`, `/sdd-implementar`, `/sdd-validar`, `/sdd-cambio`, `/sdd-spec-inversa`).

## Reglas
- Lee `docs/constitution.md` y la spec activa antes de tocar nada. Si una petición choca con la constitución o el enunciado del PB3, detente y dilo.
- Respeta la fase en la que estamos. En spec, clarificación, plan y tareas NO se escribe código.
- En implementación: una sola tarea de `tasks.md` cada vez, tests primero, y te paras al terminarla.
- No modifiques `specs/` salvo que la fase lo pida. El contrato HTTP (rutas, bodies, códigos) se aprueba en la spec antes de implementarlo; si cambia el comportamiento, primero se cambia la spec.
- Stack cerrado (Python 3.10+, LangChain/LangGraph, Gemini, ChromaDB, FastAPI, Pydantic, SQLModel, PostgreSQL, Docker, Render, Streamlit, pytest). Fuera: Kubernetes, JWT/OAuth, Redis, Alembic, varias réplicas, checkpoint en Postgres. No añadas dependencias si la spec y el plan no lo dicen.
- No cambies el contrato de `responder()` / `rag_ask()` (`src/generate.py`) ni de `procesar_turno` / `aprobar_plan` (`src/agent.py`) si la spec no lo dice.
- Capas separadas: la API solo llama a `procesar_turno` y `aprobar_plan`; el front es un cliente HTTP y no importa el grafo.
- El modelo propone, Python decide: allowlist de tools, validación de argumentos, límites y cierre del plan se resuelven en código. HITL obligatorio: un plan solo se cierra con decisión humana. Excepción del enunciado: la API acepta `auto_aprobar` (`true` por defecto, comodidad en Swagger) y el front siempre envía `auto_aprobar=false`.
- Toda tool devuelve `ok`, `error` o `blocked`, nunca lanza excepciones; una API externa siempre tiene fallback local.
- Las constantes y variables de entorno (`DATABASE_URL`, `API_KEY`, límites) se leen en `config.py`; no se definen en los módulos.
- Los logs de peticiones no incluyen claves ni la connection string. Las claves solo viven en `.env` local y en el panel de Render.
- Tests sin API ni red: LLM, embeddings, AEMET y Postgres se sustituyen por dobles o una BD de prueba. No avances con tests en rojo.
- Git: no se trabaja en `main` (lo que despliega Render); una rama por bloque hacia `develop` y PR revisada por otra persona.
- Idioma (constitución §14): mensajes y documentación en español; campos de dominio del contrato HTTP en español (`pregunta`, `respuesta`, `plan`, `decision`, `comentario`); en inglés los fijados por el enunciado o FastAPI (`role`, `content`, `detail`) y los técnicos (`created_at`, `status`, `storage`, `db`); identificadores internos nuevos en inglés técnico neutro; el código heredado no se renombra.
- Los comentarios del código son breves y neutrales, sin nombres de personas ni referencias a herramientas de IA.
- No ejecutes comandos marcados con ⚠️ salvo que te lo pida: cuestan dinero y tiempo. Para verificar, usa `pytest`.
- Nunca leas ni muestres el contenido de `.env`.

## Al terminar cualquier tarea
- Ejecuta `pytest` y pega el resumen del resultado.
- Indica qué RF de la spec cubre lo que has hecho.
