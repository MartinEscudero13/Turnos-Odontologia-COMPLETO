"""Task 1.4 — máquina de estados: RED primero."""
from __future__ import annotations

import pytest

from app.turnos.estados import libera_hueco, transicion_valida


def test_pendiente_a_confirmado_ok():
    assert transicion_valida("PENDIENTE", "CONFIRMADO") is True


def test_pendiente_a_cancelado_ok():
    assert transicion_valida("PENDIENTE", "CANCELADO") is True


def test_confirmado_a_presente_ok():
    assert transicion_valida("CONFIRMADO", "PRESENTE") is True


def test_presente_es_final():
    assert transicion_valida("PRESENTE", "CANCELADO") is False
    assert transicion_valida("PRESENTE", "CONFIRMADO") is False


def test_cancelado_no_sale():
    assert transicion_valida("CANCELADO", "PENDIENTE") is False


def test_reprogramado_es_final():
    assert transicion_valida("REPROGRAMADO", "CONFIRMADO") is False


def test_finales_liberan_hueco():
    assert libera_hueco("CANCELADO") is True
    assert libera_hueco("REPROGRAMADO") is True
    assert libera_hueco("PENDIENTE") is False
    assert libera_hueco("CONFIRMADO") is False


def test_confirmado_a_ausente_ok_y_ausente_es_final():
    assert transicion_valida("CONFIRMADO", "AUSENTE") is True
    assert transicion_valida("AUSENTE", "CANCELADO") is False
    assert libera_hueco("AUSENTE") is False


def test_reprogramar_solo_desde_activos():
    assert transicion_valida("PENDIENTE", "REPROGRAMADO") is True
    assert transicion_valida("CONFIRMADO", "REPROGRAMADO") is True
