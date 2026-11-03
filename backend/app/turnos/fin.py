"""Cálculo de fin de turno — task 1.2 (D3).

fin = inicio + prestacion.duracion_min, calculado servidor-side.
El fin del cliente se ignora/valida: solo es válido si coincide EXACTO.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def _positive_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"duracion_min inválida: {value!r}")
    return value


def calcular_fin(inicio: datetime, duracion_min: object) -> datetime:
    """Calcula fin servidor-side. Falla con ValueError si duración inválida."""
    minutes = _positive_int(duracion_min)
    return inicio + timedelta(minutes=minutes)


def fin_cliente_valido(inicio: datetime, duracion_min: object, fin_cliente: datetime) -> bool:
    """True solo si el fin provisto coincide EXACTO con el cálculo servidor-side."""
    return calcular_fin(inicio, duracion_min) == fin_cliente
