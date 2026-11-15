"""Tasks 1.1–1.10 — migración Alembic 009 (señas y Mercado Pago): RED primero.

Sin PostgreSQL vivo la DDL se verifica por estructura (mismo desvío declarado
que 001/003/005/006/007/008). Las verificaciones que necesitan una base real
están marcadas con `skipif` sobre `C02_DATABASE_URL` y nunca se simulan con
SQLite: un SQLite no tiene RLS, `current_setting`, GRANT/REVOKE por columna,
`jsonb`, ni UNIQUE parcial con el mismo comportamiento.

Cubre: 2 tablas (`senas`, `pagos_mp`), `down_revision =
"008_caja_cierre_diario"`, CHECKs estado↔instante de D2, CHECKs de D3, UNIQUE
`(tenant_id, turno_id)`, UNIQUE globales de `mp_payment_id` y `token_hash`,
RLS forzada fail-closed, grants por columna, backfill legacy conservador,
`prestaciones.sena_modo`/`sena_valor` y modelos SQLAlchemy espejo.

Datos ficticios (RN-GL-03): "Paciente Demo", "Conducto Demo", `precio_base=10000`,
`PORCENTAJE=30` ⇒ `3000`.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import CheckConstraint, DateTime, Index, UniqueConstraint, create_engine
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from app.models.catalogos import Prestacion
from app.models.sena import PagoMP, Sena

MIG = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "alembic"
    / "versions"
    / "009_senas_mercadopago.py"
)
BACKEND = Path(__file__).resolve().parent.parent / "backend"

PG_URL = os.environ.get("C02_DATABASE_URL")
requiere_pg = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 13, 9, 0, tzinfo=TZ)
EXPIRA = datetime(2026, 11, 14, 9, 0, tzinfo=TZ)

TABLAS = ("senas", "pagos_mp")


def texto() -> str:
    assert MIG.exists(), f"falta la migración 009: {MIG}"
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
# 1.1 — upgrade: 2 tablas, columnas de override y RLS
# ---------------------------------------------------------------------------


def test_upgrade_head_crea_tablas_de_senas() -> None:
    sql = texto()
    assert 'revision = "009_senas_mercadopago"' in sql
    assert 'down_revision = "008_caja_cierre_diario"' in sql
    for tabla in TABLAS:
        assert f"CREATE TABLE {tabla}" in sql
    # Regla dura: tenant_id NOT NULL en las dos tablas.
    assert sql.count("tenant_id UUID NOT NULL") >= 2
    # Instantes con zona horaria (D2/D3).
    assert sql.count("TIMESTAMPTZ") >= 10
    # D1/D14: el override vive en `prestaciones`, no en `tenant_parametros`.
    assert "ALTER TABLE prestaciones ADD COLUMN sena_modo TEXT" in sql
    assert "ALTER TABLE prestaciones ADD COLUMN sena_valor INTEGER" in sql
    assert "ALTER TABLE tenant_parametros" not in solo_ejecutable(sql)

    # RLS forzada fail-closed en las dos tablas.
    assert (
        "for tabla in (\n"
        '        "senas",\n'
        '        "pagos_mp",\n'
        "    )"
    ) in sql
    assert "ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY" in sql
    assert "NULLIF(current_setting('app.tenant_id', true), '')::uuid" in sql
    assert "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)" in sql
    assert "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)" in sql

    # La 009 no crea tablas de C-12/C-13.
    for prohibida in ("obras_sociales", "coberturas", "liquidaciones", "mensajes_wa"):
        assert f"CREATE TABLE {prohibida}" not in sql


# ---------------------------------------------------------------------------
# 1.3 — downgrade reversible y acotado a la 009
# ---------------------------------------------------------------------------


def test_downgrade_elimina_solo_009() -> None:
    sql = texto()
    assert "def downgrade(" in sql
    for tabla in TABLAS:
        assert f"DROP TABLE IF EXISTS {tabla}" in sql
        assert f"DROP POLICY IF EXISTS {tabla}_tenant_aislamiento ON {tabla}" in sql
    for columna in ("sena_modo", "sena_valor"):
        assert f"ALTER TABLE prestaciones DROP COLUMN IF EXISTS {columna}" in sql
    for constraint in (
        "prestaciones_sena_modo_valido",
        "prestaciones_sena_valor_no_negativo",
        "prestaciones_sin_sena_sin_valor",
        "prestaciones_sena_valor_requerido",
    ):
        assert f"DROP CONSTRAINT IF EXISTS {constraint}" in sql
    # No toca 001–008 ni las columnas legacy de la prestación.
    for intacta in (
        "turnos",
        "pacientes",
        "prestaciones",
        "tenants",
        "usuarios",
        "auditoria",
        "presupuestos",
        "movimientos_caja",
        "cierres_diarios",
        "cobros_pendientes",
        "ajustes_post_cierre",
        "cuentas_por_cobrar_os",
        "tenant_parametros",
    ):
        assert f"DROP TABLE IF EXISTS {intacta}" not in sql
    assert "DROP COLUMN IF EXISTS requiere_sena" not in sql
    assert "DROP COLUMN IF EXISTS monto_sena" not in sql


# ---------------------------------------------------------------------------
# 1.4 — la 009 no toca caja, turnos ni las columnas legacy
# ---------------------------------------------------------------------------


def test_009_no_toca_caja_ni_legacy() -> None:
    ddl = solo_ejecutable(texto())
    for ajena in (
        "ALTER TABLE movimientos_caja",
        "ALTER TABLE cierres_diarios",
        "ALTER TABLE cobros_pendientes",
        "ALTER TABLE ajustes_post_cierre",
        "ALTER TABLE cuentas_por_cobrar_os",
        "ALTER TABLE turnos",
        "ALTER TABLE tenant_parametros",
        "CREATE TABLE movimientos_caja",
        "DROP TABLE IF EXISTS movimientos_caja",
    ):
        assert ajena not in ddl
    # Sólo se crean las dos tablas de C-11.
    assert ddl.count("CREATE TABLE") == 2
    # `requiere_sena`/`monto_sena` sólo se leen en el backfill: nunca se dropean.
    assert "DROP COLUMN" in ddl  # las dos columnas nuevas del downgrade
    assert "requiere_sena" in ddl
    assert "monto_sena" in ddl
    for legacy in ("ALTER TABLE prestaciones DROP COLUMN IF EXISTS requiere_sena",
                   "ALTER TABLE prestaciones DROP COLUMN IF EXISTS monto_sena"):
        assert legacy not in ddl


# ---------------------------------------------------------------------------
# 1.5 — CHECKs de estado↔instante de D2 y de D3
# ---------------------------------------------------------------------------


def test_check_estado_e_instantes_en_db() -> None:
    sql = texto()
    assert (
        "CHECK (estado IN ('PENDIENTE','ACREDITADA','LIBERADA','APLICADA','DEVUELTA'))" in sql
    )
    assert "CHECK (monto_centavos > 0)" in sql
    assert "CHECK (regla_modo IN ('PORCENTAJE','MONTO_FIJO'))" in sql
    assert "CHECK (regla_valor > 0)" in sql
    assert "CHECK (precio_base_centavos >= 0)" in sql
    assert "CHECK (anticipacion_cancelacion_h >= 0)" in sql
    assert "CHECK (preferencia_estado IN ('POR_CREAR','CREADA','FALLIDA'))" in sql
    assert "CHECK (intentos_preferencia >= 0)" in sql
    assert (
        "CHECK (motivo_liberacion IS NULL OR motivo_liberacion IN ('EXPIRACION','CANCELACION'))"
        in sql
    )
    assert (
        "CHECK (concepto_aplicacion IS NULL OR concepto_aplicacion IN "
        "('TRATAMIENTO','CANCELACION_TARDIA'))" in sql
    )
    # Coherencia estado↔instante: ningún estado sin su hecho.
    assert (
        "CONSTRAINT senas_acreditada_coherente CHECK "
        "(estado <> 'ACREDITADA' OR acreditada_en IS NOT NULL)" in sql
    )
    assert (
        "CONSTRAINT senas_aplicada_coherente CHECK (estado <> 'APLICADA' OR "
        "(aplicada_en IS NOT NULL AND movimiento_caja_id IS NOT NULL "
        "AND concepto_aplicacion IS NOT NULL))" in sql
    )
    assert (
        "CONSTRAINT senas_liberada_coherente CHECK (estado <> 'LIBERADA' OR "
        "(liberada_en IS NOT NULL AND motivo_liberacion IS NOT NULL))" in sql
    )
    assert (
        "CONSTRAINT senas_devuelta_coherente CHECK (estado <> 'DEVUELTA' OR "
        "(devuelta_en IS NOT NULL AND motivo_devolucion IS NOT NULL "
        "AND motivo_devolucion <> ''))" in sql
    )
    assert (
        "CONSTRAINT senas_preferencia_coherente CHECK (preferencia_estado <> 'CREADA' OR "
        "(mp_preference_id IS NOT NULL AND mp_init_point IS NOT NULL))" in sql
    )
    # D3: estados y resultados propios del pago. La moneda NO se restringe a
    # ARS en la base (corrección 2026-11-13): el pago en otra moneda tiene que
    # poder registrarse con `MONTO_DISTINTO` y dejar la devolución visible.
    assert "CHECK (moneda = 'ARS')" not in sql
    assert "moneda TEXT NOT NULL DEFAULT 'ARS'" in sql
    assert "moneda = upper(moneda)" in sql
    assert (
        "CHECK (estado IN ('APPROVED','PENDING','IN_PROCESS','REJECTED',"
        "'CANCELLED','REFUNDED','OTHER'))" in sql
    )
    assert "CHECK (resultado IN (" in sql


# ---------------------------------------------------------------------------
# 1.6 — unicidad: turno por tenant, pago y token globales, movimiento
# ---------------------------------------------------------------------------


def test_unique_turno_pago_token_y_movimiento() -> None:
    sql = texto()
    assert "CONSTRAINT senas_tenant_turno_unique UNIQUE (tenant_id, turno_id)" in sql
    assert "CONSTRAINT senas_token_hash_unique UNIQUE (token_hash)" in sql
    assert "CONSTRAINT pagos_mp_mp_payment_id_unique UNIQUE (mp_payment_id)" in sql
    # `token_hash` y `mp_payment_id` NO se acotan al tenant: son globales.
    assert "UNIQUE (tenant_id, token_hash)" not in sql
    assert "UNIQUE (tenant_id, mp_payment_id)" not in sql
    assert (
        "CREATE UNIQUE INDEX senas_tenant_movimiento_unique"
        " ON senas (tenant_id, movimiento_caja_id)"
        " WHERE movimiento_caja_id IS NOT NULL" in sql
    )
    assert (
        "CREATE UNIQUE INDEX senas_tenant_mp_preference_unique"
        " ON senas (tenant_id, mp_preference_id)"
        " WHERE mp_preference_id IS NOT NULL" in sql
    )


# ---------------------------------------------------------------------------
# 1.7 — RLS fail-closed y grants por columna (estructura)
# ---------------------------------------------------------------------------


def test_rls_fail_closed_y_grants_senas() -> None:
    sql = texto()
    assert "GRANT SELECT, INSERT ON senas TO turnos_app" in sql
    assert "GRANT SELECT, INSERT ON pagos_mp TO turnos_app" in sql
    assert "REVOKE UPDATE, DELETE ON senas FROM turnos_app" in sql
    assert "REVOKE UPDATE, DELETE ON pagos_mp FROM turnos_app" in sql
    # Superficie mutable de la seña: estado, instantes, preferencia, token y la
    # transferencia de reprogramación (`turno_id`/`expira_at`, D12/F-16).
    for columna in (
        "estado",
        "turno_id",
        "expira_at",
        "acreditada_en",
        "aplicada_en",
        "liberada_en",
        "devuelta_en",
        "motivo_liberacion",
        "concepto_aplicacion",
        "devuelta_por",
        "motivo_devolucion",
        "movimiento_caja_id",
        "mp_preference_id",
        "mp_init_point",
        "preferencia_estado",
        "intentos_preferencia",
        "proximo_reintento_at",
        "token_hash",
        "token_rotado_en",
    ):
        assert columna in sql.split("GRANT UPDATE (", 1)[1].split(") ON senas", 1)[0]
    # Las columnas de plata y de la regla quedan fuera del UPDATE.
    for inmutable in ("monto_centavos", "regla_valor"):
        assert inmutable not in sql.split("GRANT UPDATE (", 1)[1].split(") ON senas", 1)[0]
    assert (
        "GRANT UPDATE (estado, resultado, raw_json, actualizado_en, aprobado_en)"
        " ON pagos_mp TO turnos_app" in sql
    )


# ---------------------------------------------------------------------------
# 1.8 — backfill legacy conservador (estructura)
# ---------------------------------------------------------------------------


def test_backfill_legacy_conservador() -> None:
    sql = texto()
    assert "SET sena_modo = 'MONTO_FIJO'" in sql
    assert "sena_valor = monto_sena" in sql
    assert "requiere_sena = true" in sql
    assert "monto_sena IS NOT NULL" in sql
    assert "monto_sena > 0" in sql
    # Sin monto no se inventa configuración: queda NULL y se avisa.
    assert "RAISE NOTICE" in sql
    assert "revisión de seña" in sql
    # `requiere_sena = false` no se toca: no hay UPDATE para ese caso.
    assert "requiere_sena = false" not in sql


# ---------------------------------------------------------------------------
# 1.9 — modelos SQLAlchemy espejo
# ---------------------------------------------------------------------------


def test_modelos_sqlalchemy_senas_cargan() -> None:
    assert Sena.__tablename__ == "senas"
    assert PagoMP.__tablename__ == "pagos_mp"

    columnas = Sena.__table__.columns
    assert columnas["tenant_id"].nullable is False
    assert columnas["turno_id"].nullable is False
    assert columnas["monto_centavos"].nullable is False
    assert columnas["token_hash"].nullable is False
    assert columnas["token_hash"].unique is True
    assert columnas["expira_at"].type.timezone is True
    assert isinstance(columnas["expira_at"].type, DateTime)
    for instante in ("acreditada_en", "aplicada_en", "liberada_en", "devuelta_en", "creado_en"):
        assert columnas[instante].type.timezone is True
    assert columnas["mp_init_point"].nullable is True

    checks = [str(c.sqltext) for c in Sena.__table__.constraints if isinstance(c, CheckConstraint)]
    assert any("monto_centavos > 0" in c for c in checks)
    assert any("estado IN" in c for c in checks)
    assert any("regla_modo IN" in c for c in checks)
    assert any("acreditada_en IS NOT NULL" in c for c in checks)
    assert any("movimiento_caja_id IS NOT NULL" in c for c in checks)
    assert any("motivo_liberacion IS NOT NULL" in c for c in checks)
    assert any("motivo_devolucion" in c for c in checks)
    assert any("mp_preference_id IS NOT NULL" in c for c in checks)

    unicos = [c for c in Sena.__table__.constraints if isinstance(c, UniqueConstraint)]
    assert any({col.name for col in c.columns} == {"tenant_id", "turno_id"} for c in unicos)
    assert columnas["token_hash"].unique is True
    parciales = [i for i in Sena.__table__.indexes if isinstance(i, Index) and i.unique]
    assert any(i.dialect_options["postgresql"].get("where") is not None for i in parciales)

    columnas_pago = PagoMP.__table__.columns
    assert columnas_pago["tenant_id"].nullable is False
    assert columnas_pago["mp_payment_id"].nullable is False
    assert columnas_pago["mp_payment_id"].unique is True
    assert columnas_pago["recibido_en"].type.timezone is True
    checks_pago = [
        str(c.sqltext) for c in PagoMP.__table__.constraints if isinstance(c, CheckConstraint)
    ]
    # La moneda es la real que informa la pasarela; el CHECK sólo normaliza y
    # prohíbe el vacío (la exigencia de ARS para acreditar es de aplicación).
    assert not any("moneda = 'ARS'" in c for c in checks_pago)
    assert any("moneda = upper(moneda)" in c for c in checks_pago)
    assert any("resultado IN" in c for c in checks_pago)

    # El override de la prestación es nullable: NULL = hereda del tenant (D1).
    assert Prestacion.__table__.columns["sena_modo"].nullable is True
    assert Prestacion.__table__.columns["sena_valor"].nullable is True
    checks_prestacion = [
        str(c.sqltext) for c in Prestacion.__table__.constraints if isinstance(c, CheckConstraint)
    ]
    assert any("SIN_SENA" in c for c in checks_prestacion)
    assert any("sena_valor" in c for c in checks_prestacion)
    # Las columnas legacy siguen intactas.
    assert Prestacion.__table__.columns["requiere_sena"].nullable is False
    assert Prestacion.__table__.columns["monto_sena"].nullable is True


# ---------------------------------------------------------------------------
# 1.10 — CHECK del override de la prestación (estructura)
# ---------------------------------------------------------------------------


def test_check_prestacion_sena_modo_valor() -> None:
    sql = texto()
    assert (
        "ALTER TABLE prestaciones ADD CONSTRAINT prestaciones_sena_modo_valido"
        " CHECK (sena_modo IS NULL OR sena_modo IN ('SIN_SENA','PORCENTAJE','MONTO_FIJO'))" in sql
    )
    assert (
        "ALTER TABLE prestaciones ADD CONSTRAINT prestaciones_sena_valor_no_negativo"
        " CHECK (sena_valor IS NULL OR sena_valor >= 0)" in sql
    )
    assert (
        "ALTER TABLE prestaciones ADD CONSTRAINT prestaciones_sin_sena_sin_valor"
        " CHECK (sena_modo <> 'SIN_SENA' OR sena_valor IS NULL)" in sql
    )
    assert (
        "ALTER TABLE prestaciones ADD CONSTRAINT prestaciones_sena_valor_requerido"
        " CHECK (sena_modo IS NULL OR sena_modo = 'SIN_SENA' OR sena_valor IS NOT NULL)" in sql
    )


# ---------------------------------------------------------------------------
# Integración real (sólo con C02_DATABASE_URL; se salta sin PostgreSQL)
# ---------------------------------------------------------------------------


def _owner_engine() -> Engine:
    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


def _telefono_ficticio(paciente_id: str) -> str:
    digitos = int(paciente_id.replace("-", ""), 16) % 10**10
    return f"+5491{digitos:010d}"


def _sembrar(conn: Connection) -> dict[str, str]:
    """Dos tenants con paciente, profesional, prestación, usuario, turno y caja."""
    ids = {
        clave: str(uuid.uuid4())
        for clave in (
            "t1",
            "t2",
            "pac1",
            "pac2",
            "prof1",
            "prof2",
            "prest1",
            "prest2",
            "user1",
            "user2",
            "turno1",
            "turno2",
            "turno3",
            "turno4",
            "turno5",
            "mov1",
        )
    }
    conn.execute(
        sql_text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T11', :slug)"),
        [
            {"id": ids["t1"], "slug": f"c11a-{ids['t1'][:8]}"},
            {"id": ids["t2"], "slug": f"c11b-{ids['t2'][:8]}"},
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
            " VALUES (:id, :t, 'Conducto Demo', 30, 10000)"
        ),
        [
            {"id": ids["prest1"], "t": ids["t1"]},
            {"id": ids["prest2"], "t": ids["t2"]},
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO usuarios (id, tenant_id, nombre, email, password_hash, rol)"
            " VALUES (:id, :t, 'Usuario Demo', :email, 'x', 'ADMIN')"
        ),
        [
            {"id": ids["user1"], "t": ids["t1"], "email": f"u11a-{ids['t1'][:8]}@demo.test"},
            {"id": ids["user2"], "t": ids["t2"], "email": f"u11b-{ids['t2'][:8]}@demo.test"},
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO turnos"
            " (id, tenant_id, profesional_id, sillon_id, paciente_id, prestacion_id, inicio, fin)"
            " VALUES (:id, :t, :prof, :sil, :pac, :pres, :inicio, :fin)"
        ),
        [
            {
                "id": ids["turno1"],
                "t": ids["t1"],
                "prof": ids["prof1"],
                "sil": str(uuid.uuid4()),
                "pac": ids["pac1"],
                "pres": ids["prest1"],
                "inicio": AHORA + timedelta(days=7),
                "fin": AHORA + timedelta(days=7, minutes=30),
            },
            {
                "id": ids["turno2"],
                "t": ids["t2"],
                "prof": ids["prof2"],
                "sil": str(uuid.uuid4()),
                "pac": ids["pac2"],
                "pres": ids["prest2"],
                "inicio": AHORA + timedelta(days=7),
                "fin": AHORA + timedelta(days=7, minutes=30),
            },
            {
                "id": ids["turno3"],
                "t": ids["t1"],
                "prof": ids["prof1"],
                "sil": str(uuid.uuid4()),
                "pac": ids["pac1"],
                "pres": ids["prest1"],
                "inicio": AHORA + timedelta(days=8),
                "fin": AHORA + timedelta(days=8, minutes=30),
            },
            {
                "id": ids["turno4"],
                "t": ids["t1"],
                "prof": ids["prof1"],
                "sil": str(uuid.uuid4()),
                "pac": ids["pac1"],
                "pres": ids["prest1"],
                "inicio": AHORA + timedelta(days=9),
                "fin": AHORA + timedelta(days=9, minutes=30),
            },
            {
                "id": ids["turno5"],
                "t": ids["t2"],
                "prof": ids["prof2"],
                "sil": str(uuid.uuid4()),
                "pac": ids["pac2"],
                "pres": ids["prest2"],
                "inicio": AHORA + timedelta(days=9),
                "fin": AHORA + timedelta(days=9, minutes=30),
            },
        ],
    )
    conn.execute(
        sql_text(
            "INSERT INTO movimientos_caja"
            " (id, tenant_id, fecha, medio, monto, tipo, usuario_id, origen)"
            " VALUES (:id, :t, :f, 'MP', 3000, 'INGRESO', :u, 'MANUAL')"
        ),
        {"id": ids["mov1"], "t": ids["t1"], "f": date(2026, 11, 13), "u": ids["user1"]},
    )
    return ids


def _limpiar(engine: Engine, ids: dict[str, str]) -> None:
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


def _sena(ids: dict[str, str], **overrides: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "t": ids["t1"],
        "turno": ids["turno1"],
        "monto": 3000,
        "estado": "PENDIENTE",
        "modo": "PORCENTAJE",
        "valor": 30,
        "precio": 10000,
        "anticipacion": 24,
        "expira": EXPIRA,
        "token": uuid.uuid4().hex,
        "acreditada_en": None,
        "aplicada_en": None,
        "liberada_en": None,
        "devuelta_en": None,
        "motivo_liberacion": None,
        "concepto": None,
        "devuelta_por": None,
        "motivo_devolucion": None,
        "movimiento": None,
        "pref": None,
        "init_point": None,
        "pref_estado": "POR_CREAR",
    }
    datos.update(overrides)
    return datos


_INSERT_SENA = sql_text(
    "INSERT INTO senas"
    " (id, tenant_id, turno_id, monto_centavos, estado, regla_modo, regla_valor,"
    "  precio_base_centavos, anticipacion_cancelacion_h, expira_at, token_hash,"
    "  acreditada_en, aplicada_en, liberada_en, devuelta_en, motivo_liberacion,"
    "  concepto_aplicacion, devuelta_por, motivo_devolucion, movimiento_caja_id,"
    "  mp_preference_id, mp_init_point, preferencia_estado)"
    " VALUES (:id, :t, :turno, :monto, :estado, :modo, :valor,"
    "  :precio, :anticipacion, :expira, :token,"
    "  :acreditada_en, :aplicada_en, :liberada_en, :devuelta_en, :motivo_liberacion,"
    "  :concepto, :devuelta_por, :motivo_devolucion, :movimiento,"
    "  :pref, :init_point, :pref_estado)"
)

_INSERT_PAGO = sql_text(
    "INSERT INTO pagos_mp"
    " (id, tenant_id, mp_payment_id, sena_id, monto_centavos, moneda, estado,"
    "  resultado, raw_json, recibido_en, actualizado_en, aprobado_en)"
    " VALUES (:id, :t, :mp, :sena, :monto, :moneda, :estado, :resultado,"
    "  CAST(:raw AS jsonb), :recibido, :recibido, NULL)"
)


def _pago(ids: dict[str, str], sena_id: str, **overrides: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "t": ids["t1"],
        "mp": f"PAG-{uuid.uuid4().hex[:12]}",
        "sena": sena_id,
        "monto": 3000,
        "moneda": "ARS",
        "estado": "APPROVED",
        "resultado": "ACREDITADA",
        "raw": '{"id": "PAG", "status": "approved"}',
        "recibido": AHORA,
    }
    datos.update(overrides)
    return datos


def _inserta(engine: Engine, sql: Any, params: Any) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        conn.execute(sql, params)
        tx.commit()


def _rechaza(engine: Engine, sql: Any, params: Any) -> None:
    with engine.connect() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql, params)
        conn.rollback()


@requiere_pg
def test_check_estado_e_instantes_en_pg(pg: Any) -> None:
    engine, ids = pg

    for campo, valor in (
        ("estado", "PAGADA"),
        ("monto", 0),
        ("modo", "SIN_SENA"),
        ("valor", 0),
        ("precio", -1),
        ("anticipacion", -1),
        ("pref_estado", "ENVIADA"),
    ):
        _rechaza(engine, _INSERT_SENA, _sena(ids, **{campo: valor}))

    # DEVUELTA exige instante y motivo no vacío.
    for faltante, valor in (
        ("devuelta_en", None),
        ("motivo_devolucion", None),
        ("motivo_devolucion", ""),
    ):
        datos = _sena(ids, estado="DEVUELTA", devuelta_en=AHORA, motivo_devolucion="demo")
        datos[faltante] = valor
        _rechaza(engine, _INSERT_SENA, datos)

    # APLICADA exige instante, movimiento de caja y concepto.
    for faltante in ("aplicada_en", "movimiento", "concepto"):
        datos = _sena(
            ids,
            estado="APLICADA",
            aplicada_en=AHORA,
            movimiento=ids["mov1"],
            concepto="TRATAMIENTO",
        )
        datos[faltante] = None
        _rechaza(engine, _INSERT_SENA, datos)

    # LIBERADA exige instante y motivo.
    for faltante in ("liberada_en", "motivo_liberacion"):
        datos = _sena(ids, estado="LIBERADA", liberada_en=AHORA, motivo_liberacion="EXPIRACION")
        datos[faltante] = None
        _rechaza(engine, _INSERT_SENA, datos)

    # ACREDITADA exige instante.
    _rechaza(engine, _INSERT_SENA, _sena(ids, estado="ACREDITADA", acreditada_en=None))

    # CREADA exige preferencia e init point.
    for faltante in ("pref", "init_point"):
        datos = _sena(ids, pref_estado="CREADA", pref="pref-1", init_point="https://mp.test/x")
        datos[faltante] = None
        _rechaza(engine, _INSERT_SENA, datos)

    # Las filas coherentes sí entran (un caso por estado terminal).
    _inserta(engine, _INSERT_SENA, _sena(ids))
    _inserta(
        engine,
        _INSERT_SENA,
        _sena(
            ids,
            id=str(uuid.uuid4()),
            turno=ids["turno3"],
            token=uuid.uuid4().hex,
            estado="APLICADA",
            aplicada_en=AHORA,
            movimiento=ids["mov1"],
            concepto="TRATAMIENTO",
        ),
    )
    _inserta(
        engine,
        _INSERT_SENA,
        _sena(
            ids,
            id=str(uuid.uuid4()),
            monto=3000,
            turno=ids["turno2"],
            t=ids["t2"],
            token=uuid.uuid4().hex,
            estado="DEVUELTA",
            devuelta_en=AHORA,
            motivo_devolucion="POLITICA_CANCELACION",
        ),
    )


@requiere_pg
def test_unique_turno_pago_token_y_movimiento_en_pg(pg: Any) -> None:
    engine, ids = pg

    sena_t1 = _sena(ids, token="token-t1")
    _inserta(engine, _INSERT_SENA, sena_t1)

    # Segunda seña del mismo turno en el mismo tenant: rechazada.
    _rechaza(engine, _INSERT_SENA, _sena(ids, token=uuid.uuid4().hex))

    # Una seña del turno homónimo de otro tenant con otro token: aceptada.
    _inserta(engine, _INSERT_SENA, _sena(ids, t=ids["t2"], turno=ids["turno2"], token="token-t2"))

    # `token_hash` es global: el de T1 no se repite en T2.
    _rechaza(
        engine,
        _INSERT_SENA,
        _sena(ids, id=str(uuid.uuid4()), t=ids["t2"], turno=ids["turno5"], token="token-t1"),
    )

    # `mp_payment_id` es global: el mismo pago no pertenece a dos consultorios.
    _inserta(engine, _INSERT_PAGO, _pago(ids, sena_t1["id"], mp="PAG-1"))
    _rechaza(
        engine,
        _INSERT_PAGO,
        _pago(ids, sena_t1["id"], id=str(uuid.uuid4()), t=ids["t2"], mp="PAG-1"),
    )
    _inserta(engine, _INSERT_PAGO, _pago(ids, sena_t1["id"], id=str(uuid.uuid4()), mp="PAG-2"))

    # Dos señas del mismo tenant no pueden apuntar al mismo movimiento de caja.
    _inserta(
        engine,
        _INSERT_SENA,
        _sena(
            ids,
            id=str(uuid.uuid4()),
            turno=ids["turno3"],
            token=uuid.uuid4().hex,
            estado="APLICADA",
            aplicada_en=AHORA,
            movimiento=ids["mov1"],
            concepto="TRATAMIENTO",
        ),
    )
    _rechaza(
        engine,
        _INSERT_SENA,
        _sena(
            ids,
            id=str(uuid.uuid4()),
            turno=ids["turno4"],
            token=uuid.uuid4().hex,
            estado="APLICADA",
            aplicada_en=AHORA,
            movimiento=ids["mov1"],
            concepto="TRATAMIENTO",
        ),
    )
    # El UNIQUE del movimiento es por tenant: T2 puede apuntar al mismo id.
    _inserta(
        engine,
        _INSERT_SENA,
        _sena(
            ids,
            id=str(uuid.uuid4()),
            t=ids["t2"],
            turno=ids["turno5"],
            token=uuid.uuid4().hex,
            estado="APLICADA",
            aplicada_en=AHORA,
            movimiento=ids["mov1"],
            concepto="TRATAMIENTO",
        ),
    )


@requiere_pg
def test_pago_en_otra_moneda_se_registra_con_su_resultado(pg: Any) -> None:
    """Corrección 2026-11-13: la base acepta la moneda real de la pasarela.

    §6 exige registrar un `APPROVED` en `USD` como `MONTO_DISTINTO` para que la
    obligación de devolución quede visible. Con `CHECK moneda='ARS'` la fila no
    se podía insertar y el escenario era inalcanzable.
    """
    engine, ids = pg
    sena = _sena(ids, token="token-usd")
    _inserta(engine, _INSERT_SENA, sena)
    _inserta(
        engine,
        _INSERT_PAGO,
        _pago(ids, sena["id"], mp="PAG-USD", moneda="USD", resultado="MONTO_DISTINTO"),
    )

    with engine.connect() as conn:
        fila = conn.execute(
            sql_text("SELECT moneda, resultado FROM pagos_mp WHERE mp_payment_id = 'PAG-USD'")
        ).one()
    assert (fila.moneda, fila.resultado) == ("USD", "MONTO_DISTINTO")

    # La moneda sigue normalizada: vacía o en minúsculas no entra.
    _rechaza(
        engine,
        _INSERT_PAGO,
        _pago(ids, sena["id"], id=str(uuid.uuid4()), mp="PAG-usd", moneda="usd"),
    )
    _rechaza(
        engine,
        _INSERT_PAGO,
        _pago(ids, sena["id"], id=str(uuid.uuid4()), mp="PAG-vacia", moneda=""),
    )


@requiere_pg
def test_rls_fail_closed_y_grants_senas_en_pg(pg: Any) -> None:
    engine, ids = pg
    sena = _sena(ids, token="token-rls")
    _inserta(engine, _INSERT_SENA, sena)
    _inserta(engine, _INSERT_PAGO, _pago(ids, sena["id"], mp="PAG-RLS"))

    def app(tenant: str | None) -> Connection:
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
        assert len(conn.execute(sql_text("SELECT id FROM senas")).all()) == 1
        assert len(conn.execute(sql_text("SELECT id FROM pagos_mp")).all()) == 1
        sena_id = conn.execute(sql_text("SELECT id FROM senas")).scalar_one()

    # Columnas de plata y de la regla inmutables para el rol de aplicación.
    for columna, valor in (
        ("monto_centavos", "1"),
        ("regla_valor", "99"),
        ("regla_modo", "'MONTO_FIJO'"),
        ("precio_base_centavos", "1"),
    ):
        with app(ids["t1"]) as conn:
            with pytest.raises(DBAPIError):
                conn.execute(
                    sql_text(f"UPDATE senas SET {columna} = {valor} WHERE id = :id"),
                    {"id": sena_id},
                )
            conn.rollback()

    # `turno_id`/`expira_at` son mutables **sólo** para la transferencia de
    # reprogramación (D12/F-16): la seña acompaña al turno nuevo sin crear otra.
    with app(ids["t1"]) as conn:
        conn.execute(
            sql_text(
                "UPDATE senas SET turno_id = turno_id, expira_at = expira_at"
                " WHERE id = :id"
            ),
            {"id": sena_id},
        )
        conn.commit()

    # El estado y sus instantes sí se escriben.
    with app(ids["t1"]) as conn:
        conn.execute(
            sql_text(
                "UPDATE senas SET estado = 'LIBERADA', liberada_en = now(),"
                " motivo_liberacion = 'EXPIRACION' WHERE id = :id"
            ),
            {"id": sena_id},
        )
        conn.commit()

    # La superficie de preferencia y la rotación de token son la excepción
    # declarada (D6/D14): `token_hash` se reemite, no se edita a mano.
    with app(ids["t1"]) as conn:
        conn.execute(
            sql_text(
                "UPDATE senas SET mp_preference_id = 'pref-1',"
                " mp_init_point = 'https://mp.test/checkout/1',"
                " preferencia_estado = 'CREADA' WHERE id = :id"
            ),
            {"id": sena_id},
        )
        conn.execute(
            sql_text("UPDATE senas SET token_hash = :t, token_rotado_en = now() WHERE id = :id"),
            {"id": sena_id, "t": uuid.uuid4().hex},
        )
        conn.commit()

    # DELETE nunca: la seña no se borra (RN-AU-02).
    with app(ids["t1"]) as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql_text("DELETE FROM senas"))
        conn.rollback()

    # pagos_mp: append-only salvo estado/resultado/raw_json/instantes.
    with app(ids["t1"]) as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql_text("UPDATE pagos_mp SET monto_centavos = 1"))
        conn.rollback()
    with app(ids["t1"]) as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql_text("UPDATE pagos_mp SET sena_id = :s"), {"s": str(uuid.uuid4())})
        conn.rollback()
    with app(ids["t1"]) as conn:
        conn.execute(
            sql_text(
                "UPDATE pagos_mp SET estado = 'REFUNDED', resultado = 'REEMBOLSADO',"
                " raw_json = CAST('{\"id\": \"PAG-RLS\"}' AS jsonb), actualizado_en = now()"
            )
        )
        conn.commit()
    with app(ids["t1"]) as conn:
        with pytest.raises(DBAPIError):
            conn.execute(sql_text("DELETE FROM pagos_mp"))
        conn.rollback()


@requiere_pg
def test_check_prestacion_sena_modo_valor_en_pg(pg: Any) -> None:
    engine, ids = pg
    insert = sql_text(
        "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base,"
        " sena_modo, sena_valor) VALUES (:id, :t, :nombre, 30, 10000, :modo, :valor)"
    )
    base = {"t": ids["t1"], "nombre": f"Conducto Demo {uuid.uuid4().hex[:6]}"}

    for modo, valor in (
        ("MITAD", 50),
        ("SIN_SENA", 5000),
        ("PORCENTAJE", None),
        ("MONTO_FIJO", None),
        ("PORCENTAJE", -1),
        ("MONTO_FIJO", -100),
    ):
        _rechaza(
            engine,
            insert,
            dict(base, id=str(uuid.uuid4()), nombre=f"{base['nombre']}-{modo}", modo=modo, valor=valor),
        )

    for modo, valor in ((None, None), ("SIN_SENA", None), ("PORCENTAJE", 30), ("MONTO_FIJO", 5000)):
        _inserta(
            engine,
            insert,
            dict(
                base,
                id=str(uuid.uuid4()),
                nombre=f"{base['nombre']}-{modo}-{valor}",
                modo=modo,
                valor=valor,
            ),
        )


# ---------------------------------------------------------------------------
# Ciclo real de migración: downgrade, backfill y re-upgrade
# ---------------------------------------------------------------------------


def _alembic_config() -> Any:
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", PG_URL or "")
    return config


def _migrar(destino: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from alembic import command

    assert PG_URL is not None
    monkeypatch.setenv("DATABASE_OWNER_URL", PG_URL)
    config = _alembic_config()
    if destino == "head":
        command.upgrade(config, "head")
    else:
        command.downgrade(config, destino)


def _columnas(engine: Engine, tabla: str) -> set[str]:
    with engine.connect() as conn:
        return {
            fila[0]
            for fila in conn.execute(
                sql_text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema = 'public' AND table_name = :t"
                ),
                {"t": tabla},
            ).all()
        }


def _tablas(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return {
            fila[0]
            for fila in conn.execute(
                sql_text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            ).all()
        }


def _revision(engine: Engine) -> str:
    with engine.connect() as conn:
        return str(conn.execute(sql_text("SELECT version_num FROM alembic_version")).scalar_one())


@requiere_pg
def test_downgrade_y_reupgrade_en_pg(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _owner_engine()
    try:
        antes = _tablas(engine)
        columnas_antes = _columnas(engine, "prestaciones")
        assert {"senas", "pagos_mp"} <= antes
        assert _revision(engine) == "010_obras_sociales_liquidacion"

        _migrar("008_caja_cierre_diario", monkeypatch)

        despues = _tablas(engine)
        assert "senas" not in despues
        assert "pagos_mp" not in despues
        assert "obras_sociales" not in despues
        assert "liquidaciones" not in despues
        columnas = _columnas(engine, "prestaciones")
        assert "sena_modo" not in columnas
        assert "sena_valor" not in columnas
        # 001–008 intactas y las columnas legacy también.
        assert {"requiere_sena", "monto_sena"} <= columnas
        assert {
            "movimientos_caja",
            "cierres_diarios",
            "tenant_parametros",
            "turnos",
            "prestaciones",
        } <= despues
        assert columnas_antes - columnas == {"sena_modo", "sena_valor"}
        assert _revision(engine) == "008_caja_cierre_diario"

        _migrar("head", monkeypatch)

        assert {"senas", "pagos_mp"} <= _tablas(engine)
        assert {"obras_sociales", "coberturas", "liquidaciones"} <= _tablas(engine)
        assert {"sena_modo", "sena_valor"} <= _columnas(engine, "prestaciones")
        assert _revision(engine) == "010_obras_sociales_liquidacion"
    finally:
        _migrar("head", monkeypatch)
        engine.dispose()


@requiere_pg
def test_backfill_legacy_conservador_en_pg(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _owner_engine()
    tenant = str(uuid.uuid4())
    con_monto = str(uuid.uuid4())
    sin_monto = str(uuid.uuid4())
    sin_sena = str(uuid.uuid4())
    try:
        _migrar("008_caja_cierre_diario", monkeypatch)
        with engine.connect() as conn:
            tx = conn.begin()
            conn.execute(
                sql_text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T11B', :slug)"),
                {"id": tenant, "slug": f"c11c-{tenant[:8]}"},
            )
            insert = sql_text(
                "INSERT INTO prestaciones"
                " (id, tenant_id, nombre, duracion_min, precio_base, requiere_sena, monto_sena)"
                " VALUES (:id, :t, :nombre, 30, 10000, :req, :monto)"
            )
            conn.execute(
                insert,
                [
                    {"id": con_monto, "t": tenant, "nombre": "Conducto Demo A", "req": True, "monto": 5000},
                    {"id": sin_monto, "t": tenant, "nombre": "Conducto Demo B", "req": True, "monto": None},
                    {"id": sin_sena, "t": tenant, "nombre": "Conducto Demo C", "req": False, "monto": None},
                ],
            )
            tx.commit()

        _migrar("head", monkeypatch)

        with engine.connect() as conn:
            filas = {
                str(fila[0]): (fila[1], fila[2])
                for fila in conn.execute(
                    sql_text(
                        "SELECT id, sena_modo, sena_valor FROM prestaciones WHERE tenant_id = :t"
                    ),
                    {"t": tenant},
                ).all()
            }
        assert filas[con_monto] == ("MONTO_FIJO", 5000)
        # Sin monto válido no se inventa configuración: hereda del tenant.
        assert filas[sin_monto] == (None, None)
        assert filas[sin_sena] == (None, None)
    finally:
        _migrar("head", monkeypatch)
        with engine.connect() as conn:
            tx = conn.begin()
            conn.execute(sql_text("DELETE FROM tenants WHERE id = :id"), {"id": tenant})
            tx.commit()
        engine.dispose()
