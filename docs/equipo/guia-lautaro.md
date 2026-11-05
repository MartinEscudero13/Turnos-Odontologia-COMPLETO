# Guía de continuación — Lautaro Naranjo

> **La entrada canónica para la IA es [`CONTINUAR.md`](../../CONTINUAR.md).**
> Esta página sólo conserva el contexto extendido de entorno y verificación.

## Estado

- C-01 a C-04, C-05 y F-01: terminados y archivados.
- TP2 skill + MCP: terminado y pusheado.
- **C-06 `reserva-online-publica`: activo, 0/50 tareas, desbloqueado.**
- Video: no hace falta ahora.

## Para empezar

1. Abrí OpenCode en el repo actualizado.
2. Pegá el prompt de [`CONTINUAR.md`](../../CONTINUAR.md).
3. Esperá el resumen del agente antes de que modifique archivos.

Si el clone está viejo:

```bash
git fetch origin
git reset --hard origin/master
```

La identidad de Git sólo se configura antes de commitear:

```bash
git config --local user.name "Lautaro Naranjo"
git config --local user.email "228012306+lauty-naranjo@users.noreply.github.com"
```

## Verificación

Con PostgreSQL de Compose:

```bash
docker compose up -d db
DATABASE_OWNER_URL=postgresql+psycopg://turnos_owner:dev-only-owner-password@localhost:5433/turnos \
  py -m alembic -c backend/alembic.ini upgrade head
C02_DATABASE_URL=postgresql+psycopg://turnos_owner:dev-only-owner-password@localhost:5433/turnos \
  py -m pytest tests/ -q
```

Sin base:

```bash
py -m pytest tests/ -q          # 4 RLS skipped
py -m ruff check .
py -m mypy --config-file pyproject.toml
openspec validate --all --strict
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## C-06

```bash
openspec status --change c-06-reserva-online-publica --json
openspec instructions apply --change c-06-reserva-online-publica --json
```

Antes de implementar: cargar `revisor-escenarios-turnos` y auditar la spec.
Para la UI: cargar `visual-turnos` y leer `PRODUCT.md`/`DESIGN.md`.
No tocar C-01 a C-04 ni F-01 sin hablarlo con Martin.
