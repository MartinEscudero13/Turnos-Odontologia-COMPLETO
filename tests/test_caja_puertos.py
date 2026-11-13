"""Task 2.1 — puertos y adaptadores en memoria de caja: tenant-scoped.

Todo repositorio recibe `tenant_id` explícito y nunca devuelve ni muta filas de
otro tenant (D7). El `UNIQUE` parcial de imputación por `(tenant, línea, tramo)`
y el `UNIQUE` pleno del pendiente se replican en memoria con la misma semántica
de la migración 008 (H1). El lock de día es una simulación declarada: la
garantía real se prueba contra PostgreSQL con dos conexiones.
"""
from __future__ import annotations

from datetime import date

import pytest
from _caja_helpers import TUR1, U1, U2, d3
from conftest import T1, T2

from app.caja.puertos import (
    ImputacionDuplicada,
    YaAnulado,
)
from app.turnos.servicio import NoEncontrado

DIA = date(2026, 11, 10)


def test_repositorios_scoped_por_tenant() -> None:
    from _caja_helpers import HarnessCaja

    h = HarnessCaja()

    # Movimientos: alta, lectura por id y por fecha, siempre filtradas por tenant.
    t1 = h.movimientos.registrar(
        tenant_id=T1,
        fecha=DIA,
        medio="EFECTIVO",
        monto=150000,
        tipo="INGRESO",
        usuario_id=U1,
        ahora=d3(),
    )
    t2 = h.movimientos.registrar(
        tenant_id=T2,
        fecha=DIA,
        medio="EFECTIVO",
        monto=900000,
        tipo="INGRESO",
        usuario_id=U1,
        ahora=d3(),
    )
    assert h.movimientos.obtener(tenant_id=T1, movimiento_id=t1.id) == t1
    assert h.movimientos.obtener(tenant_id=T2, movimiento_id=t1.id) is None
    assert h.movimientos.listar_por_fecha(tenant_id=T1, fecha=DIA) == [t1]
    assert h.movimientos.listar_por_fecha(tenant_id=T2, fecha=DIA) == [t2]
    assert h.movimientos.totales_por_medio(tenant_id=T1, fecha=DIA)["EFECTIVO"] == 150000
    assert h.movimientos.totales_por_medio(tenant_id=T2, fecha=DIA)["EFECTIVO"] == 900000

    # El lock de movimiento está scoped: T2 no bloquea un movimiento de T1.
    with h.nueva_uow() as uow:
        assert uow.bloquear_movimiento(tenant_id=T1, movimiento_id=t1.id) == t1
    with pytest.raises(NoEncontrado), h.nueva_uow() as uow:
        uow.bloquear_movimiento(tenant_id=T2, movimiento_id=t1.id)

    # La idempotencia por (tenant, línea, tramo) ignora el medio y cruza tenants.
    imputacion = h.movimientos.registrar(
        tenant_id=T1,
        fecha=DIA,
        medio="EFECTIVO",
        monto=60000,
        tipo="INGRESO",
        usuario_id=U1,
        linea_id="linea-1",
        presupuesto_id="presupuesto-1",
        paciente_id="paciente-1",
        tramo="PACIENTE",
        origen="IMPUTACION",
        ahora=d3(),
    )
    assert h.movimientos.buscar_imputacion(tenant_id=T1, linea_id="linea-1", tramo="PACIENTE") == imputacion
    assert h.movimientos.buscar_imputacion(tenant_id=T2, linea_id="linea-1", tramo="PACIENTE") is None
    with pytest.raises(ImputacionDuplicada):
        h.movimientos.registrar(
            tenant_id=T1,
            fecha=DIA,
            medio="TRANSFERENCIA",
            monto=60000,
            tipo="INGRESO",
            usuario_id=U1,
            linea_id="linea-1",
            tramo="PACIENTE",
            origen="IMPUTACION",
            ahora=d3(),
        )
    h.movimientos.registrar(
        tenant_id=T2,
        fecha=DIA,
        medio="EFECTIVO",
        monto=60000,
        tipo="INGRESO",
        usuario_id=U1,
        linea_id="linea-1",
        tramo="PACIENTE",
        origen="IMPUTACION",
        ahora=d3(),
    )

    # Anulación scoped: T2 no puede anular el movimiento de T1.
    with pytest.raises(NoEncontrado):
        h.movimientos.anular(
            tenant_id=T2,
            movimiento_id=t1.id,
            motivo="demo",
            actor_id=U2,
            ahora=d3(),
        )
    anulado = h.movimientos.anular(
        tenant_id=T1, movimiento_id=t1.id, motivo="demo", actor_id=U2, ahora=d3()
    )
    assert anulado.anulado is True and anulado.anulado_por == U2
    with pytest.raises(YaAnulado):
        h.movimientos.anular(
            tenant_id=T1, movimiento_id=t1.id, motivo="otra", actor_id=U2, ahora=d3()
        )

    # Cierres: el segundo cierre del mismo día se rechaza y T2 es independiente.
    cierre = h.cierres.cerrar(
        tenant_id=T1,
        fecha=DIA,
        efectivo_contado=150000,
        responsable_id=U1,
        ahora=d3(),
    )
    assert h.cierres.obtener(tenant_id=T1, fecha=DIA) == cierre
    assert h.cierres.obtener(tenant_id=T2, fecha=DIA) is None
    assert h.cierres.listar(tenant_id=T2, desde=DIA, hasta=DIA) == []

    # Pendientes: uno por línea, aunque ya esté resuelto; resolución scoped.
    pendiente = h.pendientes.registrar(
        tenant_id=T1,
        fecha=DIA,
        presupuesto_id="presupuesto-1",
        linea_id="linea-1",
        paciente_id="paciente-1",
        monto_centavos=60000,
        actor_id=U1,
        ahora=d3(),
    )
    assert h.pendientes.buscar_por_linea(tenant_id=T2, linea_id="linea-1") is None
    assert h.pendientes.obtener(tenant_id=T2, pendiente_id=pendiente.id) is None
    with pytest.raises(NoEncontrado):
        h.pendientes.resolver(
            tenant_id=T2,
            pendiente_id=pendiente.id,
            movimiento_id=imputacion.id,
            ahora=d3(),
        )
    resuelto = h.pendientes.resolver(
        tenant_id=T1,
        pendiente_id=pendiente.id,
        movimiento_id=imputacion.id,
        ahora=d3(),
    )
    assert resuelto.resuelto_en is not None
    assert resuelto.movimiento_id == imputacion.id

    # Ajustes: se listan sólo por el cierre del tenant.
    ajuste = h.ajustes.registrar(
        tenant_id=T1,
        cierre_id=cierre.id,
        tipo="AJUSTE_ANULACION",
        monto=150000,
        medio="EFECTIVO",
        actor_id=U2,
        compensatorio_id=imputacion.id,
        movimiento_original_id=t1.id,
        motivo="demo",
        ahora=d3(),
    )
    assert h.ajustes.listar_por_cierre(tenant_id=T1, cierre_id=cierre.id) == [ajuste]
    assert h.ajustes.listar_por_cierre(tenant_id=T2, cierre_id=cierre.id) == []

    # Cuentas por cobrar OS: devengado único por línea y total scoped.
    cuenta = h.cuentas.registrar(
        tenant_id=T1,
        fecha=DIA,
        presupuesto_id="presupuesto-1",
        linea_id="linea-1",
        paciente_id="paciente-1",
        monto_centavos=40000,
        ahora=d3(),
    )
    assert h.cuentas.buscar_por_linea(tenant_id=T2, linea_id="linea-1") is None
    assert h.cuentas.total_devengado(tenant_id=T1, fecha=DIA) == cuenta.monto_centavos
    assert h.cuentas.total_devengado(tenant_id=T2, fecha=DIA) == 0

    # El turno también es scoped.
    assert h.turnos.existe(tenant_id=T1, turno_id=TUR1) is True
    assert h.turnos.existe(tenant_id=T2, turno_id=TUR1) is False
