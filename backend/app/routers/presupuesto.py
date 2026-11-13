"""Router FastAPI de presupuesto — C-09 (§7, backend-only, inyectable).

Mapea el dominio a HTTP: `201` al crear el presupuesto o una línea, `200` al
leer/emitir/aceptar, `404` cross-tenant, `403` RBAC (`ODONTOLOGO` no acepta),
`409` conflicto de estado o línea ya decidida, `422` payload inválido y `401`
cuando la petición trae identidad de paciente (v1 no tiene sesión de paciente).
No existe `PATCH` ni `DELETE` de línea (D8.1).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.presupuesto.puertos import Aceptacion, Linea, Presupuesto
from app.presupuesto.servicio import (
    DecisionRegistrada,
    PresupuestoConsultado,
    ServicioPresupuesto,
)
from app.routers.turnos import actor_desde_headers
from app.schemas.presupuesto import (
    AceptacionIn,
    AceptacionOut,
    DecisionOut,
    EmisionIn,
    LineaDecisionOut,
    LineaIn,
    LineaOut,
    PresupuestoDetalleOut,
    PresupuestoIn,
    PresupuestoOut,
)
from app.schemas.turno import ErrorOut
from app.turnos.servicio import Actor, TurnoError


def _presupuesto_out(p: Presupuesto) -> PresupuestoOut:
    return PresupuestoOut(
        id=p.id,
        paciente_id=p.paciente_id,
        estado=p.estado,
        vence_en=p.vence_en,
        creado_en=p.creado_en,
        actualizado_en=p.actualizado_en,
    )


def _linea_out(linea: Linea) -> LineaOut:
    return LineaOut(
        id=linea.id,
        presupuesto_id=linea.presupuesto_id,
        hallazgo_id=linea.hallazgo_id,
        pieza_fdi=linea.pieza_fdi,
        prestacion_id=linea.prestacion_id,
        monto=linea.monto,
        cobertura_os=linea.cobertura_os,
        a_cargo_paciente=linea.a_cargo_paciente,
        origen_cobertura=linea.origen_cobertura,
        validada_en_vivo=linea.validada_en_vivo,
        creado_en=linea.creado_en,
    )


def _aceptacion_out(a: Aceptacion) -> AceptacionOut:
    return AceptacionOut(
        id=a.id,
        linea_id=a.linea_id,
        acepta=a.acepta,
        fecha=a.fecha,
        canal=a.canal,
        medio=a.medio,
    )


def _detalle_out(c: PresupuestoConsultado) -> PresupuestoDetalleOut:
    return PresupuestoDetalleOut(
        id=c.presupuesto.id,
        paciente_id=c.presupuesto.paciente_id,
        estado=c.estado_reportado,
        vence_en=c.presupuesto.vence_en,
        creado_en=c.presupuesto.creado_en,
        actualizado_en=c.presupuesto.actualizado_en,
        lineas=[
            LineaDecisionOut(
                linea=_linea_out(item.linea),
                aceptacion=(
                    _aceptacion_out(item.aceptacion)
                    if item.aceptacion is not None
                    else None
                ),
            )
            for item in c.lineas
        ],
    )


def _decision_out(d: DecisionRegistrada, actor: Actor) -> DecisionOut:
    return DecisionOut(
        presupuesto_id=d.presupuesto.id,
        estado=d.presupuesto.estado,
        actor_id=actor.user_id,
        linea_id=d.aceptacion.linea_id,
        acepta=d.aceptacion.acepta,
        fecha=d.aceptacion.fecha,
        canal=d.aceptacion.canal,
        medio=d.aceptacion.medio,
    )


def _error_body(exc: TurnoError) -> dict[str, object]:
    return ErrorOut(detalle=exc.mensaje).model_dump(mode="json")


def crear_router(svc: ServicioPresupuesto) -> APIRouter:
    """Router de presupuesto inyectando el servicio (testeable sin DB)."""
    r = APIRouter()

    @r.post("/api/presupuestos", status_code=201, response_model=PresupuestoOut)
    def crear(body: PresupuestoIn, actor: Actor = Depends(actor_desde_headers)) -> PresupuestoOut:
        return _presupuesto_out(svc.crear(actor, paciente_id=body.paciente_id))

    @r.get("/api/presupuestos", response_model=list[PresupuestoDetalleOut])
    def listar(
        paciente_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> list[PresupuestoDetalleOut]:
        return [
            _detalle_out(c)
            for c in svc.listar(actor, paciente_id=paciente_id)
        ]

    @r.get("/api/presupuestos/{presupuesto_id}", response_model=PresupuestoDetalleOut)
    def obtener(
        presupuesto_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> PresupuestoDetalleOut:
        return _detalle_out(svc.obtener(actor, presupuesto_id=presupuesto_id))

    @r.post(
        "/api/presupuestos/{presupuesto_id}/lineas",
        status_code=201,
        response_model=LineaOut,
    )
    def agregar_linea(
        presupuesto_id: str,
        body: LineaIn,
        actor: Actor = Depends(actor_desde_headers),
    ) -> LineaOut:
        return _linea_out(
            svc.agregar_linea(
                actor,
                presupuesto_id=presupuesto_id,
                prestacion_id=body.prestacion_id,
                monto=body.monto,
                pieza_fdi=body.pieza_fdi,
                hallazgo_id=body.hallazgo_id,
            )
        )

    @r.post("/api/presupuestos/{presupuesto_id}/emitir", response_model=PresupuestoOut)
    def emitir(
        presupuesto_id: str,
        body: EmisionIn,
        actor: Actor = Depends(actor_desde_headers),
    ) -> PresupuestoOut:
        return _presupuesto_out(
            svc.emitir(actor, presupuesto_id=presupuesto_id, vence_en=body.vence_en)
        )

    @r.post(
        "/api/presupuestos/{presupuesto_id}/aceptar", response_model=DecisionOut
    )
    def aceptar(
        presupuesto_id: str,
        body: AceptacionIn,
        actor: Actor = Depends(actor_desde_headers),
    ) -> DecisionOut:
        return _decision_out(
            svc.registrar_aceptacion(
                actor,
                presupuesto_id=presupuesto_id,
                linea_id=body.linea_id,
                acepta=body.acepta,
                canal=body.canal,
                medio=body.medio,
            ),
            actor,
        )

    return r


def crear_app(svc: ServicioPresupuesto) -> FastAPI:
    """App mínima del change (patrón `crear_app` de C-05/C-06/C-07/C-08)."""
    app = FastAPI(title="Turnos-Odontologia C-09 presupuesto")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc))

    app.include_router(crear_router(svc))
    return app
