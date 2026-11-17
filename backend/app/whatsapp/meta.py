"""Adaptador oficial de WhatsApp Cloud API (Meta) para C-13.

Envía texto libre por la Graph API y traduce los webhooks de Meta al contrato
interno que ya consume `ServicioWhatsApp` (`MessageSid`, `Body`, `MessageStatus`).
No usa SDK: sólo `urllib` y `hmac`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from app.whatsapp.puertos import (
    EnvioWA,
    PasarelaWhatsAppPort,
    WhatsAppNoDisponible,
)

__all__ = [
    "PasarelaMeta",
    "eventos_meta",
    "firma_meta_valida",
    "meta_desde_env",
    "normalizar_telefono_meta",
]

_API = "https://graph.facebook.com/{version}/{phone_number_id}/messages"


def normalizar_telefono_meta(destino: str) -> str:
    """Meta espera el número sólo con dígitos y código de país."""
    return re.sub(r"\D", "", destino)


def firma_meta_valida(
    *, cuerpo: bytes, app_secret: str, firma: str | None
) -> bool:
    """Valida `X-Hub-Signature-256: sha256=<hex>` sobre el cuerpo crudo."""
    if not firma or not firma.startswith("sha256="):
        return False
    esperada = hmac.new(app_secret.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma[len("sha256=") :])


class PasarelaMeta:
    def __init__(
        self,
        *,
        token: str,
        phone_number_id: str,
        version: str = "v23.0",
        timeout_s: int = 10,
    ) -> None:
        self._token = token
        self._phone_number_id = phone_number_id
        self._version = version
        self._timeout_s = timeout_s

    def enviar(
        self, *, destino: str, cuerpo: str, turno_id: str | None = None
    ) -> EnvioWA:
        del turno_id
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalizar_telefono_meta(destino),
            "type": "text",
            "text": {"preview_url": False, "body": cuerpo},
        }
        request = urllib.request.Request(
            _API.format(
                version=self._version, phone_number_id=self._phone_number_id
            ),
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                body: object = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise WhatsAppNoDisponible("meta no disponible") from exc
        if not isinstance(body, dict):
            raise WhatsAppNoDisponible("respuesta inválida de meta")
        mensajes = body.get("messages")
        if not isinstance(mensajes, list) or not mensajes:
            raise WhatsAppNoDisponible("meta no devolvió el id del mensaje")
        primero = mensajes[0]
        if not isinstance(primero, dict) or not isinstance(primero.get("id"), str):
            raise WhatsAppNoDisponible("meta no devolvió el id del mensaje")
        return EnvioWA(provider_message_id=str(primero["id"]), estado="ENVIADO")


def eventos_meta(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """Aplana un webhook de Meta en eventos con el contrato interno.

    - Estados (`statuses`) → `MessageSid` + `MessageStatus`.
    - Mensajes (`messages`) → `MessageSid` (contexto si es respuesta), `Body` y `From`.
    """
    eventos: list[dict[str, str]] = []
    entradas = payload.get("entry")
    if not isinstance(entradas, list):
        return eventos
    for entrada in entradas:
        if not isinstance(entrada, dict):
            continue
        cambios = entrada.get("changes")
        if not isinstance(cambios, list):
            continue
        for cambio in cambios:
            if not isinstance(cambio, dict):
                continue
            valor = cambio.get("value")
            if not isinstance(valor, dict):
                continue
            estados = valor.get("statuses")
            if isinstance(estados, list):
                for estado in estados:
                    if isinstance(estado, dict) and isinstance(estado.get("id"), str):
                        eventos.append(
                            {
                                "MessageSid": str(estado["id"]),
                                "MessageStatus": str(estado.get("status", "")),
                            }
                        )
            mensajes = valor.get("messages")
            if isinstance(mensajes, list):
                for mensaje in mensajes:
                    if not isinstance(mensaje, dict):
                        continue
                    contexto = mensaje.get("context")
                    contexto_id = (
                        str(contexto["id"])
                        if isinstance(contexto, dict) and isinstance(contexto.get("id"), str)
                        else ""
                    )
                    texto = ""
                    cuerpo = mensaje.get("text")
                    if isinstance(cuerpo, dict) and isinstance(cuerpo.get("body"), str):
                        texto = cuerpo["body"]
                    evento: dict[str, str] = {
                        "MessageSid": contexto_id or str(mensaje.get("id", "")),
                        "Body": texto,
                    }
                    if isinstance(mensaje.get("from"), str):
                        remitente = mensaje["from"]
                        evento["From"] = (
                            f"+{remitente}" if remitente.isdigit() else remitente
                        )
                    eventos.append(evento)
    return eventos


def meta_desde_env() -> PasarelaWhatsAppPort | None:
    """Devuelve el adaptador sólo si `WA_PROVIDER=meta` y hay credenciales."""
    if os.environ.get("WA_PROVIDER", "").strip().lower() != "meta":
        return None
    token = os.environ.get("META_WA_TOKEN", "").strip()
    phone_number_id = os.environ.get("META_PHONE_NUMBER_ID", "").strip()
    if not (token and phone_number_id):
        return None
    return PasarelaMeta(
        token=token,
        phone_number_id=phone_number_id,
        version=os.environ.get("META_API_VERSION", "v23.0").strip() or "v23.0",
    )

