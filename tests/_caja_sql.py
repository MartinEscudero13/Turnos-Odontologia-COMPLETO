"""Wiring SQLAlchemy real de caja y presupuesto para los tests PG — C-10 §5.

No es un helper de dominio: es el cableado de **persistencia** que usa la misma
`Session` para los repositorios de C-09 (`aceptaciones`, `presupuesto_lineas`,
`presupuestos`) y los de C-10 (`movimientos_caja`, `cuentas_por_cobrar_os`), para
probar M4 contra PostgreSQL real: si la escritura de caja falla, la transacción
revierte la aceptación de C-09.

Se salta todo sin `C02_DATABASE_URL`. Datos ficticios (RN-GL-03): tenant, usuario
`ADMIN`, paciente, prestación, presupuesto `VIGENTE` con una línea de
`100000 = 40000 OS + 60000 paciente` y un turno del mismo tenant.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.caja.adaptador_imputacion import AdaptadorCaja
from app.caja.repositorios import (
    AjustesSQL,
    AuditoriaSQL,
    CierresSQL,
    CobrosSQL,
    CuentasOSSQL,
    LineasPresupuestoSQL,
    MovimientosSQL,
    TurnosSQL,
    UnidadDeTrabajoCajaSQL,
)
from app.caja.servicio import ServicioCaja
from app.ficha_clinica.puertos import ConsentimientoMemoria
from app.presupuesto.puertos import CoberturaSinDatos, PacienteMemoria, PrestacionMemoria
from app.presupuesto.repositorios import (
    AceptacionesSQL,
    LineasSQL,
    PresupuestosSQL,
    UnidadDeTrabajoPresupuestoSQL,
)
from app.presupuesto.servicio import ServicioPresupuesto

PG_URL = os.environ.get("C02_DATABASE_URL")
requiere_pg = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 11, 10, 0, tzinfo=TZ)
FECHA = AHORA.date()
MONTO = 100000
COBERTURA_OS = 40000
A_CARGO_PACIENTE = 60000


def motor() -> Engine:
    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


def sembrar_caja(conn: Connection) -> dict[str, str]:
    """Crea tenant, usuario, paciente, prestación, presupuesto, línea y turno."""
    ids = {
        clave: str(uuid.uuid4())
        for clave in (
            "tenant",
            "usuario",
            "paciente",
            "prestacion",
            "presupuesto",
            "linea",
            "turno",
            "profesional",
            "sillon",
        )
    }
    conn.execute(
        text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T10 §5', :slug)"),
        {"id": ids["tenant"], "slug": f"c10s5-{ids['tenant'][:8]}"},
    )
    conn.execute(
        text(
            "INSERT INTO usuarios (id, tenant_id, nombre, email, password_hash, rol)"
            " VALUES (:id, :t, 'Recepción Demo', :email, 'x', 'RECEPCION')"
        ),
        {
            "id": ids["usuario"],
            "t": ids["tenant"],
            "email": f"u10s5-{ids['usuario'][:8]}@demo.test",
        },
    )
    conn.execute(
        text(
            "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
            " VALUES (:id, :t, 'Paciente Demo', :tel)"
        ),
        {
            "id": ids["paciente"],
            "t": ids["tenant"],
            "tel": f"+5491{int(ids['paciente'].replace('-', ''), 16) % 10**10:010d}",
        },
    )
    conn.execute(
        text(
            "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base)"
            " VALUES (:id, :t, 'Conducto Demo', 30, :monto)"
        ),
        {"id": ids["prestacion"], "t": ids["tenant"], "monto": MONTO},
    )
    conn.execute(
        text(
            "INSERT INTO presupuestos (id, tenant_id, paciente_id, estado)"
            " VALUES (:id, :t, :p, 'VIGENTE')"
        ),
        {"id": ids["presupuesto"], "t": ids["tenant"], "p": ids["paciente"]},
    )
    conn.execute(
        text(
            "INSERT INTO presupuesto_lineas"
            " (id, tenant_id, presupuesto_id, prestacion_id, monto, cobertura_os,"
            "  a_cargo_paciente)"
            " VALUES (:id, :t, :pr, :pres, :monto, :os, :pac)"
        ),
        {
            "id": ids["linea"],
            "t": ids["tenant"],
            "pr": ids["presupuesto"],
            "pres": ids["prestacion"],
            "monto": MONTO,
            "os": COBERTURA_OS,
            "pac": A_CARGO_PACIENTE,
        },
    )
    conn.execute(
        text(
            "INSERT INTO turnos"
            " (id, tenant_id, profesional_id, sillon_id, paciente_id, prestacion_id,"
            "  inicio, fin)"
            " VALUES (:id, :t, :prof, :sil, :pac, :pres, :inicio, :fin)"
        ),
        {
            "id": ids["turno"],
            "t": ids["tenant"],
            "prof": ids["profesional"],
            "sil": ids["sillon"],
            "pac": ids["paciente"],
            "pres": ids["prestacion"],
            "inicio": AHORA,
            "fin": AHORA + timedelta(minutes=30),
        },
    )
    return ids


@dataclass(frozen=True)
class CableadoCaja:
    """Repositorios y servicios de caja sobre una `Session`."""

    movimientos: MovimientosSQL
    cierres: CierresSQL
    pendientes: CobrosSQL
    ajustes: AjustesSQL
    cuentas: CuentasOSSQL
    turnos: TurnosSQL
    lineas: LineasPresupuestoSQL
    auditoria: AuditoriaSQL
    servicio: ServicioCaja
    adaptador: AdaptadorCaja


def cablear_caja(session: Session, *, ahora: datetime = AHORA) -> CableadoCaja:
    """Cablea el dominio de caja con persistencia real sobre `session`."""
    movimientos = MovimientosSQL(session)
    cuentas = CuentasOSSQL(session)
    cierres = CierresSQL(session, movimientos, cuentas)
    pendientes = CobrosSQL(session)
    ajustes = AjustesSQL(session)
    turnos = TurnosSQL(session)
    lineas = LineasPresupuestoSQL(session)
    auditoria = AuditoriaSQL(session)

    def uow_factory() -> UnidadDeTrabajoCajaSQL:
        return UnidadDeTrabajoCajaSQL(session)

    servicio = ServicioCaja(
        movimientos,
        cierres,
        pendientes,
        ajustes,
        cuentas,
        turnos,
        auditoria,
        uow_factory=uow_factory,
        reloj=lambda: ahora,
    )
    adaptador = AdaptadorCaja(
        servicio=servicio,
        cuentas=cuentas,
        lineas=lineas,
        uow_factory=uow_factory,
        reloj=lambda: ahora,
    )
    return CableadoCaja(
        movimientos=movimientos,
        cierres=cierres,
        pendientes=pendientes,
        ajustes=ajustes,
        cuentas=cuentas,
        turnos=turnos,
        lineas=lineas,
        auditoria=auditoria,
        servicio=servicio,
        adaptador=adaptador,
    )


def cablear_presupuesto(
    session: Session,
    caja: CableadoCaja,
    ids: dict[str, str],
    *,
    ahora: datetime = AHORA,
) -> ServicioPresupuesto:
    """C-09 real sobre la **misma** `Session`; su puerto de caja es el adaptador."""
    pacientes = PacienteMemoria()
    pacientes.agregar(ids["tenant"], ids["paciente"])
    return ServicioPresupuesto(
        PresupuestosSQL(session),
        LineasSQL(session),
        AceptacionesSQL(session),
        PrestacionMemoria(),
        pacientes,
        CoberturaSinDatos(),
        caja.adaptador,
        caja.auditoria,
        consentimientos=ConsentimientoMemoria(),
        uow_factory=lambda: UnidadDeTrabajoPresupuestoSQL(session),
        reloj=lambda: ahora,
    )


def limpiar(engine: Engine, ids: dict[str, str]) -> None:
    """Borra el tenant sembrado (cascade) y libera el engine."""
    if ids:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": ids["tenant"]})
            tx.commit()
    engine.dispose()
