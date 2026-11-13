"""Task 6.13 — aislamiento multi-tenant del odontograma (D7).

Leer, resolver y derivar un hallazgo/paciente de T1 desde T2 responde `404` y no
muta nada: el repositorio recibe `tenant_id` explícito y un id de T2 nunca
resuelve en T1.
"""
from __future__ import annotations

import pytest
from _odontograma_helpers import KEY, PAC1, PREST1, HarnessOdontograma, actor, d3
from conftest import T1, T2

from app.turnos.servicio import NoEncontrado


def test_operaciones_de_t1_no_tocan_t2():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    hallazgo = h.svc.registrar_hallazgo(
        actor("ADMIN", user_id="admin-1"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id="profesional-1",
    )

    with pytest.raises(NoEncontrado):
        h.svc.listar_historial(
            actor("ADMIN", tenant=T2), paciente_id=PAC1, pieza_fdi=36
        )
    with pytest.raises(NoEncontrado):
        h.svc.resolver(actor("ADMIN", tenant=T2), hallazgo_id=hallazgo.id)
    with pytest.raises(NoEncontrado):
        h.svc.derivar(
            actor("ADMIN", tenant=T2),
            paciente_id=PAC1,
            pieza_fdi=36,
            hallazgo="caries oclusal",
            fecha=d3(),
            prestacion_id=PREST1,
            idempotency_key=KEY,
        )

    persistido = h.hallazgos.obtener(tenant_id=T1, hallazgo_id=hallazgo.id)
    assert persistido is not None and persistido.resuelto is False
    assert h.hallazgos.total(T2) == 0
    assert h.lineas.total(T2) == 0
    assert h.presupuestos.total(T2) == 0
    assert h.auditoria.de_tenant(T2) == []
