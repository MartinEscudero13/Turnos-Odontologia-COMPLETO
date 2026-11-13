"""Tasks 6.32 y 6.33 — carrera movimiento ↔ cierre contra PostgreSQL real (H2).

Esta prueba **no se simula con adaptadores en memoria**: la invariante
"ningún movimiento del día cerrado queda fuera de su cierre" depende de que
toda escritura de caja y el cierre tomen el **mismo**
`pg_advisory_xact_lock(hashtext(tenant || ':' || fecha))` en la misma
transacción, antes de validar el estado del día y de insertar (D14).

Cada escenario se ejecuta en los **dos órdenes de interleaving**: la
transacción que corre primero queda pausada con el lock ya tomado y la otra
tiene que esperarlo de verdad. Resultados admitidos:

- 6.32: o el movimiento entra antes y el cierre lo cuenta (`total_efectivo=50000`),
  o el cierre gana y el alta responde `409 CIERRE_CERRADO`. Nunca un movimiento
  del día fuera del cierre y nunca `500`.
- 6.33: o el cobro entra antes y el cierre lo cuenta, o el cierre gana y el
  cobro asienta el ajuste post-cierre en el día abierto en lugar de insertar en
  el día cerrado.

Se salta sin `C02_DATABASE_URL`.
"""
from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from datetime import timedelta

import pytest
from _caja_sql import (
    FECHA,
    CableadoCaja,
    UowObservada,
    cablear_caja,
    limpiar,
    motor,
    requiere_pg,
    sembrar_caja,
)
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.caja.puertos import CobroPendiente
from app.caja.servicio import ConflictoCaja
from app.models.caja import AjustePostCierre, CierreDiario, MovimientoCaja
from app.models.caja import CobroPendiente as PendienteModel
from app.turnos.servicio import Actor

pytestmark = requiere_pg

ESPERA_MAXIMA = 30
DEMORA_ANTES_DE_LIBERAR = 0.3
DIA = FECHA
DIA_ANTERIOR = FECHA - timedelta(days=1)


def _actor(ids: dict[str, str]) -> Actor:
    return Actor(tenant_id=ids["tenant"], rol="RECEPCION", user_id=ids["usuario"])


def _alta(caja: CableadoCaja, ids: dict[str, str]) -> str:
    try:
        caja.servicio.registrar_movimiento(
            _actor(ids),
            monto=50000,
            medio="EFECTIVO",
            fecha=DIA,
        )
        return "201"
    except ConflictoCaja as exc:
        return "409" if exc.codigo_dominio == "CIERRE_CERRADO" else "500"


def _cerrar(
    caja: CableadoCaja, ids: dict[str, str], *, fecha: object, efectivo_contado: int
) -> str:
    try:
        caja.servicio.cerrar_dia(
            _actor(ids),
            fecha=fecha,  # type: ignore[arg-type]
            efectivo_contado=efectivo_contado,
            responsable_id=ids["usuario"],
            motivo_diferencia="arqueo de prueba",
        )
        return "201"
    except ConflictoCaja as exc:
        return "409" if exc.codigo_dominio == "CIERRE_EXISTENTE" else "500"


def _correr_en_paralelo(
    engine: Engine,
    *,
    primero: str,
    acciones: dict[str, Callable[[CableadoCaja], str]],
) -> tuple[dict[str, str], dict[str, float], list[BaseException]]:
    """Corre dos acciones: `primero` retiene el lock hasta que la otra espera."""
    segundo = next(clave for clave in acciones if clave != primero)
    listo = threading.Event()
    liberar = threading.Event()
    resultados: dict[str, str] = {}
    esperas: dict[str, float] = {}
    errores: list[BaseException] = []

    def correr(clave: str, *, pausa: bool, esperar_primero: bool) -> None:
        try:
            if esperar_primero:
                assert listo.wait(ESPERA_MAXIMA), f"{primero} nunca tomó el lock"
            with Session(engine) as session:

                def al_bloquear(_fecha: object) -> None:
                    if pausa:
                        listo.set()
                        if not liberar.wait(ESPERA_MAXIMA):
                            raise RuntimeError("la prueba no liberó el lock")

                caja = cablear_caja(
                    session,
                    uow_factory=lambda: UowObservada(session, al_bloquear=al_bloquear),
                )
                inicio = time.monotonic()
                resultados[clave] = acciones[clave](caja)
                esperas[clave] = time.monotonic() - inicio
        except BaseException as exc:  # noqa: BLE001 - se reporta en el test
            errores.append(exc)

    hilos = [
        threading.Thread(
            target=correr,
            args=(primero,),
            kwargs={"pausa": True, "esperar_primero": False},
            daemon=True,
        ),
        threading.Thread(
            target=correr,
            args=(segundo,),
            kwargs={"pausa": False, "esperar_primero": True},
            daemon=True,
        ),
    ]
    for hilo in hilos:
        hilo.start()
    assert listo.wait(ESPERA_MAXIMA)
    time.sleep(DEMORA_ANTES_DE_LIBERAR)
    liberar.set()
    for hilo in hilos:
        hilo.join(timeout=ESPERA_MAXIMA)
        assert not hilo.is_alive()
    return resultados, esperas, errores


def _total_efectivo(session: Session, tenant: uuid.UUID, fecha: object) -> int:
    """Neto de efectivo de los movimientos vigentes del día (D4)."""
    total = 0
    filas = session.scalars(
        select(MovimientoCaja).where(
            MovimientoCaja.tenant_id == tenant,
            MovimientoCaja.fecha == fecha,
            MovimientoCaja.anulado.is_(False),
        )
    ).all()
    for fila in filas:
        signo = 1 if fila.tipo == "INGRESO" else -1
        total += signo * fila.monto
    return total


def _sembrar(engine: Engine) -> dict[str, str]:
    with engine.connect() as owner:
        tx = owner.begin()
        ids = sembrar_caja(owner)
        tx.commit()
    return ids


@pytest.mark.parametrize("primero", ["movimiento", "cierre"])
def test_movimiento_y_cierre_no_se_cruzan(primero: str) -> None:
    """6.32 — el alta y el cierre del mismo día no se cruzan (ambos órdenes)."""
    engine = motor()
    ids: dict[str, str] = {}
    try:
        ids = _sembrar(engine)
        resultados, esperas, errores = _correr_en_paralelo(
            engine,
            primero=primero,
            acciones={
                "movimiento": lambda caja: _alta(caja, ids),
                "cierre": lambda caja: _cerrar(
                    caja, ids, fecha=DIA, efectivo_contado=50000
                ),
            },
        )

        assert errores == []
        assert resultados["cierre"] == "201"
        assert resultados[primero] == "201"
        segunda = "cierre" if primero == "movimiento" else "movimiento"
        assert esperas[segunda] >= DEMORA_ANTES_DE_LIBERAR / 2

        tenant = uuid.UUID(ids["tenant"])
        with Session(engine) as inspector:
            cierre = inspector.scalars(
                select(CierreDiario).where(CierreDiario.tenant_id == tenant)
            ).one()
            movimientos = inspector.scalars(
                select(MovimientoCaja).where(
                    MovimientoCaja.tenant_id == tenant,
                    MovimientoCaja.fecha == DIA,
                )
            ).all()

            if primero == "movimiento":
                # El movimiento entró antes: el cierre lo cuenta.
                assert resultados["movimiento"] == "201"
                assert cierre.total_efectivo == 50000
                assert len(movimientos) == 1
            else:
                # El cierre ganó: el alta es rechazada y no deja movimientos.
                assert resultados["movimiento"] == "409"
                assert cierre.total_efectivo == 0
                assert movimientos == []

            # Invariante central: ningún movimiento del día cerrado queda fuera.
            assert cierre.total_efectivo == _total_efectivo(inspector, tenant, DIA)
            assert cierre.diferencia == cierre.efectivo_contado - cierre.total_efectivo
    finally:
        limpiar(engine, ids)


@pytest.mark.parametrize("primero", ["cobro", "cierre"])
def test_cobro_de_pendiente_respeta_el_lock(primero: str) -> None:
    """6.33 — el cobro de un pendiente del día cerrado asienta el ajuste."""
    engine = motor()
    ids: dict[str, str] = {}
    try:
        ids = _sembrar(engine)
        with Session(engine) as session:
            caja = cablear_caja(session)
            creado = caja.servicio.imputar_tramo_paciente(
                tenant_id=ids["tenant"],
                presupuesto_id=ids["presupuesto"],
                linea_id=ids["linea"],
                paciente_id=ids["paciente"],
                monto_paciente_centavos=60000,
                actor_id=ids["usuario"],
                medio=None,
                fecha=DIA_ANTERIOR,
            )
        assert isinstance(creado, CobroPendiente)
        pendiente_id = uuid.UUID(creado.id)

        def cobrar(caja: CableadoCaja) -> str:
            caja.servicio.cobrar_pendiente(
                _actor(ids), pendiente_id=creado.id, medio="EFECTIVO"
            )
            return "201"

        resultados, esperas, errores = _correr_en_paralelo(
            engine,
            primero=primero,
            acciones={
                "cobro": cobrar,
                "cierre": lambda caja: _cerrar(
                    caja, ids, fecha=DIA_ANTERIOR, efectivo_contado=60000
                ),
            },
        )

        assert errores == []
        assert resultados == {"cobro": "201", "cierre": "201"}
        segunda = "cierre" if primero == "cobro" else "cobro"
        assert esperas[segunda] >= DEMORA_ANTES_DE_LIBERAR / 2

        tenant = uuid.UUID(ids["tenant"])
        with Session(engine) as inspector:
            cierre = inspector.scalars(
                select(CierreDiario).where(
                    CierreDiario.tenant_id == tenant,
                    CierreDiario.fecha == DIA_ANTERIOR,
                )
            ).one()
            movimientos = inspector.scalars(
                select(MovimientoCaja).where(
                    MovimientoCaja.tenant_id == tenant,
                    MovimientoCaja.fecha.in_({DIA, DIA_ANTERIOR}),
                )
            ).all()
            pendiente = inspector.get(PendienteModel, pendiente_id)
            assert pendiente is not None
            assert pendiente.resuelto_en is not None
            assert pendiente.movimiento_id is not None

            if primero == "cobro":
                # El cobro entró antes: el cierre del día anterior lo cuenta.
                assert cierre.total_efectivo == 60000
                assert len(movimientos) == 1
                assert movimientos[0].fecha == DIA_ANTERIOR
                assert movimientos[0].medio == "EFECTIVO"
                assert (
                    inspector.scalars(
                        select(AjustePostCierre).where(
                            AjustePostCierre.tenant_id == tenant
                        )
                    ).all()
                    == []
                )
            else:
                # El cierre ganó: el cobro no inserta en el día cerrado, se
                # fecha el día del registro y asienta el ajuste contra el cierre.
                assert cierre.total_efectivo == 0
                assert len(movimientos) == 1
                assert movimientos[0].fecha == DIA
                ajustes = inspector.scalars(
                    select(AjustePostCierre).where(
                        AjustePostCierre.tenant_id == tenant
                    )
                ).all()
                assert len(ajustes) == 1
                assert ajustes[0].tipo == "COBRO_PENDIENTE"
                assert ajustes[0].cierre_id == cierre.id
                assert ajustes[0].cobro_pendiente_id == pendiente_id
                assert ajustes[0].monto == 60000
                assert ajustes[0].medio == "EFECTIVO"

            # Invariante central: el día cerrado no tiene movimientos sin contar.
            assert cierre.total_efectivo == _total_efectivo(
                inspector, tenant, DIA_ANTERIOR
            )
    finally:
        limpiar(engine, ids)
