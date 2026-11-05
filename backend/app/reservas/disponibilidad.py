"""Disponibilidad pública server-side — tasks 1.1→1.5 (D1).

Huecos reales = intersección(horario profesional, horario consultorio) − bloqueos −
turnos activos, con grilla `PASO_MINUTOS` (15 min) y `fin = calcular_fin(inicio,
duracion_min)`. Reusa el predicado de solape de C-05 (`es_bloqueante`) y
`intervalos_solapan` para paridad exacta de comportamiento (CA-G1).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.reservas.puertos import Bloqueo, HorarioSemanal, Prestacion, Profesional, Sillon
from app.turnos.alternativas import PASO_MINUTOS, HuecoOcupado, es_bloqueante
from app.turnos.fin import calcular_fin
from app.turnos.overlap import intervalos_solapan


@dataclass(frozen=True)
class DisponibilidadSlot:
    """Hueco libre ofrecido al público (sin datos de terceros: RN-CL-04)."""

    inicio: datetime
    fin: datetime
    profesional_id: str
    sillon_id: str


def _dia_semana(d: datetime) -> int:
    return d.weekday() + 1  # Lunes=1 .. Domingo=7


def _intervalos_dia(
    dia: datetime,
    dia_semana: int,
    horario_profesional: Sequence[HorarioSemanal],
    horario_consultorio: Sequence[HorarioSemanal],
) -> list[tuple[datetime, datetime]]:
    """Intersección (en datetimes absolutos) de los horarios de ese día."""
    inicio_dia = dia.replace(hour=0, minute=0, second=0, microsecond=0)
    pro = [
        (
            inicio_dia.replace(hour=h.desde.hour, minute=h.desde.minute),
            inicio_dia.replace(hour=h.hasta.hour, minute=h.hasta.minute),
        )
        for h in horario_profesional
        if h.dia == dia_semana
    ]
    con = [
        (
            inicio_dia.replace(hour=h.desde.hour, minute=h.desde.minute),
            inicio_dia.replace(hour=h.hasta.hour, minute=h.hasta.minute),
        )
        for h in horario_consultorio
        if h.dia == dia_semana
    ]
    if not pro or not con:
        return []
    resultado: list[tuple[datetime, datetime]] = []
    for ps, pe in pro:
        for cs, ce in con:
            s = max(ps, cs)
            e = min(pe, ce)
            if s < e:
                resultado.append((s, e))
    return resultado


def _bloqueo_aplica(b: Bloqueo, profesional_id: str, sillon_id: str) -> bool:
    profesional_ok = b.profesional_id is None or b.profesional_id == profesional_id
    sillon_ok = b.sillon_id is None or b.sillon_id == sillon_id
    return profesional_ok and sillon_ok


def calcular_disponibilidad(
    *,
    prestacion: Prestacion,
    profesional: Profesional,
    sillones: Sequence[Sillon],
    desde: datetime,
    ahora: datetime,
    horario_profesional: Sequence[HorarioSemanal],
    horario_consultorio: Sequence[HorarioSemanal],
    bloqueos: Sequence[Bloqueo],
    ocupados: Sequence[HuecoOcupado],
    horizonte_dias: int,
) -> list[DisponibilidadSlot]:
    """Huecos reales para un profesional, en orden cronológico.

    La ventana arranca en `max(desde, ahora)` (nunca ofrece huecos pasados) y se
    extiende `horizonte_dias` días.
    """
    inicio_ventana = max(desde, ahora)
    fin_ventana = inicio_ventana + timedelta(days=horizonte_dias)
    duracion_td = timedelta(minutes=prestacion.duracion_min)
    paso = timedelta(minutes=PASO_MINUTOS)
    tenant_id = prestacion.tenant_id

    slots: list[DisponibilidadSlot] = []
    dia = inicio_ventana
    while dia < fin_ventana:
        dia_semana = _dia_semana(dia)
        intervalos = _intervalos_dia(dia, dia_semana, horario_profesional, horario_consultorio)
        for sillon in sillones:
            if not sillon.activo:
                continue
            for istart, iend in intervalos:
                cursor = istart
                while cursor + duracion_td <= iend:
                    if cursor < inicio_ventana:
                        cursor += paso
                        continue
                    fin = calcular_fin(cursor, prestacion.duracion_min)
                    choca_bloqueo = any(
                        _bloqueo_aplica(b, profesional.id, sillon.id)
                        and intervalos_solapan(cursor, fin, b.desde, b.hasta)
                        for b in bloqueos
                    )
                    choca_ocupado = any(
                        es_bloqueante(o, tenant_id, profesional.id, sillon.id)
                        and intervalos_solapan(cursor, fin, o.inicio, o.fin)
                        for o in ocupados
                    )
                    if not choca_bloqueo and not choca_ocupado:
                        slots.append(
                            DisponibilidadSlot(
                                inicio=cursor,
                                fin=fin,
                                profesional_id=profesional.id,
                                sillon_id=sillon.id,
                            )
                        )
                    cursor += paso
        dia += timedelta(days=1)

    slots.sort(key=lambda s: (s.inicio, s.profesional_id, s.sillon_id))
    return slots
