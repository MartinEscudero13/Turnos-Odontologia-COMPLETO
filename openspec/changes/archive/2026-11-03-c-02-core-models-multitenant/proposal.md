# Proposal

## Why

C-01 dejó una base ejecutable, pero todavía no existe el núcleo de identidad y tenancy sobre el que se apoyan todos los changes de negocio. C-02 define tenants, usuarios, auditoría append-only, RLS y seed por tenant antes de construir agenda, reservas o caja.

## What Changes

- Se agregan modelos y migración 001 para `tenants`, `usuarios`, `auditoria` y parámetros de tenant.
- Se implementa aislamiento por `tenant_id` con Row-Level Security y una prueba de fuga cross-tenant.
- Se agrega seed idempotente por tenant con roles, estados, medios de pago, parámetros, plantillas y una configuración inicial de sillón/prestaciones que C-04 materializará.
- Se endurecen los bordes: email único por tenant, roles válidos, nadie opera sin `app.tenant_id` y auditoría sin UPDATE/DELETE.
- **Breaking change**: las migraciones 001 y 002 dejan de ser placeholders; 003 mantiene `turnos` y su dependencia pasa a ser real.

## Capabilities

### New Capabilities

- `tenant-core`: identidad, tenancy, usuarios, auditoría y configuración base por tenant.

### Modified Capabilities

- Ninguna capacidad de negocio existente cambia; C-05 sigue igual funcionalmente, pero su `tenant_id` se alinea al tipo UUID de `tenants.id`.

## Impact

- `backend/app/models/`, `backend/alembic/versions/001_core_multitenant.py`, `backend/alembic/versions/003_turnos_anti_solape.py`.
- Seed en `backend/app/seed.py` y pruebas de modelo/migración/RLS.
- `CHANGES.md` y documentación de C-02.
