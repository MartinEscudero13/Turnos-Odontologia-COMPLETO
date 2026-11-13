"""Router público de la seña — C-11 §5 (D13, F-30).

Dos rutas, sin sesión ni `verificacion_id`:

- `GET  /api/publico/{token_tenant}/senas/{token}` → `200` / `404` uniforme / `429`.
- `POST /api/publico/{token_tenant}/senas/{token}/preferencia` → `200` (ya
  existe), `201` (creada), `202` (backoff con `reintentar_en`), `404`, `409
  SENA_VENCIDA`, `429`.

No existe un endpoint de pago server-side (`.../pagar` es `404`): el paciente
paga en el checkout de Mercado Pago con el `init_point`. Los errores de dominio
salen por `TurnoError` con su `codigo` HTTP y, cuando lo declaran, el
`codigo_dominio` observable. El token nunca se loguea.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.reservas.servicio import DemasiadasSolicitudes
from app.schemas.senas import (
    ErrorSenaOut,
    PoliticaOut,
    SenaPreferenciaOut,
    SenaPublicaOut,
    TurnoSenaOut,
)
from app.senas.servicio import ResultadoPreferencia, SenaPublica, ServicioSenas
from app.turnos.servicio import TurnoError

_CODIGO_POR_RESULTADO = {"EXISTENTE": 200, "CREADA": 201, "BACKOFF": 202}


def _ip_del_request(request: Request) -> str:
    client = request.client
    return client.host if client is not None else "desconocida"


def _politica_out(vista: SenaPublica) -> PoliticaOut:
    return PoliticaOut(
        anticipacion_cancelacion_h=vista.politica.anticipacion_cancelacion_h,
        reembolsable=vista.politica.reembolsable,
        hay_pago_acreditado=vista.politica.hay_pago_acreditado,
    )


def _turno_out(vista: SenaPublica) -> TurnoSenaOut:
    return TurnoSenaOut(
        inicio=vista.turno.inicio,
        fin=vista.turno.fin,
        prestacion=vista.turno.prestacion,
    )


def _publica_out(vista: SenaPublica) -> SenaPublicaOut:
    return SenaPublicaOut(
        sena_id=vista.sena_id,
        estado=vista.estado,
        monto_centavos=vista.monto_centavos,
        expira_at=vista.expira_at,
        preferencia_estado=vista.preferencia_estado,
        init_point=vista.init_point,
        turno=_turno_out(vista),
        politica=_politica_out(vista),
    )


def _preferencia_out(resultado: ResultadoPreferencia) -> SenaPreferenciaOut:
    base = _publica_out(resultado.vista)
    return SenaPreferenciaOut(
        **base.model_dump(),
        reintentar_en=resultado.reintentar_en,
    )


def _error_body(exc: TurnoError) -> dict[str, object]:
    codigo = getattr(exc, "codigo_dominio", None)
    return ErrorSenaOut(detalle=exc.mensaje, codigo=codigo).model_dump(mode="json")


def crear_router_publico(svc: ServicioSenas) -> APIRouter:
    """Router público de la seña, inyectando el servicio (testeable sin DB)."""
    r = APIRouter()

    @r.get(
        "/api/publico/{token_tenant}/senas/{token}",
        response_model=SenaPublicaOut,
    )
    def leer(token_tenant: str, token: str, request: Request) -> SenaPublicaOut:
        vista = svc.leer_publica(
            token_tenant=token_tenant,
            token=token,
            ip=_ip_del_request(request),
        )
        return _publica_out(vista)

    @r.post(
        "/api/publico/{token_tenant}/senas/{token}/preferencia",
        response_model=SenaPreferenciaOut,
    )
    def preferencia(
        token_tenant: str, token: str, request: Request
    ) -> JSONResponse:
        resultado = svc.pedir_preferencia(
            token_tenant=token_tenant,
            token=token,
            ip=_ip_del_request(request),
        )
        return JSONResponse(
            status_code=_CODIGO_POR_RESULTADO[resultado.resultado],
            content=_preferencia_out(resultado).model_dump(mode="json"),
        )

    return r


def crear_app_senas(svc: ServicioSenas) -> FastAPI:
    """App mínima del borde público de la seña (patrón `crear_app` de C-05…C-10)."""
    app = FastAPI(title="Turnos-Odontologia C-11 senas")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        headers = None
        if isinstance(exc, DemasiadasSolicitudes):
            headers = {"Retry-After": str(exc.retry_after_s)}
        return JSONResponse(status_code=exc.codigo, content=_error_body(exc), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorSenaOut(
                detalle="Revisá los datos enviados e intentá nuevamente."
            ).model_dump(mode="json"),
        )

    app.include_router(crear_router_publico(svc))
    return app
