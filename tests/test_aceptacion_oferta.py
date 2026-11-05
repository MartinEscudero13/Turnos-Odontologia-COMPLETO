"""Tasks 5.1–5.4 — aceptación de la oferta con revalidación de solape (primer aceptante)."""
from __future__ import annotations

import threading

import pytest
from _lista_espera_helpers import PREST30, HarnessLista
from conftest import P1, S1, T1, dt

from app.lista_espera.servicio import Conflicto
from app.turnos.servicio import Actor


def _recep(tenant: str = T1) -> Actor:
    return Actor(tenant_id=tenant, rol="RECEPCION", user_id="recep-1")


def _oferta_vigente(h: HarnessLista):
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-13", 9))
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10))
    # el hueco se libera por cancelación antes de ofrecerlo
    h.cancelar_turno(turno.id, ahora=dt("2026-10-13", 9))
    oferta = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert oferta is not None
    return h, turno, oferta


def test_aceptacion_crea_turno_y_convierte_entrada():
    h, turno, oferta = _oferta_vigente(HarnessLista())
    entrada_id = oferta.entrada_id
    creado = h.svc_ofertas.aceptar(T1, oferta.token, ahora=dt("2026-10-13", 9, 30))
    assert creado.origen == "LISTA_ESPERA"
    assert creado.inicio == dt("2026-10-14", 10)
    assert creado.fin == dt("2026-10-14", 10, 30)
    assert creado.profesional_id == turno.profesional_id
    assert h.oferta_repo.por_token(tenant_id=T1, token=oferta.token).estado == "ACEPTADA"
    assert h.lista_repo.obtener(tenant_id=T1, entrada_id=entrada_id).estado == "CONVERTIDO"


def test_aceptacion_tras_expira_responde_409_sin_turno():
    h, _, oferta = _oferta_vigente(HarnessLista())
    entrada_id = oferta.entrada_id
    n_antes = len(h.turnos.listar(_recep()))
    with pytest.raises(Conflicto):
        h.svc_ofertas.aceptar(T1, oferta.token, ahora=dt("2026-10-13", 11, 1))
    assert h.oferta_repo.por_token(tenant_id=T1, token=oferta.token).estado == "VENCIDA"
    assert h.lista_repo.obtener(tenant_id=T1, entrada_id=entrada_id).estado == "PENDIENTE"
    assert len(h.turnos.listar(_recep())) == n_antes  # sin turno nuevo


def test_aceptacion_con_hueco_tomado_no_crea_turno():
    h, turno, oferta = _oferta_vigente(HarnessLista())
    entrada_id = oferta.entrada_id
    # recepción ocupa el hueco liberado antes de que el paciente acepte
    h.turnos.crear(
        _recep(),
        profesional_id=P1, sillon_id=S1, paciente_id="paciente-recep",
        prestacion_id=PREST30, inicio=dt("2026-10-14", 10), duracion_min=30,
    )
    n_antes = len(h.turnos.listar(_recep()))
    with pytest.raises(Conflicto):
        h.svc_ofertas.aceptar(T1, oferta.token, ahora=dt("2026-10-13", 9, 30))
    assert h.oferta_repo.por_token(tenant_id=T1, token=oferta.token).estado == "VENCIDA"
    assert h.lista_repo.obtener(tenant_id=T1, entrada_id=entrada_id).estado == "PENDIENTE"
    assert len(h.turnos.listar(_recep())) == n_antes  # no se creó turno extra


def test_doble_aceptacion_crea_un_solo_turno():
    h, _, oferta = _oferta_vigente(HarnessLista())
    resultados: list[tuple[str, str | None]] = []

    def aceptar() -> None:
        try:
            t = h.svc_ofertas.aceptar(T1, oferta.token, ahora=dt("2026-10-13", 9, 30))
            resultados.append(("ok", t.id))
        except Conflicto:
            resultados.append(("conflicto", None))

    hilos = [threading.Thread(target=aceptar) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert [r for r, _ in resultados].count("ok") == 1
    assert [r for r, _ in resultados].count("conflicto") == 1
    assert h.lista_repo.obtener(tenant_id=T1, entrada_id=oferta.entrada_id).estado == "CONVERTIDO"
