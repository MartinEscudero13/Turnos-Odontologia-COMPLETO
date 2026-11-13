"""Task 6.14 — aislamiento multi-tenant del presupuesto (D7).

Leer, aceptar e imputar un presupuesto/línea de T1 desde T2 responde `404`, sin
registrar aceptación en T2 ni imputar nada; una aceptación de T1 no se hereda en
T2 aunque el identificador coincida.
"""
from __future__ import annotations

import pytest
from _odontograma_helpers import actor, d3
from _presupuesto_helpers import HarnessPresupuesto, presupuesto_vigente, registrar_aceptacion
from conftest import T1, T2

from app.turnos.servicio import NoEncontrado


def test_leer_aceptar_e_imputar_de_otro_tenant_404():
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h)
    linea_id = lineas[0]

    with pytest.raises(NoEncontrado):
        h.svc.obtener(actor("RECEPCION", tenant=T2), presupuesto_id=presupuesto_id)
    with pytest.raises(NoEncontrado):
        registrar_aceptacion(
            h,
            presupuesto_id,
            linea_id,
            actor_=actor("RECEPCION", tenant=T2),
        )

    assert h.aceptaciones.total(T2) == 0
    assert h.aceptaciones.total(T1) == 0
    assert h.imputacion.llamadas_caja == []
    assert h.imputacion.llamadas_agenda == []

    # La aceptación de T1 no se hereda en T2: el mismo id sigue siendo 404.
    registrar_aceptacion(h, presupuesto_id, linea_id, ahora=d3("2026-11-10", 11))
    assert h.aceptaciones.total(T1) == 1
    with pytest.raises(NoEncontrado):
        h.svc.obtener(actor("RECEPCION", tenant=T2), presupuesto_id=presupuesto_id)
