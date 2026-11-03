"""Security primitives for auth: password hashing, JWT and TOTP encryption."""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_hasher = PasswordHasher()


class SecurityError(Exception):
    """Generic security failure; never contains a credential or secret."""


@dataclass(frozen=True)
class AccessClaims:
    user_id: str
    tenant_id: str
    role: str


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _fernet(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_totp_secret(secret: str, jwt_secret: str) -> str:
    return _fernet(jwt_secret).encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_totp_secret(encrypted: str, jwt_secret: str) -> str:
    try:
        return _fernet(jwt_secret).decrypt(encrypted.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecurityError("TOTP secret inválido") from exc


def create_access_token(
    *,
    user_id: str,
    tenant_id: str,
    role: str,
    jwt_secret: str,
    expires_minutes: int = 15,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access",
        "iat": issued,
        "exp": issued + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def decode_access_token(token: str, jwt_secret: str) -> AccessClaims:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "tenant_id", "role", "type", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise SecurityError("Token inválido") from exc
    if payload.get("type") != "access":
        raise SecurityError("Token inválido")
    return AccessClaims(
        user_id=str(payload["sub"]),
        tenant_id=str(payload["tenant_id"]),
        role=str(payload["role"]),
    )


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_totp(encrypted_secret: str, code: str, jwt_secret: str) -> bool:
    secret = decrypt_totp_secret(encrypted_secret, jwt_secret)
    return pyotp.TOTP(secret).verify(code, valid_window=1)
