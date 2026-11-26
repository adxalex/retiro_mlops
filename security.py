
import logging
import re
import time
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger("security")


class RateLimiter:
    """Limitador de peticiones por API key usando ventanas de 60 segundos."""

    def __init__(
        self,
        limit: int = 30,
        clock: Callable[[], float] = time.time,
    ):
        if limit < 1:
            raise ValueError("El límite debe ser mayor que cero")

        self.limit = limit
        self.clock = clock
        self.requests: dict[str, tuple[int, int]] = {}

    def allow(self, api_key: str) -> bool:
        """Devuelve True si permite la petición y False si supera el límite."""

        current_window = int(self.clock() // 60)
        window, count = self.requests.get(api_key, (current_window, 0))

        if window != current_window:
            window = current_window
            count = 0

        if count >= self.limit:
            self.requests[api_key] = (window, count)
            return False

        self.requests[api_key] = (window, count + 1)
        return True


class ApiKeyMaskingFilter(logging.Filter):
    """Oculta las API keys que aparezcan en mensajes de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()

        message = re.sub(
            r"([?&]api_key=)[^&\s]+",
            r"\1***",
            message,
            flags=re.IGNORECASE,
        )

        record.msg = message
        record.args = ()

        return True


class SecurityGateMiddleware(BaseHTTPMiddleware):
    """Controla el acceso y registra las peticiones protegidas."""

    def __init__(
        self,
        app,
        api_key: str | None,
        limiter: RateLimiter,
        protected_paths: set[str],
    ):
        super().__init__(app)
        self.api_key = api_key
        self.limiter = limiter
        self.protected_paths = protected_paths

    def log_request(
        self,
        request: Request,
        status: int,
        start_time: float,
    ) -> None:
        """Registra los datos de una petición sin incluir información secreta."""

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "Petición protegida",
            extra={
                "method": request.method,
                "path": request.url.path,
                "thread_id": request.query_params.get("thread_id"),
                "duration_ms": duration_ms,
                "status": status,
            },
        )

    async def dispatch(self, request: Request, call_next):
        # OPTIONS queda fuera del control de seguridad.
        if request.method == "OPTIONS":
            return await call_next(request)

        # Las rutas públicas no necesitan autenticación.
        if request.url.path not in self.protected_paths:
            return await call_next(request)

        start_time = time.perf_counter()

        # 1. Comprobar si la API key está configurada.
        if not self.api_key:
            response = JSONResponse(
                status_code=503,
                content={"detail": "Servicio no configurado"},
            )
            self.log_request(request, response.status_code, start_time)
            return response

        # 2. Comprobar la API key enviada por el cliente.
        provided_api_key = request.query_params.get("api_key")

        if provided_api_key != self.api_key:
            response = JSONResponse(
                status_code=401,
                content={"detail": "API key ausente o incorrecta"},
            )
            self.log_request(request, response.status_code, start_time)
            return response

        # 3. Comprobar el límite de peticiones.
        if not self.limiter.allow(provided_api_key):
            response = JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas peticiones"},
            )
            self.log_request(request, response.status_code, start_time)
            return response

        # 4. La petición puede llegar al endpoint.
        try:
            response = await call_next(request)
        except Exception:
            self.log_request(request, 500, start_time)
            raise

        self.log_request(request, response.status_code, start_time)

        return response
