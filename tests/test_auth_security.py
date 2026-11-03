"""Auth security primitives: hashing, JWT and TOTP encryption."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyotp
import pytest

from app.auth.security import (
    SecurityError,
    create_access_token,
    decode_access_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_totp,
)

SECRET = "test-secret-that-is-long-enough-for-local-dev-1234567890"


def test_argon2_hash_does_not_store_plaintext() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password(hashed, "correct horse battery staple")
    assert not verify_password(hashed, "wrong")


def test_jwt_roundtrip_and_tamper_rejection() -> None:
    token = create_access_token(
        user_id="user-1", tenant_id="tenant-1", role="ADMIN", jwt_secret=SECRET
    )
    claims = decode_access_token(token, SECRET)
    assert claims.user_id == "user-1"
    assert claims.role == "ADMIN"
    with pytest.raises(SecurityError):
        decode_access_token(token + "x", SECRET)


def test_expired_jwt_is_rejected() -> None:
    token = create_access_token(
        user_id="user-1",
        tenant_id="tenant-1",
        role="ADMIN",
        jwt_secret=SECRET,
        expires_minutes=-1,
        now=datetime.now(UTC) - timedelta(minutes=10),
    )
    with pytest.raises(SecurityError):
        decode_access_token(token, SECRET)


def test_totp_secret_is_encrypted_and_verified() -> None:
    raw_secret = pyotp.random_base32()
    encrypted = encrypt_totp_secret(raw_secret, SECRET)
    assert raw_secret not in encrypted
    assert decrypt_totp_secret(encrypted, SECRET) == raw_secret
    assert verify_totp(encrypted, pyotp.TOTP(raw_secret).now(), SECRET)
    assert not verify_totp(encrypted, "000000", SECRET)


def test_refresh_hash_is_deterministic_and_not_raw() -> None:
    token = "refresh-token-demo"
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert token not in hash_refresh_token(token)
