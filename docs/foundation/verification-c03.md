# Verification report — C-03 `auth-rbac-auditoria`

**Fecha**: 2026-11-03 · **Entorno**: PostgreSQL 15 en Docker + SQLite para API tests
**Base de integración**: `postgresql+psycopg://turnos:test-password@localhost:5434/turnos`
**Cambio archivado**: `openspec/changes/archive/2026-11-03-c-03-auth-rbac-auditoria/`

## Resultado

| Gate | Comando | Resultado |
|---|---|---|
| Suite completa | `py -m pytest tests/ -q` con `C02_DATABASE_URL` | **152 tests**, exit 0 |
| Tests RLS | `pytest tests/test_rls_c02.py tests/test_rls_c03.py` | **3 passed** |
| Login/refresh/logout/me | `pytest tests/test_auth_api.py` | **5 passed** |
| Seguridad | `pytest tests/test_auth_security.py` | **5 passed** |
| Rate limit | `pytest tests/test_auth_rate_limit.py` | **2 passed** |
| Servicio auth | `pytest tests/test_auth_service.py` | **7 passed** |
| Lint | `py -m ruff check .` | `All checks passed!` |
| Type check | `py -m mypy --config-file pyproject.toml` | Success, 37 archivos |
| Migración 004 | `alembic upgrade head`, `downgrade -1`, `upgrade head` | exit 0 |
| OpenSpec | `openspec validate c-03-auth-rbac-auditoria --strict` | `is valid` |

## Cobertura funcional

- Login con Argon2id y respuesta genérica `401` para credenciales inválidas.
- Tenant/usuario inactivo bloqueado (`403`).
- Access JWT HS256 con `sub`, `tenant_id`, `role`, `type=access` y expiración.
- Refresh token opaco, sólo hash SHA-256 en DB, rotación y revocación.
- Logout revoca el refresh presentado.
- 2FA TOTP con secreto cifrado con Fernet derivada de `JWT_SECRET`; sin secreto no hay login.
- RBAC: `ADMIN`, `RECEPCION`, `ODONTOLOGO`; ruta admin rechaza recepción con `403`.
- Rate-limit por `(IP, email)` de 5 intentos/60 s, `429` + `Retry-After`.
- Auditoría de `LOGIN`, `REFRESH` y `LOGOUT` sin password, token, email completo ni PHI.
- RLS de `refresh_tokens` probada con `SET ROLE turnos_app` y tenants T1/T2.

## Verificación RLS de refresh tokens

`tests/test_rls_c03.py` inserta tokens de dos tenants como owner, cambia a
`turnos_app`, fija `app.tenant_id=T1` y comprueba:

- sólo se ve el hash de T1;
- insertar un refresh de T2 desde T1 falla por la política `WITH CHECK`.

## Deuda y notas

- El rate-limit es **en proceso**: al escalar a múltiples workers habrá que moverlo a Redis.
- Los endpoints de C-05 siguen usando el actor por headers provisorio; C-03 deja el dependency JWT listo para C-06.
- Migración 004 va después de C-05 (003); 002 sigue reservada a C-04.
- No se agregaron datos reales ni credenciales productivas.

