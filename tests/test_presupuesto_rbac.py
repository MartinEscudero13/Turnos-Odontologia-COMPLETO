"""Tasks 6.9–6.11 — RBAC del presupuesto (D10).

Crean `ODONTOLOGO`, `RECEPCION` y `ADMIN`; aceptan sólo `RECEPCION` y `ADMIN`,
en nombre del paciente y con `canal=CONSULTORIO`. El `ODONTOLOGO` crea pero no
acepta (`403`).
"""
from __future__ import annotations

from _odontograma_helpers import PAC1, PREST1, d3
from _presupuesto_helpers import HarnessPresupuesto
from conftest import P1, T1
from fastapi.testclient import TestClient

from app.routers.presupuesto import crear_app

RECEP = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}
ADMIN = {"X-Tenant-Id": T1, "X-User-Id": "admin-1", "X-Rol": "ADMIN"}
ODONTO = {
    "X-Tenant-Id": T1,
    "X-User-Id": "odont-1",
    "X-Rol": "ODONTOLOGO",
    "X-Profesional-Id": P1,
}


def _client(h: HarnessPresupuesto) -> TestClient:
    return TestClient(crear_app(h.svc))


def _presupuesto_con_linea(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    alta = client.post("/api/presupuestos", json={"paciente_id": PAC1}, headers=headers)
    assert alta.status_code == 201
    presupuesto_id = alta.json()["id"]
    linea = client.post(
        f"/api/presupuestos/{presupuesto_id}/lineas",
        json={"prestacion_id": PREST1, "monto": 100000},
        headers=headers,
    )
    assert linea.status_code == 201
    return presupuesto_id, linea.json()["id"]


def _emitir(client: TestClient, presupuesto_id: str, headers: dict[str, str]) -> None:
    emitido = client.post(
        f"/api/presupuestos/{presupuesto_id}/emitir",
        json={"vence_en": d3("2026-12-31", 23, 59).isoformat()},
        headers=headers,
    )
    assert emitido.status_code == 200
    assert emitido.json()["estado"] == "VIGENTE"


def test_recepcion_crea_y_registra_aceptacion_consultorio():
    h = HarnessPresupuesto()
    client = _client(h)
    presupuesto_id, linea_id = _presupuesto_con_linea(client, RECEP)
    _emitir(client, presupuesto_id, RECEP)

    r = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={"linea_id": linea_id, "acepta": True, "canal": "CONSULTORIO"},
        headers=RECEP,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "ACEPTADO"
    assert body["canal"] == "CONSULTORIO"
    assert body["actor_id"] == "recep-1"
    assert body["medio"] is None


def test_admin_registra_aceptacion_en_nombre_del_paciente():
    h = HarnessPresupuesto()
    client = _client(h)
    presupuesto_id, linea_id = _presupuesto_con_linea(client, ADMIN)
    _emitir(client, presupuesto_id, ADMIN)

    r = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={"linea_id": linea_id, "acepta": True, "canal": "CONSULTORIO"},
        headers=ADMIN,
    )
    assert r.status_code == 200
    assert r.json()["actor_id"] == "admin-1"
    assert h.imputacion.llamadas_caja[0].actor_id == "admin-1"


def test_odontologo_crea_pero_no_acepta_403():
    h = HarnessPresupuesto()
    client = _client(h)
    presupuesto_id, linea_id = _presupuesto_con_linea(client, ODONTO)
    assert client.get(f"/api/presupuestos/{presupuesto_id}", headers=ODONTO).status_code == 200

    r = client.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        json={"linea_id": linea_id, "acepta": True, "canal": "CONSULTORIO"},
        headers=ODONTO,
    )
    assert r.status_code == 403
    assert h.aceptaciones.total(T1) == 0
    assert h.imputacion.llamadas_caja == []
    assert h.imputacion.llamadas_agenda == []
