# Bootstrap y verificación de la fundación

Este documento define cómo preparar, levantar y verificar el estado actual del
repositorio desde un clone limpio. Contiene comandos que deben fallar o pasar por
motivos explícitos; ninguno depende de credenciales ocultas ni datos reales de pacientes.

## Requisitos

- Python 3.12 o superior (verificado con Python 3.14).
- Node.js 20 o superior y npm.
- Docker Desktop o Docker Engine compatible con Compose v2+.
- Puerto libre: `5173` (web), `8000` (API), `5432` (PostgreSQL), `6379` (Redis).

## 1. Clonado e instalación

```bash
git clone <url>
cd Turnos-Odontologia
py -m pip install -r requirements-dev.txt
cd frontend && npm ci && cd ..
cp .env.example .env
```

En Windows, PowerShell acepta las mismas rutas. `.env` tiene solo credenciales
de desarrollo y nunca debe ser commiteado.

## 2. Verificación local de Python

```bash
py -m pytest tests/ -q
py -m ruff check .
py -m mypy --config-file pyproject.toml
```

Resultados esperados:

- `tests/`: todos verdes, incluidos los 104 tests históricos de C-05.
- `ruff check .`: `All checks passed!`.
- `mypy`: `Success: no issues found`.

## 3. Base de datos y Alembic

Generar SQL desde cero:

```bash
py -m alembic -c backend/alembic.ini heads
py -m alembic -c backend/alembic.ini upgrade head --sql
```

Con Docker disponible, crear una base efímera y aplicar/eliminar el esquema:

```bash
docker compose up -d db
DATABASE_URL=postgresql+psycopg://turnos:dev-only-db-password@localhost:5433/turnos \
  py -m alembic -c backend/alembic.ini upgrade head
DATABASE_URL=postgresql+psycopg://turnos:dev-only-db-password@localhost:5433/turnos \
  py -m alembic -c backend/alembic.ini downgrade base
```

Debe mostrar `003_turnos_anti_solape` como head. Las migraciones 001/002 son
orquestadoras mínimas de la base y se completan en C-02/C-04.

## 4. Frontend

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

Salida esperada: lint y typecheck sin errores, 2 tests aprobados, build en
`frontend/dist/`.

## 5. Docker Compose

```bash
docker compose config --quiet
docker compose build
docker compose up -d
curl --fail http://localhost:8000/api/health
docker compose ps
docker compose down -v
```

`docker compose config --quiet` debe terminar con código `0`. El API responde:

```json
{"status":"UP","service":"turnos-api","version":"0.1.0"}
```

`.env` o environment de compose no imprimen secretos en logs; `tools/secret_scan.py`
falla el build si detecta patrones de secreto o claves demasiado laxas.

## 6. Escaneo de secretos e higiene de repo

```bash
py tools/secret_scan.py
git diff --check
git status --short
```

La salida esperada es `secret scan: OK`. `git diff --check` no debe producir
cambios. Las credenciales de `.env` son de desarrollo y no son producción.

## Solución de problemas

| Síntoma | Causa | Verificación/solución |
|---|---|---|
| `ModuleNotFoundError: app` | Correr Alembic desde directorio incorrecto | Usar la ruta `-c backend/alembic.ini` y el comando desde la raíz |
| `docker compose config` falla | `.env` ausente/incorrecta o compose inválido | `cp .env.example .env`; o revisar `docker compose config` sin `--quiet` |
| Health 500 | `DATABASE_URL` inválida o DB no levantada | Revisar `docker compose logs api db` y healthchecks |
| Alembic no encuentra head | Migraciones 001/002 aún vacías | Verificar los archivos `backend/alembic/versions/001_*` y `002_*` |
| `401` en la health API | No aplica: `/api/health` es público | Si se ve 401, el router/proxy está apuntando al backend equivocado |

## Veriable de entorno opcionales para este change

`MP_*`, `WA_*` y `GCAL_*` están reservadas para sus integraciones futuras y no
son usadas por C-01. Nunca poner tokens/API keys reales en `.env.example`, CI
ni documentación.
