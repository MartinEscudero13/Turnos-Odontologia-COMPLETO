"""Tasks 8.1–8.3 — aislamiento multi-tenant de la lista de espera."""
from __future__ import annotations

import pytest
from _lista_espera_helpers import PREST30, HarnessLista
from conftest import P1, S1, T1, T2, dt

from app.turnos.servicio import NoEncontrado


def _h_con_oferta() -> tuple[HarnessLista, str]:
    h = HarnessLista()
    h.seed_catalogo(T1)
    h.seed_paciente("p-a", T1)
    h.alta_entrada(paciente_id="p-a", prestacion_id=PREST30, tenant=T1, ahora=dt("2026-10-13", 9))
    turno = h.crear_turno(paciente_id="otro-a", inicio=dt("2026-10-14", 10), tenant=T1)
    h.cancelar_turno(turno.id, tenant=T1, ahora=dt("2026-10-13", 9))
    oferta = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert oferta is not None
    return h, oferta.token


def test_token_oferta_de_a_en_b_responde_404():
    h, token = _h_con_oferta()
    client = h.build_lista()
    r = client.post(f"/api/publico/t2/ofertas/{token}/aceptar")
    assert r.status_code == 404
    # la oferta de T1 no se muta
    assert h.oferta_repo.por_token(tenant_id=T1, token=token).estado == "PENDIENTE"
    with pytest.raises(NoEncontrado):
        h.svc_ofertas.aceptar(T2, token)


def test_operaciones_de_a_no_tocan_b():
    h = HarnessLista()
    h.seed_catalogo(T1)
    h.seed_catalogo(T2)
    h.seed_paciente("p-a", T1)
    h.seed_paciente("p-b", T2)
    e_a = h.alta_entrada(paciente_id="p-a", prestacion_id=PREST30, tenant=T1, ahora=dt("2026-10-13", 9))
    # T2 no ve la entrada de T1
    assert h.lista_repo.listar(tenant_id=T2) == []
    assert h.lista_repo.obtener(tenant_id=T2, entrada_id=e_a.id) is None
    # alta en T2 es independiente
    h.alta_entrada(paciente_id="p-b", prestacion_id=PREST30, tenant=T2, ahora=dt("2026-10-13", 9))
    assert len(h.lista_repo.listar(tenant_id=T1)) == 1
    assert len(h.lista_repo.listar(tenant_id=T2)) == 1


def test_retencion_de_a_no_afecta_disponibilidad_de_b():
    h = HarnessLista()
    h.seed_catalogo(T1)
    h.seed_catalogo(T2)
    h.seed_paciente("p-a", T1)
    h.alta_entrada(paciente_id="p-a", prestacion_id=PREST30, tenant=T1, ahora=dt("2026-10-13", 9))
    turno_a = h.crear_turno(paciente_id="otro-a", inicio=dt("2026-10-14", 10), tenant=T1)
    h.cancelar_turno(turno_a.id, tenant=T1, ahora=dt("2026-10-13", 9))
    h.svc_ofertas.procesar_hueco_liberado(T1, turno_a.id, ahora=dt("2026-10-13", 9))

    svc, _ = h.build_publico()
    # en T2 el hueco 10:00 de S1 sigue disponible (la retención es de T1)
    slots_b = svc.disponibilidad("t2", PREST30, P1, dt("2026-10-14", 0), ahora=dt("2026-10-13", 9))
    assert any(s.sillon_id == S1 and s.inicio == dt("2026-10-14", 10) for s in slots_b)
