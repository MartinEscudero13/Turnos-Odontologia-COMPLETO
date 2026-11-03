# Tasks — C-03 `auth-rbac-auditoria`

> TDD rojo-primero en login, rotación, RBAC, 2FA y rate-limit. Sin secretos ni PHI en tests/logs.

## 1. Modelo y migración

- [x] 1.1 Agregar `two_factor_secret` a `Usuario` y modelo `RefreshToken`; verificar con `tests/test_modelos_c03.py` que el modelo y la tabla tienen tipos/constraints.
- [x] 1.2 Implementar migración `004_auth_rbac` con refresh tokens, RLS, índices y grants; verificar `alembic upgrade head` y `downgrade base`/re-upgrade en PostgreSQL de Compose.

## 2. Seguridad y servicio

- [x] 2.1 Implementar `app/auth/security.py` (Argon2, JWT, hash de refresh y cifrado TOTP); verificar con `tests/test_auth_security.py` la verificación de password, token inválido y secreto no expuesto.
- [x] 2.2 Implementar `app/auth/rate_limit.py` con ventana 5/60s; verificar con `tests/test_auth_rate_limit.py` el sexto intento y `Retry-After`.
- [x] 2.3 Implementar `app/core/audit.py` y `app/auth/service.py` (login, refresh rotado, logout, me, 2FA); verificar con `tests/test_auth_service.py` login válido/inválido, refresh, reuso y usuario inactivo.

## 3. API y RBAC

- [x] 3.1 Crear `app/schemas/auth.py` y `app/routers/auth.py` con login, refresh, logout, me y ruta protegida de comprobación de rol; verificar con `tests/test_auth_api.py` los códigos 200/401/403/429 y que no se filtren secretos.
- [x] 3.2 Agregar `get_current_user`/`require_roles` y contexto de tenant RLS; verificar token de otro tenant y rol insuficiente con `tests/test_auth_rbac.py`.
- [x] 3.3 Integrar el router en `create_app` sin romper `/api/health` ni los tests C-05; verificar suite completa.

## 4. Verificación y cierre

- [x] 4.1 Ejecutar RLS de autenticación contra PostgreSQL real con rol `turnos_app`; documentar en `docs/foundation/verification-c03.md`.
- [x] 4.2 Correr `py -m pytest tests/ -q`, `ruff`, `mypy`, `openspec validate c-03-auth-rbac-auditoria --strict`; corregir todo antes de archivar.
- [x] 4.3 Actualizar `README.md`/`CHANGES.md`, archivar el change y verificar `openspec validate --all --strict`.

## Workflow follow-up

- Migrar C-05 a JWT en un change posterior; no cambiar su contrato en C-03.
- El rate-limit distribuido queda para la etapa de workers/Redis.
