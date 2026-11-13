"""Task 4.11 — los controles de C-06 siguen aplicando con seña (F-21).

Verificación, rate-limit y anti-spam corren **antes** de crear el turno o la seña:
si fallan, no se persiste nada y la pasarela no se invoca. Datos ficticios.
"""
from __future__ import annotations

import pytest
from _reserva_helpers import emitir, reservar
from _senas_helpers import PREST30, HarnessReservaConSena
from conftest import P1, T1, dt

from app.reservas.servicio import DemasiadasSolicitudes
from app.turnos.servicio import Actor, Prohibido


def _actor() -> Actor:
    return Actor(tenant_id=T1, rol="RECEPCION", user_id="recepcion-1")


def test_controles_c06_siguen_aplicando() -> None:    # (1) Verificación inexistente ⇒ 403, sin turno, sin seña y sin pasarela.
    h = HarnessReservaConSena()
    with pytest.raises(Prohibido):
        h.base.svc.reservar(
            "t1",
            prestacion_id=PREST30,
            profesional_id=P1,
            inicio=dt("2026-10-06", 10),
            nombre="Paciente Demo",
            telefono="+5491130551234",
            verificacion_id="VER-INEXISTENTE",
            ip="10.0.0.1",
        )
    assert h.turnos.listar(_actor()) == []
    assert h.senas.listar(tenant_id=T1) == []
    assert h.pasarela.preferencias == []

    # (2) Verificación vencida ⇒ 403, tampoco crea nada.
    desafio = h.base.svc.emitir_verificacion("t1", "reservar", "10.0.0.2")
    with pytest.raises(Prohibido):
        h.base.svc.reservar(
            "t1",
            prestacion_id=PREST30,
            profesional_id=P1,
            inicio=dt("2026-10-06", 10),
            nombre="Paciente Demo",
            telefono="+5491130551234",
            verificacion_id=desafio.verificacion_id,
            ip="10.0.0.2",
            ahora=desafio.expira_at.replace(second=1),
        )
    assert h.turnos.listar(_actor()) == []
    assert h.senas.listar(tenant_id=T1) == []
    assert h.pasarela.preferencias == []

    # (3) La reserva sin `verificacion_id` no pasa el contrato: 422 y nada creado.
    sin_verificacion = h.client.post(
        "/api/publico/t1/reservas",
        json={
            "prestacion": PREST30,
            "profesional": P1,
            "inicio": "2026-10-06T10:00:00+00:00",
            "nombre": "Paciente Demo",
            "telefono": "+5491130551234",
        },
    )
    assert sin_verificacion.status_code == 422
    assert h.turnos.listar(_actor()) == []
    assert h.senas.listar(tenant_id=T1) == []
    assert h.pasarela.preferencias == []

    # (4) Rate-limit agotado ⇒ 429 con Retry-After, sin segundo turno ni seña.
    limitado = HarnessReservaConSena(rate_limit_max=1)
    assert reservar(limitado.base).status_code == 201
    with pytest.raises(DemasiadasSolicitudes) as excinfo:
        limitado.base.svc.reservar(
            "t1",
            prestacion_id=PREST30,
            profesional_id=P1,
            inicio=dt("2026-10-06", 11),
            nombre="Paciente Demo",
            telefono="+5491130551234",
            verificacion_id=emitir(limitado.base),
            ip="testclient",
        )
    assert excinfo.value.codigo == 429
    assert excinfo.value.retry_after_s >= 0
    assert len(limitado.turnos.listar(_actor())) == 1
    assert limitado.senas.total(T1) == 1
    assert len(limitado.pasarela.preferencias) == 1


def test_sin_sena_mantiene_el_contrato_anterior() -> None:
    h = HarnessReservaConSena()
    h.configuracion.configurar(tenant_id=T1, modo="SIN_SENA", valor=None)

    respuesta = reservar(h.base)

    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert "sena" not in body
    assert set(body.keys()) == {
        "turno_id",
        "estado",
        "inicio",
        "fin",
        "origen",
        "prestacion",
        "sillon_id",
        "token_publico",
    }
    assert h.senas.total(T1) == 0
    assert h.pasarela.preferencias == []
