"""Router FastAPI de WhatsApp — C-13."""
from __future__ import annotations

import os
import urllib.parse

from fastapi import APIRouter, Depends, Query, Request

from app.routers.turnos import actor_desde_headers
from app.schemas.whatsapp import (
    EnvioOut,
    MensajeOut,
    RecallIn,
    WebhookOut,
)
from app.turnos.servicio import Actor
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
        return _webhook_out(svc.recibir_webhook(params, tenant_id=tenant))

    return r
