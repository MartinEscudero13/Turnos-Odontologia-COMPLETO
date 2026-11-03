"""Authentication HTTP endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.deps import get_auth_service, get_current_user, require_roles
from app.auth.service import AuthError, AuthService, CurrentUser
from app.schemas.auth import LoginIn, RefreshIn, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _http_error(exc: AuthError) -> HTTPException:
    headers: dict[str, str] = {}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return HTTPException(status_code=exc.status_code, detail=exc.message, headers=headers)


@router.post("/login", response_model=TokenOut)
def login(
    body: LoginIn,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenOut:
    ip = request.client.host if request.client else "unknown"
    try:
        tokens = service.login(
            tenant_slug=body.tenant_slug,
            email=body.email,
            password=body.password,
            two_factor_code=body.two_factor_code,
            ip=ip,
        )
    except AuthError as exc:
        raise _http_error(exc) from exc
    return TokenOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/refresh", response_model=TokenOut)
def refresh(
    body: RefreshIn,
    service: AuthService = Depends(get_auth_service),
) -> TokenOut:
    try:
        tokens = service.refresh(tenant_slug=body.tenant_slug, raw_refresh_token=body.refresh_token)
    except AuthError as exc:
        raise _http_error(exc) from exc
    return TokenOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: RefreshIn,
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout(tenant_slug=body.tenant_slug, raw_refresh_token=body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=user.id,
        tenant_id=user.tenant_id,
        nombre=user.nombre,
        email=user.email,
        rol=user.rol,
        two_factor=user.two_factor,
    )


@router.get("/admin-check")
def admin_check(user: CurrentUser = Depends(require_roles("ADMIN"))) -> dict[str, str]:
    return {"status": "ok", "user_id": str(user.id)}
