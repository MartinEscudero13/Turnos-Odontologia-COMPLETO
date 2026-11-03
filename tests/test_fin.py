"""Task 1.2 — fin = inicio + duracion_min (servidor-side): RED primero."""
from __future__ import annotations

import pytest
from conftest import dt

from app.turnos.fin import calcular_fin, fin_cliente_valido


def test_fin_30_min():
    assert calcular_fin(dt(hora=10), 30) == dt(hora=10, minuto=30)


def test_fin_45_min():
    assert calcular_fin(dt(hora=9), 45) == dt(hora=9, minuto=45)


def test_fin_60_min_cruza_hora():
    assert calcular_fin(dt(hora=10, minuto=30), 60) == dt(hora=11, minuto=30)


def test_duracion_invalida_falla():
    with pytest.raises(ValueError):
        calcular_fin(dt(hora=10), 0)
    with pytest.raises(ValueError):
        calcular_fin(dt(hora=10), -15)


def test_fin_cliente_exacta_es_valida():
    assert fin_cliente_valido(dt(hora=10), 30, dt(hora=10, minuto=30)) is True


def test_fin_cliente_distinta_se_rechaza():
    assert fin_cliente_valido(dt(hora=10), 30, dt(hora=10, minuto=45)) is False


def test_duracion_bool_se_rechaza():
    # bool es subclase de int: True no puede ser duración válida.
    with pytest.raises(ValueError):
        calcular_fin(dt(hora=10), True)


def test_fin_cruza_medianoche():
    assert calcular_fin(dt("2026-10-06", 23, 45), 30) == dt("2026-10-07", 0, 15)
