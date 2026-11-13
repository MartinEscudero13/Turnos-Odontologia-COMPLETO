"""Router del webhook de Mercado Pago — C-11 §6 (D7/D8, RN-SE-03).

Una sola ruta, sin tenant en el path (MP notifica a una URL por aplicación) y sin
sesión: la autenticidad es la firma HMAC del header `x-signature`.

- `200`: notificación autenticada procesada (aunque no mueva plata: el
  `resultado` dice por qué).
- `401`: firma ausente o inválida. No se persiste ni se consulta la pasarela.
- `503`: no hay `MP_WEBHOOK_SECRET` (fail-closed) o MP no responde al
  re-consultar el pago; MP reintenta.
- `500`: el pago no resuelve a una seña del tenant. No se persiste; queda el log
  estructurado para que operación lo vea y MP reintente (nunca se descarta plata).

El `data.id` se toma del query string (`?data.id=…`, como manda MP) con caída al
cuerpo (`{"data": {"id": …}}`). El cuerpo **no** aporta estado, monto ni
metadata: eso siempre sale de la re-consulta a la pasarela.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from app.schemas.senas import ErrorSenaOut, WebhookSalida
from app.senas.webhook import ResultadoWebhook, ServicioSenasWebhook
from app.turnos.servicio import TurnoError


def _data_id(body: dict[str, Any]) -> str | None:
    data = body.get("data")
    if isinstance(data, dict):
        valor = data.get("id")
        if isinstance(valor, (str, int)):
            return str(valor)
    return None


def _tipo(request: Request, body: dict[str, Any]) -> str | None:
    for fuente in (request.query_params.get("type"), body.get("type")):
        if isinstance(fuente, str):
            return fuente
    for fuente in (request.query_params.get("topic"), body.get("topic")):
        if isinstance(fuente, str):
            return fuente
    return None


def _salida(resultado: ResultadoWebhook) -> WebhookSalida:
    return WebhookSalida(
        resultado=resultado.resultado,
        mp_payment_id=resultado.mp_payment_id,
        sena_id=resultado.sena_id,
        estado_pago=resultado.estado_pago,
    )


def crear_router_webhook(svc: ServicioSenasWebhook) -> APIRouter:
    """Router del webhook, inyectando el servicio (testeable sin DB)."""
    r = APIRouter()

    @r.post("/api/webhooks/mercadopago", response_model=WebhookSalida)
    async def webhook(request: Request) -> JSONResponse:
        try:
            body: dict[str, Any] = await request.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        data_id = request.query_params.get("data.id") or request.query_params.get(
            "data_id"
        )
        resultado = svc.procesar(
            x_signature=request.headers.get("x-signature"),
            request_id=request.headers.get("x-request-id"),
            data_id=data_id or _data_id(body),
            tipo=_tipo(request, body),
        )
        return JSONResponse(
            status_code=200, content=_salida(resultado).model_dump(mode="json")
        )

    return r


def crear_app_webhooks(svc: ServicioSenasWebhook) -> FastAPI:
    """App mínima del webhook (patrón `crear_app` de C-05…C-10)."""
    app = FastAPI(title="Turnos-Odontologia C-11 webhooks")

    @app.exception_handler(TurnoError)
    async def _turno_error(_request: Request, exc: TurnoError) -> JSONResponse:
        codigo = getattr(exc, "codigo_dominio", None)
        return JSONResponse(
            status_code=exc.codigo,
            content=ErrorSenaOut(detalle=exc.mensaje, codigo=codigo).model_dump(
                mode="json"
            ),
        )

    app.include_router(crear_router_webhook(svc))
    return app
