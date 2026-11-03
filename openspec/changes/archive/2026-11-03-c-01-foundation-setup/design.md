# Design

## Context

The repository already carries domain logic (C-05) but lacks the reproducible base stack required by DD-01. See `proposal.md` for why. This design aligns the implementation with DD-01, RN-AU boundaries, and the CI/verification requirements in the spec.

## Goals / Non-Goals

**Goals:**

- Bootstrap backend (`FastAPI`, `SQLAlchemy`, `Alembic`), frontend (`React` + strict `TypeScript` + `Vite`), and Docker/Compose plumbing.
- Create `backend/app/core` shared primitives: settings, logger without PHI, DB session factory, request-scoped exceptions, shared schemas.
- Provide one gateable command set for local and CI: backend test/lint/typecheck, frontend lint/test/build, compose config verification.
- Keep behavior covered by spec requirements before any code is added.

**Non-Goals:**

- No business features from C-02+ (tenants, users, patients, business CRUD).
- No production deployment automation beyond Compose and CI.
- No authentication/RBAC implementation (C-03), no full domain seed (C-02), no DB migrations of C-02 models.

## Decisions

**D1 — Build one Python service bootstrapping from `backend/app/`**
- Keep one API service with explicit composition (`create_app()`), because later changes add routers/domain logic incrementally.
- Alternative: monolithic `main.py` only → rejected (hard to test and to extend).
- Impact: `GET /api/health` is independently testable, app factory supports injectable settings.

**D2 — Python strict by configuration, not by codebase-wide rewrite**
- Add `pyproject.toml` with `ruff` and `mypy` configs plus `python_requires: >=3.12`.
- Existing C-05 code must remain unchanged functionally; new files must pass strict checks.
- Alternative: enforce without config → rejected (tests/CI would be dependent on global machine settings).

**D3 — Settings fail-fast with explicit value validation**
- `backend/app/core/settings.py` validates required env vars and validates placeholder-like secrets when `ENVIRONMENT=production`.
- Alternative: lazy defaulting/load fallback → rejected (silent prod misconfiguration is unsafe).

**D4 — Logging and error path are safe by construction**
- Use `structlog`-style JSON logging without PHI and central exception handlers.
- Correlation IDs are generated in middleware; they are returned to clients and written to logs.
- Alternative: default `FastAPI` tracebacks in responses → rejected (leak risk).

**D5 — Frontend is a thin shell with typed contract, not business UI**
- Create Vite + React + TS scaffold with `npm run lint`, `npm run test`, `npm run build` working on CI.
- Use strict config and deny explicit `any` margin.
- Alternative: skip tests for static shell → rejected (no verification before delivery; spec explicitly requires reproducible checks).

**D6 — Compose defines service contracts, not deployment opinions**
- `docker-compose.yml` with services `api`, `web`, `db`, `redis`, and healthchecks/ordering.
- `web` talks to `api` through `VITE_API_BASE_URL` / static config in frontend.
- Alternative: keep compose stub-only → rejected (spec requires validating service graph; can be automated by `docker compose config`).

**D7 — CI runs backend and frontend jobs in parallel**
- Two workflows or one workflow with independent jobs; use existing cache mechanisms and exact commands.
- Alternative: single job serial pipeline → rejected (worse signal and slower iteration).

**D8 — Migration baseline remains empty until C-02**
- Alembic env points to `DATABASE_URL` and existing `003` remains unchanged (already tagged C-05 migration).
- No fake migration 001 in C-01; C-02 creates 001 and this change only validates chain execution.
- Alternative: create singleton placeholder migration → rejected (would create fake source of truth).

## Risks / Trade-offs

- `docker compose up` not run in CI where no daemon is available → mitigation: use `docker compose config` + Dockerfile build validation; on local verify full stack and document the actual result.
- `ruff/mypy` on preexisting C-05 modules may fail if too strict → mitigation: configure target packages and exclude preexisting noisy defaults if needed, but do not hide new files.
- Frontend adds toolchain complexity in existing Python repo → mitigation: ensure scripts are pinned and README lists exact commands.
- Compose in Windows may hit local file permission/naming issues → mitigation: explicit Linux container tests, then verify with macOS/Linux CI runner.

## Validation strategy

- Tests in `tests/` (Python): settings, health, exception handling, logging shape.
- Tests in `frontend` (Vite/vitest): render/smoke and build path.
- Structural validation scripts for compose and CI; run `docker compose config`; optionally `docker build` if daemon available.
- `openspec validate c-01-foundation-setup --strict`.

## Open Questions

- None blocking implementation; feasibility of running Docker daemon in this machine is orthogonal to code correctness.

## Migration plan

1. Create scaffolding and configs.
2. Apply backend app factory + health endpoint.
3. Add CI and validate with existing tests.
4. Run strict openspec validation.
5. Roll back: revert C-01 scaffold files (they are isolated); no data model exists yet.
