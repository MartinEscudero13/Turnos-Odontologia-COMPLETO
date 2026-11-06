"""Tasks 4.1–4.4 — adjuntos scoped por tenant con referencia opaca."""
from __future__ import annotations

import pytest
from _ficha_clinica_helpers import HarnessClinica, actor
from conftest import P1, T1

from app.turnos.servicio import Invalido, NoEncontrado


def _h_con_ficha(paciente_id: str = "paciente-1", *, consentido: bool = True) -> HarnessClinica:
    h = HarnessClinica()
    h.seed_paciente(paciente_id)
    h.seed_profesional(P1)
    h.seed_atiende(P1, paciente_id)
    if consentido:
        h.dar_consentimiento(paciente_id)
        h.svc.crear_ficha(actor("RECEPCION"), paciente_id=paciente_id)
    return h


def test_adjunto_valido_tipo_rx():
    h = _h_con_ficha()
    ficha = h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1")
    adj = h.svc.registrar_adjunto(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        ficha_id=ficha.id,
        tipo="RX",
        storage_ref="objetos/rx-1.dcm",
    )
    assert adj.tipo == "RX"
    assert adj.storage_ref == "objetos/rx-1.dcm"
    assert adj.ficha_id == ficha.id
    assert h.adjuntos.listar(tenant_id=T1, ficha_id=ficha.id) == [adj]


def test_adjunto_tipo_foto_tambien_valido():
    h = _h_con_ficha()
    ficha = h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1")
    adj = h.svc.registrar_adjunto(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        ficha_id=ficha.id,
        tipo="FOTO",
        storage_ref="objetos/foto-1.jpg",
    )
    assert adj.tipo == "FOTO"


def test_adjunto_tipo_invalido_422():
    h = _h_con_ficha()
    ficha = h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1")
    with pytest.raises(Invalido):
        h.svc.registrar_adjunto(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            ficha_id=ficha.id,
            tipo="CT",
            storage_ref="objetos/x",
        )


def test_adjunto_ficha_otro_tenant_404():
    h = _h_con_ficha()
    with pytest.raises(NoEncontrado):
        h.svc.registrar_adjunto(
            actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
            ficha_id="ficha-ajena",
            tipo="RX",
            storage_ref="objetos/x",
        )


def test_storage_ref_sin_phi():
    h = _h_con_ficha()
    ficha = h.fichas.por_paciente(tenant_id=T1, paciente_id="paciente-1")
    ref = "objetos/adjunto-1"
    adj = h.svc.registrar_adjunto(
        actor("ODONTOLOGO", user_id="odont-1", profesional_id=P1),
        ficha_id=ficha.id,
        tipo="RX",
        storage_ref=ref,
    )
    # La referencia se guarda opaca, tal cual, sin PHI del paciente.
    assert adj.storage_ref == ref
    # La auditoría del adjunto no vuelca storage_ref ni nombre/teléfono.
    entradas = [e for e in h.auditoria.entradas if e.accion == "ADJUNTO_REGISTRADO"]
    assert len(entradas) == 1
    despues = entradas[0].despues or {}
    assert "storage_ref" not in despues
    assert "nombre" not in str(despues) and "telefono" not in str(despues)
