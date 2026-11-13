"""Tasks 4.6–4.10 — preferencia de pago, caída de MP y backoff (RN-IN-03, D5).

El orden es contrato: la seña se persiste **antes** de pedir la preferencia, así
un webhook no puede llegar antes de que la fila exista. La pasarela se ejerce con
`AdaptadorPasarelaFake`; ningún test abre sockets.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from _reserva_helpers import reservar
from _senas_helpers import (
    AHORA,
    TUR1,
    HarnessReservaConSena,
    HarnessSenas,
)
from conftest import T1

from app.senas.puertos import AdaptadorPasarelaFake, SenaMemoria
from app.turnos.servicio import Actor


class PasarelaObservada(AdaptadorPasarelaFake):
    """Cuenta los pedidos de preferencia hechos antes de persistir la seña."""

    def __init__(self, senas: SenaMemoria) -> None:
        super().__init__()
        self._senas = senas
        self.pedidos: int = 0
        self.pedidos_sin_sena: int = 0
        self.sena_persistida_al_pedir: bool | None = None

    def crear_preferencia(self, **kwargs: Any) -> Any:
        self.pedidos += 1
        persistida = (
            self._senas.por_turno(
                tenant_id=kwargs["tenant_id"], turno_id=kwargs["turno_id"]
            )
            is not None
        )
        self.sena_persistida_al_pedir = persistida
        if not persistida:
            self.pedidos_sin_sena += 1
        return super().crear_preferencia(**kwargs)


def test_preferencia_con_metadata_y_external_reference() -> None:
    senas = SenaMemoria()
    pasarela = PasarelaObservada(senas)
    h = HarnessSenas(pasarela=pasarela, senas=senas)
    h.configurar()

    creada = h.crear()

    assert pasarela.sena_persistida_al_pedir is True
    assert pasarela.pedidos == 1
    assert pasarela.pedidos_sin_sena == 0
    assert len(pasarela.preferencias) == 1
    pedido = pasarela.preferencias[0]
    sena = h.senas.obtener(tenant_id=T1, sena_id=creada.sena.id)
    assert sena is not None
    assert pedido["tenant_id"] == T1
    assert pedido["sena_id"] == sena.id
    assert pedido["external_reference"] == sena.id
    assert pedido["metadata"] == {
        "sena_id": sena.id,
        "turno_id": TUR1,
        "tenant_id": T1,
    }
    assert pedido["turno_id"] == TUR1
    assert pedido["monto_centavos"] == 3000
    assert pedido["descripcion"] == "Seña de turno"
    assert pedido["expira_at"] == sena.expira_at
    assert pedido["url_webhook"].endswith("/api/webhooks/mercadopago")
    assert pedido["url_pago"].endswith(creada.token_sena)
    # La seña queda CREADA con la preferencia persistida.
    assert sena.preferencia_estado == "CREADA"
    assert sena.mp_preference_id == f"pref-{sena.id}"
    assert sena.mp_init_point == f"https://mp.test/checkout/{sena.id}"
    assert sena.proximo_reintento_at is None
    assert h.auditoria.de_accion("SENA_PREFERENCIA_CREADA")


def test_mp_caido_reserva_201_y_preferencia_fallida() -> None:
    h = HarnessReservaConSena()
    h.pasarela.fallar()

    respuesta = reservar(h.base)

    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "PENDIENTE"
    bloque = body["sena"]
    assert bloque["estado"] == "PENDIENTE"
    assert bloque["preferencia_estado"] == "FALLIDA"
    assert bloque["init_point"] is None
    assert bloque["token_sena"]
    sena = h.senas.por_turno(tenant_id=T1, turno_id=body["turno_id"])
    assert sena is not None
    assert sena.estado == "PENDIENTE"
    assert sena.preferencia_estado == "FALLIDA"
    assert sena.mp_preference_id is None
    assert sena.intentos_preferencia == 1
    assert sena.proximo_reintento_at == h.ahora_actual + timedelta(minutes=2)
    # Nada se pierde: turno y seña existen aunque la pasarela esté caída.
    actor = Actor(tenant_id=T1, rol="RECEPCION", user_id="recepcion-1")
    assert len(h.turnos.listar(actor)) == 1
    assert h.senas.total(T1) == 1
    assert h.pasarela.preferencias == []
    assert h.auditoria_senas.de_accion("SENA_PREFERENCIA_FALLIDA")
    # La reserva siempre deja una salida: el link del token funciona y avisa el estado.
    consulta = h.client_senas.get(f"/api/publico/t1/senas/{bloque['token_sena']}")
    assert consulta.status_code == 200
    assert consulta.json()["preferencia_estado"] == "FALLIDA"
    assert consulta.json()["init_point"] is None


def test_reintento_devuelve_la_misma_preferencia() -> None:
    h = HarnessSenas()
    h.configurar()
    creada = h.crear()
    sena = h.senas.obtener(tenant_id=T1, sena_id=creada.sena.id)
    assert sena is not None and sena.preferencia_estado == "CREADA"

    respuesta = h.client.post(f"/api/publico/t1/senas/{creada.token_sena}/preferencia")

    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert body["init_point"] == sena.mp_init_point
    assert body["preferencia_estado"] == "CREADA"
    # Sin segunda preferencia y sin sumar intentos (C11-OQ-05).
    assert len(h.pasarela.preferencias) == 1
    actual = h.senas.obtener(tenant_id=T1, sena_id=sena.id)
    assert actual is not None
    assert actual.intentos_preferencia == 0
    assert actual.mp_preference_id == sena.mp_preference_id
    assert actual.mp_init_point == sena.mp_init_point


def test_reintento_respeta_backoff() -> None:
    h = HarnessSenas()
    h.configurar()
    h.pasarela.fallar()
    creada = h.crear()  # preferencia FALLIDA
    sena = h.senas.obtener(tenant_id=T1, sena_id=creada.sena.id)
    assert sena is not None and sena.preferencia_estado == "FALLIDA"

    proximo = AHORA + timedelta(hours=1)
    actualizada = h.senas.actualizar(
        tenant_id=T1,
        sena_id=sena.id,
        campos={"intentos_preferencia": 2, "proximo_reintento_at": proximo},
    )
    assert actualizada is not None
    h.fijar_ahora(AHORA + timedelta(minutes=1))
    h.pasarela.recuperar()

    respuesta = h.client.post(f"/api/publico/t1/senas/{creada.token_sena}/preferencia")

    assert respuesta.status_code == 202, respuesta.text
    body = respuesta.json()
    assert datetime.fromisoformat(body["reintentar_en"]) == proximo
    assert body["preferencia_estado"] == "FALLIDA"
    # No se llamó a la pasarela ni se tocaron los intentos.
    assert h.pasarela.preferencias == []
    actual = h.senas.obtener(tenant_id=T1, sena_id=sena.id)
    assert actual is not None
    assert actual.intentos_preferencia == 2
    assert actual.preferencia_estado == "FALLIDA"


def test_backoff_tope_de_15_minutos() -> None:
    h = HarnessSenas()
    h.configurar()
    h.pasarela.fallar()
    creada = h.crear()  # primer fallo: intentos=1 ⇒ +2 min
    sena = h.senas.obtener(tenant_id=T1, sena_id=creada.sena.id)
    assert sena is not None
    assert sena.proximo_reintento_at == AHORA + timedelta(minutes=2)

    for intentos, minutos in ((2, 4), (3, 8), (4, 15)):
        assert sena.proximo_reintento_at is not None
        momento = sena.proximo_reintento_at + timedelta(seconds=1)
        h.fijar_ahora(momento)
        respuesta = h.client.post(f"/api/publico/t1/senas/{creada.token_sena}/preferencia")
        assert respuesta.status_code == 202, respuesta.text
        actual = h.senas.obtener(tenant_id=T1, sena_id=sena.id)
        assert actual is not None
        assert actual.intentos_preferencia == intentos
        # `min(2**intentos, 15)` minutos: techo de espera (C11-OQ-05 provisional).
        assert actual.proximo_reintento_at == momento + timedelta(minutes=minutos)
        sena = actual


def test_preferencia_vencida_409() -> None:
    h = HarnessSenas()
    h.configurar()
    h.pasarela.fallar()
    creada = h.crear()
    sena = h.senas.obtener(tenant_id=T1, sena_id=creada.sena.id)
    assert sena is not None and sena.estado == "PENDIENTE"
    vencida = h.senas.actualizar(
        tenant_id=T1,
        sena_id=sena.id,
        campos={"expira_at": AHORA - timedelta(hours=1)},
    )
    assert vencida is not None
    h.pasarela.recuperar()

    respuesta = h.client.post(f"/api/publico/t1/senas/{creada.token_sena}/preferencia")

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["codigo"] == "SENA_VENCIDA"
    # La guarda decide antes de la red: ninguna preferencia nueva (F-09).
    assert h.pasarela.preferencias == []
    assert h.pasarela.consultas == []
    actual = h.senas.obtener(tenant_id=T1, sena_id=sena.id)
    assert actual is not None
    assert actual.estado == "PENDIENTE"
    assert actual.mp_init_point is None
    assert actual.intentos_preferencia == sena.intentos_preferencia


def test_mp_caido_no_pide_preferencia_de_una_prestacion_sin_sena() -> None:
    h = HarnessSenas()
    h.configurar(modo="SIN_SENA", valor=None)
    h.pasarela.fallar()

    assert h.crear() is None
    assert h.senas.total(T1) == 0
    assert h.pasarela.preferencias == []
