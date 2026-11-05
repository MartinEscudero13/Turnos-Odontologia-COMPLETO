"""Tasks 9.1–9.3 — trazabilidad append-only sin PHI (RN-AU-02)."""
from __future__ import annotations

import dataclasses

from _lista_espera_helpers import PREST30, HarnessLista
from conftest import T1, T2, dt

from app.lista_espera.puertos import AuditoriaMemoria, AuditoriaPort
from app.turnos.servicio import Actor

_CAMPOS_AUDITORIA = {
    "tenant_id", "accion", "actor", "entrada_id", "oferta_id", "turno_id",
    "estado_antes", "estado_despues", "registrado_en",
}


def _flujo_oferta_aceptada(h: HarnessLista):
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-13", 9))
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10))
    h.cancelar_turno(turno.id, ahora=dt("2026-10-13", 9))
    oferta = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert oferta is not None
    h.svc_ofertas.aceptar(T1, oferta.token, ahora=dt("2026-10-13", 9, 30))
    return h


def test_oferta_y_aceptacion_auditadas_sin_phi():
    h = _flujo_oferta_aceptada(HarnessLista())
    acciones = [e.accion for e in h.auditoria.entradas]
    assert "ALTA" in acciones
    assert "OFRECIDO" in acciones
    assert "OFERTA_ACEPTADA" in acciones
    aceptada = next(e for e in h.auditoria.entradas if e.accion == "OFERTA_ACEPTADA")
    assert aceptada.turno_id is not None and aceptada.oferta_id is not None
    for e in h.auditoria.entradas:
        assert set(dataclasses.asdict(e)) == _CAMPOS_AUDITORIA
        texto = str(set(dataclasses.asdict(e)))
        assert "paciente" not in texto and "nombre" not in texto and "telefono" not in texto
        assert "dni" not in texto.lower()


def test_vencimiento_y_baja_auditadas():
    h = HarnessLista()
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    entrada = h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-13", 9))
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10))
    h.cancelar_turno(turno.id, ahora=dt("2026-10-13", 9))
    h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    h.svc_ofertas.procesar_expiracion(T1, ahora=dt("2026-10-13", 11, 1))
    h.svc_lista.baja(
        Actor(tenant_id=T1, rol="RECEPCION", user_id="recep-1"),
        entrada_id=entrada.id,
        ahora=dt("2026-10-13", 12),
    )
    acciones = [e.accion for e in h.auditoria.entradas]
    assert "OFERTA_VENCIDA" in acciones
    assert "BAJA" in acciones


def test_auditoria_sin_delete_ni_update():
    for metodo in ("delete", "update", "borrar", "editar"):
        assert not hasattr(AuditoriaPort, metodo)
        assert not hasattr(AuditoriaMemoria, metodo)


def test_auditoria_de_a_no_incluye_registros_de_b():
    h = HarnessLista()
    h.seed_catalogo(T1)
    h.seed_catalogo(T2)
    h.seed_paciente("p-a", T1)
    h.seed_paciente("p-b", T2)
    h.alta_entrada(paciente_id="p-a", prestacion_id=PREST30, tenant=T1, ahora=dt("2026-10-13", 9))
    h.alta_entrada(paciente_id="p-b", prestacion_id=PREST30, tenant=T2, ahora=dt("2026-10-13", 9))
    de_a = h.auditoria.de_tenant(T1)
    assert de_a and all(e.tenant_id == T1 for e in de_a)
    assert all(e.tenant_id in (T1, T2) for e in h.auditoria.entradas)
    assert any(e.tenant_id == T2 for e in h.auditoria.entradas)
