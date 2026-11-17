"""Router FastAPI de WhatsApp — C-13."""
from __future__ import annotations

import json
import os
import urllib.parse

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse

from app.routers.turnos import actor_desde_headers
from app.schemas.whatsapp import (
    EnvioOut,
    MensajeOut,
    RecallIn,
    WebhookOut,
)
from app.turnos.servicio import Actor, TurnoError
from app.whatsapp.meta import eventos_meta, firma_meta_valida
from app.whatsapp.puertos import (
    FirmaInvalida,
    Mensaje,
    WebhookNoConfigurado,
)
from app.whatsapp.servicio import ResultadoEnvio, ResultadoWebhook, ServicioWhatsApp
from app.whatsapp.twilio import firma_valida

__all__ = ["crear_router"]


def _mensaje_out(mensaje: Mensaje) -> MensajeOut:
    return MensajeOut(
        id=mensaje.id,
        paciente_id=mensaje.paciente_id,
        turno_id=mensaje.turno_id,
        plantilla=mensaje.plantilla,
        canal=mensaje.canal,
        estado=mensaje.estado,
        provider_message_id=mensaje.provider_message_id,
        intentos=mensaje.intentos,
        proximo_intento=mensaje.proximo_intento,
        cuerpo=mensaje.cuerpo,
        respuesta=mensaje.respuesta,
        creado_en=mensaje.creado_en,
    )


def _envio_out(resultado: ResultadoEnvio) -> EnvioOut:
    return EnvioOut(
        enviados=resultado.enviados,
        fallidos=resultado.fallidos,
        mensajes=[_mensaje_out(mensaje) for mensaje in resultado.mensajes],
    )


def _webhook_out(resultado: ResultadoWebhook) -> WebhookOut:
    return WebhookOut(
        estado=resultado.estado,
        respuesta=resultado.respuesta,
        turno_id=resultado.turno_id,
        link_confirmacion=resultado.link_confirmacion,
    )


def crear_router(svc: ServicioWhatsApp) -> APIRouter:
    r = APIRouter()

    @r.post("/api/whatsapp/recordatorios/programar", response_model=EnvioOut)
    def programar(actor: Actor = Depends(actor_desde_headers)) -> EnvioOut:
        return _envio_out(svc.programar_recordatorios(actor))

    @r.post("/api/whatsapp/cola/procesar", response_model=EnvioOut)
    def procesar(actor: Actor = Depends(actor_desde_headers)) -> EnvioOut:
        return _envio_out(svc.procesar_pendientes(actor))

    @r.get("/api/whatsapp/mensajes", response_model=list[MensajeOut])
    def listar(
        turno_id: str | None = Query(default=None),
        actor: Actor = Depends(actor_desde_headers),
    ) -> list[MensajeOut]:
        return [
            _mensaje_out(mensaje)
            for mensaje in svc.listar_mensajes(actor, turno_id=turno_id)
        ]

    @r.post("/api/whatsapp/recall", response_model=MensajeOut)
    def recall(body: RecallIn, actor: Actor = Depends(actor_desde_headers)) -> MensajeOut:
        return _mensaje_out(
            svc.crear_recall(
                actor,
                paciente_id=body.paciente_id,
                motivo=body.motivo,
                fecha_objetivo=body.fecha_objetivo,
            )
        )

    @r.post("/api/webhooks/whatsapp", response_model=WebhookOut)
    async def webhook(request: Request, tenant: str | None = Query(default=None)) -> WebhookOut:
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
        if not auth_token:
            raise WebhookNoConfigurado("el webhook de WhatsApp no está configurado")
        raw = (await request.body()).decode("utf-8")
        params = {
            clave: valores[0]
            for clave, valores in urllib.parse.parse_qs(raw, keep_blank_values=True).items()
        }
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        url = f"{scheme}://{host}{request.url.path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
        firma = request.headers.get("x-twilio-signature")
        if not firma_valida(
            url=url, params=params, auth_token=auth_token, signature=firma
        ):
            raise FirmaInvalida("firma de Twilio inválida")
        return _webhook_out(
            svc.recibir_webhook(params, tenant_id=tenant, origen="twilio")
        )

    # -- Meta WhatsApp Cloud API ---------------------------------------
    @r.get("/api/webhooks/whatsapp/meta")
    async def verificar_meta(request: Request) -> PlainTextResponse:
        params = request.query_params
        verify_token = os.environ.get("META_VERIFY_TOKEN", "").strip()
        if not verify_token:
            raise WebhookNoConfigurado("META_VERIFY_TOKEN no está configurado")
        if params.get("hub.mode") != "subscribe":
            raise FirmaInvalida("modo de verificación inválido")
        if params.get("hub.verify_token") != verify_token:
            raise FirmaInvalida("token de verificación inválido")
        return PlainTextResponse(params.get("hub.challenge", ""))

    @r.post("/api/webhooks/whatsapp/meta")
    async def webhook_meta(
        request: Request, tenant: str | None = Query(default=None)
    ) -> dict[str, object]:
        app_secret = os.environ.get("META_APP_SECRET", "").strip()
        if not app_secret:
            raise WebhookNoConfigurado("META_APP_SECRET no está configurado")
        raw = await request.body()
        if not firma_meta_valida(
            cuerpo=raw,
            app_secret=app_secret,
            firma=request.headers.get("x-hub-signature-256"),
        ):
            raise FirmaInvalida("firma de Meta inválida")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise FirmaInvalida("payload de Meta inválido") from exc
        if not isinstance(payload, dict):
            raise FirmaInvalida("payload de Meta inválido")
        procesados = 0
        for evento in eventos_meta(payload):
            try:
                svc.recibir_webhook(
                    evento, tenant_id=tenant, origen="meta"
                )
            except TurnoError:
                # Un evento viejo o ajeno no debe hacer que Meta reintente todo.
                continue
            procesados += 1
        return {"received": True, "eventos": procesados}

    return r
