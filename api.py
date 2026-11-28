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

    def comprobar_repositorio():
        """Comprueba que el repositorio está disponible."""

        from fastapi import HTTPException

        try:
            if not repo.ping():
                raise HTTPException(
                    status_code=503,
                    detail="Repositorio no disponible",
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="Repositorio no disponible",
            )

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

    @app.post(
        "/ask",
        response_model=AskResponse,
        openapi_extra={
            "parameters": [
                {
                    "name": "api_key",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ]
        },
    )

    async def ask(request: AskRequest):
        """Procesa una pregunta con timeout y reserva por hilo."""

        comprobar_repositorio()

        thread_id = request.thread_id or uuid.uuid4().hex

        from fastapi import HTTPException

        if thread_id in app.state.pending_threads:
            raise HTTPException(
                status_code=409,
                detail="El hilo tiene un plan pendiente de aprobación",
            )

        if thread_id in app.state.in_flight_threads:
            raise HTTPException(
                status_code=409,
                detail="Ya hay una petición en ejecución para este hilo",
            )

        app.state.in_flight_threads.add(thread_id)

        reserva_diferida = False

        def liberar_reserva(tarea):
            app.state.in_flight_threads.discard(thread_id)

            if not tarea.cancelled():
                tarea.exception()

        async def ejecutar_en_hilo(funcion, **kwargs):
            nonlocal reserva_diferida

            tarea = asyncio.create_task(
                asyncio.to_thread(funcion, **kwargs)
            )

            try:
                return await asyncio.shield(tarea)

            except asyncio.CancelledError:
                reserva_diferida = True
                tarea.add_done_callback(liberar_reserva)
                raise

        tarea_agente = asyncio.create_task(
            asyncio.to_thread(
                agent.procesar_turno,
                texto=request.pregunta,
                thread_id=thread_id,
            )
        )

        try:
            # El timeout se aplica únicamente a la ejecución del agente.
            try:
                resultado = await asyncio.wait_for(
                    asyncio.shield(tarea_agente),
                    timeout=config.ASK_TIMEOUT_SECONDS,
                )

            except asyncio.TimeoutError:
                # El agente sigue trabajando. No guardamos su resultado.
                reserva_diferida = True
                tarea_agente.add_done_callback(liberar_reserva)

                raise HTTPException(
                    status_code=504,
                    detail="Tiempo de espera agotado al procesar la consulta",
                )

            except asyncio.CancelledError:
                # Si el cliente se desconecta, el agente puede seguir trabajando.
                reserva_diferida = True
                tarea_agente.add_done_callback(liberar_reserva)
                raise

            if resultado.get("error"):
                raise RuntimeError("Error al procesar la consulta")

            respuesta = resultado.get("respuesta", "") or ""
            plan = resultado.get("plan", []) or []
            pendiente_aprobacion = bool(
                resultado.get("pendiente_aprobacion", False)
            )

            if pendiente_aprobacion:
                if request.auto_aprobar:
                    resultado_aprobacion = await ejecutar_en_hilo(
                        agent.aprobar_plan,
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

                    await ejecutar_en_hilo(
                        repo.save,
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
                        "done": bool(
                            resultado_aprobacion.get("done", False)
                        ),
                        "pendiente_hitl": False,
                        "error": None,
                    }

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

            await ejecutar_en_hilo(
                repo.save,
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

        finally:
            if not reserva_diferida:
                app.state.in_flight_threads.discard(thread_id)

    @app.post(
        "/approve",
        openapi_extra={
            "parameters": [
                {
                    "name": "api_key",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ]
        },
    )
    def approve(request: ApproveRequest):
        """Aprueba o rechaza un plan pendiente."""
        comprobar_repositorio()

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
    openapi_extra={
        "parameters": [
            {
                "name": "api_key",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            }
        ]
    },
)
    def get_thread_messages(
        thread_id: str = Path(
            min_length=1,
            max_length=64,
            pattern=r"^\S+$",
        ),
    ):
        """Devuelve el historial de mensajes de un hilo."""

        comprobar_repositorio()

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