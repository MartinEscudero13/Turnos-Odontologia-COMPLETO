"""Tasks 1.1–1.8 — migración Alembic 007 (odontograma + presupuesto): RED primero.

Sin PostgreSQL vivo en el entorno la DDL se verifica por estructura (mismo
desvío declarado que 001/003/005/006); la migración real corre en CI. Las
verificaciones que necesitan una base viva están marcadas con
`pytest.mark.skipif` sobre `C02_DATABASE_URL` y nunca se simulan con SQLite:
un SQLite no tiene RLS, ni `current_setting`, ni GRANT/REVOKE por columna.

Cubre: 4 tablas, `down_revision="006_ficha_clinica"`, RLS forzada fail-closed
con `NULLIF(current_setting('app.tenant_id', true), '')`, CHECK de grilla FDI
(cuadrante 1–4 × diente 1–8), CHECK de la suma de la línea, UNIQUE parcial de
`idempotency_key` por tenant, `origen_cobertura` acotado, `validada_en_vivo`
DEFAULT false, inmutabilidad clínica (UPDATE sólo de `resuelto`, DELETE
revocado) y modelos SQLAlchemy.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, Index
from sqlalchemy import text as sql_text
from sqlalchemy.exc import DBAPIError

from app.models.odontograma import OdontogramaHallazgo
from app.models.presupuesto import Aceptacion, Presupuesto, PresupuestoLinea

MIG = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "alembic"
    / "versions"
    / "007_odontograma_presupuesto.py"
)

PG_URL = os.environ.get("C02_DATABASE_URL")
requiere_pg = pytest.mark.skipif(not PG_URL, reason="C02_DATABASE_URL no configurada")


def telefono_ficticio(paciente_id: str) -> str:
    """E.164 ficticio: el CHECK de 002 exige `+` y 8–15 dígitos."""
    digitos = int(paciente_id.replace("-", ""), 16) % 10**10
    return f"+5491{digitos:010d}"


def texto() -> str:
    assert MIG.exists(), f"falta la migración 007: {MIG}"
    return MIG.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1.1 — upgrade crea las 4 tablas con RLS
# ---------------------------------------------------------------------------


def test_upgrade_head_crea_tablas_odontograma_y_presupuesto():
    sql = texto()
    assert 'revision = "007_odontograma_presupuesto"' in sql
    assert 'down_revision = "006_ficha_clinica"' in sql
    for tabla in (
        "odontograma_hallazgos",
        "presupuestos",
        "presupuesto_lineas",
        "aceptaciones",
    ):
        assert f"CREATE TABLE {tabla}" in sql
    # Timestamptz en todas las fechas (nunca timestamp sin zona).
    assert sql.count("TIMESTAMPTZ") >= 8
    # RLS forzada en las 4 tablas y política fail-closed con NULLIF.
    assert (
        'for table in (\n'
        '        "odontograma_hallazgos",\n'
        '        "presupuestos",\n'
        '        "presupuesto_lineas",\n'
        '        "aceptaciones",\n'
        "    )"
    ) in sql
    assert "ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
    assert "NULLIF(current_setting('app.tenant_id', true), '')::uuid" in sql
    # La política usa el mismo predicado en USING y WITH CHECK (el loop lo repite
    # en runtime para las 4 tablas).
    assert (
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        in sql
    )
    assert (
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        in sql
    )
    # La 007 no crea tablas de C-10 (caja) ni C-12 (coberturas).
    for prohibida in ("movimientos_caja", "coberturas", "obras_sociales"):
        assert f"CREATE TABLE {prohibida}" not in sql


# ---------------------------------------------------------------------------
# 1.3 — downgrade reversible y acotado a la 007
# ---------------------------------------------------------------------------


def test_downgrade_elimina_solo_007():
    sql = texto()
    assert "def downgrade(" in sql
    for tabla in ("aceptaciones", "presupuesto_lineas", "presupuestos", "odontograma_hallazgos"):
        assert f"DROP TABLE IF EXISTS {tabla}" in sql
        assert f"DROP POLICY IF EXISTS {tabla}_tenant_aislamiento ON {tabla}" in sql
    # No toca 001–006.
    for intacta in (
        "turnos",
        "pacientes",
        "prestaciones",
        "lista_espera",
        "fichas",
        "consentimientos",
        "evoluciones",
        "tenants",
    ):
        assert f"DROP TABLE IF EXISTS {intacta}" not in sql


# ---------------------------------------------------------------------------
# 1.4 — CHECK de grilla FDI y de la suma de la línea
# ---------------------------------------------------------------------------


def test_check_fdi_y_suma_de_linea_en_db():
    sql = texto()
    # División entera de PostgreSQL: cuadrante = decena, diente = unidad.
    assert "(pieza_fdi / 10) BETWEEN 1 AND 4" in sql
    assert "(pieza_fdi % 10) BETWEEN 1 AND 8" in sql
    # No se usa un BETWEEN 11 AND 48 que acepte 19/29/39/20/30/40.
    assert "BETWEEN 11 AND 48" not in sql
    # La línea opcional valida la grilla sólo si trae pieza.
    assert "pieza_fdi IS NULL OR" in sql
    # Invariante de dinero.
    assert "cobertura_os + a_cargo_paciente = monto" in sql


# ---------------------------------------------------------------------------
# 1.5 — UNIQUE parcial de idempotency_key por tenant
# ---------------------------------------------------------------------------


def test_unique_parcial_idempotency_key():
    sql = texto()
    assert "CREATE UNIQUE INDEX presupuesto_lineas_tenant_idempotency_key_unique" in sql
    assert "ON presupuesto_lineas (tenant_id, idempotency_key)" in sql
    assert "WHERE idempotency_key IS NOT NULL" in sql


# ---------------------------------------------------------------------------
# 1.6 — RLS fail-closed, inmutabilidad clínica y grants
# ---------------------------------------------------------------------------


def test_rls_fail_closed_y_grants():
    sql = texto()
    # GRANT/REVOKE por tabla.
    for tabla in ("odontograma_hallazgos", "presupuestos", "presupuesto_lineas", "aceptaciones"):
        assert f"GRANT SELECT, INSERT ON {tabla} TO turnos_app" in sql
    # Sólo `resuelto` es mutable en el hallazgo (grant por columna de PostgreSQL).
    assert "GRANT UPDATE (resuelto) ON odontograma_hallazgos TO turnos_app" in sql
    assert "REVOKE UPDATE ON odontograma_hallazgos FROM turnos_app" in sql
    assert "REVOKE DELETE ON odontograma_hallazgos FROM turnos_app" in sql
    # Presupuesto: sólo estado y vencimiento.
    assert "GRANT UPDATE (estado, vence_en) ON presupuestos TO turnos_app" in sql
    assert "REVOKE DELETE ON presupuestos FROM turnos_app" in sql
    # Líneas y aceptaciones: ledger sin UPDATE ni DELETE en v1 (D8.1).
    for tabla in ("presupuesto_lineas", "aceptaciones"):
        assert f"REVOKE UPDATE, DELETE ON {tabla} FROM turnos_app" in sql
    # Un UPDATE de tabla completa del hallazgo permitiría editar contenido clínico.
    assert "GRANT UPDATE, DELETE ON odontograma_hallazgos" not in sql


# ---------------------------------------------------------------------------
# 1.7 — origen_cobertura acotado y validada_en_vivo con default false
# ---------------------------------------------------------------------------


def test_origen_cobertura_check_y_default_validada_en_vivo():
    sql = texto()
    assert (
        "origen_cobertura TEXT NOT NULL DEFAULT 'SIN_COBERTURA'"
        in sql
    )
    assert "CHECK (origen_cobertura IN ('CONFIGURADA','SIN_COBERTURA'))" in sql
    assert "validada_en_vivo BOOLEAN NOT NULL DEFAULT false" in sql


# ---------------------------------------------------------------------------
# 1.8 — modelos SQLAlchemy
# ---------------------------------------------------------------------------


def test_modelos_sqlalchemy_cargan_sin_errores():
    assert OdontogramaHallazgo.__tablename__ == "odontograma_hallazgos"
    assert Presupuesto.__tablename__ == "presupuestos"
    assert PresupuestoLinea.__tablename__ == "presupuesto_lineas"
    assert Aceptacion.__tablename__ == "aceptaciones"
    # tenant_id NOT NULL en las 4 (regla dura multi-tenant).
    for modelo in (OdontogramaHallazgo, Presupuesto, PresupuestoLinea, Aceptacion):
        assert modelo.__table__.columns["tenant_id"].nullable is False

    checks_hallazgo = [
        str(c.sqltext) for c in OdontogramaHallazgo.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("pieza_fdi / 10" in c and "pieza_fdi % 10" in c for c in checks_hallazgo)
    assert any("hallazgo <> ''" in c for c in checks_hallazgo)
    assert any("superficie IS NULL OR superficie <> ''" in c for c in checks_hallazgo)
    assert OdontogramaHallazgo.__table__.columns["resuelto"].nullable is False
    assert OdontogramaHallazgo.__table__.columns["superficie"].nullable is True

    checks_presupuesto = [
        str(c.sqltext) for c in Presupuesto.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("estado IN" in c and "BORRADOR" in c and "VENCIDO" in c for c in checks_presupuesto)
    assert Presupuesto.__table__.columns["vence_en"].nullable is True

    checks_linea = [
        str(c.sqltext) for c in PresupuestoLinea.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("cobertura_os + a_cargo_paciente = monto" in c for c in checks_linea)
    assert any("origen_cobertura IN" in c for c in checks_linea)
    assert PresupuestoLinea.__table__.columns["idempotency_key"].nullable is True
    assert PresupuestoLinea.__table__.columns["validada_en_vivo"].nullable is False
    assert PresupuestoLinea.__table__.columns["hallazgo_id"].nullable is True
    unicos = [
        i for i in PresupuestoLinea.__table__.indexes
        if isinstance(i, Index) and i.unique
    ]
    assert any(i.dialect_options["postgresql"].get("where") is not None for i in unicos)

    checks_aceptacion = [
        str(c.sqltext) for c in Aceptacion.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]
    assert any("canal <> ''" in c for c in checks_aceptacion)
    assert Aceptacion.__table__.columns["acepta"].nullable is False


# ---------------------------------------------------------------------------
# Integración real (sólo con C02_DATABASE_URL; se salta sin PostgreSQL)
# ---------------------------------------------------------------------------


def _owner_engine():
    from sqlalchemy import create_engine

    assert PG_URL is not None
    return create_engine(PG_URL, future=True)


def test_check_fdi_y_suma_de_linea_en_pg():
    """La base rechaza 19/20/29/30/39/40/49 y la suma inconsistente."""
    if not PG_URL:
        pytest.skip("C02_DATABASE_URL no configurada")
    import uuid

    engine = _owner_engine()
    ids = {k: str(uuid.uuid4()) for k in ("t1", "pac", "prof", "pres", "presu")}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                sql_text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T7', :slug)"),
                {"id": ids["t1"], "slug": f"c09-{ids['t1'][:8]}"},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
                    " VALUES (:id, :t, 'Paciente Demo', :tel)"
                ),
                {"id": ids["pac"], "t": ids["t1"], "tel": telefono_ficticio(ids["pac"])},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO profesionales (id, tenant_id, nombre, especialidad)"
                    " VALUES (:id, :t, 'Profesional Demo', 'Odontología')"
                ),
                {"id": ids["prof"], "t": ids["t1"]},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base)"
                    " VALUES (:id, :t, 'Conducto Demo', 30, 150000)"
                ),
                {"id": ids["pres"], "t": ids["t1"]},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO presupuestos (id, tenant_id, paciente_id)"
                    " VALUES (:id, :t, :pac)"
                ),
                {"id": ids["presu"], "t": ids["t1"], "pac": ids["pac"]},
            )
            tx.commit()

        with engine.connect() as owner:
            for pieza in (19, 20, 29, 30, 39, 40, 49):
                with pytest.raises(DBAPIError):
                    owner.execute(
                        sql_text(
                            "INSERT INTO odontograma_hallazgos"
                            " (tenant_id, paciente_id, pieza_fdi, hallazgo, fecha, profesional_id)"
                            " VALUES (:t, :pac, :pieza, 'demo', now(), :prof)"
                        ),
                        {
                            "t": ids["t1"], "pac": ids["pac"], "pieza": pieza,
                            "prof": ids["prof"],
                        },
                    )
                owner.rollback()

        with engine.connect() as owner:
            with pytest.raises(DBAPIError):
                owner.execute(
                    sql_text(
                        "INSERT INTO presupuesto_lineas"
                        " (tenant_id, presupuesto_id, prestacion_id, monto,"
                        "  cobertura_os, a_cargo_paciente)"
                        " VALUES (:t, :p, :pr, 100000, 60000, 30000)"
                    ),
                    {"t": ids["t1"], "p": ids["presu"], "pr": ids["pres"]},
                )
            owner.rollback()
    finally:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(sql_text("DELETE FROM tenants WHERE id = :id"), {"id": ids["t1"]})
            tx.commit()
        engine.dispose()


def test_unique_parcial_idempotency_key_en_pg():
    """Dos líneas de T1 con la misma key: la segunda falla; en T2 se acepta."""
    if not PG_URL:
        pytest.skip("C02_DATABASE_URL no configurada")
    import uuid

    engine = _owner_engine()
    ids = {
        k: str(uuid.uuid4())
        for k in ("t1", "t2", "pac1", "pac2", "prof1", "prof2", "pres1", "pres2", "presu1", "presu2")
    }
    key = "550e8400-e29b-41d4-a716-446655440000"
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                sql_text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T7', :slug)"),
                [
                    {"id": ids["t1"], "slug": f"c09a-{ids['t1'][:8]}"},
                    {"id": ids["t2"], "slug": f"c09b-{ids['t2'][:8]}"},
                ],
            )
            owner.execute(
                sql_text(
                    "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
                    " VALUES (:id, :t, 'Paciente Demo', :tel)"
                ),
                [
                    {"id": ids["pac1"], "t": ids["t1"], "tel": telefono_ficticio(ids["pac1"])},
                    {"id": ids["pac2"], "t": ids["t2"], "tel": telefono_ficticio(ids["pac2"])},
                ],
            )
            owner.execute(
                sql_text(
                    "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base)"
                    " VALUES (:id, :t, 'Conducto Demo', 30, 150000)"
                ),
                [
                    {"id": ids["pres1"], "t": ids["t1"]},
                    {"id": ids["pres2"], "t": ids["t2"]},
                ],
            )
            owner.execute(
                sql_text("INSERT INTO presupuestos (id, tenant_id, paciente_id) VALUES (:id, :t, :p)"),
                [
                    {"id": ids["presu1"], "t": ids["t1"], "p": ids["pac1"]},
                    {"id": ids["presu2"], "t": ids["t2"], "p": ids["pac2"]},
                ],
            )
            tx.commit()

        insert = sql_text(
            "INSERT INTO presupuesto_lineas"
            " (tenant_id, presupuesto_id, prestacion_id, monto, cobertura_os,"
            "  a_cargo_paciente, idempotency_key)"
            " VALUES (:t, :p, :pr, 150000, 0, 150000, :key)"
        )
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                insert,
                {"t": ids["t1"], "p": ids["presu1"], "pr": ids["pres1"], "key": key},
            )
            tx.commit()
        with engine.connect() as owner:
            with pytest.raises(DBAPIError):
                owner.execute(
                    insert,
                    {"t": ids["t1"], "p": ids["presu1"], "pr": ids["pres1"], "key": key},
                )
            owner.rollback()
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                insert,
                {"t": ids["t2"], "p": ids["presu2"], "pr": ids["pres2"], "key": key},
            )
            tx.commit()
    finally:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                sql_text("DELETE FROM tenants WHERE id = ANY(:ids)"),
                {"ids": [ids["t1"], ids["t2"]]},
            )
            tx.commit()
        engine.dispose()


def test_rls_fail_closed_y_grants_en_pg():
    """Sin tenant ⇒ 0 filas sin 42704; inmutable clínico; UPDATE (resuelto) sí."""
    if not PG_URL:
        pytest.skip("C02_DATABASE_URL no configurada")
    import uuid

    engine = _owner_engine()
    ids = {k: str(uuid.uuid4()) for k in ("t1", "pac", "prof", "pres", "presu", "hal", "linea", "ace")}
    try:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(
                sql_text("INSERT INTO tenants (id, nombre, slug) VALUES (:id, 'T7', :slug)"),
                {"id": ids["t1"], "slug": f"c09r-{ids['t1'][:8]}"},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO pacientes (id, tenant_id, nombre, telefono)"
                    " VALUES (:id, :t, 'Paciente Demo', :tel)"
                ),
                {"id": ids["pac"], "t": ids["t1"], "tel": telefono_ficticio(ids["pac"])},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO profesionales (id, tenant_id, nombre, especialidad)"
                    " VALUES (:id, :t, 'Profesional Demo', 'Odontología')"
                ),
                {"id": ids["prof"], "t": ids["t1"]},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO prestaciones (id, tenant_id, nombre, duracion_min, precio_base)"
                    " VALUES (:id, :t, 'Conducto Demo', 30, 150000)"
                ),
                {"id": ids["pres"], "t": ids["t1"]},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO odontograma_hallazgos"
                    " (id, tenant_id, paciente_id, pieza_fdi, superficie, hallazgo, fecha, profesional_id)"
                    " VALUES (:id, :t, :pac, 36, 'O', 'caries oclusal demo', now(), :prof)"
                ),
                {"id": ids["hal"], "t": ids["t1"], "pac": ids["pac"], "prof": ids["prof"]},
            )
            owner.execute(
                sql_text("INSERT INTO presupuestos (id, tenant_id, paciente_id) VALUES (:id, :t, :pac)"),
                {"id": ids["presu"], "t": ids["t1"], "pac": ids["pac"]},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO presupuesto_lineas"
                    " (id, tenant_id, presupuesto_id, prestacion_id, monto, cobertura_os,"
                    "  a_cargo_paciente)"
                    " VALUES (:id, :t, :p, :pr, 150000, 0, 150000)"
                ),
                {"id": ids["linea"], "t": ids["t1"], "p": ids["presu"], "pr": ids["pres"]},
            )
            owner.execute(
                sql_text(
                    "INSERT INTO aceptaciones (id, tenant_id, linea_id, acepta, fecha, canal)"
                    " VALUES (:id, :t, :l, true, now(), 'CONSULTORIO')"
                ),
                {"id": ids["ace"], "t": ids["t1"], "l": ids["linea"]},
            )
            tx.commit()

        def app(tenant: str | None):
            conn = engine.connect()
            conn.execute(sql_text("SET ROLE turnos_app"))
            if tenant is not None:
                conn.execute(sql_text("SELECT set_config('app.tenant_id', :t, false)"), {"t": tenant})
            return conn

        # Sin tenant y con cadena vacía: 0 filas, sin error 42704.
        for tenant in (None, ""):
            with app(tenant) as conn:
                assert conn.execute(sql_text("SELECT id FROM presupuestos")).all() == []
                assert conn.execute(sql_text("SELECT id FROM odontograma_hallazgos")).all() == []

        with app(ids["t1"]) as conn:
            with pytest.raises(DBAPIError):
                conn.execute(
                    sql_text("UPDATE odontograma_hallazgos SET hallazgo = 'otro' WHERE id = :id"),
                    {"id": ids["hal"]},
                )
            conn.rollback()
        with app(ids["t1"]) as conn:
            with pytest.raises(DBAPIError):
                conn.execute(
                    sql_text("DELETE FROM odontograma_hallazgos WHERE id = :id"),
                    {"id": ids["hal"]},
                )
            conn.rollback()
        with app(ids["t1"]) as conn:
            conn.execute(
                sql_text("UPDATE odontograma_hallazgos SET resuelto = true WHERE id = :id"),
                {"id": ids["hal"]},
            )
            conn.commit()
        for tabla, col in (
            ("presupuesto_lineas", "monto"),
            ("aceptaciones", "canal"),
        ):
            with app(ids["t1"]) as conn:
                with pytest.raises(DBAPIError):
                    conn.execute(
                        sql_text(f"UPDATE {tabla} SET {col} = {col} WHERE tenant_id = :t"),
                        {"t": ids["t1"]},
                    )
                conn.rollback()
            with app(ids["t1"]) as conn:
                with pytest.raises(DBAPIError):
                    conn.execute(
                        sql_text(f"DELETE FROM {tabla} WHERE tenant_id = :t"),
                        {"t": ids["t1"]},
                    )
                conn.rollback()
    finally:
        with engine.connect() as owner:
            tx = owner.begin()
            owner.execute(sql_text("DELETE FROM tenants WHERE id = :id"), {"id": ids["t1"]})
            tx.commit()
        engine.dispose()
