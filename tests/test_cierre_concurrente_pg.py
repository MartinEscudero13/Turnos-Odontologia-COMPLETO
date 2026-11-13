"""Task 6.31 — dos cierres simultáneos del mismo día contra PostgreSQL real.

La garantía "un cierre por `(tenant, fecha)`" no se prueba con adaptadores en
memoria: depende del advisory lock `pg_advisory_xact_lock(hashtext(tenant ||
':' || fecha))` que el cierre toma **antes** de leer los totales y de insertar
(D14) y del `UNIQUE (tenant_id, fecha)` de la 008 como última barrera.

Dos conexiones independientes cierran el mismo día a la vez: la primera queda
pausada con el lock tomado, la segunda tiene que esperarlo de verdad, y después
del commit ve el cierre existente y responde `409 CIERRE_EXISTENTE`. Resultado:
un `201`, un `409`, exactamente una fila y ninguna conexión `500`.
Se salta sin `C02_DATABASE_URL`.
"""
from __future__ import annotations

import threading
import time
import uuid

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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.caja.servicio import ConflictoCaja
from app.models.caja import CierreDiario
from app.turnos.servicio import Actor

pytestmark = requiere_pg

ESPERA_MAXIMA = 30
DEMORA_ANTES_DE_LIBERAR = 0.3


def _actor(ids: dict[str, str]) -> Actor:
    return Actor(tenant_id=ids["tenant"], rol="RECEPCION", user_id=ids["usuario"])


def _cerrar(caja: CableadoCaja, ids: dict[str, str]) -> str:
    """Cierre mapeado al contrato observable: `201` o `409`, nunca `500`."""
    try:
        caja.servicio.cerrar_dia(
            _actor(ids),
            fecha=FECHA,
            efectivo_contado=0,
            responsable_id=ids["usuario"],
            motivo_diferencia="arqueo de prueba",
        )
        return "201"
    except ConflictoCaja as exc:
        return "409" if exc.codigo_dominio == "CIERRE_EXISTENTE" else "500"


def test_dos_cierres_simultaneos_crean_uno_solo() -> None:
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            ids = sembrar_caja(owner)
            tx.commit()

        listo = threading.Event()
        liberar = threading.Event()
        resultados: dict[str, str] = {}
        esperas: list[float] = []
        errores: list[BaseException] = []

        def primera() -> None:
            try:
                with Session(engine) as session:
                    def pausar_con_lock(fecha: object) -> None:
                        # El lock del día ya está tomado en esta transacción.
                        assert fecha == FECHA
                        listo.set()
                        if not liberar.wait(ESPERA_MAXIMA):
                            raise RuntimeError("la prueba no liberó el lock")

                    caja = cablear_caja(
                        session,
                        uow_factory=lambda: UowObservada(session, al_bloquear=pausar_con_lock),
                    )
                    resultados["primera"] = _cerrar(caja, ids)
            except BaseException as exc:  # noqa: BLE001 - se reporta en el test
                errores.append(exc)

        def segunda() -> None:
            try:
                assert listo.wait(ESPERA_MAXIMA), "la primera nunca tomó el lock"
                with Session(engine) as session:
                    caja = cablear_caja(session)
                    inicio = time.monotonic()
                    # Bloquea en `pg_advisory_xact_lock` hasta el commit de la primera.
                    resultados["segunda"] = _cerrar(caja, ids)
                    esperas.append(time.monotonic() - inicio)
            except BaseException as exc:  # noqa: BLE001 - se reporta en el test
                errores.append(exc)

        hilos = [
            threading.Thread(target=primera, daemon=True),
            threading.Thread(target=segunda, daemon=True),
        ]
        for hilo in hilos:
            hilo.start()
        # La segunda ya está esperando el lock: se libera la primera.
        assert listo.wait(ESPERA_MAXIMA)
        time.sleep(DEMORA_ANTES_DE_LIBERAR)
        liberar.set()
        for hilo in hilos:
            hilo.join(timeout=ESPERA_MAXIMA)
            assert not hilo.is_alive()

        assert errores == []
        assert resultados == {"primera": "201", "segunda": "409"}
        # La segunda esperó el lock real de verdad (no ganó por tiempo de arranque).
        assert esperas and esperas[0] >= DEMORA_ANTES_DE_LIBERAR / 2

        tenant = uuid.UUID(ids["tenant"])
        with Session(engine) as inspector:
            total = inspector.scalar(
                select(func.count()).select_from(CierreDiario).where(
                    CierreDiario.tenant_id == tenant
                )
            )
            assert total == 1
            cierre = inspector.scalars(
                select(CierreDiario).where(CierreDiario.tenant_id == tenant)
            ).one()
            assert cierre.fecha == FECHA
            assert cierre.total_efectivo == 0
            assert cierre.efectivo_contado == 0
            assert cierre.diferencia == 0
            assert cierre.responsable_id == uuid.UUID(ids["usuario"])
    finally:
        limpiar(engine, ids)
