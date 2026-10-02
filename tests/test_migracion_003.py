"""Tasks 2.1–2.3 — migración Alembic 003 (verificación estructural): RED primero.

Sin PostgreSQL vivo en el entorno la DDL se verifica por estructura
(mismo desvío documentado que la corrida TS anterior, no se finge DB).
"""
from __future__ import annotations

from pathlib import Path

MIG = Path(__file__).resolve().parent.parent / "backend" / "alembic" / "versions" / "003_turnos_anti_solape.py"


def texto():
    assert MIG.exists(), f"falta la migración 003: {MIG}"
    return MIG.read_text(encoding="utf-8")


def test_extension_btree_gist_y_tabla_turnos():
    sql = texto()
    assert 'btree_gist' in sql
    assert 'CREATE TABLE turnos' in sql
    assert 'TIMESTAMPTZ' in sql


def test_dos_exclude_parciales_half_open():
    sql = texto()
    assert sql.count("EXCLUDE USING gist") == 2
    assert "tstzrange(inicio, fin)" in sql
    assert "profesional_id WITH =" in sql
    assert "sillon_id WITH =" in sql
    assert "CANCELADO" in sql and "REPROGRAMADO" in sql and "sobreturno = false" in sql


def test_indices_y_rls_por_tenant():
    sql = texto()
    assert "turnos_tenant_profesional_inicio_idx" in sql
    assert "turnos_tenant_sillon_inicio_idx" in sql
    assert "turnos_tenant_estado_idx" in sql
    assert "ROW LEVEL SECURITY" in sql
    assert "current_setting('app.tenant_id')" in sql


def test_revision_alembic_con_downgrade():
    sql = texto()
    assert "revision = " in sql and "down_revision" in sql
    assert "def upgrade(" in sql and "def downgrade(" in sql
    assert "DROP TABLE IF EXISTS turnos" in sql


def test_fks_deferidas_a_c04_expand_contract():
    sql = texto()
    assert "expand-contract" in sql and "C-04" in sql
