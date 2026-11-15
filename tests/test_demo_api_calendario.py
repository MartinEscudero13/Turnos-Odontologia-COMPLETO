"""HTTP tests de C-14 en la demo (Google Calendar)."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings
from app.demo import (
    DEMO_TENANT_ID,
    DEMO_USER_ID,
    PROFESIONAL_DEMO_1,
    PROFESIONAL_DEMO_2,
    demo_periodo_actual,
)

SETTINGS = Settings(
    APP_ENV="test",
    DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
    REDIS_URL="redis://localhost:6379/0",
    JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
    APP_URL="http://localhost:5173",
)

TZ = timezone(timedelta(hours=-3))


def client() -> TestClient:
    return TestClient(create_app(SETTINGS))


def actor(
    rol: str = "ADMIN", profesional_id: str | None = None
) -> dict[str, str]:
    headers = {
        "X-Tenant-Id": DEMO_TENANT_ID,
        "X-User-Id": DEMO_USER_ID,
        "X-Rol": rol,
    }
    if profesional_id is not None:
        headers["X-Profesional-Id"] = profesional_id
    return headers


def turno_demo() -> tuple[datetime, datetime, datetime]:
    desde, _ = demo_periodo_actual()
    inicio = datetime.combine(desde.replace(day=10), time(10, 0), tzinfo=TZ)
    return inicio, inicio + timedelta(minutes=30), inicio + timedelta(minutes=15)


def test_link_demo_y_conexion_de_otro_profesional() -> None:
    c = client()

    links = c.get("/api/calendar/links", headers=actor())
    assert links.status_code == 200, links.text
    assert [link["profesional_id"] for link in links.json()] == [PROFESIONAL_DEMO_1]
    assert "oauth_ref" not in links.json()[0]

    conectado = c.post(
        "/api/calendar/oauth",
        headers=actor(),
        json={
            "profesional_id": PROFESIONAL_DEMO_2,
            "gcal_calendar_id": "demo-dos@example.test",
            "oauth_ref": "demo-oauth-ref-2",
        },
    )
    assert conectado.status_code == 201, conectado.text
    assert conectado.json()["estado"] == "CONECTADO"

    duplicado = c.post(
        "/api/calendar/oauth",
        headers=actor(),
        json={
            "profesional_id": PROFESIONAL_DEMO_2,
            "gcal_calendar_id": "otro@example.test",
            "oauth_ref": "otro-ref",
        },
    )
    assert duplicado.status_code == 409, duplicado.text
    assert duplicado.json()["codigo"] == "LINK_DUPLICADO"


def test_push_y_evento_externo_con_conflicto() -> None:
    c = client()
    inicio, fin, solapado = turno_demo()

    push = c.post(
        "/api/calendar/push",
        headers=actor(),
        json={
            "turno_id": "turno-demo-calendario",
            "profesional_id": PROFESIONAL_DEMO_1,
            "inicio": inicio.isoformat(),
            "fin": fin.isoformat(),
            "estado": "PENDIENTE",
            "resumen": "Turno demo",
        },
    )
    assert push.status_code == 200, push.text
    assert push.json()["estado"] == "SINCRONIZADO"
    assert push.json()["evento"]["gcal_event_id"]

    link_id = c.get("/api/calendar/links", headers=actor()).json()[0]["id"]

    bloqueo = c.post(
        "/api/calendar/webhook",
        json={
            "link_id": link_id,
            "token": "demo-oauth-ref",
            "event_id": "externo-libre",
            "inicio": (fin + timedelta(hours=1)).isoformat(),
            "fin": (fin + timedelta(hours=2)).isoformat(),
            "resumen": "Reunión externa",
        },
    )
    assert bloqueo.status_code == 200, bloqueo.text
    assert bloqueo.json()["estado"] == "BLOQUEADO"

    conflicto = c.post(
        "/api/calendar/webhook",
        json={
            "link_id": link_id,
            "token": "demo-oauth-ref",
            "event_id": "externo-solapa",
            "inicio": solapado.isoformat(),
            "fin": (solapado + timedelta(minutes=20)).isoformat(),
        },
    )
    assert conflicto.status_code == 200, conflicto.text
    assert conflicto.json()["estado"] == "CONFLICTO_SISTEMA"

    bloqueos = c.get(
        "/api/calendar/bloqueos",
        headers=actor(),
        params={
            "desde": (inicio - timedelta(days=1)).isoformat(),
            "hasta": (fin + timedelta(days=1)).isoformat(),
        },
    )
    assert bloqueos.status_code == 200, bloqueos.text
    assert [evento["estado"] for evento in bloqueos.json()] == [
        "CONFLICTO_SISTEMA",
        "BLOQUEADO",
    ]


def test_webhook_con_token_invalido_es_401() -> None:
    c = client()
    inicio, fin, _ = turno_demo()
    link_id = c.get("/api/calendar/links", headers=actor()).json()[0]["id"]

    response = c.post(
        "/api/calendar/webhook",
        json={
            "link_id": link_id,
            "token": "incorrecto",
            "event_id": "externo-x",
            "inicio": inicio.isoformat(),
            "fin": fin.isoformat(),
        },
    )
    assert response.status_code == 401, response.text


def test_push_sin_link_es_no_op() -> None:
    c = client()
    inicio, fin, _ = turno_demo()

    response = c.post(
        "/api/calendar/push",
        headers=actor(),
        json={
            "turno_id": "turno-x",
            "profesional_id": "profesional-demo-9",
            "inicio": inicio.isoformat(),
            "fin": fin.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"estado": "SIN_LINK", "evento": None}


def test_rbac_de_calendario() -> None:
    c = client()

    assert c.get("/api/calendar/links", headers=actor("PACIENTE")).status_code == 401
    assert (
        c.post(
            "/api/calendar/oauth",
            headers=actor("RECEPCION"),
            json={
                "profesional_id": PROFESIONAL_DEMO_2,
                "gcal_calendar_id": "x@test",
                "oauth_ref": "x",
            },
        ).status_code
        == 403
    )
    propio = c.post(
        "/api/calendar/oauth",
        headers=actor("ODONTOLOGO", PROFESIONAL_DEMO_2),
        json={
            "profesional_id": PROFESIONAL_DEMO_2,
            "gcal_calendar_id": "propio@test",
            "oauth_ref": "propio",
        },
    )
    assert propio.status_code == 201, propio.text
    ajeno = c.post(
        "/api/calendar/oauth",
        headers=actor("ODONTOLOGO", PROFESIONAL_DEMO_1),
        json={
            "profesional_id": PROFESIONAL_DEMO_2,
            "gcal_calendar_id": "ajeno@test",
            "oauth_ref": "ajeno",
        },
    )
    assert ajeno.status_code == 403, ajeno.text


def test_cola_sin_pendientes() -> None:
    c = client()

    response = c.post("/api/calendar/cola/procesar", headers=actor())
    assert response.status_code == 200, response.text
    assert response.json() == {
        "procesados": 0,
        "pendientes": 0,
        "agotados": 0,
        "token_revocado": False,
    }
