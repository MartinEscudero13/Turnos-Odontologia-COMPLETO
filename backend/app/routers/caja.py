"""Router FastAPI de caja — C-10 §7–§9 (backend-only, inyectable).

Superficie completa de caja:

- alta (`201`), consulta diaria (`GET /api/caja/movimientos?fecha=`) y detalle
  por id (`200`/`404`); la anulación tiene su propio endpoint (`200`) porque no
  existe `PATCH` ni `DELETE` de movimientos (D2/RN-CJ-03);
- cobros pendientes (lista y cobro, `201`), cierre del día (`201`) y su consulta
  (`200`/`404`), estado del día, listado de cierres por rango y reportes base;
- **no** existe reapertura de cierre, exportación de caja ni KPIs de agenda
  (C10-OQ-1, D10/D12): sus rutas responden `404`/`405`.

Mapeo de errores: `404` no encontrado/cross-tenant, `403` RBAC, `409` conflicto
de estado, `422` validación y `503` cuando C-09 traduce un fallo del puerto. El
body de error de caja agrega `codigo` con el código de dominio observable
(`CIERRE_CERRADO`, `ANULADO`, …) cuando la excepción lo declara.

El actor llega por headers (`actor_desde_headers`, igual que C-05/C-09); el JWT
real de C-03 reemplaza la dependencia sin cambiar el contrato.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.caja.puertos import Ajuste, Cierre, CobroPendiente, MedioPago, Movimiento
from app.caja.servicio import ConsultaDia, ServicioCaja
from app.routers.turnos import actor_desde_headers
from app.schemas.caja import (
    AjusteSalida,
    AnulacionEntrada,
    CierreEntrada,
    CierreSalida,
    CobroEntrada,
    CobroSalida,
    ConsultaDiaSalida,
    DiaReporteSalida,
    ErrorCajaOut,
    EstadoDiaSalida,
    MovimientoEntrada,
    MovimientoSalida,
    PendienteSalida,
    ReporteSalida,
    TotalesCierreSalida,
    TotalesVigentesSalida,
)
from app.turnos.servicio import Actor, TurnoError


def _movimiento_out(movimiento: Movimiento) -> MovimientoSalida:
    return MovimientoSalida(
        id=movimiento.id,
        fecha=movimiento.fecha,
        medio=movimiento.medio,
        monto=movimiento.monto,
        tipo=movimiento.tipo,
        tramo=movimiento.tramo,
        turno_id=movimiento.turno_id,
        usuario_id=movimiento.usuario_id,
        anulado=movimiento.anulado,
        motivo_anulacion=movimiento.motivo_anulacion,
        anulado_por=movimiento.anulado_por,
        anulado_en=movimiento.anulado_en,
        origen=movimiento.origen,
        creado_en=movimiento.creado_en,
    )


def _pendiente_out(pendiente: CobroPendiente) -> PendienteSalida:
    return PendienteSalida(
        id=pendiente.id,
        fecha=pendiente.fecha,
        presupuesto_id=pendiente.presupuesto_id,
        linea_id=pendiente.linea_id,
        monto_centavos=pendiente.monto_centavos,
        actor_id=pendiente.actor_id,
        turno_id=pendiente.turno_id,
        creado_en=pendiente.creado_en,
        resuelto_en=pendiente.resuelto_en,
        movimiento_id=pendiente.movimiento_id,
    )


def _ajuste_out(ajuste: Ajuste) -> AjusteSalida:
    return AjusteSalida(
        id=ajuste.id,
        cierre_id=ajuste.cierre_id,
        tipo=ajuste.tipo,
        movimiento_original_id=ajuste.movimiento_original_id,
        cobro_pendiente_id=ajuste.cobro_pendiente_id,
        monto=ajuste.monto,
        medio=ajuste.medio,
        motivo=ajuste.motivo,
        actor_id=ajuste.actor_id,
        compensatorio_id=ajuste.compensatorio_id,
        creado_en=ajuste.creado_en,
    )


def _totales_vigentes_out(totales: dict[MedioPago, int]) -> TotalesVigentesSalida:
    return TotalesVigentesSalida(
        efectivo=totales["EFECTIVO"],
        transferencia=totales["TRANSFERENCIA"],
        mp=totales["MP"],
        os=totales["OS"],
    )


def _totales_cierre_out(cierre: Cierre) -> TotalesCierreSalida:
    return TotalesCierreSalida(
        total_efectivo=cierre.total_efectivo,
        total_transferencia=cierre.total_transferencia,
        total_mp=cierre.total_mp,
        total_os_cobrado=cierre.total_os_cobrado,
        total_os=cierre.total_os,
    )


def _cierre_out(cierre: Cierre) -> CierreSalida:
    return CierreSalida(
        id=cierre.id,
        fecha=cierre.fecha,
        totales=_totales_cierre_out(cierre),
        efectivo_contado=cierre.efectivo_contado,
        diferencia=cierre.diferencia,
        responsable_id=cierre.responsable_id,
        motivo_diferencia=cierre.motivo_diferencia,
        observacion=cierre.observacion,
        cerrado_at=cierre.cerrado_at,
    )


def _consulta_out(consulta: ConsultaDia) -> ConsultaDiaSalida:
    return ConsultaDiaSalida(
        fecha=consulta.fecha,
        estado=consulta.estado,
        movimientos=[_movimiento_out(m) for m in consulta.movimientos],
        pendientes=[_pendiente_out(p) for p in consulta.pendientes],
        ajustes=[_ajuste_out(a) for a in consulta.ajustes],
        totales_vigentes=_totales_vigentes_out(consulta.totales_vigentes),
        totales_cierre=(
            None
            if consulta.totales_cierre is None
            else _totales_cierre_out(consulta.totales_cierre)
        ),
        difieren_del_cierre=consulta.difieren_del_cierre,
    )


def _error_body(exc: TurnoError) -> dict[str, object]:
    codigo: str | None = getattr(exc, "codigo_dominio", None)
    return ErrorCajaOut(detalle=exc.mensaje, codigo=codigo).model_dump(mode="json")


def crear_router(svc: ServicioCaja) -> APIRouter:
    """Router de caja inyectando el servicio (testeable sin DB)."""
    r = APIRouter()

    # -- movimientos ---------------------------------------------------
    @r.post("/api/caja/movimientos", status_code=201, response_model=MovimientoSalida)
    def registrar(
        body: MovimientoEntrada, actor: Actor = Depends(actor_desde_headers)
    ) -> MovimientoSalida:
        return _movimiento_out(
            svc.registrar_movimiento(
                actor,
                monto=body.monto,
                medio=body.medio,
                tipo=body.tipo,
                fecha=body.fecha,
                turno_id=body.turno_id,
            )
        )

    @r.get("/api/caja/movimientos", response_model=ConsultaDiaSalida)
    def consultar_dia(
        fecha: date, actor: Actor = Depends(actor_desde_headers)
    ) -> ConsultaDiaSalida:
        return _consulta_out(svc.consultar_dia(actor, fecha=fecha))

    @r.get("/api/caja/movimientos/{movimiento_id}", response_model=MovimientoSalida)
    def obtener(
        movimiento_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> MovimientoSalida:
        return _movimiento_out(svc.obtener_movimiento(actor, movimiento_id=movimiento_id))

    @r.post(
        "/api/caja/movimientos/{movimiento_id}/anular",
        response_model=MovimientoSalida,
    )
    def anular(
        movimiento_id: str,
        body: AnulacionEntrada,
        actor: Actor = Depends(actor_desde_headers),
    ) -> MovimientoSalida:
        return _movimiento_out(
            svc.anular_movimiento(actor, movimiento_id=movimiento_id, motivo=body.motivo)
        )

    # -- cobros pendientes ---------------------------------------------
    @r.get("/api/caja/pendientes", response_model=list[PendienteSalida])
    def listar_pendientes(
        fecha: date | None = None, actor: Actor = Depends(actor_desde_headers)
    ) -> list[PendienteSalida]:
        return [
            _pendiente_out(p)
            for p in svc.listar_pendientes(actor, fecha=fecha)
        ]

    @r.post(
        "/api/caja/pendientes/{pendiente_id}/cobrar",
        status_code=201,
        response_model=CobroSalida,
    )
    def cobrar(
        pendiente_id: str,
        body: CobroEntrada,
        actor: Actor = Depends(actor_desde_headers),
    ) -> CobroSalida:
        resultado = svc.cobrar_pendiente(actor, pendiente_id=pendiente_id, medio=body.medio)
        return CobroSalida(
            pendiente=_pendiente_out(resultado.pendiente),
            movimiento=_movimiento_out(resultado.movimiento),
            ajuste=(
                None if resultado.ajuste is None else _ajuste_out(resultado.ajuste)
            ),
        )

    # -- cierre --------------------------------------------------------
    @r.post("/api/caja/cierre", status_code=201, response_model=CierreSalida)
    def cerrar(
        body: CierreEntrada, actor: Actor = Depends(actor_desde_headers)
    ) -> CierreSalida:
        return _cierre_out(
            svc.cerrar_dia(
                actor,
                fecha=body.fecha,
                efectivo_contado=body.efectivo_contado,
                responsable_id=body.responsable_id,
                motivo_diferencia=body.motivo_diferencia,
                observacion=body.observacion,
            )
        )

    @r.get("/api/caja/cierre", response_model=CierreSalida)
    def obtener_cierre(
        fecha: date, actor: Actor = Depends(actor_desde_headers)
    ) -> CierreSalida:
        return _cierre_out(svc.obtener_cierre(actor, fecha=fecha))

    @r.get("/api/caja/cierre/estado", response_model=EstadoDiaSalida)
    def estado_dia(
        fecha: date, actor: Actor = Depends(actor_desde_headers)
    ) -> EstadoDiaSalida:
        estado = svc.estado_dia(actor, fecha=fecha)
        return EstadoDiaSalida(
            fecha=estado.fecha,
            estado=estado.estado,
            totales=_totales_vigentes_out(estado.totales),
            cierre=None if estado.cierre is None else _cierre_out(estado.cierre),
        )

    @r.get("/api/caja/cierres", response_model=list[CierreSalida])
    def listar_cierres(
        desde: date, hasta: date, actor: Actor = Depends(actor_desde_headers)
    ) -> list[CierreSalida]:
        return [
            _cierre_out(cierre)
            for cierre in svc.listar_cierres(actor, desde=desde, hasta=hasta)
        ]

    # -- reportes base (sin KPIs de agenda: C-15) ----------------------
    @r.get("/api/caja/reportes", response_model=ReporteSalida)
    def reportes(
        desde: date, hasta: date, actor: Actor = Depends(actor_desde_headers)
    ) -> ReporteSalida:
        reporte = svc.reporte_caja(actor, desde=desde, hasta=hasta)
        return ReporteSalida(
            desde=reporte.desde,
            hasta=reporte.hasta,
            fuente=reporte.fuente,
            totales=_totales_vigentes_out(reporte.totales),
            por_dia=[
                DiaReporteSalida(
                    fecha=dia.fecha,
                    efectivo=dia.totales["EFECTIVO"],
                    transferencia=dia.totales["TRANSFERENCIA"],
                    mp=dia.totales["MP"],
                    os=dia.totales["OS"],
                    movimientos=dia.movimientos,
                    anulados=dia.anulados,
                )
                for dia in reporte.por_dia
            ],
            cierres=reporte.cierres,
            movimientos_anulados=reporte.movimientos_anulados,
        )

    return r


def crear_app(svc: ServicioCaja) -> FastAPI:
    """App mínima del change (patrón `crear_app` de C-05/C-06/C-07/C-08/C-09)."""
    app = FastAPI(title="Turnos-Odontologia C-10 caja")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc))

    app.include_router(crear_router(svc))
    return app
