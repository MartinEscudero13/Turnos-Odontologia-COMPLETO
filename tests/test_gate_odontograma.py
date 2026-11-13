"""Tasks 2.9 y 6.1–6.3 — gate de consentimiento en la clínica del odontograma.

Sin consentimiento con `timestamp` válido no se registra, resuelve ni deriva
(`409 CONSENTIMIENTO_REQUERIDO`) y el hallazgo sigue con `resuelto=false`. La
agenda del mismo paciente no se bloquea (RN-AU-03).
"""
from __future__ import annotations

import pytest
from _odontograma_helpers import KEY, PAC1, PREST1, HarnessOdontograma, actor, d3
from conftest import P1, T1
from fastapi.testclient import TestClient

from app.ficha_clinica.servicio import ConsentimientoRequerido
from app.routers.odontograma import crear_app
from app.turnos.servicio import ServicioTurnos

ODONTO = {
    "X-Tenant-Id": T1,
    "X-User-Id": "odont-1",
    "X-Rol": "ODONTOLOGO",
    "X-Profesional-Id": P1,
}
RECEP = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}


def _hallazgo_body(*, pieza_fdi: int = 36, derivar: bool = False) -> dict[str, object]:
    body: dict[str, object] = {
        "paciente_id": PAC1,
        "pieza_fdi": pieza_fdi,
        "superficie": "O",
        "hallazgo": "caries oclusal",
        "fecha": d3().isoformat(),
        "profesional_id": P1,
    }
    if derivar:
        body["derivar"] = {"prestacion_id": PREST1}
    return body


def test_sin_consentimiento_no_resuelve_hallazgo():
    h = HarnessOdontograma()
    hallazgo = h.hallazgos.registrar(
        tenant_id=T1,
        paciente_id=PAC1,
        pieza_fdi=36,
        superficie=None,
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id=P1,
    )
    with pytest.raises(ConsentimientoRequerido) as exc:
        h.svc.resolver(actor("ADMIN"), hallazgo_id=hallazgo.id)
    assert exc.value.codigo == 409
    assert "CONSENTIMIENTO_REQUERIDO" in exc.value.mensaje
    persistido = h.hallazgos.obtener(tenant_id=T1, hallazgo_id=hallazgo.id)
    assert persistido is not None and persistido.resuelto is False


# ---------------------------------------------------------------------------
# 6.1 — sin consentimiento no se registra ni se deriva; con consentimiento sí
# ---------------------------------------------------------------------------


def test_sin_consentimiento_hallazgo_y_derivacion_409():
    h = HarnessOdontograma()
    client = TestClient(crear_app(h.svc))

    simple = client.post("/api/odontograma", json=_hallazgo_body(), headers=ODONTO)
    assert simple.status_code == 409
    assert simple.json()["detalle"] == "CONSENTIMIENTO_REQUERIDO"

    derivada = client.post(
        "/api/odontograma",
        json=_hallazgo_body(derivar=True),
        headers={**ODONTO, "Idempotency-Key": KEY},
    )
    assert derivada.status_code == 409
    assert derivada.json()["detalle"] == "CONSENTIMIENTO_REQUERIDO"

    assert h.hallazgos.total(T1) == 0
    assert h.lineas.total(T1) == 0
    assert h.presupuestos.total(T1) == 0


def test_con_consentimiento_hallazgo_201():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    client = TestClient(crear_app(h.svc))

    r = client.post("/api/odontograma", json=_hallazgo_body(), headers=ODONTO)
    assert r.status_code == 201
    body = r.json()
    assert body["pieza_fdi"] == 36
    assert body["resuelto"] is False
    assert h.hallazgos.total(T1) == 1


# ---------------------------------------------------------------------------
# 6.2 — la agenda no se bloquea por falta de consentimiento (RN-AU-03)
# ---------------------------------------------------------------------------


def test_sin_consentimiento_agenda_201():
    turnos = ServicioTurnos(anticipacion_min_horas=0.0)
    turno = turnos.crear(
        actor("RECEPCION", user_id="recep-1"),
        profesional_id=P1,
        sillon_id="sillon-1",
        paciente_id=PAC1,
        prestacion_id=PREST1,
        inicio=d3(),
        duracion_min=30,
    )
    assert turno.estado == "PENDIENTE"
    assert turno.paciente_id == PAC1


# ---------------------------------------------------------------------------
# 6.3 — una fila sin timestamp válido no habilita el odontograma
# ---------------------------------------------------------------------------


def test_fila_sin_timestamp_valido_no_habilita():
    h = HarnessOdontograma()
    h.consentimientos.registrar(
        tenant_id=T1,
        paciente_id=PAC1,
        timestamp=None,
        canal="móvil",
        ahora=d3(),
    )
    client = TestClient(crear_app(h.svc))

    r = client.post("/api/odontograma", json=_hallazgo_body(), headers=ODONTO)
    assert r.status_code == 409
    assert r.json()["detalle"] == "CONSENTIMIENTO_REQUERIDO"
    assert h.hallazgos.total(T1) == 0
