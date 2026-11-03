"""C-04 catalog model and migration contract."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.catalogos import (
    Bloqueo,
    HorarioSemanal,
    Paciente,
    Prestacion,
    Profesional,
    ProfesionalPrestacion,
    Sillon,
)


def test_catalog_tables_and_tenant_constraints() -> None:
    assert Sillon.__table__.columns["tenant_id"].nullable is False
    assert Prestacion.__table__.columns["duracion_min"].nullable is False
    checks = [str(c.sqltext) for c in Prestacion.__table__.constraints if isinstance(c, CheckConstraint)]
    assert any("duracion_min > 0" in check for check in checks)
    uniques = [c for c in Paciente.__table__.constraints if isinstance(c, UniqueConstraint)]
    assert any([col.name for col in c.columns] == ["tenant_id", "telefono"] for c in uniques)
    assert Profesional.__table__.columns["nombre"].nullable is False
    assert ProfesionalPrestacion.__table__.primary_key is not None
    assert HorarioSemanal.__table__.columns["dia"].nullable is False
    assert Bloqueo.__table__.columns["motivo"].nullable is False


def test_migration_002_creates_catalog_with_rls() -> None:
    path = (
        Path(__file__).resolve().parent.parent
        / "backend"
        / "alembic"
        / "versions"
        / "002_catalogos_pacientes.py"
    )
    text = path.read_text(encoding="utf-8")
    for table in (
        "sillones",
        "prestaciones",
        "profesionales",
        "profesional_prestacion",
        "horarios_semanales",
        "bloqueos",
        "pacientes",
    ):
        assert f'"{table}"' in text
    assert "ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in text
    assert "ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in text
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO turnos_app" in text
    assert "current_setting('app.tenant_id')::uuid" in text
    assert "DROP TABLE IF EXISTS {table}" in text
