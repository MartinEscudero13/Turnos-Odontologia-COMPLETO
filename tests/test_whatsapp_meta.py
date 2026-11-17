"""Tests del adaptador Meta WhatsApp Cloud API (sin red)."""
from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error

import pytest

from app.whatsapp import meta
from app.whatsapp.meta import (
    PasarelaMeta,
    eventos_meta,
    firma_meta_valida,
    normalizar_telefono_meta,
)
from app.whatsapp.puertos import WhatsAppNoDisponible


class _Respuesta:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self) -> _Respuesta:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_envia_texto_por_graph_api(monkeypatch: pytest.MonkeyPatch) -> None:
    capturado: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: int) -> _Respuesta:
        capturado["url"] = request.full_url  # type: ignore[attr-defined]
        capturado["headers"] = dict(request.headers)  # type: ignore[attr-defined]
        capturado["body"] = json.loads(request.data.decode())  # type: ignore[attr-defined]
        capturado["timeout"] = timeout
        return _Respuesta({"messages": [{"id": "wamid.123"}]})

    monkeypatch.setattr(meta.urllib.request, "urlopen", fake_urlopen)
    pasarela = PasarelaMeta(token="token-demo", phone_number_id="123456")

    envio = pasarela.enviar(destino="+54 9 261 390-7099", cuerpo="Hola")

    assert envio.provider_message_id == "wamid.123"
    assert envio.estado == "ENVIADO"
    body = capturado["body"]
    assert isinstance(body, dict)
    assert body["to"] == "5492613907099"
    assert body["type"] == "text"
    assert body["text"]["body"] == "Hola"
    assert body["messaging_product"] == "whatsapp"
    assert str(capturado["url"]).endswith("/123456/messages")
    headers = {clave.lower(): valor for clave, valor in capturado["headers"].items()}  # type: ignore[union-attr]
    assert headers["authorization"] == "Bearer token-demo"


def test_falla_si_meta_no_devuelve_id(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_request: object, timeout: int) -> _Respuesta:
        del timeout
        return _Respuesta({"messages": []})

    monkeypatch.setattr(meta.urllib.request, "urlopen", fake_urlopen)
    pasarela = PasarelaMeta(token="token", phone_number_id="1")

    with pytest.raises(WhatsAppNoDisponible):
        pasarela.enviar(destino="+5491100000000", cuerpo="Hola")


def test_falla_de_red_se_traduce(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_request: object, timeout: int) -> _Respuesta:
        del timeout
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(meta.urllib.request, "urlopen", fake_urlopen)
    pasarela = PasarelaMeta(token="token", phone_number_id="1")

    with pytest.raises(WhatsAppNoDisponible):
        pasarela.enviar(destino="+5491100000000", cuerpo="Hola")


def test_normaliza_telefono() -> None:
    assert normalizar_telefono_meta("+54 9 261 390-7099") == "5492613907099"


def test_eventos_de_estado() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {"id": "wamid.out", "status": "delivered"},
                                {"id": "wamid.out2", "status": "read"},
                            ]
                        }
                    }
                ]
            }
        ]
    }

    assert eventos_meta(payload) == [
        {"MessageSid": "wamid.out", "MessageStatus": "delivered"},
        {"MessageSid": "wamid.out2", "MessageStatus": "read"},
    ]


def test_evento_de_respuesta_usa_contexto_y_telefono() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.in",
                                    "from": "5491130551001",
                                    "text": {"body": "Sí"},
                                    "context": {"id": "wamid.out"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    assert eventos_meta(payload) == [
        {
            "MessageSid": "wamid.out",
            "Body": "Sí",
            "From": "+5491130551001",
        }
    ]


def test_respuesta_sin_contexto_conserva_su_id() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"id": "wamid.in", "from": "5491130551001", "text": {"body": "NO"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    evento = eventos_meta(payload)[0]
    assert evento["MessageSid"] == "wamid.in"
    assert evento["From"] == "+5491130551001"


def test_firma_meta() -> None:
    cuerpo = b'{"entry":[]}'
    firma = "sha256=" + hmac.new(b"secreto", cuerpo, hashlib.sha256).hexdigest()

    assert firma_meta_valida(cuerpo=cuerpo, app_secret="secreto", firma=firma)
    assert not firma_meta_valida(cuerpo=cuerpo, app_secret="otro", firma=firma)
    assert not firma_meta_valida(cuerpo=cuerpo, app_secret="secreto", firma=None)
    assert not firma_meta_valida(cuerpo=cuerpo, app_secret="secreto", firma="sha1=abc")
