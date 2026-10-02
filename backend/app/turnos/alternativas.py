"""Selector de N alternativas ante 409 — task 1.3 (RN-GL-02).

Grilla de 15 min desde `desde` (primer candidato = `desde` exacto),
orden cronológico, ≤ cantidad, horizonte 30 días.
Un turno existente bloquea solo si: mismo tenant, mismo profesional
O mismo sillón, estado activo y no es sobreturno (predicado del EXCLUDE 003).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.turnos.fin import calcular_fin
from app.turnos.overlap import intervalos_solapan

PASO_MINUTOS = 15
HORIZONTE_DIAS = 30


@dataclass(frozen=True)
class HuecoOcupado:
    """Turno existente proyectado a intervalo (tenant + recurso + estado)."""

    tenant_id: str
    profesional_id: str
    sillon_id: str
    inicio: datetime
    fin: datetime
    estado: str
    sobreturno: bool


@dataclass(frozen=True)
class Alternativa:
    """Hueco libre propuesto (datetimes aware; el borde API serializa ISO)."""

    inicio: datetime
    fin: datetime


def es_bloqueante(
    o: HuecoOcupado, tenant_id: str, profesional_id: str, sillon_id: str
) -> bool:
    """True si el turno existente bloquea el recurso pedido (predicado EXCLUDE)."""
    from app.turnos.estados import ESTADOS_NO_BLOQUEANTES

    if o.tenant_id != tenant_id:
        return False
    if o.profesional_id != profesional_id and o.sillon_id != sillon_id:
        return False
    if o.estado in ESTADOS_NO_BLOQUEANTES:
        return False
    if o.sobreturno:
        return False
    return True


def buscar_alternativas(
    desde: datetime,
    duracion_min: int,
    tenant_id: str,
    profesional_id: str,
    sillon_id: str,
    ocupados: list[HuecoOcupado] | tuple[HuecoOcupado, ...],
    bloqueos: list[tuple[datetime, datetime]] | tuple[tuple[datetime, datetime], ...] = (),
    cantidad: int = 3,
) -> list[Alternativa]:
    """Primeros `cantidad` huecos libres en grilla de 15 min desde `desde`."""
    relevantes = [o for o in ocupados if es_bloqueante(o, tenant_id, profesional_id, sillon_id)]
    resultado: list[Alternativa] = []
    limite = desde + timedelta(days=HORIZONTE_DIAS)
    cursor = desde
    paso = timedelta(minutes=PASO_MINUTOS)
    while len(resultado) < cantidad and cursor < limite:
        fin = calcular_fin(cursor, duracion_min)
        choca = any(intervalos_solapan(cursor, fin, o.inicio, o.fin) for o in relevantes)
        choca = choca or any(intervalos_solapan(cursor, fin, b_i, b_f) for b_i, b_f in bloqueos)
        if not choca:
            resultado.append(Alternativa(inicio=cursor, fin=fin))
        cursor = cursor + paso
    return resultado
