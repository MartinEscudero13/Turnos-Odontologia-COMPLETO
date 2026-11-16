"""Regresión de alineación entre el seed SQL y el composition root demo.

El SPA usa los IDs del catálogo SQL (UUIDs). Si los adaptadores en memoria
vuelven a sembrar IDs ficticios distintos, clínica, presupuesto, OS y caja
dejan de funcionar con 404. Este test fija el contrato con los UUIDs literales
del seed.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings

SETTINGS = Settings(
    APP_ENV="test",
    DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
    REDIS_URL="redis://localhost:6379/0",
    JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
    APP_URL="http://localhost:5173",
)

TENANT = "a0000000-0000-4000-8000-000000000001"
ADMIN = "a1000000-0000-4000-8000-000000000001"
PACIENTE = "e1000000-0000-4000-8000-000000000001"
PRESTACION = "d1000000-0000-4000-8000-000000000001"


def headers() -> dict[str, str]:
    return {"X-Tenant-Id": TENANT, "X-User-Id": ADMIN, "X-Rol": "ADMIN"}


def test_seed_sql_ids_are_wired_to_demo_services() -> None:
    c = TestClient(create_app(SETTINGS))

    consentimiento = c.post(
        "/api/consentimientos",
        headers=headers(),
        json={
            "paciente_id": PACIENTE,
            "timestamp": "2026-11-16T10:00:00-03:00",
            "canal": "mostrador",
        },
    )
    assert consentimiento.status_code == 201, consentimiento.text

    ficha = c.post(f"/api/pacientes/{PACIENTE}/ficha", headers=headers())
    assert ficha.status_code == 201, ficha.text

    presupuesto = c.post(
        "/api/presupuestos", headers=headers(), json={"paciente_id": PACIENTE}
    )
    assert presupuesto.status_code == 201, presupuesto.text

    preview = c.get(
        "/api/coberturas/preview",
        headers=headers(),
        params={"paciente_id": PACIENTE, "prestacion_id": PRESTACION},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["origen"] == "CONFIGURADA"

    cierre = c.post(
        "/api/caja/cierre",
        headers=headers(),
        json={
            "efectivo_contado": 0,
            "responsable_id": ADMIN,
            "fecha": "2026-11-16",
        },
    )
    assert cierre.status_code == 201, cierre.text
