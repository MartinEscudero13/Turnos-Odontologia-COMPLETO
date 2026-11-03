# Verification report — C-02 `core-models-multitenant`

**Fecha**: 2026-11-03 · **Entorno**: PostgreSQL 15 en Docker Compose, Python 3.14, Windows
**Base**: `postgresql+psycopg://turnos_owner:dev-only-owner-password@localhost:5433/turnos`
**Cambio archivado**: `openspec/changes/archive/2026-11-03-c-02-core-models-multitenant/`

## Resultado

| Gate | Comando | Resultado |
|---|---|---|
| Suite completa | `py -m pytest tests/ -q` | **130 tests**, exit 0 (con `C02_DATABASE_URL`; sin DB: 2 RLS skipped) |
| RLS real | `py -m pytest tests/test_rls_c02.py -q` con `C02_DATABASE_URL` | **2 passed** |
| Lint | `py -m ruff check .` | `All checks passed!` |
| Type check | `py -m mypy --config-file pyproject.toml` | Success, 28 archivos |
| Migración | `alembic upgrade head` | 001 → 002 → 003, exit 0 |
| Rollback | `alembic downgrade base` | borra 003/002/001, exit 0 |
| Re-upgrade | `alembic upgrade head` | exit 0 |
| Seed real | dos llamadas a `seed_tenant` contra PostgreSQL | primera crea 8 parámetros; segunda inserta 0 |
| Rol app | login `turnos_app` con password de desarrollo | `current_user=turnos_app`, `current_database=turnos` |
| Compose | `docker compose config --quiet` | exit 0 |

## RLS comprobada en base real

`tests/test_rls_c02.py` crea tenants T1/T2 como owner, cambia a `SET ROLE turnos_app`,
setea `app.tenant_id` y verifica:

- `SELECT usuarios` devuelve sólo el usuario de T1.
- Consultar el tenant T2 devuelve 0 filas.
- Insertar un usuario con `tenant_id=T2` desde T1 falla (WITH CHECK).
- Insertar auditoría funciona; `UPDATE` y `DELETE` fallan por permisos.
- La limpieza posterior se ejecuta como owner.

## Seed idempotente verificado en PostgreSQL

```text
first  SeedResult(tenant_id=a0000000-..., tenant_created=True, parametros_insertados=8)
second SeedResult(tenant_id=a0000000-..., tenant_created=False, parametros_insertados=0)
params 8
```

Los valores son ficticios y no incluyen precios ni señas: se guardan como
parámetros (`politica_sena`, `cancelacion_anticipacion_h`) para C-04.

## Desvíos y deuda

- Migración 002 sigue siendo un placeholder de orden; C-04 la implementa.
- `turnos.tenant_id` pasó de `TEXT` a `UUID` con FK a `tenants`; los tests C-05
  se adaptaron a IDs UUID ficticios y siguen verdes.
- La API usa `turnos_app`; las migraciones y el seed usan `turnos_owner`.
- RLS se fuerza con `FORCE ROW LEVEL SECURITY` y se prueba con un rol no-owner;
  no basta con que la API tenga el rol de owner.
- C-06 sigue bloqueado hasta que C-02/C-03/C-04 estén archivados.
