"""Tasks 1.1–1.11 — migración Alembic 008 (caja y cierre diario): RED primero.

Sin PostgreSQL vivo la DDL se verifica por estructura (mismo desvío declarado
que 001/003/005/006/007). Las verificaciones que necesitan una base real están
marcadas con `skipif` sobre `C02_DATABASE_URL` y nunca se simulan con SQLite:
un SQLite no tiene RLS, ni `current_setting`, ni GRANT/REVOKE por columna, ni
UNIQUE parcial con el mismo comportamiento.

Cubre: 5 tablas (`movimientos_caja`, `cierres_diarios`, `cobros_pendientes`,
`ajustes_post_cierre`, `cuentas_por_cobrar_os`), `down_revision =
"007_odontograma_presupuesto"`, CHECKs de dominio (monto, anulación, tramo,
diferencia), UNIQUE del cierre y UNIQUE parcial de idempotencia por tramo,
UNIQUE del pendiente sin condición de resolución, ledger de ajustes, RLS
forzada fail-closed con `NULLIF(current_setting('app.tenant_id', true), '')`,
grants por columna y modelos SQLAlchemy espejo. La 008 **no** toca
`aceptaciones` (M7).
"""
from __future__ import annotations

import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import CheckConstraint, Date, DateTime, Index, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.exc import DBAPIError

from app.models.caja import (
    AjustePostCierre,
    CierreDiario,
    CobroPendiente,
    CuentaPorCobrarOS,
    MovimientoCaja,
)

MIG = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "alembic"
    / "versions"
    / "008_caja_cierre_diario.py"
)

PG_URL = os.environ.get("C02_DATABASE_URL")
requiere_pg = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")

TABLAS = (
    "movimientos_caja",
    "cierres_diarios",
    "cobros_pendientes",
    "ajustes_post_cierre",
    "cuentas_por_cobrar_os",
)


def texto() -> str:
    assert MIG.exists(), f"falta la migración 008: {MIG}"
    return MIG.read_text(encoding="utf-8")


def solo_ejecutable(sql: str) -> str:
    """DDL ejecutable: descarta docstring, comentarios y líneas vacías."""
    cuerpo = sql.split('"""', 2)[-1] if sql.startswith('"""') else sql
    return "\n".join(
        linea
        for linea in cuerpo.splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    )


# ---------------------------------------------------------------------------
# 1.1 — upgrade crea las 5 tablas con RLS
# ---------------------------------------------------------------------------


def test_upgrade_head_crea_tablas_de_caja():
    sql = texto()
    assert 'revision = "008_caja_cierre_diario"' in sql
    assert 'down_revision = "007_odontograma_presupuesto"' in sql
    for tabla in TABLAS:
        assert f"CREATE TABLE {tabla}" in sql
    # D1: la fecha operativa es DATE y los instantes son TIMESTAMPTZ.
    assert sql.count("TIMESTAMPTZ") >= 8
    assert sql.count("fecha DATE NOT NULL") >= 4
    # Regla dura: tenant_id NOT NULL en las 5 tablas.
    assert sql.count("tenant_id UUID NOT NULL") >= 5
    # RLS forzada en las 5 tablas y política fail-closed con NULLIF.
    assert (
        'for tabla in (\n'
        '        "movimientos_caja",\n'
        '        "cierres_diarios",\n'
        '        "cobros_pendientes",\n'
        '        "ajustes_post_cierre",\n'
        '        "cuentas_por_cobrar_os",\n'
        "    )"
    ) in sql
    assert "ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY" in sql
    assert "NULLIF(current_setting('app.tenant_id', true), '')::uuid" in sql
    assert (
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        in sql
    )
    assert (
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        in sql
    )
    # La 008 no crea tablas de C-11 (señas/MP) ni C-12 (OS/liquidaciones).
    for prohibida in ("senas", "pagos_mp", "obras_sociales", "liquidaciones", "coberturas"):
        assert f"CREATE TABLE {prohibida}" not in sql
    # M7: el medio de pago no se agrega a `aceptaciones`.
    assert "ALTER TABLE aceptaciones" not in sql


# ---------------------------------------------------------------------------
# 1.3 — downgrade reversible y acotado a la 008
# ---------------------------------------------------------------------------


def test_downgrade_elimina_solo_008():
    sql = texto()
    assert "def downgrade(" in sql
    for tabla in TABLAS:
        assert f"DROP TABLE IF EXISTS {tabla}" in sql
        assert f"DROP POLICY IF EXISTS {tabla}_tenant_aislamiento ON {tabla}" in sql
    # No toca 001–007.
    for intacta in (
        "turnos",
        "pacientes",
        "prestaciones",
        "tenants",
        "usuarios",
        "auditoria",
        "presupuestos",
        "presupuesto_lineas",
        "aceptaciones",
        "odontograma_hallazgos",
        "fichas",
        "consentimientos",
    ):
        assert f"DROP TABLE IF EXISTS {intacta}" not in sql


# ---------------------------------------------------------------------------
# 1.4 — la 008 no toca aceptaciones (M7)
# ---------------------------------------------------------------------------


def test_008_no_toca_aceptaciones():
    ddl = solo_ejecutable(texto())
    # Ninguna sentencia ejecutable menciona `aceptaciones`.
    assert "aceptaciones" not in ddl
    for sentencia in (
        "ALTER TABLE aceptaciones",
        "ADD COLUMN",
        "DROP COLUMN",
    ):
        assert sentencia not in ddl
    # El medio de pago vive sólo en movimientos_caja.
    assert "medio TEXT NOT NULL CHECK (medio IN" in ddl


# ---------------------------------------------------------------------------
# 1.5 — CHECK de monto y anulación
# ---------------------------------------------------------------------------


def test_check_monto_anulacion_y_diferencia_en_db():
    sql = texto()
    assert "CHECK (monto > 0)" in sql
    assert "CHECK (medio IN ('EFECTIVO','TRANSFERENCIA','MP','OS'))" in sql
    assert "CHECK (tipo IN ('INGRESO','EGRESO'))" in sql
    # NULL no puede satisfacer el CHECK de anulación: `motivo_anulacion IS NOT NULL`.
    assert (
        "CHECK (anulado = false OR (motivo_anulacion IS NOT NULL"
        " AND motivo_anulacion <> ''"
        " AND anulado_por IS NOT NULL AND anulado_en IS NOT NULL))" in sql
    )
    assert "CHECK (origen IN ('MANUAL','IMPUTACION','COMPENSACION'))" in sql
    assert "CHECK (origen <> 'COMPENSACION' OR compensa_a_id IS NOT NULL)" in sql
    assert "CHECK (tramo IS NULL OR tramo IN ('PACIENTE','OS'))" in sql
    assert "CHECK (origen <> 'IMPUTACION' OR tramo IS NOT NULL)" in sql
    # Cierre: el efectivo contado nunca es negativo y la diferencia es exacta.
    assert "CHECK (efectivo_contado >= 0)" in sql
    assert "CHECK (diferencia = efectivo_contado - total_efectivo)" in sql
    # Ajustes: monto positivo (segundo CHECK de monto del archivo).
    assert sql.count("CHECK (monto > 0)") >= 2


# ---------------------------------------------------------------------------
# 1.6 — la diferencia sólo exige motivo (observación opcional, M2)
# ---------------------------------------------------------------------------


def test_check_diferencia_solo_exige_motivo():
    sql = texto()
    assert (
        "CHECK (diferencia = 0 OR (motivo_diferencia IS NOT NULL"
        " AND motivo_diferencia <> ''))" in sql
    )
    assert "CHECK (motivo_diferencia IS NULL OR motivo_diferencia <> '')" in sql
    assert "CHECK (observacion IS NULL OR observacion <> '')" in sql
    # `motivo_diferencia` y `observacion` son opcionales: no llevan NOT NULL.
    assert "motivo_diferencia TEXT NOT NULL" not in sql
    assert "observacion TEXT NOT NULL" not in sql


# ---------------------------------------------------------------------------
# 1.7 — UNIQUE del cierre e idempotencia por tramo (H1)
# ---------------------------------------------------------------------------


def test_unique_cierre_e_idempotencia_por_tramo():
    sql = texto()
    assert "CONSTRAINT cierres_diarios_tenant_fecha_unique UNIQUE (tenant_id, fecha)" in sql
    assert "CREATE UNIQUE INDEX movimientos_caja_tenant_linea_tramo_unique" in sql
    assert "ON movimientos_caja (tenant_id, linea_id, tramo)" in sql
    assert "WHERE linea_id IS NOT NULL AND origen = 'IMPUTACION'" in sql
    # El medio NO integra la clave de idempotencia.
    assert "ON movimientos_caja (tenant_id, linea_id, tramo, medio)" not in sql


# ---------------------------------------------------------------------------
# 1.8 — UNIQUE del pendiente (sin condición) y de la cuenta por cobrar OS
# ---------------------------------------------------------------------------


def test_unique_pendiente_y_cuenta_por_cobrar_os():
    sql = texto()
    assert (
        "CONSTRAINT cobros_pendientes_tenant_linea_unique UNIQUE (tenant_id, linea_id)" in sql
    )
    assert (
        "CONSTRAINT cuentas_por_cobrar_os_tenant_linea_unique"
        " UNIQUE (tenant_id, linea_id)" in sql
    )
    # El UNIQUE del pendiente no depende de la resolución (H1).
    assert "WHERE resuelto_en IS NULL" not in sql


# ---------------------------------------------------------------------------
# 1.9 — CHECK y UNIQUE del ledger de ajustes post-cierre
# ---------------------------------------------------------------------------


def test_check_ajuste_post_cierre():
    sql = texto()
    assert "CHECK (tipo IN ('AJUSTE_ANULACION','COBRO_PENDIENTE'))" in sql
    assert (
        "CHECK ((tipo = 'AJUSTE_ANULACION' AND movimiento_original_id IS NOT NULL"
        " AND cobro_pendiente_id IS NULL)"
        " OR (tipo = 'COBRO_PENDIENTE' AND cobro_pendiente_id IS NOT NULL"
        " AND movimiento_original_id IS NULL))" in sql
    )
    assert (
        "CHECK (tipo <> 'AJUSTE_ANULACION' OR (motivo IS NOT NULL AND motivo <> ''))"
        in sql
    )
    assert (
        "CREATE UNIQUE INDEX ajustes_post_cierre_tenant_movimiento_unique"
        " ON ajustes_post_cierre (tenant_id, movimiento_original_id)"
        " WHERE movimiento_original_id IS NOT NULL" in sql
    )
    assert (
        "CREATE UNIQUE INDEX ajustes_post_cierre_tenant_pendiente_unique"
        " ON ajustes_post_cierre (tenant_id, cobro_pendiente_id)"
        " WHERE cobro_pendiente_id IS NOT NULL" in sql
    )


# ---------------------------------------------------------------------------
# 1.11 — modelos SQLAlchemy
# ---------------------------------------------------------------------------


def test_modelos_sqlalchemy_caja_cargan_sin_errores():
    assert MovimientoCaja.__tablename__ == "movimientos_caja"
    assert CierreDiario.__tablename__ == "cierres_diarios"
    assert CobroPendiente.__tablename__ == "cobros_pendientes"
    assert AjustePostCierre.__tablename__ == "ajustes_post_cierre"
    assert CuentaPorCobrarOS.__tablename__ == "cuentas_por_cobrar_os"

    for modelo in (
        MovimientoCaja,
        CierreDiario,
        CobroPendiente,
        CuentaPorCobrarOS,
    ):
        assert modelo.__table__.columns["tenant_id"].nullable is False
        # D1: la fecha operativa es DATE (no un instante).
        assert isinstance(modelo.__table__.columns["fecha"].type, Date)
        assert not isinstance(modelo.__table__.columns["fecha"].type, DateTime)
        assert modelo.__table__.columns["creado_en"].type.timezone is True
    assert AjustePostCierre.__table__.columns["tenant_id"].nullable is False
    assert AjustePostCierre.__table__.columns["creado_en"].type.timezone is True
    assert AjustePostCierre.__table__.columns["cierre_id"].nullable is False

    checks_mov = [
        str(c.sqltext)
        for c in MovimientoCaja.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("monto > 0" in c for c in checks_mov)
    assert any("medio IN" in c for c in checks_mov)
    assert any("tipo IN" in c for c in checks_mov)
    assert any("tramo IS NULL OR tramo IN" in c for c in checks_mov)
    assert any("origen <> 'IMPUTACION' OR tramo IS NOT NULL" in c for c in checks_mov)
    assert any("motivo_anulacion IS NOT NULL" in c for c in checks_mov)
    assert MovimientoCaja.__table__.columns["anulado"].nullable is False
    assert MovimientoCaja.__table__.columns["anulado_en"].type.timezone is True
    unicos_mov = [
        i for i in MovimientoCaja.__table__.indexes if isinstance(i, Index) and i.unique
    ]
    assert any(i.dialect_options["postgresql"].get("where") is not None for i in unicos_mov)

    checks_cierre = [
        str(c.sqltext)
        for c in CierreDiario.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("diferencia = efectivo_contado - total_efectivo" in c for c in checks_cierre)
    assert any("efectivo_contado >= 0" in c for c in checks_cierre)
    assert any("motivo_diferencia IS NOT NULL" in c for c in checks_cierre)
    unicos_cierre = [
        c for c in CierreDiario.__table__.constraints if isinstance(c, UniqueConstraint)
    ]
    assert any(
        {col.name for col in c.columns} == {"tenant_id", "fecha"} for c in unicos_cierre
    )

    checks_pend = [
        str(c.sqltext)
        for c in CobroPendiente.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("monto_centavos > 0" in c for c in checks_pend)
    assert any("(resuelto_en IS NULL) = (movimiento_id IS NULL)" in c for c in checks_pend)
    unicos_pend = [
        c for c in CobroPendiente.__table__.constraints if isinstance(c, UniqueConstraint)
    ]
    assert any({col.name for col in c.columns} == {"tenant_id", "linea_id"} for c in unicos_pend)

    checks_ajuste = [
        str(c.sqltext)
        for c in AjustePostCierre.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("AJUSTE_ANULACION" in c and "COBRO_PENDIENTE" in c for c in checks_ajuste)
    assert any("motivo IS NOT NULL" in c for c in checks_ajuste)

    checks_cuenta = [
        str(c.sqltext)
        for c in CuentaPorCobrarOS.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("monto_centavos > 0" in c for c in checks_cuenta)


# ---------------------------------------------------------------------------
# Integración real (sólo con C02_DATABASE_URL; se salta sin PostgreSQL)
# ---------------------------------------------------------------------------


def _owner_engine() -> Any:
    from sqlalchemy import create_engine

    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


def _telefono_ficticio(paciente_id: str) -> str:
    digitos = int(paciente_id.replace("-", ""), 16) % 10**10
    return f"+5491{digitos:010d}"


def _sembrar(conn: Any) -> dict[str, str]:
    """Dos tenants con usuario, presupuesto, línea y turno ficticios."""
    ids = {
        clave: str(uuid.uuid4())
        for clave in (
            "t1",
            "t2",
            "pac1",
            "pac2",
            "prof1",
            "prof2",
            "pres1",
            "pres2",
            "presu1",
            "presu2",
            "linea1",
            "linea2",
            "user1",
            "user2",
        )
    }
    conn.execute(
        sql_text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T8', :slug)"),
        [
            {"id": ids["t1"], "slug": f"c10a-{ids['t1'][:8]}"},
            {"id": ids["t2"], "slug": f"c10b-{ids['t2'][:8]}"},
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
            " VALUES (:id, :t, 'Paciente Demo', :tel)"
        ),
        [
            {"id": ids["pac1"], "t": ids["t1"], "tel": _telefono_ficticio(ids["pac1"])},
            {"id": ids["pac2"], "t": ids["t2"], "tel": _telefono_ficticio(ids["pac2"])},
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO profesionales (id, tenant_id, nombre, especialidad)"
            " VALUES (:id, :t, 'Profesional Demo', 'Odontología')"
        ),
        [
            {"id": ids["prof1"], "t": ids["t1"]},
            {"id": ids["prof2"], "t": ids["t2"]},
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base)"
            " VALUES (:id, :t, 'Conducto Demo', 30, 150000)"
        ),
        [
            {"id": ids["pres1"], "t": ids["t1"]},
            {"id": ids["pres2"], "t": ids["t2"]},
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO usuarios (id, tenant_id, nombre, email, password_hash, rol)"
            " VALUES (:id, :t, 'Usuario Demo', :email, 'x', 'ADMIN')"
        ),
        [
            {"id": ids["user1"], "t": ids["t1"], "email": f"u1-{ids['t1'][:8]}@demo.test"},
            {"id": ids["user2"], "t": ids["t2"], "email": f"u2-{ids['t2'][:8]}@demo.test"},
        ],
    )
    conn.execute(
        sql_text("INSERT INTO presupuestos (id, tenant_id, paciente_id) VALUES (:id, :t, :p)"),
        [
            {"id": ids["presu1"], "t": ids["t1"], "p": ids["pac1"]},
            {"id": ids["presu2"], "t": ids["t2"], "p": ids["pac2"]},
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO presupuesto_lineas"
            " (id, tenant_id, presupuesto_id, prestacion_id, monto, cobertura_os, a_cargo_paciente)"
            " VALUES (:id, :t, :p, :pr, 100000, 0, 100000)"
        ),
        [
            {"id": ids["linea1"], "t": ids["t1"], "p": ids["presu1"], "pr": ids["pres1"]},
            {"id": ids["linea2"], "t": ids["t2"], "p": ids["presu2"], "pr": ids["pres2"]},
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO turnos"
            " (id, tenant_id, profesional_id, sillon_id, paciente_id, prestacion_id, inicio, fin)"
            " VALUES (:id, :t, :prof, :sil, :pac, :pres, now(), now() + interval '30 minutes')"
        ),
        [
            {
                "id": str(uuid.uuid4()),
                "t": ids["t1"],
                "prof": ids["prof1"],
                "sil": str(uuid.uuid4()),
                "pac": ids["pac1"],
                "pres": ids["pres1"],
            },
            {
                "id": str(uuid.uuid4()),
                "t": ids["t2"],
                "prof": ids["prof2"],
                "sil": str(uuid.uuid4()),
                "pac": ids["pac2"],
                "pres": ids["pres2"],
            },
        ],
    )
    return ids


def _limpiar(engine: Any, ids: dict[str, str]) -> None:
    with engine.connect() as owner:
        tx = owner.begin()
        owner.execute(
            sql_text("DELETE FROM tenants WHERE id = ANY(:ids)"),
            {"ids": [ids["t1"], ids["t2"]]},
        )
        tx.commit()
    engine.dispose()


@pytest.fixture()
def pg() -> Any:
    """Engine + ids sembrados; se salta sin `C02_DATABASE_URL`."""
    if not PG_URL:
        pytest.skip("C02_DATABASE_URL no configurada")
    engine = _owner_engine()
    with engine.connect() as conn:
        tx = conn.begin()
        ids = _sembrar(conn)
        tx.commit()
    try:
        yield engine, ids
    finally:
        _limpiar(engine, ids)


def _movimiento(ids: dict[str, str], **overrides: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "tenant": ids["t1"],
        "fecha": date(2026, 11, 10),
        "medio": "EFECTIVO",
        "monto": 150000,
        "tipo": "INGRESO",
        "usuario": ids["user1"],
        "tramo": None,
        "origen": "MANUAL",
        "compensa": None,
        "anulado": False,
        "motivo": None,
        "anulado_por": None,
        "anulado_en": None,
        "linea": None,
        "presupuesto": None,
        "paciente": None,
        "turno": None,
    }
    datos.update(overrides)
    return datos


_INSERT_MOV = sql_text(
    "INSERT INTO movimientos_caja"
    " (id, tenant_id, fecha, medio, monto, tipo, usuario_id, tramo, origen,"
    "  compensa_a_id, anulado, motivo_anulacion, anulado_por, anulado_en,"
    "  linea_id, presupuesto_id, paciente_id, turno_id)"
    " VALUES (:id, :tenant, :fecha, :medio, :monto, :tipo, :usuario, :tramo, :origen,"
    "  :compensa, :anulado, :motivo, :anulado_por, :anulado_en,"
    "  :linea, :presupuesto, :paciente, :turno)"
)

_INSERT_CIERRE = sql_text(
    "INSERT INTO cierres_diarios"
    " (id, tenant_id, fecha, total_efectivo, total_transferencia, total_mp,"
    "  total_os_cobrado, total_os, efectivo_contado, diferencia, responsable_id,"
    "  motivo_diferencia, observacion, cerrado_at)"
    " VALUES (:id, :t, :f, :efectivo, 0, 0, 0, 0, :contado, :diferencia, :resp,"
    "  :motivo, :obs, now())"
)


def _cierre(ids: dict[str, str], **overrides: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "t": ids["t1"],
        "f": date(2026, 11, 10),
        "efectivo": 100000,
        "contado": 100000,
        "diferencia": 0,
        "resp": ids["user1"],
        "motivo": None,
        "obs": None,
    }
    datos.update(overrides)
    return datos


def _inserta(engine: Any, sql: Any, params: Any) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        conn.execute(sql, params)
        tx.commit()


def _rechaza(engine: Any, sql: Any, params: Any) -> None:
    with engine.connect() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql, params)
        conn.rollback()


@requiere_pg
def test_check_monto_anulacion_y_diferencia_en_pg(pg: Any) -> None:
    engine, ids = pg
    for campo, valor in (
        ("monto", 0),
        ("monto", -100),
        ("medio", "CHEQUE"),
        ("tipo", "AJUSTE"),
        ("tramo", "OTRO"),
        ("origen", "IMPUTACION"),
        ("origen", "COMPENSACION"),
    ):
        _rechaza(engine, _INSERT_MOV, _movimiento(ids, **{campo: valor}))
    # `anulado=true` sin motivo, sin actor y sin instante se rechaza.
    for faltante in ("motivo", "anulado_por", "anulado_en"):
        datos = _movimiento(
            ids,
            anulado=True,
            motivo="cobro duplicado",
            anulado_por=ids["user1"],
            anulado_en="2026-11-10T10:00:00-03:00",
        )
        datos[faltante] = None
        _rechaza(engine, _INSERT_MOV, datos)
    # Un movimiento anulado correcto sí entra.
    _inserta(
        engine,
        _INSERT_MOV,
        _movimiento(
            ids,
            anulado=True,
            motivo="cobro duplicado",
            anulado_por=ids["user1"],
            anulado_en="2026-11-10T10:00:00-03:00",
        ),
    )

    # Cierre: diferencia inconsistente, efectivo negativo y motivo obligatorio.
    _rechaza(engine, _INSERT_CIERRE, _cierre(ids, diferencia=5000))
    _rechaza(engine, _INSERT_CIERRE, _cierre(ids, contado=-1, diferencia=-1))
    _rechaza(engine, _INSERT_CIERRE, _cierre(ids, contado=95000, diferencia=-5000))
    _rechaza(engine, _INSERT_CIERRE, _cierre(ids, contado=95000, diferencia=-5000, motivo=""))
    _rechaza(engine, _INSERT_CIERRE, _cierre(ids, obs=""))
    _inserta(
        engine,
        _INSERT_CIERRE,
        _cierre(ids, contado=95000, diferencia=-5000, motivo="faltante"),
    )


@requiere_pg
def test_unique_cierre_e_idempotencia_por_tramo_en_pg(pg: Any) -> None:
    engine, ids = pg
    _inserta(engine, _INSERT_CIERRE, _cierre(ids))
    _rechaza(engine, _INSERT_CIERRE, _cierre(ids))
    _inserta(engine, _INSERT_CIERRE, _cierre(ids, t=ids["t2"], resp=ids["user2"]))

    imputacion = _movimiento(
        ids,
        origen="IMPUTACION",
        tramo="PACIENTE",
        linea=ids["linea1"],
        presupuesto=ids["presu1"],
        paciente=ids["pac1"],
    )
    _inserta(engine, _INSERT_MOV, imputacion)
    # Mismo (tenant, línea, tramo) con otro medio y monto: el UNIQUE parcial lo rechaza.
    _rechaza(
        engine,
        _INSERT_MOV,
        dict(imputacion, id=str(uuid.uuid4()), medio="TRANSFERENCIA", monto=90000),
    )
    # El mismo tramo OS de la misma línea sí entra.
    _inserta(engine, _INSERT_MOV, dict(imputacion, id=str(uuid.uuid4()), tramo="OS", medio="OS", monto=40000))
    # T2 puede imputar su propia línea.
    _inserta(
        engine,
        _INSERT_MOV,
        _movimiento(
            ids,
            tenant=ids["t2"],
            origen="IMPUTACION",
            tramo="PACIENTE",
            linea=ids["linea2"],
            presupuesto=ids["presu2"],
            paciente=ids["pac2"],
            usuario=ids["user2"],
        ),
    )
    # Un MANUAL con la misma línea no colisiona con el índice parcial.
    _inserta(
        engine,
        _INSERT_MOV,
        _movimiento(ids, linea=ids["linea1"], presupuesto=ids["presu1"], paciente=ids["pac1"]),
    )


@requiere_pg
def test_unique_pendiente_y_cuenta_por_cobrar_os_en_pg(pg: Any) -> None:
    engine, ids = pg
    movimiento = _movimiento(ids)
    _inserta(engine, _INSERT_MOV, movimiento)
    insert_pend = sql_text(
        "INSERT INTO cobros_pendientes"
        " (tenant_id, fecha, presupuesto_id, linea_id, paciente_id, monto_centavos, actor_id)"
        " VALUES (:t, :f, :presu, :linea, :pac, 60000, :actor)"
    )
    base = {
        "f": date(2026, 11, 10),
        "presu": ids["presu1"],
        "linea": ids["linea1"],
        "pac": ids["pac1"],
    }
    _inserta(engine, insert_pend, dict(base, t=ids["t1"], actor=ids["user1"]))
    # Aunque el primero esté resuelto, el UNIQUE pleno rechaza el segundo.
    with engine.connect() as conn:
        tx = conn.begin()
        conn.execute(
            sql_text(
                "UPDATE cobros_pendientes SET resuelto_en = now(), movimiento_id = :m"
                " WHERE tenant_id = :t AND linea_id = :l"
            ),
            {"m": movimiento["id"], "t": ids["t1"], "l": ids["linea1"]},
        )
        tx.commit()
    _rechaza(engine, insert_pend, dict(base, t=ids["t1"], actor=ids["user1"]))
    _inserta(
        engine,
        insert_pend,
        {
            "t": ids["t2"],
            "f": date(2026, 11, 10),
            "presu": ids["presu2"],
            "linea": ids["linea2"],
            "pac": ids["pac2"],
            "actor": ids["user2"],
        },
    )

    insert_cuenta = sql_text(
        "INSERT INTO cuentas_por_cobrar_os"
        " (tenant_id, fecha, presupuesto_id, linea_id, paciente_id, monto_centavos)"
        " VALUES (:t, :f, :presu, :linea, :pac, 40000)"
    )
    _inserta(engine, insert_cuenta, dict(base, t=ids["t1"]))
    _rechaza(engine, insert_cuenta, dict(base, t=ids["t1"]))
    _inserta(
        engine,
        insert_cuenta,
        {
            "t": ids["t2"],
            "f": date(2026, 11, 10),
            "presu": ids["presu2"],
            "linea": ids["linea2"],
            "pac": ids["pac2"],
        },
    )


@requiere_pg
def test_check_ajuste_post_cierre_en_pg(pg: Any) -> None:
    engine, ids = pg
    cierre = _cierre(ids)
    _inserta(engine, _INSERT_CIERRE, cierre)
    original = _movimiento(ids)
    _inserta(engine, _INSERT_MOV, original)
    compensatorio = _movimiento(
        ids, origen="COMPENSACION", compensa=original["id"], monto=150000, tipo="EGRESO"
    )
    _inserta(engine, _INSERT_MOV, compensatorio)

    insert_ajuste = sql_text(
        "INSERT INTO ajustes_post_cierre"
        " (tenant_id, cierre_id, tipo, movimiento_original_id, cobro_pendiente_id,"
        "  monto, medio, motivo, actor_id, compensatorio_id)"
        " VALUES (:t, :cierre, :tipo, :original, :pendiente, :monto, :medio,"
        "  :motivo, :actor, :comp)"
    )
    base = {
        "t": ids["t1"],
        "cierre": cierre["id"],
        "tipo": "AJUSTE_ANULACION",
        "original": original["id"],
        "pendiente": None,
        "monto": 150000,
        "medio": "EFECTIVO",
        "motivo": "error de carga",
        "actor": ids["user1"],
        "comp": compensatorio["id"],
    }
    _rechaza(engine, insert_ajuste, dict(base, original=None))
    _rechaza(engine, insert_ajuste, dict(base, monto=0))
    _rechaza(engine, insert_ajuste, dict(base, motivo=""))
    _rechaza(
        engine,
        insert_ajuste,
        dict(base, tipo="COBRO_PENDIENTE", original=None, pendiente=None),
    )
    _inserta(engine, insert_ajuste, base)
    # Un segundo ajuste para el mismo movimiento original choca con el UNIQUE parcial.
    _rechaza(engine, insert_ajuste, base)


@requiere_pg
def test_rls_fail_closed_y_grants_caja(pg: Any) -> None:
    engine, ids = pg
    _inserta(engine, _INSERT_MOV, _movimiento(ids))
    _inserta(
        engine,
        _INSERT_MOV,
        _movimiento(ids, tenant=ids["t2"], usuario=ids["user2"]),
    )
    _inserta(engine, _INSERT_CIERRE, _cierre(ids, f=date(2026, 11, 9)))
    _inserta(
        engine,
        sql_text(
            "INSERT INTO cobros_pendientes"
            " (tenant_id, fecha, presupuesto_id, linea_id, paciente_id, monto_centavos, actor_id)"
            " VALUES (:t, :f, :presu, :linea, :pac, 60000, :actor)"
        ),
        {
            "t": ids["t1"],
            "f": date(2026, 11, 10),
            "presu": ids["presu1"],
            "linea": ids["linea1"],
            "pac": ids["pac1"],
            "actor": ids["user1"],
        },
    )
    _inserta(
        engine,
        sql_text(
            "INSERT INTO cuentas_por_cobrar_os"
            " (tenant_id, fecha, presupuesto_id, linea_id, paciente_id, monto_centavos)"
            " VALUES (:t, :f, :presu, :linea, :pac, 40000)"
        ),
        {
            "t": ids["t1"],
            "f": date(2026, 11, 10),
            "presu": ids["presu1"],
            "linea": ids["linea1"],
            "pac": ids["pac1"],
        },
    )

    def app(tenant: str | None) -> Any:
        conn = engine.connect()
        conn.execute(sql_text("SET ROLE turnos_app"))
        if tenant is not None:
            conn.execute(sql_text("SELECT set_config('app.tenant_id', :t, false)"), {"t": tenant})
        return conn

    # Sin tenant y con cadena vacía: 0 filas, sin error 42704.
    for tenant in (None, ""):
        with app(tenant) as conn:
            for tabla in TABLAS:
                assert conn.execute(sql_text(f"SELECT id FROM {tabla}")).all() == []
    with app(ids["t1"]) as conn:
        filas = conn.execute(sql_text("SELECT id FROM movimientos_caja")).all()
        assert len(filas) == 1

    with app(ids["t1"]) as conn:
        mov_id = conn.execute(sql_text("SELECT id FROM movimientos_caja")).scalar_one()
        conn.rollback()

    # movimientos_caja: DELETE y UPDATE de columnas inmutables rechazados.
    for columna, valor in (
        ("monto", "1"),
        ("medio", "'OS'"),
        ("tramo", "'OS'"),
        ("fecha", "'2020-01-01'"),
    ):
        with app(ids["t1"]) as conn:
            with pytest.raises(DBAPIError):
                conn.execute(
                    sql_text(f"UPDATE movimientos_caja SET {columna} = {valor} WHERE id = :id"),
                    {"id": mov_id},
                )
            conn.rollback()
    with app(ids["t1"]) as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql_text("DELETE FROM movimientos_caja WHERE id = :id"), {"id": mov_id})
        conn.rollback()
    # Las 4 columnas de anulación sí se pueden escribir.
    with app(ids["t1"]) as conn:
        conn.execute(
            sql_text(
                "UPDATE movimientos_caja SET anulado = true,"
                " motivo_anulacion = 'demo', anulado_por = :u, anulado_en = now()"
                " WHERE id = :id"
            ),
            {"id": mov_id, "u": ids["user1"]},
        )
        conn.commit()

    # cierres_diarios y cuentas_por_cobrar_os son inmutables.
    for tabla in ("cierres_diarios", "cuentas_por_cobrar_os"):
        with app(ids["t1"]) as conn:
            with pytest.raises(DBAPIError):
                conn.execute(sql_text(f"UPDATE {tabla} SET tenant_id = tenant_id"))
            conn.rollback()
        with app(ids["t1"]) as conn:
            with pytest.raises(DBAPIError):
                conn.execute(sql_text(f"DELETE FROM {tabla}"))
            conn.rollback()

    # cobros_pendientes: UPDATE sólo de (resuelto_en, movimiento_id); DELETE no.
    with app(ids["t1"]) as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql_text("UPDATE cobros_pendientes SET monto_centavos = 1"))
        conn.rollback()
    with app(ids["t1"]) as conn:
        conn.execute(
            sql_text("UPDATE cobros_pendientes SET resuelto_en = now(), movimiento_id = :m"),
            {"m": mov_id},
        )
        conn.commit()
    with app(ids["t1"]) as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql_text("DELETE FROM cobros_pendientes"))
        conn.rollback()


@requiere_pg
def test_008_no_toca_aceptaciones_en_pg(pg: Any) -> None:
    engine, _ids = pg
    with engine.connect() as conn:
        columnas = {
            fila[0]
            for fila in conn.execute(
                sql_text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'aceptaciones'"
                )
            ).all()
        }
    assert columnas == {"id", "tenant_id", "linea_id", "acepta", "fecha", "canal", "creado_en"}
    assert "medio" not in columnas
