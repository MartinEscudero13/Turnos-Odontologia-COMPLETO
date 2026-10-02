# Reimplementación Python — C-05 `turnos-anti-solape` (2026-10-02)

## Fecha y motivo

2026-10-02. La corrida TS (2026-10-01, 79 tests, archivada) se implementó en un
stack ajeno al proyecto. El dueño exige el stack obligatorio
(**Python + FastAPI + SQLAlchemy + PostgreSQL + Redis + JWT**, `AGENTS.md`),
así que el change se reimplementó entero en Python. El spec NO cambió:
`openspec/specs/turnos-anti-solape/spec.md` (6 requisitos, 12 escenarios)
sigue intacto, y el spec del archive tampoco se tocó.

## Qué se reutilizó del spec y del diseño TS

- Los 6 requisitos y 12 escenarios, 1:1 (regresión `test_regresion_agenda.py`).
- Las decisiones D1–D7: EXCLUDE parciales, RLS, timestamptz + fin calculado,
  índices, sobreturno auditado, transiciones con anticipación, standalone sin
  PG + contrato 409+3.
- El seed ficticio (mismos IDs demo) y la anticipación default de 24 h.
- La historia git conserva todo el proceso TS (eliminado con `git rm`, sin
  reescribir historia).

## Qué cambió (código solamente)

| Antes (TS) | Ahora (Python) |
|---|---|
| `src/turnos/*.ts` (7 archivos) | `backend/app/turnos/*.py` (overlap, fin, estados, alternativas, servicio) |
| `zod` en borde | Pydantic v2 (`backend/app/schemas/turno.py`; strict donde el contrato era strict) |
| `Resultado<T>` (unión ok/err) | Excepciones de dominio con `codigo` HTTP (`TurnoError`, `ConflictoSolape` con alternativas) mapeadas por el router |
| Prisma `schema.prisma` + `migration.sql` | SQLAlchemy (`backend/app/models/turno.py`) + revisión Alembic 003 (`backend/alembic/versions/`) |
| `prisma/seed-test.ts` | `backend/seed_test.py` (`aplicar_seed()` + `seed_sql()` para PG real) |
| 13 suites vitest, 79 tests | 15 archivos pytest, **104 tests** (`py -m pytest tests/ -q`) |
| `package.json` / `tsconfig.json` / `node_modules/` | `backend/requirements.txt` (pines verificados) / sin build-step |
| `npx tsc --noEmit` (tipado) | Type hints obligatorios en todo el código (regla dura; sin mypy en el entorno — desvío) |

## Decisiones nuevas

- **Sin installs**: el entorno ya traía pytest 9.1.1, FastAPI 0.115.0, SQLAlchemy
  2.0.35, Pydantic 2.13.4, Alembic 1.19.1, httpx 0.28.1 (`py` launcher, Python
  3.14.0; `python` apunta al Store y no se usa). No se instaló `redis`: C-05 no
  tiene workers/colas (eso es C-07/C-13).
- **Actor por headers** (`X-Tenant-Id`/`X-User-Id`/`X-Rol`) como sostén provisorio
  del router; el JWT real llega en C-03 sin cambiar el contrato.
- **Pydantic serializa UTC con `Z`** (no `+00:00`); ambas son ISO-8601 válida.
- **`Mapped[X | None]` evitado** en modelos (incompat SQLAlchemy 2.0.35 ×
  Python 3.14): `Mapped[str]` + `nullable=True` explícito.
- **App mínima como adelanto parcial de C-01** (`crear_app()` + requirements):
  no es la entrega de C-01 (falta compose, JWT, settings, frontend).

## Desvíos (lo no verificado de verdad)

1. Sin PostgreSQL vivo: la revisión 003 se verifica estructuralmente (contenido
   DDL) + paridad del predicado en el servicio — igual que la corrida TS, sin fingir DB.
2. Sin `mypy`/`tsc` equivalente corrido: los hints son manuales y estrictos, pero sin
   chequeo automático (anotar en C-01: sumar mypy/pyright al CI).
3. Tasks 4.1–4.3 green-first de aceptación (RED por módulo sí observado en 1.x–3.x);
   4.1 igual aportó un fallo real (auditoría de crear-con-flag) que se corrigió.
4. `openspec` CLI no disponible en este entorno: sin `validate --strict` (revisión
   manual del spec en su lugar).
