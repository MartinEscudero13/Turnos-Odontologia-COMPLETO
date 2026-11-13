"""Tasks 4.1–4.5 — alta de la seña atada a la reserva (RN-SE-01, D5).

Reloj `2026-11-13T09:00:00-03:00`, `SENA_TTL_H=24`, `precio_base=10000` y
`PORCENTAJE=30` ⇒ `3000`. La seña nace `PENDIENTE` y el turno sigue `PENDIENTE`
hasta que el webhook acredite (§6). Datos ficticios (RN-GL-03).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from _reserva_helpers import reservar
from _senas_helpers import AHORA, TUR1, HarnessReservaConSena, HarnessSenas, d3
from conftest import T1

from app.senas.servicio import ConflictoSena
from app.turnos.servicio import Actor


def test_crear_sena_porcentaje_3000() -> None:
    h = HarnessSenas()
    h.configurar()

    creada = h.crear()

    sena = creada.sena
    assert sena.tenant_id == T1
    assert sena.turno_id == TUR1
    assert sena.estado == "PENDIENTE"
    assert sena.monto_centavos == 3000
    assert (sena.regla_modo, sena.regla_valor) == ("PORCENTAJE", 30)
    assert sena.precio_base_centavos == 10000
    assert sena.anticipacion_cancelacion_h == 24
    assert sena.expira_at == d3("2026-11-14", 9)
    assert sena.creado_en == AHORA
    assert h.senas.total(T1) == 1
    # Token opaco: se entrega en claro una sola vez y se persiste sólo el hash.
    assert creada.token_sena
    assert sena.token_hash != creada.token_sena
    assert len(creada.token_sena) >= 43
    # Política visible desde la creación (F-01): promesa, no estado.
    assert creada.politica.anticipacion_cancelacion_h == 24
    assert creada.politica.reembolsable is True
    assert creada.politica.hay_pago_acreditado is False


def test_expira_at_acotada_al_inicio() -> None:
    h = HarnessSenas()
    h.configurar()
    inicio = d3("2026-11-13", 18)

    creada = h.crear(inicio=inicio)

    assert creada.sena.expira_at == inicio
    # El TTL sin tope habría dado 2026-11-14T09:00 (C11-OQ-08).
    assert creada.sena.expira_at != AHORA + timedelta(hours=24)


def test_turno_sigue_pendiente() -> None:
    h = HarnessReservaConSena()

    respuesta = reservar(h.base)

    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "PENDIENTE"
    assert body["origen"] == "RESERVA_ONLINE"
    assert body["sena"]["estado"] == "PENDIENTE"
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="recepcion-1")
    turnos = h.turnos.listar(actor)
    assert len(turnos) == 1
    assert turnos[0].estado == "PENDIENTE"
    assert all(t.estado != "CONFIRMADO" for t in turnos)
    sena = h.senas.por_turno(tenant_id=T1, turno_id=body["turno_id"])
    assert sena is not None
    assert sena.estado == "PENDIENTE"


def test_dos_reservas_dos_senas() -> None:
    h = HarnessReservaConSena()

    primera = reservar(h.base)
    segunda = reservar(h.base, inicio="2026-10-06T11:00:00+00:00")

    assert primera.status_code == 201, primera.text
    assert segunda.status_code == 201, segunda.text
    assert primera.json()["turno_id"] != segunda.json()["turno_id"]
    senas = h.senas.listar(tenant_id=T1)
    assert len(senas) == 2
    assert len({s.turno_id for s in senas}) == 2
    assert len({s.token_hash for s in senas}) == 2
    assert primera.json()["sena"]["token_sena"] != segunda.json()["sena"]["token_sena"]


def test_segunda_sena_del_mismo_turno_409() -> None:
    h = HarnessSenas()
    h.configurar()
    h.crear()

    with pytest.raises(ConflictoSena) as excinfo:
        h.crear()

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == "SENA_DUPLICADA"
    assert h.senas.total(T1) == 1
    # La segunda alta no llega a pedir una preferencia nueva (RN-SE-02).
    assert len(h.pasarela.preferencias) == 1
