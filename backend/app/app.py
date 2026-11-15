"""FastAPI application factory for the Turnos-Odontologia SaaS."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.service import AuthService
from app.core.exceptions import (
    error_body,
    http_exception_response,
    unexpected_response,
)
from app.core.logging import configure_logging, get_logger
from app.core.settings import Settings, get_settings
from app.db import create_db_engine
from app.db import session_factory as create_session_factory
from app.demo import build_demo_services
from app.middleware import RequestIdMiddleware
from app.routers.auth import router as auth_router
from app.routers.caja import crear_router as crear_router_caja
from app.routers.catalogos import router as catalogos_router
from app.routers.health import router as health_router
from app.routers.lista_espera import crear_router as crear_router_lista_espera
from app.routers.reservas_publicas import crear_router_publico
from app.routers.senas import crear_router_publico as crear_router_senas_publico
from app.routers.senas_internas import crear_router_interno as crear_router_senas_interno
from app.routers.turnos import crear_router as crear_router_turnos
from app.routers.webhooks_mp import crear_router_webhook
from app.turnos.servicio import ConflictoSolape, TurnoError

logger = get_logger("app.startup")


def create_app(
    settings: Settings | None = None,
    auth_service: AuthService | None = None,
    session_factory_override: Callable[[], Session] | None = None,
) -> FastAPI:
    runtime = settings or get_settings()
    configure_logging(runtime.log_level)
    app = FastAPI(title=f"{runtime.app_name} API", version=runtime.app_version)
    maker = session_factory_override or create_session_factory(create_db_engine(runtime))
    app.state.settings = runtime
    app.state.session_factory = maker
    app.state.auth_service = auth_service or AuthService(runtime, maker)
    demo = build_demo_services()
    app.state.demo_services = demo
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(catalogos_router)
    app.include_router(crear_router_turnos(demo.turnos, demo.hueco_port))
    app.include_router(crear_router_publico(demo.reservas))
    app.include_router(crear_router_lista_espera(demo.lista_espera, demo.ofertas, demo.tenants))
    app.include_router(crear_router_caja(demo.caja))
    app.include_router(crear_router_senas_publico(demo.senas))
    app.include_router(crear_router_senas_interno(demo.senas_consulta, demo.senas_aplicacion))
    app.include_router(crear_router_webhook(demo.senas_webhook))

    @app.exception_handler(TurnoError)
    async def handle_turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        body: dict[str, object] = {"detalle": exc.mensaje}
        codigo_dominio = getattr(exc, "codigo_dominio", None)
        if codigo_dominio:
            body["codigo"] = codigo_dominio
        if isinstance(exc, ConflictoSolape):
            body["alternativas"] = [
                {"inicio": alternativa.inicio, "fin": alternativa.fin}
                for alternativa in exc.alternativas
            ]
        return JSONResponse(status_code=exc.codigo, content=jsonable_encoder(body))

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
