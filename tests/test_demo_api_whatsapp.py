"""HTTP tests de C-13 en la demo (WhatsApp/Twilio)."""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings
from app.demo import (
    DEMO_ADMIN_ID,
    DEMO_PACIENTE_1,
    DEMO_TENANT_ID,
    PRESTACION_CONSULTA,
    PROFESIONAL_DEMO_1,
    SILLON_DEMO_1,
)

SETTINGS = Settings(
    APP_ENV="test",
    DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
    REDIS_URL="redis://localhost:6379/0",
    JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
    APP_URL="http://localhost:5173",
)
TOKEN = "twilio-test-token"
URL = "http://testserver/api/webhooks/whatsapp"


def client() -> TestClient:
    return TestClient(create_app(SETTINGS))


def actor(rol: str = "ADMIN", user_id: str = DEMO_ADMIN_ID) -> dict[str, str]:
    return {"X-Tenant-Id": DEMO_TENANT_ID, "X-User-Id": user_id, "X-Rol": rol}


def crear_turno(c: TestClient) -> str:
    inicio = datetime.now(UTC) + timedelta(hours=2)
    response = c.post(
        "/api/turnos",
        headers=actor(),
        json={
            "profesional_id": PROFESIONAL_DEMO_1,
            "sillon_id": SILLON_DEMO_1,
            "paciente_id": DEMO_PACIENTE_1,
            "prestacion_id": PRESTACION_CONSULTA,
            "duracion_min": 30,
            "inicio": inicio.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def firmar(payload: dict[str, str], *, token: str = TOKEN) -> str:
    data = URL + "".join(f"{clave}{payload[clave]}" for clave in sorted(payload))
    digest = hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def test_programar_listar_y_confirmar_por_whatsapp(monkeypatch) -> None:
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TOKEN)
    c = client()
    turno_id = crear_turno(c)

    programados = c.post("/api/whatsapp/recordatorios/programar", headers=actor())
    assert programados.status_code == 200, programados.text
    assert programados.json()["enviados"] == 1

    listado = c.get("/api/whatsapp/mensajes", headers=actor())
    assert listado.status_code == 200, listado.text
    mensaje = listado.json()[0]
    assert mensaje["turno_id"] == turno_id
    assert mensaje["canal"] == "WA"
    assert mensaje["estado"] == "ENVIADO"

    payload = {"MessageSid": mensaje["provider_message_id"], "Body": "SI"}
    respuesta = c.post(
        "/api/webhooks/whatsapp",
        data=payload,
        headers={"x-twilio-signature": firmar(payload)},
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["respuesta"] == "SI"

    turnos = c.get("/api/turnos", headers=actor()).json()
    assert turnos[0]["estado"] == "CONFIRMADO"


def test_cancelar_por_whatsapp(monkeypatch) -> None:
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TOKEN)
    c = client()
    crear_turno(c)
    c.post("/api/whatsapp/recordatorios/programar", headers=actor())
    mensaje = c.get("/api/whatsapp/mensajes", headers=actor()).json()[0]

    payload = {"MessageSid": mensaje["provider_message_id"], "Body": "NO"}
    respuesta = c.post(
        "/api/webhooks/whatsapp",
        data=payload,
        headers={"x-twilio-signature": firmar(payload)},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["respuesta"] == "NO"
    assert c.get("/api/turnos", headers=actor()).json()[0]["estado"] == "CANCELADO"


def test_webhook_firma_invalida_es_401(monkeypatch) -> None:
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TOKEN)
    c = client()

    respuesta = c.post(
        "/api/webhooks/whatsapp",
        data={"MessageSid": "SM1", "Body": "SI"},
        headers={"x-twilio-signature": "firma-invalida"},
    )

    assert respuesta.status_code == 401, respuesta.text


def test_webhook_sin_token_es_503(monkeypatch) -> None:
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    c = client()

    respuesta = c.post("/api/webhooks/whatsapp", data={"MessageSid": "SM1"})

    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()["codigo"] == "WEBHOOK_NO_CONFIGURADO"


def test_recall_y_rbac(monkeypatch) -> None:
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TOKEN)
    c = client()

    recall = c.post(
        "/api/whatsapp/recall",
        headers=actor(),
        json={
            "paciente_id": DEMO_PACIENTE_1,
            "motivo": "Control post-tratamiento",
            "fecha_objetivo": "2027-01-15",
        },
    )
    assert recall.status_code == 200, recall.text
    assert recall.json()["plantilla"] == "RECALL"

    assert c.post("/api/whatsapp/recordatorios/programar", headers=actor("ODONTOLOGO")).status_code == 403
    assert c.get("/api/whatsapp/mensajes", headers=actor("PACIENTE")).status_code == 401
