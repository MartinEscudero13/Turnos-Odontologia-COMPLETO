# Proposal

## Why

C-02 creó tenants y usuarios, pero todavía no hay forma segura de autenticarse, emitir sesiones ni autorizar operaciones por rol. Sin C-03, cualquier endpoint protegido seguiría dependiendo de headers de actor provisorios.

## What Changes

- Login con email/password y hash Argon2.
- Access token JWT corto + refresh token rotado y revocable.
- 2FA TOTP obligatorio para usuarios internos marcados con `two_factor=true`.
- Endpoints `login`, `refresh`, `logout`, `me`.
- Dependencia RBAC `(tenant_id, rol)` y contexto RLS por request.
- Auditoría centralizada de accesos y operaciones, sin PHI ni secretos.
- Rate-limit de login `5/60s` por IP+email.
- **BREAKING**: los endpoints que usen actor por headers deberán migrar a JWT en cambios posteriores; C-03 deja el contrato listo.

## Capabilities

### New Capabilities

- `auth-access`: autenticación, sesiones, 2FA, RBAC y auditoría de accesos.

### Modified Capabilities

- Ninguna capacidad de negocio existente cambia funcionalmente; C-05 mantiene sus endpoints y tests.

## Impact

- `backend/app/auth/`, `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`, `backend/app/core/audit.py`.
- Migración `004` para refresh tokens y secreto TOTP.
- Dependencias `argon2-cffi`, `PyJWT`, `pyotp`.
- Tests unitarios, API y RLS de sesión.
