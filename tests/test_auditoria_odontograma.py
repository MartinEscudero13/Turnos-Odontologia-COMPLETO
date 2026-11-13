"""Task 9.1 — auditoría del odontograma append-only y sin PHI (D12/RN-CL-04).

Registrar, resolver y derivar escriben acciones con `tenant_id`, actor y
`entidad_id`; nunca el texto clínico ni datos personales del paciente.
"""
from __future__ import annotations

from _odontograma_helpers import KEY, PAC1, PREST1, HarnessOdontograma, actor, d3
from conftest import P1, T1

TEXTO_SENSIBLE = "TEXTO CLINICO SENSIBLE DEL PACIENTE"


def test_mutaciones_auditadas_sin_texto_clinico():
    h = HarnessOdontograma()
    h.dar_consentimiento(PAC1)

    hallazgo = h.svc.registrar_hallazgo(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        paciente_id=PAC1,
        pieza_fdi=36,
        superficie="O",
        hallazgo=TEXTO_SENSIBLE,
        fecha=d3(),
        profesional_id=P1,
    )
    h.svc.resolver(actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1), hallazgo_id=hallazgo.id)
    h.svc.derivar(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        paciente_id=PAC1,
        pieza_fdi=37,
        hallazgo=TEXTO_SENSIBLE,
        fecha=d3(),
        prestacion_id=PREST1,
        idempotency_key=KEY,
    )

    acciones = [e.accion for e in h.auditoria.entradas]
    assert acciones.count("HALLAZGO_REGISTRADO") == 2
    assert "HALLAZGO_RESUELTO" in acciones
    assert "LINEA_PRESUPESTADA" in acciones

    for entrada in h.auditoria.entradas:
        assert entrada.tenant_id == T1
        assert entrada.actor
        assert entrada.entidad_id
        payload = str(entrada.antes) + str(entrada.despues)
        assert TEXTO_SENSIBLE not in payload
        assert "Paciente Demo" not in payload
        assert "+5491" not in payload
        assert "telefono" not in payload
