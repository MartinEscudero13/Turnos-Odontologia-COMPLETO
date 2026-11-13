"""Task 9.6 — privacidad del odontograma y del presupuesto (RN-CL-04).

Los errores de dominio no arrastran el texto clínico y los logs estructurados de
la aceptación sólo llevan identificadores y montos.
"""
from __future__ import annotations

import logging

import pytest
from _odontograma_helpers import PAC1, HarnessOdontograma, actor, d3
from _presupuesto_helpers import HarnessPresupuesto, presupuesto_vigente, registrar_aceptacion
from conftest import P1

from app.ficha_clinica.servicio import ConsentimientoRequerido

TEXTO_SENSIBLE = "SECRETO CLINICO NO DEBE APARECER"


def test_error_no_vuelca_texto_clinico():
    h = HarnessOdontograma()
    with pytest.raises(ConsentimientoRequerido) as exc:
        h.svc.registrar_hallazgo(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            paciente_id=PAC1,
            pieza_fdi=36,
            hallazgo=TEXTO_SENSIBLE,
            fecha=d3(),
            profesional_id=P1,
        )
    assert TEXTO_SENSIBLE not in str(exc.value)
    assert TEXTO_SENSIBLE not in exc.value.mensaje


def test_logs_solo_llevan_ids_y_montos(caplog):
    caplog.set_level(logging.INFO)
    h = HarnessPresupuesto()
    presupuesto_id, lineas = presupuesto_vigente(h, monto=100000)

    registrar_aceptacion(h, presupuesto_id, lineas[0], ahora=d3("2026-11-10", 11))

    texto = caplog.text
    assert presupuesto_id in texto
    assert lineas[0] in texto
    assert "monto" in texto
    assert "100000" in texto
    assert "Paciente Demo" not in texto
    assert "+5491" not in texto
    assert TEXTO_SENSIBLE not in texto
