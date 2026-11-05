"""Router FastAPI de la reserva pública — C-06 (tasks 7.1–7.5, 8.x).

El tenant se resuelve SIEMPRE desde el segmento `{token_tenant}` de la ruta; los
headers de actor (`X-Tenant-Id`, `X-Rol`, ...) se ignoran (D2/D8, deuda D-A de
C-03). Errores de dominio → `TurnoError` mapeado a `{detalle, alternativas}` sin
trazas; rate-limit → `429` con `Retry-After`.

Nota (riesgo D8): la IP del cliente se lee del peer (`request.client.host`); en
producción la fuente debe ser la config del proxy de confianza, no un header crudo.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime

from app.reservas.puertos import AccionPublica
from app.reservas.servicio import DemasiadasSolicitudes, ServicioReservasPublicas
from app.schemas.reserva import (
    AlternativaPublicaOut,
    CancelarIn,
    CatalogoPublicoOut,
    DisponibilidadOut,
    ErrorPublicoOut,
    PrestacionPublicaOut,
    ProfesionalPublicoOut,
    ReprogramarIn,
    ReservaConsultaOut,
    ReservaIn,
    ReservaOut,
    VerificacionIn,
    VerificacionOut,
)
from app.turnos.servicio import ConflictoSolape, TurnoError

ACCIONES: tuple[str, ...] = ("reservar", "cancelar", "reprogramar")


def _ip_del_request(request: Request) -> str:
    client = request.client
    return client.host if client is not None else "desconocida"


def _error_publico(exc: TurnoError) -> dict[str, object]:
    alts = exc.alternativas if isinstance(exc, ConflictoSolape) else []
    return ErrorPublicoOut(
        detalle=exc.mensaje,
        alternativas=[AlternativaPublicaOut(inicio=a.inicio, fin=a.fin) for a in alts],
    ).model_dump(mode="json")


def crear_router_publico(svc: ServicioReservasPublicas) -> APIRouter:
    r = APIRouter()

    @r.get(
        "/api/publico/{token_tenant}/catalogo",
        response_model=CatalogoPublicoOut,
    )
    def catalogo(token_tenant: str) -> CatalogoPublicoOut:
        cat = svc.catalogo(token_tenant)
        return CatalogoPublicoOut(
            prestaciones=[
                PrestacionPublicaOut(id=p.id, nombre=p.nombre, duracion_min=p.duracion_min)
                for p in cat.prestaciones
            ],
            profesionales=[
                ProfesionalPublicoOut(id=p.id, nombre=p.nombre) for p in cat.profesionales
            ],
        )

    @r.get(
        "/api/publico/{token_tenant}/disponibilidad",
        response_model=list[DisponibilidadOut],
    )
    def disponibilidad(
        token_tenant: str,
        prestacion: str,
        desde: AwareDatetime,
        profesional: str | None = None,
    ) -> list[DisponibilidadOut]:
        slots = svc.disponibilidad(token_tenant, prestacion, profesional, desde)
        return [
            DisponibilidadOut(
                inicio=s.inicio, fin=s.fin, profesional_id=s.profesional_id, sillon_id=s.sillon_id
            )
            for s in slots
        ]

    @r.post(
        "/api/publico/{token_tenant}/verificacion",
        status_code=201,
        response_model=VerificacionOut,
    )
    def verificacion(token_tenant: str, body: VerificacionIn, request: Request) -> VerificacionOut:
        accion: AccionPublica = body.accion
        d = svc.emitir_verificacion(token_tenant, accion, _ip_del_request(request))
        return VerificacionOut(
            verificacion_id=d.verificacion_id, expira_at=d.expira_at, canal=d.canal
        )

    @r.post("/api/publico/{token_tenant}/reservas", status_code=201, response_model=ReservaOut)
    def reservar(token_tenant: str, body: ReservaIn, request: Request) -> ReservaOut:
        res = svc.reservar(
            token_tenant,
            prestacion_id=body.prestacion,
            profesional_id=body.profesional,
            inicio=body.inicio,
            nombre=body.nombre,
            telefono=body.telefono,
            verificacion_id=body.verificacion_id,
            ip=_ip_del_request(request),
        )
        return ReservaOut(
            turno_id=res.turno.id,
            estado=res.turno.estado,
            inicio=res.turno.inicio,
            fin=res.turno.fin,
            origen=res.turno.origen,
            prestacion=res.turno.prestacion_id,
            sillon_id=res.turno.sillon_id,
            token_publico=res.token_publico,
        )

    @r.get(
        "/api/publico/{token_tenant}/reservas/{token}",
        response_model=ReservaConsultaOut,
    )
    def obtener_reserva(token_tenant: str, token: str) -> ReservaConsultaOut:
        t = svc.obtener(token_tenant, token)
        return ReservaConsultaOut(
            turno_id=t.id,
            estado=t.estado,
            inicio=t.inicio,
            fin=t.fin,
            prestacion=t.prestacion_id,
            token_publico=token,
        )

    @r.post(
        "/api/publico/{token_tenant}/reservas/{token}/cancelacion",
        response_model=ReservaConsultaOut,
    )
    def cancelar(token_tenant: str, token: str, body: CancelarIn, request: Request) -> ReservaConsultaOut:
        t = svc.cancelar(
            token_tenant, token, body.verificacion_id, _ip_del_request(request)
        )
        return ReservaConsultaOut(
            turno_id=t.id,
            estado=t.estado,
            inicio=t.inicio,
            fin=t.fin,
            prestacion=t.prestacion_id,
            token_publico=token,
        )

    @r.post("/api/publico/{token_tenant}/reservas/{token}/reprogramacion")
    def reprogramar(token_tenant: str, token: str, body: ReprogramarIn, request: Request) -> dict[str, object]:
        res = svc.reprogramar(
            token_tenant,
            token,
            nuevo_inicio=body.nuevo_inicio,
            verificacion_id=body.verificacion_id,
            ip=_ip_del_request(request),
        )
        return {
            "original": ReservaConsultaOut(
                turno_id=res.original.id,
                estado=res.original.estado,
                inicio=res.original.inicio,
                fin=res.original.fin,
                prestacion=res.original.prestacion_id,
                token_publico=token,
            ).model_dump(mode="json"),
            "nuevo": ReservaConsultaOut(
                turno_id=res.nuevo.id,
                estado=res.nuevo.estado,
                inicio=res.nuevo.inicio,
                fin=res.nuevo.fin,
                prestacion=res.nuevo.prestacion_id,
                token_publico=token,
            ).model_dump(mode="json"),
        }

    return r


def crear_app_publica(servicio: ServicioReservasPublicas | None = None) -> FastAPI:
    """App mínima del change (patrón `crear_app` de C-05, dependencias inyectables)."""
    app = FastAPI(title="Turnos-Odontologia C-06 reserva pública")
    svc = servicio if servicio is not None else ServicioReservasPublicas._app_default()

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        headers = None
        if isinstance(exc, DemasiadasSolicitudes):
            headers = {"Retry-After": str(exc.retry_after_s)}
        return JSONResponse(status_code=exc.codigo, content=_error_publico(exc), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorPublicoOut(detalle="Revisá los datos enviados e intentá nuevamente.").model_dump(
                mode="json"
            ),
        )

    app.include_router(crear_router_publico(svc))
    return app
