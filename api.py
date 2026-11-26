"""Aplicación FastAPI del agente del Parque del Retiro."""

import asyncio
import logging
import uuid

from fastapi import FastAPI, Request, Path
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

import config
from schemas import (
    AskRequest,
    AskResponse,
    ApproveRequest,
    MessageResponse,
)
from security import (
    ApiKeyMaskingFilter,
    RateLimiter,
    SecurityGateMiddleware,
)


def create_app(repo=None, agent=None):
    """Crea la aplicación e inyecta el repositorio y el agente."""

    # Si no se proporciona un repositorio, se utiliza el repositorio real.
    # La importación se hace aquí para no conectar con PostgreSQL
    # al importar el módulo.
    if repo is None:
        from src.db import make_repository

        repo = make_repository()

    # Si no se proporciona un agente, utilizamos el agente real.
    if agent is None:
        from src import agent as real_agent

        agent = real_agent

    app = FastAPI(
        title="API del Parque del Retiro",
        description="API del agente inteligente del Parque del Retiro.",
        version="1.0.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        redoc_url=None,
    )
    
    # Hilos con planes pendientes y datos del turno original.
    app.state.pending_threads = {}

    # Hilos que tienen una petición en ejecución.
    app.state.in_flight_threads = set()

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        return JSONResponse(
            status_code=422,
            content={"detail": "Solicitud no válida"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ):
        mensajes = {
            404: "Recurso no encontrado",
            405: "Método no permitido",
        }

        mensaje = mensajes.get(
            exc.status_code,
            "Error en la solicitud",
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": mensaje},
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(
        request: Request,
        exc: Exception,
    ):
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno del servidor"},
        )
    limiter = RateLimiter(
        limit=config.RATE_LIMIT_PER_MINUTE
    )

    app.add_middleware(
        SecurityGateMiddleware,
        api_key=config.API_KEY,
        limiter=limiter,
        protected_paths=set(config.RUTAS_PROTEGIDAS),
    )


    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


    # Evita que los logs de acceso de Uvicorn muestren la API key.
    access_logger = logging.getLogger("uvicorn.access")
    masking_filter = ApiKeyMaskingFilter()

    if not any(
        isinstance(filtro, ApiKeyMaskingFilter)
        for filtro in access_logger.filters
    ):
        access_logger.addFilter(masking_filter)

    # Guardamos las dependencias para utilizarlas en los siguientes endpoints.
    app.state.repo = repo
    app.state.agent = agent

    @app.get("/health")
    def health():
        """Comprueba el estado de la API y del repositorio."""

        try:
            db_status = "ok" if repo.ping() else "error"
        except Exception:
            db_status = "error"

        return {
            "status": "ok",
            "storage": "postgres",
            "db": db_status,
        }

    @app.post("/ask", response_model=AskResponse)
    async def ask(request: AskRequest):
        """Procesa una pregunta con timeout y reserva por hilo."""

        thread_id = request.thread_id or uuid.uuid4().hex

        from fastapi import HTTPException

        # Comprobamos si el hilo tiene un plan pendiente de aprobación.
        if thread_id in app.state.pending_threads:
            raise HTTPException(
                status_code=409,
                detail="El hilo tiene un plan pendiente de aprobación",
            )

        # Comprobamos si ya hay otra petición ejecutándose en este hilo.
        if thread_id in app.state.in_flight_threads:
            raise HTTPException(
                status_code=409,
                detail="Ya hay una petición en ejecución para este hilo",
            )

        # Reservamos el hilo antes de iniciar el agente.
        app.state.in_flight_threads.add(thread_id)

        # Ejecutamos el agente en un hilo independiente.
        tarea_agente = asyncio.create_task(
            asyncio.to_thread(
                agent.procesar_turno,
                texto=request.pregunta,
                thread_id=thread_id,
            )
        )

        try:
            resultado = await asyncio.wait_for(
                asyncio.shield(tarea_agente),
                timeout=config.ASK_TIMEOUT_SECONDS,
            )

        except asyncio.TimeoutError:
            # El agente continúa ejecutándose después del timeout.
            # Liberamos la reserva únicamente cuando termine realmente.
            def liberar_reserva(tarea):
                app.state.in_flight_threads.discard(thread_id)

                # Recuperamos posibles excepciones de la tarea.
                if not tarea.cancelled():
                    tarea.exception()

            tarea_agente.add_done_callback(liberar_reserva)

            raise HTTPException(
                status_code=504,
                detail="Tiempo de espera agotado al procesar la consulta",
            )

        except Exception:
            # Si el agente falla, liberamos inmediatamente la reserva.
            app.state.in_flight_threads.discard(thread_id)
            raise

        # El agente ha terminado correctamente.
        app.state.in_flight_threads.discard(thread_id)

        # Si el agente devuelve un error, no guardamos el turno.
        if resultado.get("error"):
            raise RuntimeError("Error al procesar la consulta")

        respuesta = resultado.get("respuesta", "") or ""
        plan = resultado.get("plan", []) or []
        pendiente_aprobacion = bool(
            resultado.get("pendiente_aprobacion", False)
        )


        # Si existe un plan pendiente, comprobamos si debe autoaprobarse.
        if pendiente_aprobacion:

            if request.auto_aprobar:
                resultado_aprobacion = agent.aprobar_plan(
                    thread_id=thread_id,
                    aprobado=True,
                    comentario="",
                )

                if resultado_aprobacion.get("error"):
                    raise RuntimeError("Error al aprobar el plan")

                respuesta = (
                    resultado_aprobacion.get("respuesta", "") or ""
                )
                plan = resultado_aprobacion.get("plan", []) or []

                repo.save(
                    thread_id=thread_id,
                    question=request.pregunta,
                    answer=respuesta,
                    decision="aprobado",
                    comment="",
                )

                return {
                    "respuesta": respuesta,
                    "plan": plan,
                    "thread_id": thread_id,
                    "done": bool(resultado_aprobacion.get("done", False)),
                    "pendiente_hitl": False,
                    "error": None,
                }

            # Si no se autoaprueba, conservamos los datos del turno pendiente.
            app.state.pending_threads[thread_id] = {
                "question": request.pregunta,
                "answer": respuesta,
                "plan": plan,
            }

            return {
                "respuesta": respuesta,
                "plan": plan,
                "thread_id": thread_id,
                "done": False,
                "pendiente_hitl": True,
                "error": None,
            }

        # Si no hay aprobación pendiente, guardamos el turno.
        repo.save(
            thread_id=thread_id,
            question=request.pregunta,
            answer=respuesta,
            decision=None,
            comment=None,
        )

        return {
            "respuesta": respuesta,
            "plan": plan,
            "thread_id": thread_id,
            "done": bool(resultado.get("done", False)),
            "pendiente_hitl": False,
            "error": None,
        }

    
    @app.post("/approve", response_model=AskResponse)
    def approve(request: ApproveRequest):
        """Aprueba o rechaza un plan pendiente."""

        from fastapi import HTTPException

        thread_id = request.thread_id

        # No permitimos aprobar mientras haya una petición en ejecución.
        if thread_id in app.state.in_flight_threads:
            raise HTTPException(
                status_code=409,
                detail="Ya hay una petición en ejecución para este hilo",
            )

        # Recuperamos los datos del turno pendiente.
        turno_pendiente = app.state.pending_threads.get(thread_id)

        if turno_pendiente is None:
            raise HTTPException(
                status_code=409,
                detail="El hilo no tiene un plan pendiente de aprobación",
            )

        comentario = request.comentario or ""

        # Enviamos la decisión al agente.
        resultado = agent.aprobar_plan(
            thread_id=thread_id,
            aprobado=request.aprobado,
            comentario=comentario,
        )

        if resultado.get("error"):
            raise RuntimeError("Error al procesar la aprobación")

        # Determinamos la decisión y la respuesta que guardaremos.
        decision = "aprobado" if request.aprobado else "rechazado"

        if request.aprobado:
            respuesta_guardada = (
                resultado.get("respuesta", "") or ""
            )
        else:
            # Al rechazar, conservamos la respuesta original de /ask.
            respuesta_guardada = turno_pendiente["answer"]

        # Guardamos el turno una vez resuelta la aprobación.
        repo.save(
            thread_id=thread_id,
            question=turno_pendiente["question"],
            answer=respuesta_guardada,
            decision=decision,
            comment=comentario,
        )

        # El hilo deja de tener un plan pendiente.
        app.state.pending_threads.pop(thread_id)

        return {
            "respuesta": resultado.get("respuesta", "") or "",
            "plan": resultado.get("plan", []) or [],
            "thread_id": thread_id,
            "done": bool(resultado.get("done", False)),
            "pendiente_hitl": bool(
                resultado.get("pendiente_aprobacion", False)
            ),
            "error": None,
        }


    @app.get(
        "/threads/{thread_id}/messages",
        response_model=list[MessageResponse],
    )
    def get_thread_messages(
        thread_id: str = Path(
            min_length=1,
            max_length=64,
            pattern=r"^\S+$",
        ),
    ):
        """Devuelve el historial de mensajes de un hilo."""

        from fastapi import HTTPException

        # Recuperamos los turnos guardados del hilo.
        turnos = repo.list(thread_id)

        # Si no hay turnos cerrados, el hilo no tiene historial.
        if not turnos:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron mensajes para este hilo",
            )

        mensajes = []

        # El repositorio devuelve los turnos cronológicamente.
        for turno in turnos:
            # Mensaje del usuario.
            mensajes.append(
                MessageResponse(
                    role="user",
                    content=turno.question,
                    created_at=turno.created_at,
                )
            )

            # Respuesta del asistente, con decisión y comentario.
            mensajes.append(
                MessageResponse(
                    role="assistant",
                    content=turno.answer,
                    created_at=turno.created_at,
                    decision=turno.decision,
                    comentario=turno.comment,
                )
            )

        return mensajes

    
    return app