"""Router FastAPI de ficha clínica — C-08 (backend-only, inyectable).

Mapea el dominio a HTTP: 201 crear, 200 leer/listar, 404 cross-tenant, 403 RBAC,
409 CONSENTIMIENTO_REQUERIDO / ficha duplicada, 422 payload/tipo inválido.

El actor se resuelve por headers (`actor_desde_headers`) igual que C-05/C-07; el
JWT real de C-03 reemplaza la dependencia sin cambiar el contrato. Errores de
dominio → `TurnoError` mapeado a `{detalle, ...}` sin trazas.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.ficha_clinica.puertos import Adjunto, Consentimiento, Evolucion, Ficha
from app.ficha_clinica.servicio import ServicioFichaClinica
from app.routers.turnos import actor_desde_headers
from app.schemas.ficha_clinica import (
    AdjuntoIn,
    AdjuntoOut,
    ConsentimientoIn,
    ConsentimientoOut,
    EvolucionIn,
    EvolucionOut,
    FichaOut,
)
from app.schemas.turno import ErrorOut
from app.turnos.servicio import Actor, TurnoError


def _ficha_out(f: Ficha) -> FichaOut:
    return FichaOut(id=f.id, paciente_id=f.paciente_id, creado_en=f.creado_en)


def _evolucion_out(e: Evolucion) -> EvolucionOut:
    return EvolucionOut(
        id=e.id,
        paciente_id=e.paciente_id,
        profesional_id=e.profesional_id,
        fecha=e.fecha,
        texto=e.texto,
        firma_hash=e.firma_hash,
        creado_en=e.creado_en,
    )


def _adjunto_out(a: Adjunto) -> AdjuntoOut:
    return AdjuntoOut(
        id=a.id, ficha_id=a.ficha_id, tipo=a.tipo, storage_ref=a.storage_ref, creado_en=a.creado_en
    )


def _consentimiento_out(c: Consentimiento) -> ConsentimientoOut:
    assert c.timestamp is not None  # el caso de uso de registro siempre exige timestamp válido
    return ConsentimientoOut(
        id=c.id, paciente_id=c.paciente_id, timestamp=c.timestamp, canal=c.canal, creado_en=c.creado_en
    )


def _error_body(exc: TurnoError) -> dict[str, object]:
    return ErrorOut(detalle=exc.mensaje).model_dump(mode="json")


def crear_router(svc: ServicioFichaClinica) -> APIRouter:
    """Router de ficha clínica inyectando el servicio (testeable sin DB)."""
    r = APIRouter()

    @r.post("/api/pacientes/{paciente_id}/ficha", status_code=201, response_model=FichaOut)
    def crear_ficha(paciente_id: str, actor: Actor = Depends(actor_desde_headers)) -> FichaOut:
        return _ficha_out(svc.crear_ficha(actor, paciente_id=paciente_id))

    @r.get("/api/pacientes/{paciente_id}/ficha", response_model=FichaOut)
    def obtener_ficha(paciente_id: str, actor: Actor = Depends(actor_desde_headers)) -> FichaOut:
        return _ficha_out(svc.obtener_ficha(actor, paciente_id=paciente_id))

    @r.post("/api/evoluciones", status_code=201, response_model=EvolucionOut)
    def registrar_evolucion(body: EvolucionIn, actor: Actor = Depends(actor_desde_headers)) -> EvolucionOut:
        return _evolucion_out(
            svc.registrar_evolucion(
                actor,
                paciente_id=body.paciente_id,
                profesional_id=body.profesional_id,
                fecha=body.fecha,
                texto=body.texto,
                firma_hash=body.firma_hash,
            )
        )

    @r.get("/api/evoluciones", response_model=list[EvolucionOut])
    def listar_evoluciones(paciente_id: str, actor: Actor = Depends(actor_desde_headers)) -> list[EvolucionOut]:
        return [_evolucion_out(e) for e in svc.listar_evoluciones(actor, paciente_id=paciente_id)]

    @r.post("/api/adjuntos", status_code=201, response_model=AdjuntoOut)
    def registrar_adjunto(body: AdjuntoIn, actor: Actor = Depends(actor_desde_headers)) -> AdjuntoOut:
        return _adjunto_out(
            svc.registrar_adjunto(
                actor, ficha_id=body.ficha_id, tipo=body.tipo, storage_ref=body.storage_ref
            )
        )

    @r.get("/api/adjuntos", response_model=list[AdjuntoOut])
    def listar_adjuntos(ficha_id: str, actor: Actor = Depends(actor_desde_headers)) -> list[AdjuntoOut]:
        return [_adjunto_out(a) for a in svc.listar_adjuntos(actor, ficha_id=ficha_id)]

    @r.post("/api/consentimientos", status_code=201, response_model=ConsentimientoOut)
    def registrar_consentimiento(
        body: ConsentimientoIn, actor: Actor = Depends(actor_desde_headers)
    ) -> ConsentimientoOut:
        return _consentimiento_out(
            svc.registrar_consentimiento(
                actor, paciente_id=body.paciente_id, timestamp=body.timestamp, canal=body.canal
            )
        )

    @r.get("/api/consentimientos", response_model=list[ConsentimientoOut])
    def listar_consentimientos(
        paciente_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> list[ConsentimientoOut]:
        return [_consentimiento_out(c) for c in svc.listar_consentimientos(actor, paciente_id=paciente_id)]

    return r


def crear_app(svc: ServicioFichaClinica) -> FastAPI:
    """App mínima del change (patrón `crear_app` de C-05/C-06/C-07)."""
    app = FastAPI(title="Turnos-Odontologia C-08 ficha clínica")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc))

    app.include_router(crear_router(svc))
    return app
