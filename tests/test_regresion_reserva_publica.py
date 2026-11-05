"""Tasks 10.1–10.2 — regresión: C-05 intacto y reuso (no copia): RED primero."""
from __future__ import annotations

import pytest
from _reserva_helpers import Harness, catalogo_estandar
from conftest import P1, PAC1, PREST30, S1, T1, dt

from app.turnos.servicio import Actor, ConflictoSolape, ServicioTurnos


def test_creacion_por_recepcion_no_requiere_token_publico():
    svc = ServicioTurnos()
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="recep-1")
    t = svc.crear(
        actor, profesional_id=P1, sillon_id=S1, paciente_id=PAC1, prestacion_id=PREST30,
        inicio=dt(hora=10), duracion_min=30, origen="RECEPCION",
    )
    assert t.estado == "PENDIENTE"
    assert t.origen == "RECEPCION"
    assert not hasattr(t, "token_publico")  # C-05 intacto: el turno no lleva token


def test_reserva_publica_reusa_anticipacion_y_alternativas_de_c05():
    h = Harness(reloj_inicial=dt("2026-10-05", 9), anticipacion_min_horas=48.0)
    catalogo_estandar(h)
    # mismo constructor ServicioTurnos(anticipacion_min_horas=...)
    assert isinstance(h.svc.servicio_turnos, ServicioTurnos)
    assert h.svc.servicio_turnos._anticipacion_min_horas == 48.0

    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="x")
    h.turnos.crear(
        actor, profesional_id=P1, sillon_id=S1, paciente_id="p", prestacion_id="PREST-30",
        inicio=dt("2026-10-06", 10), duracion_min=30,
    )
    d = h.svc.emitir_verificacion("t1", "reservar", "ip")
    with pytest.raises(ConflictoSolape) as exc:
        h.svc.reservar(
            "t1", prestacion_id="PREST-30", profesional_id=P1, inicio=dt("2026-10-06", 10),
            nombre="Paciente Demo", telefono="+5491130551234",
            verificacion_id=d.verificacion_id, ip="ip",
        )
    assert 0 < len(exc.value.alternativas) <= 3
