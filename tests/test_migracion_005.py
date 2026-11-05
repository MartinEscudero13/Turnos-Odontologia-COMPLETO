"""Tasks 1.1–1.3 — migración Alembic 005 (lista_espera + ofertas + RLS): RED primero.

Sin PostgreSQL vivo en el entorno la DDL se verifica por estructura (mismo
desvío documentado que la migración 001/003); la migración real corre en CI
(`alembic upgrade head`). Acá aseguramos que la 005 cree ambas tablas con RLS,
`down_revision="004_auth_rbac"`, downgrade reversible y que los modelos
SQLAlchemy carguen sin errores.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import CheckConstraint

from app.models.lista_espera import ListaEspera, Oferta

MIG = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "alembic"
    / "versions"
    / "005_lista_espera.py"
)


def texto() -> str:
    assert MIG.exists(), f"falta la migración 005: {MIG}"
    return MIG.read_text(encoding="utf-8")


def test_upgrade_head_crea_lista_espera_y_ofertas_con_rls():
    sql = texto()
    assert 'revision = "005_lista_espera"' in sql
    assert 'down_revision = "004_auth_rbac"' in sql
    assert "CREATE TABLE lista_espera" in sql
    assert "CREATE TABLE ofertas" in sql
    assert "TIMESTAMPTZ" in sql
    # RLS en ambas tablas: fail-closed por tenant (loop sobre lista_espera y ofertas).
    assert 'for table in ("lista_espera", "ofertas")' in sql
    assert "ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
    assert "current_setting('app.tenant_id')::uuid" in sql
    # La lista de espera mantiene la restricción de estado.
    assert "PENDIENTE" in sql and "OFRECIDO" in sql and "CONVERTIDO" in sql and "VENCIDO" in sql


def test_downgrade_elimina_solo_005():
    sql = texto()
    assert "def downgrade(" in sql
    # Sólo se elimina lo propio de la 005: lista_espera y ofertas.
    assert "DROP TABLE IF EXISTS ofertas" in sql
    assert "DROP TABLE IF EXISTS lista_espera" in sql
    # No debe tocar turnos ni catálogos (los deja intactos).
    assert "DROP TABLE IF EXISTS turnos" not in sql
    assert "DROP TABLE IF EXISTS pacientes" not in sql
    assert "DROP TABLE IF EXISTS prestaciones" not in sql


def test_modelos_sqlalchemy_cargan_sin_errores():
    assert ListaEspera.__tablename__ == "lista_espera"
    assert Oferta.__tablename__ == "ofertas"
    # tenant_id NOT NULL en ambas (regla dura multi-tenant).
    assert ListaEspera.__table__.columns["tenant_id"].nullable is False
    assert Oferta.__table__.columns["tenant_id"].nullable is False
    # FK y CHECK de estado de la oferta.
    assert ListaEspera.__table__.columns["estado"].nullable is False
    checks = [str(c.sqltext) for c in Oferta.__table__.constraints if isinstance(c, CheckConstraint)]
    assert any("estado IN" in c for c in checks)
    assert Oferta.__table__.columns["expira_at"].nullable is False
    assert Oferta.__table__.columns["token"].nullable is False
