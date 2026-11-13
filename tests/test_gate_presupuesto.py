"""Task 6.4 — gate de consentimiento en líneas clínicas del presupuesto (D11).

Una línea con `pieza_fdi` (o derivada de un hallazgo) exige consentimiento con
`timestamp` válido; una línea sin pieza (consulta administrativa) no queda sujeta
al gate clínico.
"""
from __future__ import annotations

from _odontograma_helpers import PAC1, PREST1
from _presupuesto_helpers import HarnessPresupuesto, crear_borrador
from conftest import T1
from fastapi.testclient import TestClient

from app.routers.presupuesto import crear_app

RECEP = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}


def _client(h: HarnessPresupuesto) -> TestClient:
    return TestClient(crear_app(h.svc))


def _linea_body(*, pieza_fdi: int | None = 36) -> dict[str, object]:
    body: dict[str, object] = {"prestacion_id": PREST1, "monto": 100000}
    if pieza_fdi is not None:
        body["pieza_fdi"] = pieza_fdi
    return body


def test_linea_con_pieza_sin_consentimiento_409():
    h = HarnessPresupuesto()
    presupuesto = crear_borrador(h)
    client = _client(h)

    r = client.post(
        f"/api/presupuestos/{presupuesto.id}/lineas", json=_linea_body(), headers=RECEP
    )
    assert r.status_code == 409
    assert r.json()["detalle"] == "CONSENTIMIENTO_REQUERIDO"
    assert h.lineas.listar(tenant_id=T1, presupuesto_id=presupuesto.id) == []


def test_linea_con_pieza_con_consentimiento_201():
    h = HarnessPresupuesto()
    h.dar_consentimiento(PAC1)
    presupuesto = crear_borrador(h)
    client = _client(h)

    r = client.post(
        f"/api/presupuestos/{presupuesto.id}/lineas", json=_linea_body(), headers=RECEP
    )
    assert r.status_code == 201
    assert r.json()["pieza_fdi"] == 36
    lineas = h.lineas.listar(tenant_id=T1, presupuesto_id=presupuesto.id)
    assert len(lineas) == 1 and lineas[0].pieza_fdi == 36


def test_linea_sin_pieza_no_exige_consentimiento():
    h = HarnessPresupuesto()
    presupuesto = crear_borrador(h)
    client = _client(h)

    r = client.post(
        f"/api/presupuestos/{presupuesto.id}/lineas",
        json=_linea_body(pieza_fdi=None),
        headers=RECEP,
    )
    assert r.status_code == 201
    assert r.json()["pieza_fdi"] is None
    assert len(h.lineas.listar(tenant_id=T1, presupuesto_id=presupuesto.id)) == 1
    # Una línea administrativa no crea vínculo clínico con ningún hallazgo.
    assert h.lineas.listar(tenant_id=T1, presupuesto_id=presupuesto.id)[0].hallazgo_id is None
