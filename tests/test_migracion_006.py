"""Tasks 1.1–1.4 — migración Alembic 006 (ficha clínica + consentimiento): RED primero.

Sin PostgreSQL vivo en el entorno la DDL se verifica por estructura (mismo
desvío documentado que 001/003/005); la migración real corre en CI
(`alembic upgrade head`). Acá aseguramos que la 006 cree las 4 tablas clínicas
con RLS, `down_revision="005_lista_espera"`, downgrade reversible, append-only a
nivel DB (REVOKE UPDATE/DELETE) para `evoluciones`/`consentimientos`, y que los
modelos SQLAlchemy carguen sin errores.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.ficha_clinica import Adjunto, Consentimiento, Evolucion, Ficha

MIG = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "alembic"
    / "versions"
    / "006_ficha_clinica.py"
)


def texto() -> str:
    assert MIG.exists(), f"falta la migración 006: {MIG}"
    return MIG.read_text(encoding="utf-8")


def test_upgrade_head_crea_tablas_clinicas_con_rls():
    sql = texto()
    assert 'revision = "006_ficha_clinica"' in sql
    assert 'down_revision = "005_lista_espera"' in sql
    assert "CREATE TABLE fichas" in sql
    assert "CREATE TABLE evoluciones" in sql
    assert "CREATE TABLE adjuntos" in sql
    assert "CREATE TABLE consentimientos" in sql
    assert "TIMESTAMPTZ" in sql
    # Ficha 1—1: UNIQUE (tenant_id, paciente_id).
    assert "UNIQUE (tenant_id, paciente_id)" in sql
    # RLS forzada en las 4 tablas (fail-closed por tenant).
    assert 'for table in ("fichas", "evoluciones", "adjuntos", "consentimientos")' in sql
    assert "ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
    assert "current_setting('app.tenant_id')::uuid" in sql
    # Append-only a nivel DB: evoluciones y consentimientos sin UPDATE/DELETE.
    assert "REVOKE UPDATE, DELETE ON evoluciones FROM turnos_app" in sql
    assert "REVOKE UPDATE, DELETE ON consentimientos FROM turnos_app" in sql
    # tipo CHECK de adjunto y canal no vacío de consentimiento.
    assert "RX" in sql and "FOTO" in sql
    assert "canal <> ''" in sql


def test_downgrade_elimina_solo_006():
    sql = texto()
    assert "def downgrade(" in sql
    for tabla in ("consentimientos", "adjuntos", "evoluciones", "fichas"):
        assert f"DROP TABLE IF EXISTS {tabla}" in sql
    # No debe tocar turnos, catálogos ni lista de espera.
    assert "DROP TABLE IF EXISTS turnos" not in sql
    assert "DROP TABLE IF EXISTS pacientes" not in sql
    assert "DROP TABLE IF EXISTS prestaciones" not in sql
    assert "DROP TABLE IF EXISTS lista_espera" not in sql


def test_modelos_sqlalchemy_cargan_sin_errores():
    assert Ficha.__tablename__ == "fichas"
    assert Evolucion.__tablename__ == "evoluciones"
    assert Adjunto.__tablename__ == "adjuntos"
    assert Consentimiento.__tablename__ == "consentimientos"
    # tenant_id NOT NULL en las 4 (regla dura multi-tenant).
    for modelo in (Ficha, Evolucion, Adjunto, Consentimiento):
        assert modelo.__table__.columns["tenant_id"].nullable is False
    # 1—1 paciente—ficha: UNIQUE(tenant_id, paciente_id).
    ficha_unicos = [c for c in Ficha.__table__.constraints if isinstance(c, UniqueConstraint)]
    assert any(
        {col.name for col in u.columns} == {"tenant_id", "paciente_id"} for u in ficha_unicos
    )
    # Consentimiento: timestamp NOT NULL (fuente del gate).
    assert Consentimiento.__table__.columns["timestamp"].nullable is False
    assert Consentimiento.__table__.columns["canal"].nullable is False
    # Adjunto: tipo CHECK IN ('RX','FOTO').
    checks_adj = [str(c.sqltext) for c in Adjunto.__table__.constraints if isinstance(c, CheckConstraint)]
    assert any("tipo IN" in c and "RX" in c and "FOTO" in c for c in checks_adj)
    # Evolución: texto NOT NULL, firma_hash nullable (OQ).
    assert Evolucion.__table__.columns["texto"].nullable is False
    assert Evolucion.__table__.columns["firma_hash"].nullable is True


def test_update_delete_evolucion_rechazados_por_db():
    sql = texto()
    assert "GRANT SELECT, INSERT" in sql or "GRANT SELECT, INSERT, UPDATE, DELETE" in sql
    assert "REVOKE UPDATE, DELETE ON evoluciones FROM turnos_app" in sql


def test_update_delete_consentimiento_rechazados_por_db():
    sql = texto()
    assert "REVOKE UPDATE, DELETE ON consentimientos FROM turnos_app" in sql
