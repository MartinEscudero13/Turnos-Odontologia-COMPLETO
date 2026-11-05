"""Tasks 9.1–9.4 — trazabilidad append-only sin PHI (RN-AU-02): RED primero."""
from __future__ import annotations

import dataclasses

from _reserva_helpers import Harness, catalogo_estandar, emitir, reservar
from conftest import dt

from app.reservas.puertos import AuditoriaPort

_CAMPOS_AUDITORIA = {
    "turno_id", "tenant_id", "accion", "actor", "motivo", "antes", "despues", "registrado_en",
}


def _harness(reloj: tuple = ("2026-10-20", 9, 0)) -> Harness:
    h = Harness(reloj_inicial=dt(*reloj))
    catalogo_estandar(h)
    return h


def test_reserva_publica_queda_auditada_sin_phi():
    h = _harness(("2026-10-05", 9, 0))
    body = reservar(h).json()
    turno_id = body["turno_id"]
    (e,) = [x for x in h.auditoria.entradas if x.turno_id == turno_id and x.accion == "CREADO"]
    assert e.actor == "publico"
    assert e.antes is None
    assert e.despues == "PENDIENTE"
    assert set(dataclasses.asdict(e)) == _CAMPOS_AUDITORIA  # sin nombre ni teléfono


def test_cancelacion_publica_audita_antes_y_despues():
    h = _harness(("2026-10-20", 9, 0))
    body = reservar(h, inicio="2026-10-21T09:00:00+00:00").json()
    token = body["token_publico"]
    vid = emitir(h, accion="cancelar")
    r = h.client.post(
        f"/api/publico/t1/reservas/{token}/cancelacion", json={"verificacion_id": vid}
    )
    assert r.status_code == 200
    (e,) = [x for x in h.auditoria.entradas if x.turno_id == body["turno_id"] and x.accion == "CANCELADO"]
    assert (e.antes, e.despues) == ("PENDIENTE", "CANCELADO")


def test_reprogramacion_publica_audita_antes_y_despues():
    h = _harness(("2026-10-20", 9, 0))
    body = reservar(h, inicio="2026-10-21T10:00:00+00:00").json()
    token = body["token_publico"]
    vid = emitir(h, accion="reprogramar")
    r = h.client.post(
        f"/api/publico/t1/reservas/{token}/reprogramacion",
        json={"nuevo_inicio": "2026-10-21T14:00:00+00:00", "verificacion_id": vid},
    )
    assert r.status_code == 200
    nuevo_id = r.json()["nuevo"]["turno_id"]
    (e,) = [x for x in h.auditoria.entradas if x.turno_id == body["turno_id"] and x.accion == "REPROGRAMADO"]
    assert (e.antes, e.despues) == ("PENDIENTE", "REPROGRAMADO")
    (creado,) = [x for x in h.auditoria.entradas if x.turno_id == nuevo_id and x.accion == "CREADO"]
    assert creado.antes is None and creado.despues == "PENDIENTE"


def test_rechazo_bajo_umbral_deja_entrada_sin_phi():
    h = _harness(("2026-10-20", 9, 1))  # 23h59m antes del turno
    body = reservar(h, inicio="2026-10-21T09:00:00+00:00").json()
    token = body["token_publico"]

    vid = emitir(h, accion="cancelar")
    r = h.client.post(
        f"/api/publico/t1/reservas/{token}/cancelacion", json={"verificacion_id": vid}
    )
    assert r.status_code == 403
    (e,) = [x for x in h.auditoria.entradas if x.turno_id == body["turno_id"] and x.accion == "CANCELACION_RECHAZADA"]
    assert e.motivo == "BAJO_ANTICIPACION"
    assert e.antes == e.despues == "PENDIENTE"
    assert set(dataclasses.asdict(e)) == _CAMPOS_AUDITORIA

    vid2 = emitir(h, accion="reprogramar")
    r2 = h.client.post(
        f"/api/publico/t1/reservas/{token}/reprogramacion",
        json={"nuevo_inicio": "2026-10-21T14:00:00+00:00", "verificacion_id": vid2},
    )
    assert r2.status_code == 403
    (e2,) = [x for x in h.auditoria.entradas if x.turno_id == body["turno_id"] and x.accion == "REPROGRAMACION_RECHAZADA"]
    assert e2.motivo == "BAJO_ANTICIPACION"
    assert e2.antes == e2.despues == "PENDIENTE"


def test_auditoria_no_expone_metodo_de_borrado():
    h = _harness()
    assert not hasattr(h.auditoria, "delete")
    assert not hasattr(h.auditoria, "update")
    assert not hasattr(h.auditoria, "borrar")
    for metodo in ("delete", "update", "borrar", "editar"):
        assert not hasattr(AuditoriaPort, metodo)
