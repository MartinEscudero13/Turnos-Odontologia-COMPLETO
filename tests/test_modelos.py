"""Tasks 2.1–2.3 — modelos SQLAlchemy (tenant everywhere, timestamptz): RED primero."""
from __future__ import annotations

from sqlalchemy import DateTime

from app.models.turno import Auditoria, Turno


def test_turnos_tabla_y_tenant_not_null():
    assert Turno.__tablename__ == "turnos"
    assert Turno.__table__.columns["tenant_id"].nullable is False


def test_inicio_fin_timestamptz_y_check_fin_posterior():
    from sqlalchemy import CheckConstraint

    cols = Turno.__table__.columns
    for col in ("inicio", "fin"):
        assert isinstance(cols[col].type, DateTime) and cols[col].type.timezone is True
    checks = [c for c in Turno.__table__.constraints if isinstance(c, CheckConstraint)]
    assert any("fin > inicio" in str(c.sqltext) for c in checks)


def test_defaults_pendiente_y_no_sobreturno():
    cols = Turno.__table__.columns
    assert cols["estado"].default.arg == "PENDIENTE"
    assert cols["sobreturno"].default.arg is False
    assert cols["origen"].default.arg == "RECEPCION"


def test_auditoria_append_only_por_convencion():
    assert Auditoria.__tablename__ == "auditoria"
    cols = Auditoria.__table__.columns
    assert cols["tenant_id"].nullable is False
    assert cols["motivo"].nullable is True


def test_token_publico_opcional_y_creado_en_server_default():
    cols = Turno.__table__.columns
    assert cols["token_publico"].nullable is True
    assert cols["creado_en"].server_default is not None
