# Tasks — C-01 `foundation-setup`

> Goal: deliver a verifiable MVP foundation for backend, SPA, DB migrations, compose and CI.
> Every task MUST be verified by test, lint, typecheck or reproducible command.
> Data must remain fictitious; never use real patient information.

## 1. Scenario contract

- [x] 1.1 Audit existing backend entrypoint and current route shape; produce evidence of intended route behavior by running `py -m pytest tests/test_api_turnos.py -q` and documenting expected health behavior.
- [x] 1.2 Map every foundation requirement from `specs/foundation-setup/spec.md` to a verification artifact (health test, settings test, compose validation, CI config and typechecks) before editing code.

## 2. Backend foundation and entrypoint

- [x] 2.1 Create `backend/app/core/settings.py` with `Settings` and strict env validation; verify startup fails clearly when `DATABASE_URL` is missing via `tests/test_settings_required.py`.
- [x] 2.2 Add `backend/app/middleware.py` and `backend/app/core/logging.py` with PHI-safe JSON logs + correlation ID and structured exception handling; verify with `tests/test_logging_and_correlation.py`.
- [x] 2.3 Add `backend/app/db.py` engine/session factory and `backend/app/app.py` app factory; enable `/api/health` JSON response; verify `tests/test_health.py` and `tests/test_app_docs.py`.
- [x] 2.4 Add shared error schemas and `backend/app/core/exceptions.py`; verify error payload contract with correlation ID and no PHI in `tests/test_errors_phi.py`.

## 3. Backend quality and migration baseline

- [x] 3.1 Add `pyproject.toml` with Python tooling config (`ruff`, `mypy`, `pytest`) and update `backend/requirements.txt` pins; pass `ruff check . && py -m mypy --config-file pyproject.toml backend`.
- [x] 3.2 Add `backend/alembic.ini` and `backend/alembic/env.py` adapted to SQLAlchemy 2.0 + `DATABASE_URL`; verify with `alembic current` and `alembic heads` under an empty disposable DB where docker is available.
- [x] 3.3 Add backend health/logging/errors/config tests in `tests/` and keep existing `104` tests unchanged; verify with `py -m pytest tests/ -q`.
- [x] 3.4 Add `docs/foundation/bootstrap.md` with exact setup, test, compose commands and failure troubleshooting; verify every command path from clean clone before merging.

## 4. Frontend foundation (React + Vite strict TypeScript)

- [x] 4.1 Scaffold `frontend` with React app, strict TypeScript, Vite, lint and test configs; verify `npm --version`, `node --version` and `npm ci` path in docs.
- [x] 4.2 Add `frontend/src/App.tsx`, `frontend/src/main.tsx`, and `frontend/src/App.test.tsx` for the foundation shell; verify `npm run lint && npm run test && npm run build`.
- [x] 4.3 Add frontend typed health client and smoke test asserting endpoint contract shape; verify by test fixture with mocked response.
- [x] 4.4 Define env example for frontend (`VITE_API_BASE_URL`) and clear README setup for install, dev, test and build; verify all commands exit 0 in clean install.

## 5. Infrastructure and compose wiring

- [x] 5.1 Create `.env.example` and `.dockerignore`; include required variables and placeholders only; verify command `grep -nE "JWT_SECRET|DATABASE_URL|REDIS_URL" .env.example` executes and no real values are detected by `tools/secret_scan.sh` if present.
- [x] 5.2 Create `docker-compose.yml` with services `api`, `web`, `db`, `redis`; healthchecks and dependency ordering; verify `docker compose config` exit code and rendered service list.
- [x] 5.3 Add Dockerfiles for backend and frontend; verify `docker build -f backend/Dockerfile -t turnos-api .` and equivalent web build if Docker daemon is available; otherwise run a documented syntax/config fallback and mark daemon-dependent checks separately.
- [x] 5.4 Add `scripts/verify-foundation.sh` (or PowerShell equivalent) that runs python tests, frontend checks, and compose config in one command and records one-line summary; verify by running it once.

## 6. CI workflow and stability gates

- [x] 6.1 Create `.github/workflows/quality.yml` with parallel jobs `backend` and `frontend`; verify workflow YAML syntax and matrix commands by static lint (`actionlint` or equivalent) if available, else parser-check script.
- [x] 6.2 Configure cache and job timeouts, keep all env secrets undefined in example mode only; verify `docker compose config` in workflow dependencies and no hardcoded secrets in repository.
- [x] 6.3 Add PR workflow execution evidence in docs and README; verify each command matches local command list and has no divergence drift.
- [x] 6.4 Validate change with quality checks, `openspec validate c-01-foundation-setup --strict`, and run full suite from repo root; accept no failing tests before archive.

## 7. Integration and release readiness

- [x] 7.1 End-to-end smoke check for `/api/health` + frontend `npm run dev` host/port documented; verify manual smoke flow with no hardcoded domain paths.
- [x] 7.2 Complete all tracked tasks (`- [x]`) and capture outcomes in `docs/foundation/verification-report.md`; verify `openspec status --change c-01-foundation-setup --json` marks change as complete.

## Workflow follow-up

- Do not archive until all checks are green and the workflow pass rate is 100%.
- Archive with `openspec archive c-01-foundation-setup --yes` only after verification is complete and reviewed by the owner.
- Keep implementation limited to foundation scope; C-02+ must not be hidden inside this change.
