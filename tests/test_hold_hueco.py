"""Tasks 6.1–6.3 — hold del hueco en la disponibilidad pública (C-06)."""
from __future__ import annotations

from _lista_espera_helpers import PREST30, HarnessLista
from conftest import P1, S1, S2, T1, dt


def _hueco_retenido() -> tuple[HarnessLista, object]:
    h = HarnessLista()
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-13", 9))
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10))
    h.cancelar_turno(turno.id, ahora=dt("2026-10-13", 9))
    h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    return h, turno


def test_hueco_retenido_no_aparece_en_disponibilidad():
    h, _ = _hueco_retenido()
    svc, _ = h.build_publico()
    slots = svc.disponibilidad("t1", PREST30, P1, dt("2026-10-14", 0), ahora=dt("2026-10-13", 9))
    huecos_10 = [(s.sillon_id, s.inicio) for s in slots if s.inicio == dt("2026-10-14", 10)]
    assert (S1, dt("2026-10-14", 10)) not in huecos_10  # retenido por la oferta vigente
    assert (S2, dt("2026-10-14", 10)) in huecos_10  # el otro sillón sigue libre


def test_oferta_vencida_libera_retencion():
    h, _ = _hueco_retenido()
    svc, _ = h.build_publico()
    antes = svc.disponibilidad("t1", PREST30, P1, dt("2026-10-14", 0), ahora=dt("2026-10-13", 9))
    assert not any(s.sillon_id == S1 and s.inicio == dt("2026-10-14", 10) for s in antes)
    # la oferta vence sin más compatibles → la retención se libera
    h.svc_ofertas.procesar_expiracion(T1, ahora=dt("2026-10-13", 11, 1))
    despues = svc.disponibilidad("t1", PREST30, P1, dt("2026-10-14", 0), ahora=dt("2026-10-13", 11, 1))
    assert any(s.sillon_id == S1 and s.inicio == dt("2026-10-14", 10) for s in despues)


def test_disponibilidad_sin_ofertas_no_cambia_respecto_c06():
    h = HarnessLista()
    h.seed_catalogo()
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10))
    h.cancelar_turno(turno.id, ahora=dt("2026-10-13", 9))
    svc, _ = h.build_publico()
    slots = svc.disponibilidad("t1", PREST30, P1, dt("2026-10-14", 0), ahora=dt("2026-10-13", 9))
    # sin ofertas la grilla es la misma de C-06: 09:00 y 10:00 disponibles
    assert any(s.sillon_id == S1 and s.inicio == dt("2026-10-14", 9) for s in slots)
    assert any(s.sillon_id == S1 and s.inicio == dt("2026-10-14", 10) for s in slots)
