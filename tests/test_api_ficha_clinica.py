"""Tasks 7.1–7.3 — borde API de ficha clínica (CRUD HTTP + mapeo de errores)."""
from __future__ import annotations

from _ficha_clinica_helpers import HarnessClinica, d3
from conftest import P1, T1
from fastapi.testclient import TestClient

from app.routers.ficha_clinica import crear_app

RECEP = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}
ODONTO = {"X-Tenant-Id": T1, "X-User-Id": "odont-1", "X-Rol": "ODONTOLOGO", "X-Profesional-Id": P1}
PACIENTE = {"X-Tenant-Id": T1, "X-User-Id": "paciente-1", "X-Rol": "PACIENTE"}


def _client() -> tuple[HarnessClinica, TestClient]:
    h = HarnessClinica()
    h.seed_paciente("paciente-1")
    h.seed_profesional(P1)
    h.seed_atiende(P1, "paciente-1")
    return h, TestClient(crear_app(h.svc))


def test_payload_con_campo_extra_responde_422():
    _, client = _client()
    r = client.post(
        "/api/evoluciones",
        json={
            "paciente_id": "paciente-1",
            "profesional_id": P1,
            "fecha": d3().isoformat(),
            "texto": "x",
            "tenant_id": "intruso",
        },
        headers=ODONTO,
    )
    assert r.status_code == 422
    r2 = client.post(
        "/api/consentimientos",
        json={"paciente_id": "paciente-1", "timestamp": d3().isoformat(), "canal": "móvil", "extra": 1},
        headers=RECEP,
    )
    assert r2.status_code == 422


def test_crud_por_http_201_200():
    h, client = _client()
    # consentimiento
    r = client.post(
        "/api/consentimientos",
        json={"paciente_id": "paciente-1", "timestamp": d3().isoformat(), "canal": "móvil"},
        headers=RECEP,
    )
    assert r.status_code == 201
    # ficha
    r = client.post("/api/pacientes/paciente-1/ficha", headers=RECEP)
    assert r.status_code == 201
    ficha_id = r.json()["id"]
    # evolución
    r = client.post(
        "/api/evoluciones",
        json={
            "paciente_id": "paciente-1",
            "profesional_id": P1,
            "fecha": d3().isoformat(),
            "texto": "evolución",
        },
        headers=ODONTO,
    )
    assert r.status_code == 201
    # adjunto
    r = client.post(
        "/api/adjuntos", json={"ficha_id": ficha_id, "tipo": "RX", "storage_ref": "obj/x"}, headers=ODONTO
    )
    assert r.status_code == 201
    # GETs
    assert client.get("/api/pacientes/paciente-1/ficha", headers=RECEP).status_code == 200
    assert (
        client.get("/api/evoluciones", params={"paciente_id": "paciente-1"}, headers=RECEP).status_code
        == 200
    )
    assert client.get("/api/adjuntos", params={"ficha_id": ficha_id}, headers=RECEP).status_code == 200
    assert (
        client.get(
            "/api/consentimientos", params={"paciente_id": "paciente-1"}, headers=RECEP
        ).status_code
        == 200
    )
    # paciente lee su propia ficha
    assert client.get("/api/pacientes/paciente-1/ficha", headers=PACIENTE).status_code == 200


def test_errores_mapean_404_403_409_422():
    _, client = _client()
    # 404: ficha de paciente inexistente
    r404 = client.get("/api/pacientes/paciente-999/ficha", headers=RECEP)
    assert r404.status_code == 404
    assert "trace" not in r404.text.lower() and "detalle" in r404.json()
    # 403: recepción no registra evolución
    r403 = client.post(
        "/api/evoluciones",
        json={
            "paciente_id": "paciente-1",
            "profesional_id": P1,
            "fecha": d3().isoformat(),
            "texto": "x",
        },
        headers=RECEP,
    )
    assert r403.status_code == 403
    # 409: crear ficha sin consentimiento → CONSENTIMIENTO_REQUERIDO
    r409 = client.post("/api/pacientes/paciente-1/ficha", headers=RECEP)
    assert r409.status_code == 409
    assert r409.json()["detalle"] == "CONSENTIMIENTO_REQUERIDO"
    # 422: tipo de adjunto inválido
    r422 = client.post(
        "/api/adjuntos", json={"ficha_id": "f", "tipo": "CT", "storage_ref": "x"}, headers=ODONTO
    )
    assert r422.status_code == 422
