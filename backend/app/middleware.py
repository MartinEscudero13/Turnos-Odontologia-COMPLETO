"""Request correlation middleware with PHI-safe structured logs."""
from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger("app.http")

# El token de pago de la seña viaja en el **path** del link público
# (`/api/publico/{tenant}/senas/{token}`). Ese token no es un login, pero sí una
# credencial viva: el log estructurado de la aplicación no lo copia (RN-CL-04,
# C-11 §11). El access log del servidor HTTP (uvicorn/gunicorn) queda fuera de
# este change: su redacción es de infraestructura.
_RUTA_CON_TOKEN = re.compile(r"^(/api/publico/[^/]+/senas/)[^/]+")

MARCADOR_TOKEN = "[REDACTED]"


def ruta_para_log(path: str) -> str:
    """Path sin el token público de la seña; el resto se registra igual."""
    return _RUTA_CON_TOKEN.sub(rf"\1{MARCADOR_TOKEN}", path)


def new_correlation_id() -> str:
    return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or new_correlation_id()
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": ruta_para_log(request.url.path),
                "status_code": response.status_code,
                "correlation_id": correlation_id,
            },
        )
        return response
