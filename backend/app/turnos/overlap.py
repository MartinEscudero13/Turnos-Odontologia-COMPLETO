"""Predicado de solape half-open [inicio, fin) — task 1.1.

Adyacencia exacta (fin_A == inicio_B) NO es solape por construcción.
Espeja el operador `&&` sobre `tstzrange(inicio, fin)` del EXCLUDE 003.
"""
from __future__ import annotations

from datetime import datetime


def intervalos_solapan(
    a_inicio: datetime, a_fin: datetime, b_inicio: datetime, b_fin: datetime
) -> bool:
    """True si los intervalos half-open se intersectan con duración > 0."""
    # Rango vacío [t, t): en PG tstzrange es empty y && da false.
    if a_inicio >= a_fin:
        return False
    if b_inicio >= b_fin:
        return False
    return a_inicio < b_fin and b_inicio < a_fin
