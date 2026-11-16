"""Adaptador Twilio WhatsApp (REST, sin SDK) y validación de firma."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

from app.whatsapp.puertos import (
    EnvioWA,
    EstadoMensaje,
    PasarelaWhatsAppPort,
    WhatsAppNoDisponible,
)

__all__ = ["PasarelaTwilio", "firma_valida", "mapear_estado_twilio", "twilio_desde_env"]

_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def mapear_estado_twilio(status: str | None) -> EstadoMensaje:
    if status in ("delivered",):
        return "ENTREGADO"
    if status in ("read",):
        return "LEIDO"
    if status in ("failed", "undelivered"):
        return "FALLIDO"
    return "ENVIADO"


def firma_valida(
    *, url: str, params: Mapping[str, str], auth_token: str, signature: str | None
) -> bool:
    """Valida `X-Twilio-Signature` según el algoritmo oficial."""
    if not signature:
        return False
    data = url + "".join(f"{clave}{params[clave]}" for clave in sorted(params))
    digest = hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()
    esperada = base64.b64encode(digest).decode()
    return hmac.compare_digest(esperada, signature)


class PasarelaTwilio:
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_number: str,
        timeout_s: int = 10,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"
        self._timeout_s = timeout_s

    def enviar(
        self, *, destino: str, cuerpo: str, turno_id: str | None = None
    ) -> EnvioWA:
        del turno_id
        to = destino if destino.startswith("whatsapp:") else f"whatsapp:{destino}"
        data = urllib.parse.urlencode(
            {"From": self._from, "To": to, "Body": cuerpo}
        ).encode()
        credentials = base64.b64encode(
            f"{self._account_sid}:{self._auth_token}".encode()
        ).decode()
        request = urllib.request.Request(
            _API.format(sid=self._account_sid),
            data=data,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                body: object = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise WhatsAppNoDisponible("twilio no disponible") from exc
        if not isinstance(body, dict) or not isinstance(body.get("sid"), str):
            raise WhatsAppNoDisponible("respuesta inválida de twilio")
        return EnvioWA(
            provider_message_id=str(body["sid"]),
            estado=mapear_estado_twilio(body.get("status") if isinstance(body.get("status"), str) else None),
        )


def twilio_desde_env() -> PasarelaWhatsAppPort | None:
    """Devuelve Twilio solo si el proveedor y las credenciales están configurados."""
    if os.environ.get("WA_PROVIDER", "").strip().lower() != "twilio":
        return None
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
    if not (account_sid and auth_token and from_number):
        return None
    return PasarelaTwilio(
        account_sid=account_sid,
        auth_token=auth_token,
        from_number=from_number,
    )
