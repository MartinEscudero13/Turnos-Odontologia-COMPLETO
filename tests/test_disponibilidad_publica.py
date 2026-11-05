"""Tasks 1.1–1.5 — disponibilidad pública server-side (D1): RED primero."""
from __future__ import annotations

from datetime import time, timedelta

from conftest import P1, S1, S2, T1, dt

from app.reservas.disponibilidad import calcular_disponibilidad
from app.reservas.puertos import Bloqueo, HorarioSemanal, Prestacion, Profesional, Sillon
from app.turnos.alternativas import HuecoOcupado
from app.turnos.overlap import intervalos_solapan

DIA_MAR = dt("2026-10-06", 9).weekday() + 1  # 2026-10-06 es martes


def _prestacion(pid: str = "PREST-30", duracion: int = 30) -> Prestacion:
    return Prestacion(id=pid, tenant_id=T1, duracion_min=duracion)


def _prof() -> Profesional:
    return Profesional(id=P1, tenant_id=T1)


def _sillones() -> list[Sillon]:
    return [Sillon(id=S1, tenant_id=T1), Sillon(id=S2, tenant_id=T1)]


def _horario_prof(desde: int = 9, hasta: int = 12, dia: int = DIA_MAR) -> list[HorarioSemanal]:
    return [HorarioSemanal(tenant_id=T1, dia=dia, desde=time(desde, 0), hasta=time(hasta, 0), profesional_id=P1)]


def _horario_con(desde: int = 8, hasta: int = 18, dia: int = DIA_MAR) -> list[HorarioSemanal]:
    return [HorarioSemanal(tenant_id=T1, dia=dia, desde=time(desde, 0), hasta=time(hasta, 0), profesional_id=None)]


def _ocupado(inicio_h: int, inicio_m: int, fin_h: int, fin_m: int, sillon: str = S1) -> HuecoOcupado:
    return HuecoOcupado(
        tenant_id=T1, profesional_id=P1, sillon_id=sillon,
        inicio=dt(hora=inicio_h, minuto=inicio_m), fin=dt(hora=fin_h, minuto=fin_m),
        estado="PENDIENTE", sobreturno=False,
    )


def _calcular(duracion: int = 30, **overrides) -> list:
    kwargs = dict(
        prestacion=_prestacion(duracion=duracion),
        profesional=_prof(),
        sillones=_sillones(),
        desde=dt("2026-10-06", 0),
        ahora=dt("2026-10-05", 9),
        horario_profesional=_horario_prof(),
        horario_consultorio=_horario_con(),
        bloqueos=[],
        ocupados=[],
        horizonte_dias=1,
    )
    kwargs.update(overrides)
    return calcular_disponibilidad(**kwargs)


def test_disponibilidad_excluye_turnos_ocupados():
    slots = _calcular(ocupados=[_ocupado(10, 0, 10, 30)])
    assert slots, "debe haber huecos"
    turno = (dt(hora=10), dt(hora=10, minuto=30))
    for s in slots:
        assert not intervalos_solapan(s.inicio, s.fin, *turno)
        assert s.fin == s.inicio + timedelta(minutes=30)
    inicios = {s.inicio for s in slots}
    assert dt(hora=9) in inicios
    assert dt(hora=10, minuto=30) in inicios


def test_disponibilidad_resta_bloqueos():
    bloqueo = Bloqueo(tenant_id=T1, desde=dt("2026-10-07", 9), hasta=dt("2026-10-07", 12), profesional_id=P1)
    slots = _calcular(
        desde=dt("2026-10-07", 0),
        horario_profesional=_horario_prof(dia=dt("2026-10-07", 9).weekday() + 1),
        horario_consultorio=_horario_con(dia=dt("2026-10-07", 9).weekday() + 1),
        bloqueos=[bloqueo],
    )
    assert slots == []


def test_disponibilidad_fuera_de_interseccion_es_vacia():
    dia = dt("2026-10-08", 9).weekday() + 1
    slots = _calcular(
        desde=dt("2026-10-08", 0),
        horario_profesional=_horario_prof(desde=14, hasta=18, dia=dia),
        horario_consultorio=_horario_con(desde=9, hasta=13, dia=dia),
    )
    assert slots == []


def test_disponibilidad_usa_duracion_de_prestacion():
    slots = _calcular(duracion=45, prestacion=_prestacion("PREST-45", 45))
    primero = min(slots, key=lambda s: s.inicio)
    assert primero.inicio == dt(hora=9)
    assert primero.fin == dt(hora=9, minuto=45)


def test_disponibilidad_paridad_predicado_c05():
    slots = _calcular(ocupados=[_ocupado(10, 0, 10, 30)])
    inicios = {s.inicio for s in slots}
    # adyacencia exacta (fin_A == inicio_B) NO es solape → se ofrece
    assert dt(hora=10, minuto=30) in inicios
    # solape parcial → no se ofrece
    assert dt(hora=10) not in inicios
    assert dt(hora=10, minuto=15) not in inicios
    # sin contacto → se ofrece
    assert dt(hora=11) in inicios
