
"""Aplicación FastAPI del agente del Parque del Retiro."""

from fastapi import FastAPI
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

import logging

import config
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

    return app
