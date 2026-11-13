"""Tasks 3.1–3.5 — puertos, entidades y pasarela fake de señas: RED primero.

Todo repositorio recibe `tenant_id` explícito y nunca devuelve ni muta filas de
otro tenant. `transicionar` es una transición **condicional** (devuelve `None` si
el estado esperado no coincide): en memoria no hay locks, así que la garantía de
concurrencia vive en PostgreSQL (D11) — acá se prueba el contrato del dominio.

La pasarela se ejerce **sólo** con `AdaptadorPasarelaFake`: ningún test abre un
socket (regla dura "sin credenciales reales"). Datos ficticios (RN-GL-03).
"""
from __future__ import annotations

import socket
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from conftest import T1, T2

from app.senas.puertos import (
    AdaptadorPasarelaFake,
    AplicacionCajaMemoria,
    AuditoriaSenaMemoria,
    PagoMPMemoria,
    PagoNoEncontrado,
    PasarelaNoDisponible,
    Preferencia,
    PresupuestosMemoria,
    Sena,
    SenaDuplicada,
    SenaMemoria,
    TokenDuplicado,
    TurnoMemoriaSena,
)
from app.turnos.servicio import NoEncontrado

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 13, 9, 0, tzinfo=TZ)
EXPIRA = datetime(2026, 11, 14, 9, 0, tzinfo=TZ)
TUR1 = "turno-1"
TUR2 = "turno-2"
U1 = "usuario-1"


def crear(
    repo: SenaMemoria,
    *,
    tenant_id: str = T1,
    turno_id: str = TUR1,
    token_hash: str = "hash-1",
    monto_centavos: int = 3000,
    ahora: datetime | None = AHORA,
) -> Sena:
    return repo.crear(
        tenant_id=tenant_id,
        turno_id=turno_id,
        monto_centavos=monto_centavos,
        regla_modo="PORCENTAJE",
        regla_valor=30,
        precio_base_centavos=10000,
        anticipacion_cancelacion_h=24,
        expira_at=EXPIRA,
        token_hash=token_hash,
        ahora=ahora,
    )


# ---------------------------------------------------------------------------
# 3.1 — repositorios scoped por tenant
# ---------------------------------------------------------------------------


def test_repositorios_scoped_por_tenant() -> None:
    senas = SenaMemoria()
    pagos = PagoMPMemoria()

    t1 = crear(senas, tenant_id=T1, turno_id=TUR1, token_hash="hash-t1")
    t2 = crear(senas, tenant_id=T2, turno_id=TUR1, token_hash="hash-t2")

    # El UNIQUE es `(tenant_id, turno_id)`: el mismo nombre de turno en otro
    # tenant es otra reserva.
    assert senas.obtener(tenant_id=T1, sena_id=t1.id) == t1
    assert senas.obtener(tenant_id=T2, sena_id=t1.id) is None
    assert senas.por_turno(tenant_id=T1, turno_id=TUR1) == t1
    assert senas.por_turno(tenant_id=T2, turno_id=TUR1) == t2
    assert senas.listar(tenant_id=T1) == [t1]
    assert senas.listar(tenant_id=T2) == [t2]

    with pytest.raises(SenaDuplicada):
        crear(senas, tenant_id=T1, turno_id=TUR1, token_hash="hash-t1-bis")

    # `token_hash` es único global: un token no puede existir en dos tenants.
    with pytest.raises(TokenDuplicado):
        crear(senas, tenant_id=T2, turno_id=TUR2, token_hash="hash-t1")

    # Bloquear es scoped: T2 no puede tomar la fila de T1.
    with pytest.raises(NoEncontrado):
        senas.bloquear(tenant_id=T2, sena_id=t1.id)
    assert senas.bloquear(tenant_id=T1, sena_id=t1.id) == t1

    pago_t1 = pagos.registrar_o_actualizar(
        tenant_id=T1,
        sena_id=t1.id,
        mp_payment_id="PAG-1",
        monto_centavos=3000,
        moneda="ARS",
        estado="APPROVED",
        resultado="ACREDITADA",
        raw_json={"id": "PAG-1", "status": "approved"},
        ahora=AHORA,
    )
    assert pagos.obtener(tenant_id=T1, mp_payment_id="PAG-1") == pago_t1
    assert pagos.obtener(tenant_id=T2, mp_payment_id="PAG-1") is None
    assert pagos.listar(tenant_id=T1, sena_id=t1.id) == [pago_t1]
    assert pagos.listar(tenant_id=T2, sena_id=t1.id) == []


# ---------------------------------------------------------------------------
# 3.2 — transición condicional desde el estado esperado
# ---------------------------------------------------------------------------


def test_transicionar_solo_desde_el_estado_esperado() -> None:
    senas = SenaMemoria()
    sena = crear(senas)

    acreditada = senas.transicionar(
        tenant_id=T1,
        sena_id=sena.id,
        desde="PENDIENTE",
        hacia="ACREDITADA",
        campos={"acreditada_en": AHORA},
    )

    assert acreditada is not None
    assert acreditada.estado == "ACREDITADA"
    assert acreditada.acreditada_en == AHORA

    # Segundo intento desde el mismo estado esperado: no hay transición.
    repetida = senas.transicionar(
        tenant_id=T1,
        sena_id=sena.id,
        desde="PENDIENTE",
        hacia="ACREDITADA",
        campos={"acreditada_en": AHORA + timedelta(hours=1)},
    )
    assert repetida is None
    actual = senas.obtener(tenant_id=T1, sena_id=sena.id)
    assert actual is not None
    assert actual.estado == "ACREDITADA"
    # El perdedor no pisa el instante del ganador (D11).
    assert actual.acreditada_en == AHORA

    # Estado esperado equivocado desde el principio: tampoco escribe.
    liberada = senas.transicionar(
        tenant_id=T1,
        sena_id=sena.id,
        desde="LIBERADA",
        hacia="DEVUELTA",
        campos={"devuelta_en": AHORA, "motivo_devolucion": "demo"},
    )
    assert liberada is None
    sigue = senas.obtener(tenant_id=T1, sena_id=sena.id)
    assert sigue is not None and sigue.estado == "ACREDITADA"


# ---------------------------------------------------------------------------
# 3.3 — bloquear y buscar por hash
# ---------------------------------------------------------------------------


def test_bloquear_y_buscar_por_hash() -> None:
    senas = SenaMemoria()
    sena = crear(senas, tenant_id=T1, token_hash="hash-bueno")
    crear(senas, tenant_id=T2, turno_id=TUR2, token_hash="hash-ajeno")

    bloqueada = senas.bloquear(tenant_id=T1, sena_id=sena.id)
    assert bloqueada.id == sena.id
    assert senas.bloqueos == [(T1, sena.id)]

    # Sólo el hash correcto y del tenant correcto resuelve.
    assert senas.por_token(tenant_id=T1, token_hash="hash-bueno") == sena
    assert senas.por_token(tenant_id=T1, token_hash="hash-ajeno") is None
    assert senas.por_token(tenant_id=T2, token_hash="hash-bueno") is None
    assert senas.por_token(tenant_id=T1, token_hash="hash-inexistente") is None


# ---------------------------------------------------------------------------
# 3.4 — la pasarela fake es determinista y sin red
# ---------------------------------------------------------------------------


def test_pasarela_fake_sin_red() -> None:
    pasarela = AdaptadorPasarelaFake()

    primera = pasarela.crear_preferencia(
        tenant_id=T1,
        sena_id="sena-1",
        turno_id=TUR1,
        monto_centavos=3000,
        descripcion="Seña de turno",
        expira_at=EXPIRA,
        url_pago="https://app.test/pagar/tok",
        url_webhook="https://app.test/api/webhooks/mercadopago",
    )
    segunda = pasarela.crear_preferencia(
        tenant_id=T1,
        sena_id="sena-1",
        turno_id=TUR1,
        monto_centavos=3000,
        descripcion="Seña de turno",
        expira_at=EXPIRA,
        url_pago="https://app.test/pagar/tok",
        url_webhook="https://app.test/api/webhooks/mercadopago",
    )

    assert isinstance(primera, Preferencia)
    assert primera.mp_preference_id == segunda.mp_preference_id
    assert primera.init_point == segunda.init_point
    assert "sena-1" in primera.init_point
    # La preferencia no lleva datos del paciente ni de la prestación (F-17).
    assert pasarela.preferencias[-1]["descripcion"] == "Seña de turno"
    assert pasarela.preferencias[-1]["monto_centavos"] == 3000

    pasarela.aprobar("PAG-A", sena_id="sena-1", monto_centavos=3000)
    pasarela.rechazar("PAG-B", sena_id="sena-1", monto_centavos=3000)
    pasarela.demorar("PAG-C", sena_id="sena-1", monto_centavos=3000)

    aprobado = pasarela.obtener_pago(mp_payment_id="PAG-A")
    assert aprobado.estado == "APPROVED"
    assert aprobado.monto_centavos == 3000
    assert aprobado.moneda == "ARS"
    assert aprobado.external_reference == "sena-1"
    assert pasarela.obtener_pago(mp_payment_id="PAG-B").estado == "REJECTED"
    assert pasarela.obtener_pago(mp_payment_id="PAG-C").estado == "PENDING"

    with pytest.raises(PagoNoEncontrado):
        pasarela.obtener_pago(mp_payment_id="PAG-DESCONOCIDO")

    pasarela.fallar("PAG-A")
    with pytest.raises(PasarelaNoDisponible):
        pasarela.obtener_pago(mp_payment_id="PAG-A")
    # Sólo el pago programado para fallar falla.
    assert pasarela.obtener_pago(mp_payment_id="PAG-B").estado == "REJECTED"

    pasarela.fallar()
    with pytest.raises(PasarelaNoDisponible):
        pasarela.crear_preferencia(
            tenant_id=T1,
            sena_id="sena-2",
            turno_id=TUR2,
            monto_centavos=3000,
            descripcion="Seña de turno",
            expira_at=EXPIRA,
            url_pago="https://app.test/pagar/tok2",
            url_webhook="https://app.test/api/webhooks/mercadopago",
        )


# ---------------------------------------------------------------------------
# 3.5 — ningún camino del dominio abre un socket
# ---------------------------------------------------------------------------


def test_ningun_test_abre_sockets() -> None:
    senas = SenaMemoria()
    pagos = PagoMPMemoria()
    pasarela = AdaptadorPasarelaFake()
    turnos = TurnoMemoriaSena({(T1, TUR1): AHORA + timedelta(days=7)})
    caja = AplicacionCajaMemoria()
    presupuestos = PresupuestosMemoria()
    auditoria = AuditoriaSenaMemoria()

    with patch.object(socket, "socket", side_effect=AssertionError("red prohibida en tests")):
        # Alta de la seña (paso 3 de D5).
        sena = crear(senas)
        auditoria.registrar(
            tenant_id=T1,
            accion="SENA_CREADA",
            actor="sistema",
            entidad="sena",
            entidad_id=sena.id,
            despues={"monto_centavos": 3000},
        )

        # Preferencia (paso 4 de D5), detrás de la única frontera de red.
        preferencia = pasarela.crear_preferencia(
            tenant_id=T1,
            sena_id=sena.id,
            turno_id=TUR1,
            monto_centavos=3000,
            descripcion="Seña de turno",
            expira_at=EXPIRA,
            url_pago="https://app.test/pagar/tok",
            url_webhook="https://app.test/api/webhooks/mercadopago",
        )
        assert preferencia.init_point.startswith("https://mp.test/")

        # Webhook: re-consulta del pago y registro idempotente.
        pasarela.aprobar("PAG-RED", sena_id=sena.id, monto_centavos=3000)
        externo = pasarela.obtener_pago(mp_payment_id="PAG-RED")
        pagos.registrar_o_actualizar(
            tenant_id=T1,
            sena_id=sena.id,
            mp_payment_id=externo.mp_payment_id,
            monto_centavos=externo.monto_centavos,
            moneda=externo.moneda,
            estado=externo.estado,
            resultado="ACREDITADA",
            raw_json={"id": externo.mp_payment_id, "status": "approved"},
            ahora=AHORA,
        )
        acreditada = senas.transicionar(
            tenant_id=T1,
            sena_id=sena.id,
            desde="PENDIENTE",
            hacia="ACREDITADA",
            campos={"acreditada_en": AHORA},
        )
        assert acreditada is not None
        turnos.confirmar_por_sena(tenant_id=T1, turno_id=TUR1, ahora=AHORA)

        # Aplicación al cobro: sólo el puerto, sin repositorios de caja.
        assert presupuestos.aceptado_vigente(tenant_id=T1, paciente_id="paciente-1", ahora=AHORA) is False
        movimiento = caja.registrar_ingreso_mp(
            tenant_id=T1,
            turno_id=TUR1,
            monto_centavos=3000,
            fecha=AHORA.date(),
            actor_id=U1,
            concepto="TRATAMIENTO",
        )
        assert movimiento.medio == "MP"
        assert caja.llamadas == [{"tenant_id": T1, "turno_id": TUR1, "monto_centavos": 3000}]

    # El espía registró exactamente las invocaciones de los puertos.
    assert pasarela.consultas == ["PAG-RED"]
    assert [entrada.accion for entrada in auditoria.entradas] == ["SENA_CREADA"]
