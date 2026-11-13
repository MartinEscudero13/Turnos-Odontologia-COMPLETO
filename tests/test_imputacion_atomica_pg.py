"""Task 5.16 — M4: si la escritura de caja falla, la aceptación de C-09 revierte.

Integración con PostgreSQL real (migraciones 007 y 008 aplicadas): C-09 corre
sobre repositorios SQLAlchemy y su puerto de imputación es el adaptador real de
C-10, los dos sobre la **misma** `Session`. El fallo se fuerza con un error real
de la base: el actor de la aceptación no existe en `usuarios`, y el
`INSERT` de `movimientos_caja` viola la FK `usuario_id` (RESTRICT). Como la
aceptación y la caja comparten transacción, el rollback revierte `aceptaciones`,
el estado del presupuesto y el devengado OS: no queda ningún movimiento.

No se usan adaptadores en memoria para la persistencia bajo prueba. El caso
exitoso gemelo (`test_aceptacion_exitosa...`) verifica que el mismo cableado sí
persiste los dos tramos, para que el fallo no sea un "siempre falla".
"""
from __future__ import annotations

import uuid

import pytest
from _caja_sql import (
    AHORA,
    FECHA,
    cablear_caja,
    cablear_presupuesto,
    limpiar,
    motor,
    requiere_pg,
    sembrar_caja,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.caja import (
    CobroPendiente,
    CuentaPorCobrarOS,
    MovimientoCaja,
)
from app.models.presupuesto import (
    Aceptacion,
    Presupuesto,
    PresupuestoLinea,
)
from app.presupuesto.servicio import ServicioNoDisponible
from app.turnos.servicio import Actor

pytestmark = requiere_pg


def _actor(ids: dict[str, str], *, user_id: str) -> Actor:
    return Actor(tenant_id=ids["tenant"], rol="RECEPCION", user_id=user_id)


def _aceptar(session: Session, ids: dict[str, str], actor: Actor) -> object:
    caja = cablear_caja(session)
    presupuestos = cablear_presupuesto(session, caja, ids)
    return presupuestos.registrar_aceptacion(
        actor,
        presupuesto_id=ids["presupuesto"],
        linea_id=ids["linea"],
        acepta=True,
        canal="CONSULTORIO",
        medio="EFECTIVO",
        ahora=AHORA,
    )


def _contar(session: Session, modelo: type[object], **filtros: uuid.UUID) -> int:
    consulta = select(func.count()).select_from(modelo)  # type: ignore[arg-type]
    for columna, valor in filtros.items():
        consulta = consulta.where(getattr(modelo, columna) == valor)
    return int(session.scalar(consulta) or 0)


def test_fallo_de_caja_revierte_la_aceptacion_de_c09() -> None:
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            ids = sembrar_caja(owner)
            tx.commit()

        tenant = uuid.UUID(ids["tenant"])
        linea = uuid.UUID(ids["linea"])
        # Actor cuyo usuario no existe: la aceptación no referencia `usuarios`,
        # pero el movimiento de caja sí. El INSERT falla en PostgreSQL (FK).
        fantasma = _actor(ids, user_id=str(uuid.uuid4()))

        with Session(engine) as session, pytest.raises(ServicioNoDisponible):
            _aceptar(session, ids, fantasma)

        # Segunda conexión: se inspecciona lo que quedó commiteado (nada).
        with engine.connect() as inspector:
            assert _contar(inspector, Aceptacion, tenant_id=tenant) == 0
            assert _contar(inspector, MovimientoCaja, tenant_id=tenant) == 0
            assert _contar(inspector, CuentaPorCobrarOS, tenant_id=tenant) == 0
            assert _contar(inspector, CobroPendiente, tenant_id=tenant) == 0
            estado = inspector.scalar(
                select(Presupuesto.estado).where(Presupuesto.id == uuid.UUID(ids["presupuesto"]))
            )
            assert estado == "VIGENTE"
            montos = inspector.execute(
                select(
                    PresupuestoLinea.monto,
                    PresupuestoLinea.cobertura_os,
                    PresupuestoLinea.a_cargo_paciente,
                ).where(PresupuestoLinea.id == linea)
            ).one()
            assert montos == (100000, 40000, 60000)
    finally:
        limpiar(engine, ids)


def test_aceptacion_exitosa_persiste_los_dos_tramos_en_la_misma_transaccion() -> None:
    """Control del mismo cableado: con un usuario real, C-09 + caja commitean."""
    engine = motor()
    ids: dict[str, str] = {}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            ids = sembrar_caja(owner)
            tx.commit()

        tenant = uuid.UUID(ids["tenant"])
        with Session(engine) as session:
            decision = _aceptar(session, ids, _actor(ids, user_id=ids["usuario"]))
            assert decision.aceptacion.acepta is True  # type: ignore[attr-defined]
            assert decision.aceptacion.medio == "EFECTIVO"  # type: ignore[attr-defined]
            assert decision.presupuesto.estado == "ACEPTADO"  # type: ignore[attr-defined]

        with engine.connect() as inspector:
            aceptaciones = inspector.execute(
                select(Aceptacion.acepta, Aceptacion.canal).where(
                    Aceptacion.tenant_id == tenant
                )
            ).all()
            assert aceptaciones == [(True, "CONSULTORIO")]
            movimientos = inspector.execute(
                select(MovimientoCaja.monto, MovimientoCaja.medio, MovimientoCaja.tramo).where(
                    MovimientoCaja.tenant_id == tenant
                )
            ).all()
            assert movimientos == [(60000, "EFECTIVO", "PACIENTE")]
            cuentas = inspector.execute(
                select(CuentaPorCobrarOS.monto_centavos, CuentaPorCobrarOS.fecha).where(
                    CuentaPorCobrarOS.tenant_id == tenant
                )
            ).all()
            assert cuentas == [(40000, FECHA)]
            estado = inspector.scalar(
                select(Presupuesto.estado).where(
                    Presupuesto.id == uuid.UUID(ids["presupuesto"])
                )
            )
            assert estado == "ACEPTADO"
            assert _contar(inspector, CobroPendiente, tenant_id=tenant) == 0
    finally:
        limpiar(engine, ids)
