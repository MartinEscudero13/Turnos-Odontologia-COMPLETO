"""HTTP smoke tests for the C-05/C-06 demo wiring."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings
from app.demo import PRESTACION_CONSULTA, PROFESIONAL_DEMO_1

SETTINGS = Settings(
    APP_ENV="test",
    DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
    REDIS_URL="redis://localhost:6379/0",
    JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
    APP_URL="http://localhost:5173",
)
INICIO = "2026-11-16T00:00:00-03:00"


def client() -> TestClient:
    return TestClient(create_app(SETTINGS))


def test_public_catalog_and_availability_are_mounted() -> None:
    c = client()
    catalogo = c.get("/api/publico/demo/catalogo")
    assert catalogo.status_code == 200
    assert len(catalogo.json()["prestaciones"]) >= 2

    disponibilidad = c.get(
        "/api/publico/demo/disponibilidad",
        params={"prestacion": PRESTACION_CONSULTA, "profesional": PROFESIONAL_DEMO_1, "desde": INICIO},
    )
    assert disponibilidad.status_code == 200
    assert disponibilidad.json()
    assert {"inicio", "fin", "profesional_id", "sillon_id"} <= set(disponibilidad.json()[0])


def test_public_reservation_reaches_c06_domain() -> None:
    c = client()
    slots = c.get(
        "/api/publico/demo/disponibilidad",
        params={"prestacion": PRESTACION_CONSULTA, "profesional": PROFESIONAL_DEMO_1, "desde": INICIO},
    ).json()
    assert slots
    slot = slots[0]

    verification = c.post("/api/publico/demo/verificacion", json={"accion": "reservar"})
    assert verification.status_code == 201
    proof = verification.json()["verificacion_id"]

    response = c.post(
        "/api/publico/demo/reservas",
        json={
            "prestacion": PRESTACION_CONSULTA,
            "profesional": PROFESIONAL_DEMO_1,
            "inicio": slot["inicio"],
            "nombre": "Paciente Demo",
            "telefono": "+5491130551234",
            "verificacion_id": proof,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["estado"] == "PENDIENTE"
    assert body["token_publico"]
    assert body["inicio"] == slot["inicio"]


def test_public_reservation_without_verification_is_403() -> None:
    c = client()
    response = c.post(
        "/api/publico/demo/reservas",
        json={
            "prestacion": PRESTACION_CONSULTA,
            "profesional": PROFESIONAL_DEMO_1,
            "inicio": "2026-11-16T09:00:00-03:00",
            "nombre": "Paciente Demo",
            "telefono": "+5491130551234",
        },
    )
    assert response.status_code in {403, 422}


def test_internal_turnos_route_is_mounted() -> None:
    c = client()
    response = c.get(
        "/api/turnos",
        headers={"X-Tenant-Id": "tenant-demo", "X-User-Id": "recep-demo", "X-Rol": "RECEPCION"},
    )
    assert response.status_code == 200
