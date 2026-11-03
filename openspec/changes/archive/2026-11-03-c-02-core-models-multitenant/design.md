# Design

## Context

C-01 provides the app factory, PostgreSQL migrations, Compose and tests. C-05 contains a `turnos` table with `tenant_id` as text and an audit model that was only a placeholder. C-02 is the first schema change that must make tenancy real. See `proposal.md` for the motivation.

## Goals / Non-Goals

**Goals:**

- UUID tenant identity and a real `tenants` table.
- Tenant-scoped users with a unique `(tenant_id, email)` constraint.
- Append-only audit with an explicit application role and RLS.
- Idempotent seed that gives C-04 a stable catalog/config contract.
- A real migration 001 that can be applied/rolled back in a disposable PostgreSQL.

**Non-Goals:**

- Login/JWT/RBAC enforcement (C-03).
- CRUD endpoints for tenants/users (C-03 adds auth and admin routes).
- Professional/sillón/prestación CRUD (C-04); C-02 seeds a JSON contract for those values.
- Password hashing policy; C-03 owns hashing and token issuance.

## Decisions

**D1 — Tenant IDs are UUID; `turnos.tenant_id` is migrated to UUID.**

- Keep `tenants.id UUID` as the KB specifies and make C-05 `turnos.tenant_id` UUID with a real FK. This avoids a permanent text/uuid mismatch.
- Alternative: keep tenant ids as text for compatibility with C-05 tests → rejected; it would violate the KB and push the correction into every future change.
- The in-memory C-05 service keeps `tenant_id: str`; tests use UUID-formatted strings, so domain behavior does not change.

**D2 — RLS with forced policies and a non-owner application role.**

- The migration enables and forces RLS on `usuarios`, `auditoria` and `tenant_parametros`.
- `app.tenant_id` is set per connection/transaction; policies cast to UUID.
- The Compose database uses a migration owner (`turnos_owner`) and an application login (`turnos_app`); the API uses the application role. This is essential because PostgreSQL table owners bypass RLS unless forced and superusers always bypass it.
- Alternative: use the same owner for app and migrations → rejected (RLS would be decorative).

**D3 — Audit model is generic, not turno-specific.**

- Columns: `id`, `tenant_id`, `actor_id`, `accion`, `entidad`, `entidad_id`, `antes`/`despues` JSONB, `motivo`, `registrado_en`.
- The C-05 in-memory audit type remains untouched; its SQL model is adapted to this generic schema.
- `UPDATE`/`DELETE` are revoked from the application role; append-only is enforced by privileges and a trigger is optional (not required if the role lacks privileges).

**D4 — Seed writes a stable config contract plus demo tenant.**

- `seed_tenant` inserts/upserts `tenant_parametros` rows containing roles, turn states, payment methods, WhatsApp templates, the demo sillón and base prestaciones.
- It also creates a demo tenant if missing, but never creates users with real passwords.
- `ON CONFLICT DO NOTHING` (or upsert of non-secret defaults) makes the seed idempotent; C-04 materializes sillón/prestaciones from these keys.

**D5 — Migration 003 is aligned, not duplicated.**

- Migration 001 creates the core; 002 remains an empty C-04 placeholder; 003 changes `turnos.tenant_id` from text to UUID and adds the FK to `tenants`.
- The C-05 model gets the same UUID mapping. Existing C-05 tests remain behaviorally intact.

## Risks / Trade-offs

- **Breaking type change** from text to UUID → migration downgrade must restore the original text type; tests verify upgrade/downgrade on a disposable DB. No production data exists yet.
- **RLS can be accidentally bypassed** if the API uses the owner account → Compose and CI use a separate `turnos_app` login; a live test checks that RLS blocks cross-tenant rows.
- **Seed catalog is JSON not tables** → documented as a contract for C-04; avoids duplicating C-04 schema in C-02.
- **Migrations 001/002 placeholders** → 002 stays empty by design; C-04 fills it. This is explicit in the change and README.

## Migration plan

1. Create models and the 001 migration.
2. Add the application role/grants to Compose initialization.
3. Align 003 and C-05 model tenant types.
4. Implement the idempotent seed and tests.
5. Apply 001→003 and downgrade/upgrade on a disposable PostgreSQL.
6. Archive after all tests pass.

## Open Questions

- None blocking implementation. Exact catalog prices and seña values remain open (PO-01/IN-02) and are stored as parameter names/placeholders, never invented numbers.
