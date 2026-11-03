# Tasks — C-02 `core-models-multitenant`

> TDD rojo-primero en RLS, unicidad y auditoría. Datos ficticios, sin secretos.
> La migración debe probarse contra PostgreSQL real, no solo por inspección de texto.

## 1. Modelos y tipos

- [x] 1.1 Crear `app/models/base.py`, `tenant.py`, `usuario.py` y `auditoria.py`; migrar `Turno.tenant_id` a UUID; verificar con `tests/test_modelos_c02.py` que tablas, constraints, FKs y tipos existen.
- [x] 1.2 Agregar `ParametroTenant` con PK `(tenant_id, clave)` y valor JSON; verificar que el modelo coincide con la migración y que no hay campos `any`/genéricos sin tipo.
- [x] 1.3 Actualizar `tests/conftest.py` a tenant IDs UUID ficticios y verificar que la suite C-05 sigue verde.

## 2. Migración 001 y RLS

- [x] 2.1 Escribir `tests/test_migracion_001.py` que exija `tenants`, `usuarios`, `auditoria`, `tenant_parametros`, `UNIQUE(tenant_id,email)`, FK a tenants, RLS y `FORCE ROW LEVEL SECURITY`; RED antes de implementar.
- [x] 2.2 Implementar la migración 001 completa con tablas, índices, RLS, políticas y `REVOKE UPDATE, DELETE ON auditoria`; verificar 2.1 y `alembic upgrade head` en PostgreSQL 15 de Compose.
- [x] 2.3 Alinear 003 (`tenant_id UUID` + FK a tenants) y su modelo; verificar `alembic upgrade head`, `downgrade base` y `upgrade head` otra vez.
- [x] 2.4 Verificar la protección real con rol de aplicación no-owner: insertar en T1 y T2, setear `app.tenant_id` y comprobar que T1 no ve ni escribe T2; registrar la evidencia.

## 3. Seed idempotente

- [x] 3.1 Escribir `tests/test_seed_c02.py` para primera ejecución, segunda ejecución y contenido mínimo (roles, estados, medios, parámetros, plantillas, catálogo demo); RED antes de implementar.
- [x] 3.2 Implementar `backend/app/seed.py` con tenant demo, upsert de parámetros y contrato JSON de catálogo; verificar 3.1.
- [x] 3.3 Verificar que el seed no crea usuarios con contraseñas reales ni duplica filas; documentar qué debe materializar C-04.

## 4. Compose, roles y documentación

- [x] 4.1 Actualizar `docker-compose.yml` y `db/init/` para separar `turnos_owner` (migraciones) de `turnos_app` (runtime); verificar `docker compose config` y arranque de db.
- [x] 4.2 Actualizar `.env.example` y `docs/foundation/bootstrap.md` con los dos roles, sin secretos productivos.
- [x] 4.3 Documentar C-02 en `README.md`/`CHANGES.md` y crear `docs/foundation/verification-c02.md` con las salidas reales.

## 5. Cierre

- [x] 5.1 Ejecutar `py -m pytest tests/ -q`, `ruff`, `mypy`, `openspec validate c-02-core-models-multitenant --strict` y la verificación de migración/RLS.
- [x] 5.2 Marcar este tasks, archivar `c-02-core-models-multitenant` y actualizar `CHANGES.md` a `[x]` con la ruta del archivo.

## Workflow follow-up

- Mantener 002 como placeholder de C-04; no duplicar el DDL de catálogos.
- No commitear ni pushear sin pedido explícito.
