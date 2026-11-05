"""Tasks 2.2–2.7 — dominio de lista de espera (alta/baja/listar/compatibles)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from conftest import P1, P2, T1, T2

from app.lista_espera.puertos import AuditoriaMemoria, ListaEsperaMemoria, OfertaMemoria
from app.lista_espera.servicio import Conflicto, ServicioListaEspera
from app.reservas.puertos import (
    CatalogoMemoria,
    Paciente,
    PacienteMemoria,
    Prestacion,
    Profesional,
)
from app.turnos.servicio import Actor, NoEncontrado, Prohibido

TZ = timezone(timedelta(hours=-3))
PAC1 = "paciente-1"
PAC2 = "paciente-2"
PREST30 = "PREST-30"
PREST45 = "PREST-45"


def d3(dia: str = "2026-10-14", hora: int = 10, minuto: int = 0) -> datetime:
    y, m, d = (int(x) for x in dia.split("-"))
    return datetime(y, m, d, hora, minuto, tzinfo=TZ)


def recep(tenant: str = T1) -> Actor:
    return Actor(tenant_id=tenant, rol="RECEPCION", user_id="recep-1")


def _build(*, pacientes=(), prestaciones=(), profesionales=()):
    catalogo = CatalogoMemoria(
        prestaciones=[
            Prestacion(id=pid, tenant_id=tid, duracion_min=30) for (pid, tid) in prestaciones
        ],
        profesionales=[Profesional(id=pid, tenant_id=tid) for (pid, tid) in profesionales],
    )
    pac = PacienteMemoria(
        [
            Paciente(id=pid, tenant_id=tid, nombre="Paciente Demo", telefono="+5491100000001")
            for (pid, tid) in pacientes
        ]
    )
    repo = ListaEsperaMemoria()
    ofertas = OfertaMemoria()
    audit = AuditoriaMemoria()
    svc = ServicioListaEspera(repo, ofertas, catalogo, pac, audit)
    return svc, repo, ofertas, audit


def _estandar():
    return _build(
        pacientes=[(PAC1, T1), (PAC2, T1), ("paciente-3", T1), ("paciente-4", T1)],
        prestaciones=[(PREST30, T1), (PREST45, T1)],
        profesionales=[(P1, T1), (P2, T1)],
    )


def test_alta_crea_entrada_pendiente():
    svc, repo, _, _ = _estandar()
    e = svc.alta(recep(), paciente_id=PAC1, prestacion_id=PREST30, ahora=d3(hora=9))
    assert e.estado == "PENDIENTE"
    assert e.paciente_id == PAC1
    assert e.prestacion_id == PREST30
    assert repo.obtener(tenant_id=T1, entrada_id=e.id) == e


def test_alta_paciente_o_prestacion_otro_tenant_responde_404():
    svc, repo, _, _ = _estandar()
    # paciente de otro tenant
    with pytest.raises(NoEncontrado):
        svc.alta(recep(), paciente_id="paciente-ajeno", prestacion_id=PREST30, ahora=d3())
    # prestación de otro tenant / inexistente
    with pytest.raises(NoEncontrado):
        svc.alta(recep(), paciente_id=PAC1, prestacion_id="PREST-90", ahora=d3())
    # profesional_pref de otro tenant también se rechaza
    with pytest.raises(NoEncontrado):
        svc.alta(recep(), paciente_id=PAC1, prestacion_id=PREST30, profesional_pref="prof-ajeno", ahora=d3())
    assert repo.total(T1) == 0


def test_alta_duplicada_responde_409_sin_duplicar():
    svc, repo, _, _ = _estandar()
    svc.alta(recep(), paciente_id=PAC1, prestacion_id=PREST30, ahora=d3(hora=9))
    with pytest.raises(Conflicto):
        svc.alta(recep(), paciente_id=PAC1, prestacion_id=PREST30, ahora=d3(hora=9))
    assert repo.total(T1) == 1


def test_baja_entrada_pendiente_y_baja_con_oferta_anula_oferta():
    svc, repo, ofertas, _ = _estandar()
    # (a) baja de PENDIENTE → VENCIDO
    e = svc.alta(recep(), paciente_id=PAC1, prestacion_id=PREST30, ahora=d3(hora=9))
    r = svc.baja(recep(), entrada_id=e.id, ahora=d3(hora=10))
    assert r.estado == "VENCIDO"
    # (b) baja de OFRECIDO con oferta vigente → VENCIDO + oferta CANCELADA + hueco liberado
    e2 = svc.alta(recep(), paciente_id=PAC2, prestacion_id=PREST30, ahora=d3(hora=9))
    repo.cambiar_estado(tenant_id=T1, entrada_id=e2.id, estado="OFRECIDO")
    ofertas.crear(
        tenant_id=T1, entrada_id=e2.id, hueco_turno_id="turno-1",
        expira_at=d3(hora=12), token="tok-1",
    )
    r2 = svc.baja(recep(), entrada_id=e2.id, ahora=d3(hora=10))
    assert r2.estado == "VENCIDO"
    assert ofertas.por_token(tenant_id=T1, token="tok-1").estado == "CANCELADA"
    assert ofertas.pendientes(tenant_id=T1) == []


def test_listar_ordenado_por_fecha_de_alta_sin_mezclar_tenants():
    svc, _, _, _ = _build(
        pacientes=[(PAC1, T1), (PAC2, T1), ("paciente-t2", T2)],
        prestaciones=[(PREST30, T1), (PREST30, T2)],
        profesionales=[(P1, T1)],
    )
    svc.alta(recep(), paciente_id=PAC1, prestacion_id=PREST30, ahora=d3(hora=9))
    svc.alta(recep(), paciente_id=PAC2, prestacion_id=PREST30, ahora=d3(hora=10))
    svc.alta(recep(T2), paciente_id="paciente-t2", prestacion_id=PREST30, ahora=d3(hora=8))
    lista = svc.listar(recep(), prestacion_id=PREST30)
    assert [e.paciente_id for e in lista] == [PAC1, PAC2]
    assert all(e.tenant_id == T1 for e in lista)


def test_compatibilidad_prestacion_pref_y_ventana():
    svc, _, _, _ = _estandar()
    svc.alta(recep(), paciente_id=PAC1, prestacion_id=PREST30, ahora=d3(hora=9))
    svc.alta(recep(), paciente_id=PAC2, prestacion_id=PREST30, profesional_pref=P2, ahora=d3(hora=9))
    svc.alta(
        recep(), paciente_id="paciente-3", prestacion_id=PREST30,
        ventana_hasta=d3(hora=9), ahora=d3(hora=9),
    )
    svc.alta(recep(), paciente_id="paciente-4", prestacion_id=PREST45, ahora=d3(hora=9))
    compatibles = svc.compatibles(
        T1, prestacion_id=PREST30, profesional_id=P1, inicio=d3(hora=10)
    )
    assert [e.paciente_id for e in compatibles] == [PAC1]
    # prestación exacta: la entrada PREST45 sí es compatible con un hueco PREST45.
    assert [e.paciente_id for e in svc.compatibles(
        T1, prestacion_id=PREST45, profesional_id=P1, inicio=d3(hora=10)
    )] == ["paciente-4"]


def test_rol_no_gestor_rechazado_403():
    svc, _, _, _ = _estandar()
    con_rol_paciente = Actor(tenant_id=T1, rol="PACIENTE", user_id=PAC1)
    with pytest.raises(Prohibido):
        svc.alta(con_rol_paciente, paciente_id=PAC1, prestacion_id=PREST30, ahora=d3())
