"""Tasks 8.4–8.7 — privacidad de respuestas y logs (RN-CL-04): RED primero."""
from __future__ import annotations

import json
import logging

from _reserva_helpers import Harness, catalogo_estandar, reservar
from conftest import P1, P2, S1, S2, T1, dt

from app.turnos.servicio import Actor


def _harness() -> Harness:
    h = Harness(reloj_inicial=dt("2026-10-05", 9))
    catalogo_estandar(h)
    return h


def test_disponibilidad_no_expone_pacientes():
    h = _harness()
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    h.turnos.crear(actor, profesional_id=P1, sillon_id=S1, paciente_id="pac-a", prestacion_id="PREST-30", inicio=dt("2026-10-06", 10), duracion_min=30)
    h.turnos.crear(actor, profesional_id=P2, sillon_id=S2, paciente_id="pac-b", prestacion_id="PREST-30", inicio=dt("2026-10-06", 10), duracion_min=30)
    d = h.client.get(
        "/api/publico/t1/disponibilidad",
        params={"prestacion": "PREST-30", "profesional": "profesional-1", "desde": "2026-10-06T00:00:00+00:00"},
    )
    assert d.status_code == 200
    for s in d.json():
        assert set(s.keys()) == {"inicio", "fin", "profesional_id", "sillon_id"}


def test_reserva_no_expone_telefono_ni_nombre_de_terceros():
    h = _harness()
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    h.turnos.crear(actor, profesional_id=P2, sillon_id=S2, paciente_id="otro", prestacion_id="PREST-30", inicio=dt("2026-10-06", 11), duracion_min=30)
    body = reservar(h, nombre="Paciente Demo", telefono="+5491130551234").json()
    assert set(body.keys()) == {
        "turno_id", "estado", "inicio", "fin", "origen", "prestacion", "sillon_id", "token_publico",
    }
    texto = json.dumps(body)
    assert "Otro Paciente Demo" not in texto
    assert "+5491100000001" not in texto


def test_404_no_filtra_existencia_ni_phi():
    h = _harness()
    token = reservar(h).json()["token_publico"]
    r1 = h.client.get("/api/publico/t2/reservas/NO-EXISTE")
    r2 = h.client.get(f"/api/publico/t2/reservas/{token}")
    assert r1.status_code == 404
    assert r2.status_code == 404
    assert r1.json() == r2.json()
    assert "tenant_id" not in r2.json()


def test_logs_de_reserva_no_contienen_phi_ni_token(caplog):
    caplog.set_level(logging.INFO)
    h = _harness()
    body = reservar(h, nombre="Paciente Demo", telefono="+5491130551234").json()
    token = body["token_publico"]
    texto = caplog.text
    assert body["turno_id"] in texto
    assert body["estado"] in texto
    assert "Paciente Demo" not in texto
    assert "+5491130551234" not in texto
    assert token not in texto
