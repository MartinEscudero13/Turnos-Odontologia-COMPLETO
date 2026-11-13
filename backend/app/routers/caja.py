"""Router FastAPI de caja — C-10 §2 (backend-only, inyectable).

Superficie mínima de esta capa: alta (`201`) y lectura por id (`200`/`404`).
No existe `PATCH` ni `DELETE` de movimientos (D2/RN-CJ-03): la anulación tiene
su propio endpoint en §3. El resto de rutas (consulta diaria, cierre,
pendientes y reportes) llega en §6–§9.

El actor llega por headers (`actor_desde_headers`, igual que C-05/C-09); el JWT
real de C-03 reemplaza la dependencia sin cambiar el contrato.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.caja.puertos import Movimiento
from app.caja.servicio import ServicioCaja
from app.routers.turnos import actor_desde_headers
from app.schemas.caja import MovimientoEntrada, MovimientoSalida
from app.schemas.turno import ErrorOut
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


def _error_body(exc: TurnoError) -> dict[str, object]:
    return ErrorOut(detalle=exc.mensaje).model_dump(mode="json")


def crear_router(svc: ServicioCaja) -> APIRouter:
    """Router de caja inyectando el servicio (testeable sin DB)."""
    r = APIRouter()

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

    @r.get("/api/caja/movimientos/{movimiento_id}", response_model=MovimientoSalida)
    def obtener(
        movimiento_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> MovimientoSalida:
        return _movimiento_out(svc.obtener_movimiento(actor, movimiento_id=movimiento_id))

    return r


def crear_app(svc: ServicioCaja) -> FastAPI:
    """App mínima del change (patrón `crear_app` de C-05/C-06/C-07/C-08/C-09)."""
    app = FastAPI(title="Turnos-Odontologia C-10 caja")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc))

    app.include_router(crear_router(svc))
    return app
