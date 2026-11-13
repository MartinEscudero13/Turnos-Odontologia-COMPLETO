"""Router interno de señas — C-11 §11 (D13, C11-OQ-10).

Superficie de lectura y decisión para los roles internos, separada del borde
público (`senas.py`, §5) y del webhook (`webhooks_mp.py`, §6):

- `GET  /api/senas?desde=&hasta=` — la seña visible en la agenda; filtra por
  **`turno.inicio`** en `[desde, hasta)` y, sin parámetros, usa el día operativo
  vigente. Nunca cambia el payload de `GET /api/turnos` (C-05 no se toca).
- `GET  /api/senas/{id}` — detalle; una seña de otro tenant responde `404`.
- `POST /api/senas/{id}/aplicar` — `RECEPCION`/`ADMIN`; `concepto=CANCELACION_TARDIA`
  exige `ADMIN` (el caso de uso lo verifica, F-29).
- `POST /api/senas/{id}/devolver` — sólo `ADMIN`, con motivo no vacío.

Códigos: `200`; `401` identidad de paciente (nunca `403`); `403` rol interno sin
permiso; `404` seña inexistente **o de otro tenant** (idéntico, sin filtrar
existencia); `409` conflicto de estado (`SENA_YA_APLICADA`, `CIERRE_CERRADO`,
`ESTADO_INVALIDO`, `PRESUPUESTO_CON_SENA`, `SENA_NO_DEVOLUBLE`); `422` payload
inválido o motivo vacío. **No existe** exportación de señas en C-11: nada de
`/api/senas/export` (vive en C-15, si alguna vez se pide).

El actor llega por headers (`actor_desde_headers`, igual que C-05…C-10) y el
`tenant_id` que usa el caso de uso es **siempre** el del actor, nunca un
parámetro del request. El JWT real de C-03 reemplaza la dependencia sin cambiar
el contrato.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers.turnos import actor_desde_headers
from app.schemas.senas import (
    AplicarEntrada,
    DevolverEntrada,
    ErrorSenaOut,
    ObligacionOut,
    PoliticaOut,
    SenaInternaOut,
    TurnoSenaOut,
)
from app.senas.aplicacion import ServicioSenasAplicacion
from app.senas.consulta import SenaInterna, ServicioSenasConsulta
from app.turnos.servicio import Actor, TurnoError


def _turno_out(vista: SenaInterna) -> TurnoSenaOut | None:
    sena = vista.sena
    if sena.turno_inicio is None:
        return None
    return TurnoSenaOut(
        inicio=sena.turno_inicio,
        fin=sena.turno_fin or sena.turno_inicio,
        prestacion=sena.turno_prestacion or "",
    )


def _politica_out(vista: SenaInterna) -> PoliticaOut:
    return PoliticaOut(
        anticipacion_cancelacion_h=vista.politica.anticipacion_cancelacion_h,
        reembolsable=vista.politica.reembolsable,
        hay_pago_acreditado=vista.politica.hay_pago_acreditado,
    )


def _interna_out(vista: SenaInterna) -> SenaInternaOut:
    sena = vista.sena
    return SenaInternaOut(
        sena_id=sena.id,
        turno_id=sena.turno_id,
        turno=_turno_out(vista),
        estado=sena.estado,
        monto_centavos=sena.monto_centavos,
        expira_at=sena.expira_at,
        preferencia_estado=sena.preferencia_estado,
        politica=_politica_out(vista),
        obligaciones=[
            ObligacionOut(
                origen=obligacion.origen,
                tipo=obligacion.tipo,
                monto_centavos=obligacion.monto_centavos,
                motivo=obligacion.motivo,
                mp_payment_id=obligacion.mp_payment_id,
            )
            for obligacion in vista.obligaciones
        ],
        acreditada_en=sena.acreditada_en,
        aplicada_en=sena.aplicada_en,
        liberada_en=sena.liberada_en,
        devuelta_en=sena.devuelta_en,
        motivo_liberacion=sena.motivo_liberacion,
        motivo_devolucion=sena.motivo_devolucion,
        concepto_aplicacion=sena.concepto_aplicacion,
        devuelta_por=sena.devuelta_por,
        movimiento_caja_id=sena.movimiento_caja_id,
        creado_en=sena.creado_en,
    )


def _error_body(exc: TurnoError) -> dict[str, object]:
    codigo = getattr(exc, "codigo_dominio", None)
    return ErrorSenaOut(detalle=exc.mensaje, codigo=codigo).model_dump(mode="json")


def crear_router_interno(
    consulta: ServicioSenasConsulta,
    aplicacion: ServicioSenasAplicacion,
) -> APIRouter:
    """Router interno inyectando los casos de uso (testeable sin DB)."""
    r = APIRouter()

    @r.get("/api/senas", response_model=list[SenaInternaOut])
    def listar(
        desde: date | None = None,
        hasta: date | None = None,
        actor: Actor = Depends(actor_desde_headers),
    ) -> list[SenaInternaOut]:
        return [
            _interna_out(vista)
            for vista in consulta.listar(actor=actor, desde=desde, hasta=hasta)
        ]

    @r.get("/api/senas/{sena_id}", response_model=SenaInternaOut)
    def obtener(
        sena_id: str, actor: Actor = Depends(actor_desde_headers)
    ) -> SenaInternaOut:
        return _interna_out(consulta.obtener(actor=actor, sena_id=sena_id))

    @r.post("/api/senas/{sena_id}/aplicar", response_model=SenaInternaOut)
    def aplicar(
        sena_id: str,
        body: AplicarEntrada | None = None,
        actor: Actor = Depends(actor_desde_headers),
    ) -> SenaInternaOut:
        concepto = body.concepto if body is not None else "TRATAMIENTO"
        aplicada = aplicacion.aplicar(
            tenant_id=actor.tenant_id,
            sena_id=sena_id,
            actor=actor,
            concepto=concepto,
        )
        return _interna_out(consulta.obtener(actor=actor, sena_id=aplicada.id))

    @r.post("/api/senas/{sena_id}/devolver", response_model=SenaInternaOut)
    def devolver(
        sena_id: str,
        body: DevolverEntrada,
        actor: Actor = Depends(actor_desde_headers),
    ) -> SenaInternaOut:
        devuelta = aplicacion.devolver(
            tenant_id=actor.tenant_id,
            sena_id=sena_id,
            actor=actor,
            motivo=body.motivo,
        )
        return _interna_out(consulta.obtener(actor=actor, sena_id=devuelta.id))

    return r


def crear_app_senas_internas(
    consulta: ServicioSenasConsulta,
    aplicacion: ServicioSenasAplicacion,
) -> FastAPI:
    """App mínima del borde interno de la seña (patrón `crear_app` de C-05…C-10)."""
    app = FastAPI(title="Turnos-Odontologia C-11 senas internas")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc))

    @app.exception_handler(RequestValidationError)
    async def _validacion(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorSenaOut(
                detalle="Revisá los datos enviados e intentá nuevamente."
            ).model_dump(mode="json"),
        )

    app.include_router(crear_router_interno(consulta, aplicacion))
    return app


__all__ = [
    "crear_app_senas_internas",
    "crear_router_interno",
]
