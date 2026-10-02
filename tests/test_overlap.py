"""Task 1.1 — overlap() half-open [inicio, fin): RED primero."""
from __future__ import annotations

from app.turnos.overlap import intervalos_solapan

from conftest import dt


def test_solape_parcial():
    a_i, a_f = dt(hora=10), dt(hora=10, minuto=30)
    assert intervalos_solapan(a_i, a_f, dt(hora=10, minuto=15), dt(hora=10, minuto=45)) is True


def test_solape_total_contenido():
    a_i, a_f = dt(hora=10), dt(hora=11)
    assert intervalos_solapan(a_i, a_f, dt(hora=10, minuto=15), dt(hora=10, minuto=45)) is True


def test_adyacencia_exacta_no_es_solape():
    # fin_A == inicio_B → permitido (rango half-open).
    assert intervalos_solapan(dt(hora=10), dt(hora=10, minuto=30), dt(hora=10, minuto=30), dt(hora=11)) is False


def test_sin_contacto_no_solapa():
    assert intervalos_solapan(dt(hora=10), dt(hora=10, minuto=30), dt(hora=11), dt(hora=11, minuto=30)) is False


def test_mismo_intervalo_solapa():
    assert intervalos_solapan(dt(hora=10), dt(hora=10, minuto=30), dt(hora=10), dt(hora=10, minuto=30)) is True


def test_rango_vacio_no_solapa():
    # [t, t) es empty en PG: && da false aunque caiga dentro de otro.
    assert intervalos_solapan(dt(hora=10), dt(hora=10), dt(hora=9), dt(hora=11)) is False
    assert intervalos_solapan(dt(hora=9), dt(hora=11), dt(hora=10), dt(hora=10)) is False


def test_solape_es_simetrico():
    a = (dt(hora=10), dt(hora=10, minuto=30), dt(hora=10, minuto=15), dt(hora=11))
    assert intervalos_solapan(*a) == intervalos_solapan(a[2], a[3], a[0], a[1])


def test_solape_minimo_de_un_minuto():
    assert intervalos_solapan(dt(hora=10), dt(hora=10, minuto=30), dt(hora=10, minuto=29), dt(hora=11)) is True
