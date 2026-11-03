"""FastAPI application factory for the Turnos-Odontologia SaaS."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    error_body,
    http_exception_response,
    unexpected_response,
)
from app.core.logging import configure_logging, get_logger
from app.core.settings import Settings, get_settings
from app.middleware import RequestIdMiddleware
from app.routers.health import router as health_router

logger = get_logger("app.startup")


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or get_settings()
    configure_logging(runtime.log_level)
    app = FastAPI(title=f"{runtime.app_name} API", version=runtime.app_version)
    app.state.settings = runtime
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        return http_exception_response(exc, request)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, _exc: RequestValidationError) -> JSONResponse:
        cid = getattr(request.state, "correlation_id", None) or "-"
        logger.info("validation_error", extra={"correlation_id": cid})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body("VALIDATION_ERROR", "Revisá los datos enviados e intentá nuevamente.", cid),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        return unexpected_response(exc, request)

    return app
