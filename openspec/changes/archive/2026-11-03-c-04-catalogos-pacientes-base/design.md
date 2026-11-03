# Design

## Context

C-02 provides tenants, RLS and the application role; C-03 provides authenticated `CurrentUser`. C-04 adds the first business catalog so C-05/C-06 can reference real resources. See `proposal.md`.

## Goals / Non-Goals

**Goals:** tenant-scoped catalog schema, CRUD API, patient phone linking, seed materialization, RLS and migration 002.

**Non-Goals:** clinical records, odontogram, insurance coverage, agenda availability engine (C-05), UI.

## Decisions

**D1 — UUID entities and explicit tenant_id.**
All catalog tables use `Uuid` and FK to `tenants`; queries filter both `tenant_id` and RLS. Unit tests use SQLite, production uses PostgreSQL RLS.

**D2 — Catalog ownership follows the RBAC matrix.**
Admin writes; Recepción/Odontólogo only read; patients are created by Admin/Recepción. The route dependency is `require_roles` from C-03, not headers.

**D3 — Patients deduplicate by normalized phone per tenant.**
E.164 is validated by Pydantic and a DB CHECK; `UNIQUE(tenant_id, telefono)` prevents races. POST returns the existing row when the phone already exists. DNI remains optional/encrypted and `consentimiento_ok` defaults false.

**D4 — Horarios and bloqueos are modeled now, API later.**
`HorarioSemanal` belongs to a professional; `Bloqueo` can target professional or chair and requires a reason/range. They are used by C-05/C-06; C-04 only defines/model-tests them.

**D5 — Migration 002 fills the placeholder after 001.**
C-05's 003 remains after the catalog, so future FKs can be added without renumbering. `003` remains scalar IDs; referential wiring can be expanded later.

**D6 — Seed is idempotent and provisional.**
`seed_catalogo` creates `Sillón 1` and the two base prestaciones with a **provisional** 30-minute duration because the catalog duration is an open product question. It never invents prices (0) or patient data.

## Risks / Trade-offs

- 30-minute provisional duration must be replaced with the owner's catalog; documented in verification.
- C-05 migration keeps scalar IDs for professional/chair/patient, so DB FKs for those are deferred; C-04 owns the referenced tables now, enabling a later expand-contract.
- SQLite API tests do not exercise PostgreSQL RLS; migration/RLS are tested separately on PostgreSQL.

## Migration plan

1. Implement models and migration 002.
2. Add schemas/router and integrate app.
3. Add seed and tests.
4. Apply upgrade/downgrade on disposable PostgreSQL.
5. Archive after full suite.
