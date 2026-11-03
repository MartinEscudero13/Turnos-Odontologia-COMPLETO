"""Authentication service: login, refresh rotation, logout and user resolution."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.rate_limit import LoginRateLimiter
from app.auth.security import (
    AccessClaims,
    SecurityError,
    create_access_token,
    decode_access_token,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
    verify_totp,
)
from app.core.audit import record_audit
from app.core.settings import Settings
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.usuario import Usuario


class AuthError(Exception):
    def __init__(self, status_code: int, message: str, *, retry_after: int | None = None) -> None:
        self.status_code = status_code
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    nombre: str
    email: str
    rol: str
    two_factor: bool


def _set_tenant_context(session: Session, tenant_id: uuid.UUID) -> None:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": str(tenant_id)},
        )


class AuthService:
    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        rate_limiter: LoginRateLimiter | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.rate_limiter = rate_limiter or LoginRateLimiter()

    def login(
        self,
        *,
        tenant_slug: str,
        email: str,
        password: str,
        two_factor_code: str | None,
        ip: str,
    ) -> TokenPair:
        normalized_email = email.strip().lower()
        allowed, retry_after = self.rate_limiter.allow(f"{ip}:{normalized_email}")
        if not allowed:
            raise AuthError(429, "Demasiados intentos de login", retry_after=retry_after)

        with self.session_factory() as session:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
            if tenant is None:
                raise AuthError(401, "Credenciales inválidas")
            if not tenant.activo:
                raise AuthError(403, "Tenant inactivo")
            _set_tenant_context(session, tenant.id)
            user = session.scalar(
                select(Usuario).where(
                    Usuario.tenant_id == tenant.id,
                    Usuario.email == normalized_email,
                )
            )
            if user is None:
                raise AuthError(401, "Credenciales inválidas")
            if not user.activo:
                raise AuthError(403, "Usuario inactivo")
            if not verify_password(user.password_hash, password):
                raise AuthError(401, "Credenciales inválidas")
            if user.two_factor:
                if not two_factor_code or not user.two_factor_secret:
                    raise AuthError(401, "Código 2FA requerido")
                try:
                    valid_totp = verify_totp(
                        user.two_factor_secret, two_factor_code, self.settings.jwt_secret
                    )
                except SecurityError as exc:
                    raise AuthError(401, "Código 2FA inválido") from exc
                if not valid_totp:
                    raise AuthError(401, "Código 2FA inválido")
            tokens = self._issue_pair(session, user)
            record_audit(
                session,
                tenant_id=user.tenant_id,
                actor_id=str(user.id),
                accion="LOGIN",
                entidad="usuario",
                entidad_id=str(user.id),
                despues={"resultado": "OK"},
            )
            session.commit()
            return tokens

    def refresh(self, *, tenant_slug: str, raw_refresh_token: str) -> TokenPair:
        with self.session_factory() as session:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
            if tenant is None or not tenant.activo:
                raise AuthError(401, "Refresh inválido")
            _set_tenant_context(session, tenant.id)
            stored = session.scalar(
                select(RefreshToken).where(
                    RefreshToken.tenant_id == tenant.id,
                    RefreshToken.token_hash == hash_refresh_token(raw_refresh_token),
                )
            )
            if stored is None or stored.revocado_en is not None:
                raise AuthError(401, "Refresh inválido")
            expires = stored.expira_en
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires <= datetime.now(UTC):
                raise AuthError(401, "Refresh expirado")
            user = session.get(Usuario, stored.usuario_id)
            if user is None or not user.activo:
                raise AuthError(401, "Refresh inválido")
            stored.revocado_en = datetime.now(UTC)
            tokens = self._issue_pair(session, user)
            record_audit(
                session,
                tenant_id=user.tenant_id,
                actor_id=str(user.id),
                accion="REFRESH",
                entidad="sesion",
                entidad_id=str(user.id),
                despues={"resultado": "OK"},
            )
            session.commit()
            return tokens

    def logout(self, *, tenant_slug: str, raw_refresh_token: str) -> None:
        with self.session_factory() as session:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
            if tenant is None:
                return
            _set_tenant_context(session, tenant.id)
            stored = session.scalar(
                select(RefreshToken).where(
                    RefreshToken.tenant_id == tenant.id,
                    RefreshToken.token_hash == hash_refresh_token(raw_refresh_token),
                )
            )
            if stored is None or stored.revocado_en is not None:
                return
            stored.revocado_en = datetime.now(UTC)
            record_audit(
                session,
                tenant_id=stored.tenant_id,
                actor_id=str(stored.usuario_id),
                accion="LOGOUT",
                entidad="sesion",
                entidad_id=str(stored.usuario_id),
                despues={"resultado": "OK"},
            )
            session.commit()

    def current_user(self, token: str) -> CurrentUser:
        try:
            claims = decode_access_token(token, self.settings.jwt_secret)
        except SecurityError as exc:
            raise AuthError(401, "Token inválido") from exc
        with self.session_factory() as session:
            tenant_id = uuid.UUID(claims.tenant_id)
            _set_tenant_context(session, tenant_id)
            user = session.get(Usuario, uuid.UUID(claims.user_id))
            if user is None or not user.activo or user.tenant_id != tenant_id:
                raise AuthError(401, "Token inválido")
            return CurrentUser(
                id=user.id,
                tenant_id=user.tenant_id,
                nombre=user.nombre,
                email=user.email,
                rol=user.rol,
                two_factor=user.two_factor,
            )

    def _issue_pair(self, session: Session, user: Usuario) -> TokenPair:
        access = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.rol,
            jwt_secret=self.settings.jwt_secret,
        )
        raw_refresh = new_refresh_token()
        session.add(
            RefreshToken(
                tenant_id=user.tenant_id,
                usuario_id=user.id,
                token_hash=hash_refresh_token(raw_refresh),
                expira_en=datetime.now(UTC) + timedelta(days=7),
            )
        )
        session.flush()
        return TokenPair(access_token=access, refresh_token=raw_refresh)

    def tenant_context(self, claims: AccessClaims) -> CurrentUser:
        return self.current_user(
            create_access_token(
                user_id=claims.user_id,
                tenant_id=claims.tenant_id,
                role=claims.role,
                jwt_secret=self.settings.jwt_secret,
            )
        )

