"""Shared exception envelope for API responses."""
from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("app.errors")


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", None) or str(uuid4())


def error_body(code: str, message: str, correlation_id: str) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
        }
    }


def http_exception_response(exc: HTTPException, request: Request) -> JSONResponse:
    cid = _correlation_id(request)
    message = str(exc.detail)
    code = code_from_status(exc.status_code)
    logger.warning("http_error", extra={"status_code": exc.status_code, "correlation_id": cid, "code": code})
    headers = dict(exc.headers) if exc.headers else None
    return JSONResponse(status_code=exc.status_code, content=error_body(code, message, cid), headers=headers)


def code_from_status(status_code: int) -> str:
    mapping = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
    }
    return mapping.get(status_code, "HTTP_ERROR")


def unexpected_response(exc: Exception, request: Request) -> JSONResponse:
    cid = _correlation_id(request)
    logger.exception("unexpected_error", extra={"correlation_id": cid, "error_type": type(exc).__name__})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body("INTERNAL_ERROR", "Ocurrió un error inesperado. Intentá nuevamente.", cid),
    )

