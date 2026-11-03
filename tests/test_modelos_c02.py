"""C-02 model contract: tenant, users, audit and tenant parameters."""
from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.auditoria import Auditoria
from app.models.tenant import ParametroTenant, Tenant
from app.models.turno import Turno
from app.models.usuario import Usuario


def test_tenant_identity_is_uuid_and_slug_unique() -> None:
    assert Tenant.__tablename__ == "tenants"
    assert Tenant.__table__.columns["id"].primary_key
    assert Tenant.__table__.columns["slug"].unique is True
    assert Tenant.__table__.columns["activo"].nullable is False
    assert Tenant.__table__.columns["id"].type.python_type is uuid.UUID


def test_usuario_is_tenant_scoped_with_unique_email_and_role_check() -> None:
    assert Usuario.__tablename__ == "usuarios"
    assert Usuario.__table__.columns["tenant_id"].nullable is False
    uniques = [c for c in Usuario.__table__.constraints if isinstance(c, UniqueConstraint)]
    assert any([col.name for col in c.columns] == ["tenant_id", "email"] for c in uniques)
    checks = [str(c.sqltext) for c in Usuario.__table__.constraints if isinstance(c, CheckConstraint)]
    assert any("rol IN" in check for check in checks)
    assert any("lower(email)" in check for check in checks)


def test_auditoria_has_generic_entity_and_append_only_fields() -> None:
    assert Auditoria.__tablename__ == "auditoria"
    cols = Auditoria.__table__.columns
    for name in ("tenant_id", "actor_id", "accion", "entidad", "entidad_id", "antes", "despues"):
        assert name in cols
    assert cols["tenant_id"].nullable is False
    assert cols["motivo"].nullable is True


def test_turno_tenant_is_uuid_and_foreign_key_to_tenants() -> None:
    col = Turno.__table__.columns["tenant_id"]
    assert col.type.python_type is uuid.UUID
    assert any(fk.target_fullname == "tenants.id" for fk in col.foreign_keys)


def test_tenant_parameter_composite_key() -> None:
    cols = ParametroTenant.__table__.columns
    assert [col.name for col in ParametroTenant.__table__.primary_key.columns] == ["tenant_id", "clave"]
    assert cols["valor"].nullable is False
