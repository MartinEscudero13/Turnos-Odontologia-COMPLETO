"""Task 5.15 — dos imputaciones simultáneas contra PostgreSQL real.

Esta prueba **no se simula con adaptadores en memoria**: la exclusión depende del
advisory lock por `(tenant, fecha)` (D14) que toma la unidad de trabajo real
antes de leer el estado del día, y del UNIQUE parcial
`(tenant_id, linea_id, tramo) WHERE origen='IMPUTACION'` (H1). Dos hilos abren
sesiones independientes, imputan la misma línea, tramo y medio y **ninguno**
responde error: la que pierde la carrera espera el lock y revalida el replay.
Se salta sin `C02_DATABASE_URL`.
"""
from __future__ import annotations

import threading
import uuid

import pytest
from _caja_sql import (
    AHORA,
    FECHA,
    cablear_caja,
    limpiar,
    motor,
    requiere_pg,
    sembrar_caja,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.caja import MovimientoCaja

pytestmark = requiere_pg


def _argumentos(ids: dict[str, str]) -> dict[str, object]:
    return {
        "tenant_id": ids["tenant"],
        "presupuesto_id": ids["presupuesto"],
        "linea_id": ids["linea"],
        "paciente_id": ids["paciente"],
        "prestacion_id": ids["prestacion"],
        "monto_paciente_centavos": 60000,
        "monto_os_centavos": 0,
        "actor_id": ids["usuario"],
        "turno_id": None,
        "medio": "EFECTIVO",
    }


def test_dos_imputaciones_crean_un_solo_movimiento() -> None:
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            ids = sembrar_caja(owner)
            tx.commit()

        barrera = threading.Barrier(2)
        errores: list[BaseException] = []

        def imputar() -> None:
            try:
                with Session(engine) as session:
                    caja = cablear_caja(session)
                    assert barrera.wait(timeout=10) >= 0
                    caja.adaptador.imputar_caja(**_argumentos(ids))  # type: ignore[arg-type]
            except BaseException as exc:  # noqa: BLE001 - se reporta cuál falló
                errores.append(exc)

        hilos = [threading.Thread(target=imputar) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)
        assert all(not hilo.is_alive() for hilo in hilos)
        # Ninguna conexión responde 500: la perdedora ve el replay, no un error.
        assert errores == []

        with Session(engine) as inspector:
            movimientos = inspector.query(MovimientoCaja).filter(
                MovimientoCaja.tenant_id == uuid.UUID(ids["tenant"]),
                MovimientoCaja.linea_id == uuid.UUID(ids["linea"]),
                MovimientoCaja.tramo == "PACIENTE",
            ).all()
            assert len(movimientos) == 1
            assert movimientos[0].monto == 60000
            assert movimientos[0].medio == "EFECTIVO"

            # El UNIQUE real es la última barrera (H1): un segundo ingreso de
            # imputación para la misma línea y tramo lo rechaza PostgreSQL.
            inspector.add(
                MovimientoCaja(
                    tenant_id=uuid.UUID(ids["tenant"]),
                    fecha=FECHA,
                    medio="TRANSFERENCIA",
                    monto=60000,
                    tipo="INGRESO",
                    usuario_id=uuid.UUID(ids["usuario"]),
                    tramo="PACIENTE",
                    presupuesto_id=uuid.UUID(ids["presupuesto"]),
                    linea_id=uuid.UUID(ids["linea"]),
                    paciente_id=uuid.UUID(ids["paciente"]),
                    origen="IMPUTACION",
                    creado_en=AHORA,
                )
            )
            with pytest.raises(IntegrityError):
                inspector.flush()
            inspector.rollback()
    finally:
        limpiar(engine, ids)
