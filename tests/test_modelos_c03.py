"""C-03 model and migration contract."""
from __future__ import annotations

from pathlib import Path

from app.models.refresh_token import RefreshToken
from app.models.usuario import Usuario


def test_usuario_has_encrypted_totp_slot_and_refresh_model() -> None:
    assert "two_factor_secret" in Usuario.__table__.columns
    assert Usuario.__table__.columns["two_factor_secret"].nullable is True
    assert RefreshToken.__tablename__ == "refresh_tokens"
    for column in ("tenant_id", "usuario_id", "token_hash", "expira_en", "revocado_en"):
        assert column in RefreshToken.__table__.columns


def test_migration_004_contains_rls_and_revocation() -> None:
    path = (
        Path(__file__).resolve().parent.parent
        / "backend"
        / "alembic"
        / "versions"
        / "004_auth_rbac.py"
    )
    text = path.read_text(encoding="utf-8")
    assert 'revision = "004_auth_rbac"' in text
    assert 'down_revision = "003_turnos_anti_solape"' in text
    assert "CREATE TABLE refresh_tokens" in text
    assert "two_factor_secret" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "GRANT SELECT, INSERT, UPDATE ON refresh_tokens TO turnos_app" in text
    assert "DROP TABLE IF EXISTS refresh_tokens" in text
