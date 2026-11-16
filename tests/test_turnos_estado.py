"""Regresión de las transiciones de agenda usadas por la UI y C-13."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.turnos.servicio import Actor, Invalido, ServicioTurnos


def _turno(svc: ServicioTurnos, *, offset_min: int = 0) -> str:
    return svc.crear(
        Actor(tenant_id="t1", rol="RECEPCION", user_id="u1"),
        profesional_id="prof-1",
        sillon_id="sillon-1",
        paciente_id="pac-1",
        prestacion_id="Consulta",
        inicio=datetime.now(UTC) + timedelta(days=2, minutes=offset_min),
        duracion_min=30,
    ).id


def test_confirmar_presente_y_ausente() -> None:
    svc = ServicioTurnos()
    turno_id = _turno(svc)
    actor = Actor(tenant_id="t1", rol="RECEPCION", user_id="u1")

    assert svc.confirmar(actor, turno_id).estado == "CONFIRMADO"
    assert svc.marcar_presente(actor, turno_id).estado == "PRESENTE"

    otro = _turno(svc, offset_min=60)
    svc.confirmar(actor, otro)
    assert svc.marcar_ausente(actor, otro).estado == "AUSENTE"
    # `crear` sólo audita sobreturnos: el rastro contiene las transiciones.
    acciones = [e.accion for e in svc.auditoria(actor)]
    assert acciones == ["CONFIRMADO", "PRESENTE", "CONFIRMADO", "AUSENTE"]
    presentes = [e for e in svc.auditoria(actor) if e.accion == "PRESENTE"]
    assert presentes[0].antes == "CONFIRMADO"
    assert presentes[0].despues == "PRESENTE"


def test_no_se_marca_presente_sin_confirmar() -> None:
    svc = ServicioTurnos()
    turno_id = _turno(svc)

    with pytest.raises(Invalido):
        svc.marcar_presente(
            Actor(tenant_id="t1", rol="RECEPCION", user_id="u1"), turno_id
        )
