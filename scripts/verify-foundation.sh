#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

printf '== Turnos-Odontologia foundation verification ==\n'
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements-dev.txt
python -m pytest tests/ -q
python -m ruff check .
python -m mypy --config-file pyproject.toml
python -m alembic -c backend/alembic.ini heads
python -m alembic -c backend/alembic.ini upgrade head --sql > /dev/null
python tools/secret_scan.py

(cd frontend
  npm ci --no-audit --no-fund
  npm run lint
  npm run typecheck
  npm test
  npm run build)

docker compose -f docker-compose.yml config --quiet

printf 'foundation verification: OK\n'
