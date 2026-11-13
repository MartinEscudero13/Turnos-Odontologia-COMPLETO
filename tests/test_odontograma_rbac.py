"""Tasks 6.5–6.8 — RBAC del odontograma (D10).

`ADMIN` y el `ODONTOLOGO` (acotado a los pacientes que atiende y a su propia
firma) escriben hallazgos; `RECEPCION` sólo lee. Un rol o alcance sin permiso
responde `403` sin persistir.
"""
from __future__ import annotations

import pytest
from _odontograma_helpers import PAC1, HarnessOdontograma, actor, d3
from conftest import P1, P2, T1

from app.turnos.servicio import Prohibido

PAC2 = "paciente-2"


def _registrar(h: HarnessOdontograma, profesional_id: str | None, paciente_id: str = PAC1):
    return h.svc.registrar_hallazgo(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        paciente_id=paciente_id,
        pieza_fdi=36,
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id=profesional_id,
    )


def test_odontologo_escribe_paciente_que_atiende_y_ajeno_403():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    h.seed_paciente(PAC2)
    h.dar_consentimiento(PAC2)

    propio = _registrar(h, P1)
    assert propio.paciente_id == PAC1
    assert propio.profesional_id == P1

    with pytest.raises(Prohibido) as exc:
        _registrar(h, P1, paciente_id=PAC2)
    assert exc.value.codigo == 403
    assert h.hallazgos.total(T1) == 1


def test_recepcion_lee_pero_no_escribe_hallazgo():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    h.svc.registrar_hallazgo(
        actor("ADMIN"),
        paciente_id=PAC1,
        pieza_fdi=36,
        hallazgo="caries oclusal",
        fecha=d3(),
        profesional_id=P1,
    )

    historial = h.svc.listar_historial(actor("RECEPCION"), paciente_id=PAC1)
    assert len(historial) == 1

    with pytest.raises(Prohibido) as exc:
        h.svc.registrar_hallazgo(
            actor("RECEPCION"),
            paciente_id=PAC1,
            pieza_fdi=11,
            hallazgo="hallazgo no permitido",
            fecha=d3(),
            profesional_id=P1,
        )
    assert exc.value.codigo == 403
    assert h.hallazgos.total(T1) == 1


def test_recepcion_y_odontologo_leen_historial_de_pieza():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    for dia, texto in (("2026-11-01", "control 1"), ("2026-11-10", "control 2")):
        h.svc.registrar_hallazgo(
            actor("ADMIN"),
            paciente_id=PAC1,
            pieza_fdi=36,
            hallazgo=texto,
            fecha=d3(dia),
            profesional_id=P1,
        )
    de_recepcion = h.svc.listar_historial(
        actor("RECEPCION"), paciente_id=PAC1, pieza_fdi=36
    )
    del_odontologo = h.svc.listar_historial(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        paciente_id=PAC1,
        pieza_fdi=36,
    )
    assert [x.id for x in de_recepcion] == [x.id for x in del_odontologo]
    assert [x.fecha for x in de_recepcion] == sorted(x.fecha for x in de_recepcion)


def test_odontologo_no_firma_hallazgo_de_otro_profesional():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)
    h.seed_profesional(P2)
    h.seed_atiende(P2, PAC1)

    with pytest.raises(Prohibido) as exc:
        _registrar(h, P2)

    assert exc.value.codigo == 403
    assert h.hallazgos.total(T1) == 0
