$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $Root

Write-Host '== Turnos-Odontologia foundation verification =='
py -m pip install --quiet --upgrade pip
py -m pip install --quiet -r requirements-dev.txt
py -m pytest tests/ -q
py -m ruff check .
py -m mypy --config-file pyproject.toml
py -m alembic -c backend/alembic.ini heads
py -m alembic -c backend/alembic.ini upgrade head --sql | Out-Null
py tools/secret_scan.py

Push-Location frontend
try {
  npm ci --no-audit --no-fund
  npm run lint
  npm run typecheck
  npm test
  npm run build
} finally { Pop-Location }

docker compose -f docker-compose.yml config --quiet
Write-Host 'foundation verification: OK'
