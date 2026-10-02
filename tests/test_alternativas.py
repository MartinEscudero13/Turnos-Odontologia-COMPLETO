"""Task 1.3 — selector de 3 alternativas ante 409: RED primero."""
from __future__ import annotations

from app.turnos.alternativas import HuecoOcupado, buscar_alternativas
from conftest import P1, P2, S1, S2, T1, T2, dt


def ocupado(inicio, fin, tenant=T1, prof=P1, sillon=S1, estado="PENDIENTE", sobre=False):
    return HuecoOcupado(
        tenant_id=tenant,
        profesional_id=prof,
        sillon_id=sillon,
        inicio=inicio,
        fin=fin,
        estado=estado,
        sobreturno=sobre,
    )


def test_hueco_libre_devuelve_tres_desde_exacto():
    alts = buscar_alternativas(dt(hora=10), 30, T1, P1, S1, [])
    assert len(alts) == 3
    assert alts[0].inicio == dt(hora=10)
    assert alts[0].fin == dt(hora=10, minuto=30)
    assert [a.inicio for a in alts] == sorted(a.inicio for a in alts)


def test_hueco_ocupado_se_salta():
    occ = [ocupado(dt(hora=10), dt(hora=10, minuto=30))]
    alts = buscar_alternativas(dt(hora=10), 30, T1, P1, S1, occ)
    assert len(alts) == 3
    assert all(a.inicio >= dt(hora=10, minuto=30) for a in alts)


def test_otro_tenant_no_bloquea():
    occ = [ocupado(dt(hora=10), dt(hora=11), tenant=T2)]
    alts = buscar_alternativas(dt(hora=10), 30, T1, P1, S1, occ)
    assert alts[0].inicio == dt(hora=10)


def test_cancelado_y_sobreturno_no_bloquean():
    occ = [
        ocupado(dt(hora=10), dt(hora=11), estado="CANCELADO"),
        ocupado(dt(hora=10), dt(hora=11), sobre=True),
    ]
    alts = buscar_alternativas(dt(hora=10), 30, T1, P1, S1, occ)
    assert alts[0].inicio == dt(hora=10)


def test_bloqueos_rentan_disponibilidad():
    bloqueos = [(dt(hora=10), dt(hora=12))]
    alts = buscar_alternativas(dt(hora=10), 30, T1, P1, S1, [], bloqueos=bloqueos)
    assert all(a.inicio >= dt(hora=12) for a in alts)


def test_otro_profesional_y_otro_sillon_no_bloquea():
    occ = [ocupado(dt(hora=10), dt(hora=11), prof=P2, sillon=S2)]
    alts = buscar_alternativas(dt(hora=10), 30, T1, P1, S1, occ)
    assert alts[0].inicio == dt(hora=10)


def test_reprogramado_no_bloquea():
    occ = [ocupado(dt(hora=10), dt(hora=11), estado="REPROGRAMADO")]
    alts = buscar_alternativas(dt(hora=10), 30, T1, P1, S1, occ)
    assert alts[0].inicio == dt(hora=10)


def test_agenda_saturada_devuelve_menos_de_tres():
    # Un turno gigante bloquea todo el horizonte de 30 días.
    from datetime import timedelta

    hasta = dt(hora=10) + timedelta(days=31)
    occ = [ocupado(dt(hora=10), hasta)]
    alts = buscar_alternativas(dt(hora=10), 30, T1, P1, S1, occ)
    assert alts == []
