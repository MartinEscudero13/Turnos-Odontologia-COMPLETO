"""Utilidades de PostgreSQL real para los tests de anulación de caja — C-10.

Se salta todo sin `C02_DATABASE_URL`. Datos ficticios (RN-GL-03): un tenant, un
usuario ADMIN, un ingreso manual de `150000` en efectivo del `2026-11-10` y el
cierre de ese día con sus totales. Las sentencias replican el camino que el
servicio ejecuta dentro de la unidad de trabajo (D14): advisory lock por
`(tenant, fecha)`, transición única `vigente → anulado` y, si corresponde,
compensatorio y ajuste post-cierre.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

PG_URL = os.environ.get("C02_DATABASE_URL")
requiere_pg = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")

TZ = timezone(timedelta(hours=-3))
FECHA_CERRADA = date(2026, 11, 10)
FECHA_REGISTRO = date(2026, 11, 11)
AHORA = datetime(2026, 11, 11, 9, 0, tzinfo=TZ)
MONTO = 150000


def motor() -> Engine:
    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


# D14: el lock es por (tenant, fecha) y se libera solo al commit/rollback.
BLOQUEAR_DIA = text(
    "SELECT pg_advisory_xact_lock(hashtext(CAST(:t AS text) || ':' || CAST(:f AS text)))"
)
LEER_ANULADO = text(
    "SELECT anulado FROM movimientos_caja WHERE tenant_id = :t AND id = :mov"
)
ANULAR = text(
    "UPDATE movimientos_caja SET anulado = true, motivo_anulacion = :motivo,"
    " anulado_por = :actor, anulado_en = :ahora"
    " WHERE tenant_id = :t AND id = :mov AND anulado = false"
)
INSERTAR_COMPENSATORIO = text(
    "INSERT INTO movimientos_caja"
    " (tenant_id, fecha, medio, monto, tipo, usuario_id, origen, compensa_a_id, creado_en)"
    " VALUES (:t, :f, 'EFECTIVO', :monto, 'EGRESO', :actor, 'COMPENSACION', :mov, :ahora)"
    " RETURNING id"
)
INSERTAR_AJUSTE = text(
    "INSERT INTO ajustes_post_cierre"
    " (tenant_id, cierre_id, tipo, movimiento_original_id, cobro_pendiente_id,"
    "  monto, medio, motivo, actor_id, compensatorio_id, creado_en)"
    " VALUES (:t, :cierre, 'AJUSTE_ANULACION', :mov, NULL, :monto, 'EFECTIVO',"
    "  :motivo, :actor, :compensatorio, :ahora)"
)


def sembrar_anulacion(conn: Connection) -> dict[str, str]:
    """Tenant + usuario ADMIN + ingreso del día cerrado + cierre de ese día."""
    ids = {clave: str(uuid.uuid4()) for clave in ("tenant", "usuario", "movimiento", "cierre")}
    conn.execute(
        text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T10', :slug)"),
        {"id": ids["tenant"], "slug": f"c10c-{ids['tenant'][:8]}"},
    )
    conn.execute(
        text(
            "INSERT INTO usuarios (id, tenant_id, nombre, email, password_hash, rol)"
            " VALUES (:id, :t, 'Usuario Demo', :email, 'x', 'ADMIN')"
        ),
        {
            "id": ids["usuario"],
            "t": ids["tenant"],
            "email": f"u10-{ids['tenant'][:8]}@demo.test",
        },
    )
    conn.execute(
        text(
            "INSERT INTO movimientos_caja"
            " (id, tenant_id, fecha, medio, monto, tipo, usuario_id, origen, creado_en)"
            " VALUES (:id, :t, :f, 'EFECTIVO', :monto, 'INGRESO', :usuario, 'MANUAL', :ahora)"
        ),
        {
            "id": ids["movimiento"],
            "t": ids["tenant"],
            "f": FECHA_CERRADA,
            "monto": MONTO,
            "usuario": ids["usuario"],
            "ahora": AHORA - timedelta(days=1),
        },
    )
    conn.execute(
        text(
            "INSERT INTO cierres_diarios"
            " (id, tenant_id, fecha, total_efectivo, total_transferencia, total_mp,"
            "  total_os_cobrado, total_os, efectivo_contado, diferencia, responsable_id,"
            "  cerrado_at)"
            " VALUES (:id, :t, :f, :monto, 0, 0, 0, 0, :monto, 0, :usuario, :ahora)"
        ),
        {
            "id": ids["cierre"],
            "t": ids["tenant"],
            "f": FECHA_CERRADA,
            "monto": MONTO,
            "usuario": ids["usuario"],
            "ahora": AHORA - timedelta(days=1),
        },
    )
    return ids


def anular_y_compensar(
    conn: Connection,
    ids: dict[str, str],
    *,
    motivo: str,
    actor: str,
) -> str:
    """Un intento completo de anulación post-cierre dentro de la transacción.

    Devuelve `"200"` si esta transacción ganó la transición y escribió el
    compensatorio y el ajuste, o `"409"` si el movimiento ya estaba anulado.
    """
    conn.execute(BLOQUEAR_DIA, {"t": ids["tenant"], "f": FECHA_CERRADA})
    anulado = conn.execute(
        LEER_ANULADO, {"t": ids["tenant"], "mov": ids["movimiento"]}
    ).scalar_one()
    if anulado:
        return "409"
    resultado = conn.execute(
        ANULAR,
        {
            "t": ids["tenant"],
            "mov": ids["movimiento"],
            "motivo": motivo,
            "actor": actor,
            "ahora": AHORA,
        },
    )
    if resultado.rowcount != 1:
        return "409"
    compensatorio_id = conn.execute(
        INSERTAR_COMPENSATORIO,
        {
            "t": ids["tenant"],
            "f": FECHA_REGISTRO,
            "monto": MONTO,
            "actor": actor,
            "mov": ids["movimiento"],
            "ahora": AHORA,
        },
    ).scalar_one()
    conn.execute(
        INSERTAR_AJUSTE,
        {
            "t": ids["tenant"],
            "cierre": ids["cierre"],
            "mov": ids["movimiento"],
            "monto": MONTO,
            "motivo": motivo,
            "actor": actor,
            "compensatorio": compensatorio_id,
            "ahora": AHORA,
        },
    )
    return "200"


def limpiar(engine: Engine, ids: dict[str, str]) -> None:
    """Borra el tenant sembrado (cascade) y libera el engine."""
    if ids:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                text("DELETE FROM tenants WHERE id = :id"), {"id": ids["tenant"]}
            )
            tx.commit()
    engine.dispose()
