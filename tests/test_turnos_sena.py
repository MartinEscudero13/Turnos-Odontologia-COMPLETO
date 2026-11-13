"""Task 6.18 — un turno en un estado final no se confirma ni se cancela por la seña.

La vía de la seña (`TurnoPort.confirmar_por_sena` / `cancelar_por_sena`) es una
extensión mínima de C-05: sólo actúa desde `PENDIENTE`. Un turno `PRESENTE` (o
`AUSENTE`, `CANCELADO`, `REPROGRAMADO`) responde `409` y no cambia de estado ni
emite hueco (F-21): la plata de la seña no puede "confirmar" algo que ya pasó.
"""
from __future__ import annotations

import pytest
from _senas_helpers import AHORA, TUR1, HarnessSenaCiclo
from conftest import T1

from app.senas.puertos import TransicionTurnoInvalida


def test_turno_presente_no_se_confirma_ni_cancela_por_sena() -> None:
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(turno_estado="PRESENTE")

    for accion in ("confirmar", "cancelar"):
        with pytest.raises(TransicionTurnoInvalida) as excinfo:
            if accion == "confirmar":
                h.turnos.confirmar_por_sena(tenant_id=T1, turno_id=TUR1, ahora=AHORA)
            else:
                h.turnos.cancelar_por_sena(
                    tenant_id=T1,
                    turno_id=TUR1,
                    motivo="SENA_NO_ACREDITADA",
                    ahora=AHORA,
                )
        assert excinfo.value.codigo == 409
        assert excinfo.value.codigo_dominio == "TRANSICION_TURNO_INVALIDA"

    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "PRESENTE"
    assert h.sena(sena).estado == "PENDIENTE"
    assert h.eventos_hueco() == []


def test_webhook_acredita_sin_confirmar_un_turno_presente() -> None:
    """El pago de un turno que ya ocurrió se retiene; el estado del turno no cambia."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(turno_estado="PRESENTE")

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-8")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "ACREDITADA"
    assert h.sena(sena).estado == "ACREDITADA"
    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "PRESENTE"
    assert h.eventos_hueco() == []
