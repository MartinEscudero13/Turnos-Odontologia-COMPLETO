# Verification report — C-01 `foundation-setup`

**Date**: 2026-11-03 · **Environment**: Windows, Python 3.14.0, Node 24.16.0, Docker Server 29.5.3 · **Repository**: Turnos-Odontologia

## Result summary

| Gate | Command | Result |
|---|---|---|
| Backend tests | `py -m pytest tests/ -q` | exit 0 · **114 tests collected/pass** |
| Backend lint | `py -m ruff check .` | `All checks passed!` |
| Backend type check | `py -m mypy --config-file pyproject.toml` | `Success: no issues found in 22 source files` |
| Secret scan | `py tools/secret_scan.py` | `secret scan: OK` |
| Frontend install | `npm ci` in `frontend/` | exit 0 |
| Frontend lint | `npm run lint` | exit 0 |
| Frontend type check | `npm run typecheck` | exit 0 |
| Frontend test | `npm test` | 1 file, **2 tests passed** |
| Frontend build | `npm run build` | Vite 6.0.5, `dist/` produced |
| Compose validation | `docker compose -f docker-compose.yml config --quiet` | exit 0 |
| Docker build | `docker compose -f docker-compose.yml build` | images `turnos-odontologia-api` and `web` built |
| Compose smoke | `docker compose up -d` + `curl --fail http://localhost:8000/api/health` | `{"status":"UP","service":"turnos-api","version":"0.1.0"}` |
| Local web smoke | `Invoke-WebRequest http://localhost:5173/` | `200` |
| Alembic offline SQL | `py -m alembic -c backend/alembic.ini upgrade head --sql` | generates 001 → 002 → 003 transaction |
| Alembic with ephemeral DB | add `DATABASE_URL=postgresql+psycopg://turnos:dev-only-db-password@localhost:5433/turnos` | `upgrade head`, `downgrade base`, and `upgrade head` all exit 0; `alembic current` → `003_turnos_anti_solape (head)` |
| OpenSpec | `openspec validate c-01-foundation-setup --strict` | `Change 'c-01-foundation-setup' is valid`; archived as `2026-11-03-c-01-foundation-setup` |

## Notes and evidence

- Port `5432` already had a local PostgreSQL instance. Compose binds the container to
  `5433`; this is the value in `.env.example` and the documented local URL.
- Docker daemon was available and the real Compose stack was started; API health returned
  `UP`, web answered HTTP 200; the stack was shut down with `docker compose down`.
- Alembic migrations 001 and 002 are **order placeholders** only; their business schema is
  implemented in C-02/C-04. This avoids hiding tenant/auth debt in C-01.
- The inherited C-05 implementation already carried a pending structural dependency from
  `003` to the missing `002_catalogos_pacientes` revision. C-01 closes this execution
  blocker by introducing 001/002 placeholders; no C-05 domain logic was changed.
- `.env.example` contains **development placeholders only**; no production secrets. The
  secret scanner does not accept a generic lax `_SECRET` value.
- Technical debt: direct DB verification of RLS and full cross-tenant leakage tests lands
  with C-02, because C-02 owns tenants, users and audit infrastructure.

## Artifacts produced

- Archived change: `openspec/changes/archive/2026-11-03-c-01-foundation-setup/`
- Main spec: `openspec/specs/foundation-setup/spec.md`
- Main runtime: `backend/app/`, `frontend/`, `docker-compose.yml`, CI under `.github/workflows/`

