"""Máquina de estados del turno — task 1.4.

PENDIENTE → CONFIRMADO → PRESENTE / AUSENTE,
PENDIENTE / CONFIRMADO → CANCELADO / REPROGRAMADO (finales que liberan hueco).
"""
from __future__ import annotations

from typing import Literal

EstadoTurno = Literal[
    "PENDIENTE", "CONFIRMADO", "PRESENTE", "AUSENTE", "CANCELADO", "REPROGRAMADO"
]

ESTADOS_NO_BLOQUEANTES: frozenset[str] = frozenset({"CANCELADO", "REPROGRAMADO"})

_TRANSICIONES: dict[str, tuple[str, ...]] = {
    "PENDIENTE": ("CONFIRMADO", "CANCELADO", "REPROGRAMADO"),
    "CONFIRMADO": ("PRESENTE", "AUSENTE", "CANCELADO", "REPROGRAMADO"),
    "PRESENTE": (),
    "AUSENTE": (),
    "CANCELADO": (),
    "REPROGRAMADO": (),
}


def transicion_valida(desde: EstadoTurno, hacia: EstadoTurno) -> bool:
    """True si la transición de estado está permitida."""
    return hacia in _TRANSICIONES[desde]


def libera_hueco(estado: EstadoTurno) -> bool:
    """True si el estado es final y su hueco vuelve a estar disponible."""
    return estado in ESTADOS_NO_BLOQUEANTES
