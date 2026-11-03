"""Fixtures y bootstrap de import para la suite C-05 (reimplementación Python).

Agrega `backend/` al `sys.path` para importar `app.*` sin packaging.
Todos los datos son ficticios (regla dura: NUNCA datos reales de pacientes).
"""
from __future__ import annotations

import sys
from datetime import UTC
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def dt(dia: str = "2026-10-06", hora: int = 10, minuto: int = 0):
    """Datetime aware UTC ficticio para los tests."""
    from datetime import datetime as _dt

    y, m, d = (int(x) for x in dia.split("-"))
    return _dt(y, m, d, hora, minuto, tzinfo=UTC)


T1 = "a0000000-0000-4000-8000-000000000001"
T2 = "a0000000-0000-4000-8000-000000000002"
P1 = "profesional-1"
P2 = "profesional-2"
S1 = "sillon-1"
S2 = "sillon-2"
PAC1 = "paciente-1"
PREST30 = "prestacion-30min"
