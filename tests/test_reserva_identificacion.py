"""Tasks 2.2–2.4 — identificación liviana por teléfono (RN-RE-05): RED primero."""
from __future__ import annotations

from _reserva_helpers import Harness, catalogo_estandar, reservar
from conftest import PAC1, T1, dt

from app.reservas.puertos import Paciente
from app.turnos.servicio import Actor

TEL_NUEVO = "+5491100000000"


def _harness() -> Harness:
    h = Harness(reloj_inicial=dt("2026-10-05", 9))
    catalogo_estandar(h)
    return h


def _turnos_de(h: Harness, tenant: str = T1) -> list:
    return h.turnos.listar(Actor(tenant_id=tenant, rol="RECEPCION", user_id="x"))


def test_telefono_nuevo_crea_paciente_y_turno():
    h = _harness()
    r = reservar(h, telefono=TEL_NUEVO)
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "PENDIENTE"
    assert h.pacientes.total(T1) == 1
    turnos = _turnos_de(h)
    assert len(turnos) == 1
    assert turnos[0].paciente_id == h.pacientes.buscar_por_telefono(T1, TEL_NUEVO).id


def test_telefono_existente_vincula_sin_duplicar():
    h = _harness()
    h.pacientes.agregar(
        Paciente(id=PAC1, tenant_id=T1, nombre="Paciente Demo", telefono=TEL_NUEVO)
    )
    r = reservar(h, telefono=TEL_NUEVO)
    assert r.status_code == 201, r.text
    assert h.pacientes.total(T1) == 1
    turno = _turnos_de(h)[0]
    assert turno.paciente_id == PAC1


def test_telefono_invalido_responde_422_sin_crear_paciente_ni_turno():
    h = _harness()
    r = reservar(h, telefono="no-es-un-telefono")
    assert r.status_code == 422, r.text
    assert h.pacientes.total(T1) == 0
    assert _turnos_de(h) == []
