"""Cálculo de fin de turno — task 1.2 (D3).

fin = inicio + prestacion.duracion_min, calculado servidor-side.
El fin del cliente se ignora/valida: solo es válido si coincide EXACTO.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def calcular_fin(inicio: datetime, duracion_min: int) -> datetime:
    """Calcula fin servidor-side. Falla con ValueError si duración inválida."""
    if not isinstance(duracion_min, int) or isinstance(duracion_min, bool) or duracion_min <= 0:
        raise ValueError(f"duracion_min inválida: {duracion_min!r}")
    return inicio + timedelta(minutes=duracion_min)


def fin_cliente_valido(inicio: datetime, duracion_min: int, fin_cliente: datetime) -> bool:
    """True solo si el fin provisto coincide EXACTO con el cálculo servidor-side."""
    return calcular_fin(inicio, duracion_min) == fin_cliente
