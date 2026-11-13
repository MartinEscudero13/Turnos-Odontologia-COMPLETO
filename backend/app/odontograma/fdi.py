"""Validación de la grilla FDI permanente — C-09 D1.

v1 valida sólo dentición permanente: cuadrante `1..4` (decena) × diente `1..8`
(unidad) = 32 posiciones. `19/29/39`, `10/20/30/40`, `49`, `00` y cualquier
valor no entero se rechazan con `422`; la migración 007 impone el mismo CHECK en
la base para que un INSERT directo no pueda saltarse la regla.
"""
from __future__ import annotations

from app.turnos.servicio import Invalido

MENSAJE_FDI_INVALIDA = (
    "pieza FDI inválida: cuadrante 1–4 y diente 1–8 (11–18, 21–28, 31–38, 41–48)"
)
MENSAJE_MONTO_INVALIDO = "monto inválido: se espera un entero de centavos >= 0"

GRILLA_FDI: frozenset[int] = frozenset(
    {cuadrante * 10 + diente for cuadrante in range(1, 5) for diente in range(1, 9)}
)

__all__ = [
    "GRILLA_FDI",
    "MENSAJE_FDI_INVALIDA",
    "MENSAJE_MONTO_INVALIDO",
    "validar_monto",
    "validar_pieza_fdi",
]


def validar_pieza_fdi(valor: object) -> int:
    """Devuelve la pieza FDI válida o lanza `Invalido` (422) sin persistir nada."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor not in GRILLA_FDI:
        raise Invalido(MENSAJE_FDI_INVALIDA)
    return valor


def validar_monto(valor: object) -> int:
    """Valida un monto en centavos enteros no negativo (422 si no lo es)."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise Invalido(MENSAJE_MONTO_INVALIDO)
    return valor
