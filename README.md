# Turnos-Odontologia

SaaS multi-tenant argentino de agenda odontológica: turnos con anti-solape real, reserva online, WhatsApp, Mercado Pago y obras sociales.

- Descubrimiento del problema y alcance: [`docs/discovery/`](docs/discovery/) (informe + checklist).
- Fuente de verdad del dominio (actores, datos, reglas RN-XX, historias US-XXX, arquitectura): [`knowledge-base/`](knowledge-base/README.md).
- Plan de implementación por changes: [`CHANGES.md`](CHANGES.md). Reglas para agentes: [`AGENTS.md`](AGENTS.md).

## Prerrequisitos

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Python | 3.12+ | Se usa el launcher `py` (verificado con Python **3.14.0**; `python` apunta al Store y no se usa). |
| PostgreSQL | 15+ | Solo necesario desde la persistencia real (revisión Alembic 003). El ciclo C-05 corre sin Postgres (ver Estado). |

Verificá tu entorno:

```bash
py --version
```

Sin installs para C-05: el entorno ya trae pytest 9.1.1, FastAPI 0.115.0, SQLAlchemy 2.0.35, Pydantic 2.13.4, Alembic 1.19.1 y httpx 0.28.1 (ver `backend/requirements.txt`). `redis` no se necesita en este change (sin workers; eso es C-07/C-13).

## Instalación

```bash
git clone <url-del-repo>
cd Turnos-Odontologia
py -m pip install -r backend/requirements.txt
```

## Tests

```bash
py -m pytest tests/ -q
```

Salida esperada (verificada): **15 archivos, 104 tests, todos en verde** (`104 passed`).

## Type hints

Todo el código Python lleva type hints obligatorios (regla dura de `AGENTS.md`); el chequeo automático (mypy/pyright) queda anotado para C-01, que monta el CI.

## Estructura del repo

| Directorio / archivo | Qué es |
|----------------------|--------|
| `backend/app/turnos/` | Dominio C-05: `overlap()`, cálculo de `fin`, 3 alternativas ante 409, máquina de estados, servicio + auditoría |
| `backend/app/schemas/` | Schemas Pydantic v2 del borde API (strict donde el contrato lo exige) |
| `backend/app/models/` | Modelos SQLAlchemy (`tenant_id` everywhere, `timestamptz`, CHECKs) |
| `backend/app/routers/` | Router FastAPI `/api/turnos` + `crear_app()` inyectable (actor por headers provisorio; JWT real en C-03) |
| `backend/alembic/versions/` | Revisión 003: tabla `turnos` + EXCLUDE anti-solape + índices + RLS |
| `backend/seed_test.py` | Seed ficticio idempotente (`aplicar_seed()` + `seed_sql()` para PG real) |
| `backend/requirements.txt` | Pines verificados en el entorno |
| `tests/` | 15 archivos pytest del ciclo C-05 (solape, fin, alternativas, estados, servicio CRUD, sobreturno, cancelar/reprogramar, 409, API, modelos, migración, seed, regresión, concurrencia, auditoría) |
| `openspec/specs/turnos-anti-solape/` | Spec vigente de C-05 (requisitos y escenarios aprobados) |
| `openspec/changes/archive/2026-10-01-c-05-turnos-anti-solape/` | Change C-05 archivado: `proposal.md` (+addendum Python), `design.md` (Python), `tasks.md` (re-corrida), `reimplementacion-python.md`, delta de specs, `explore-notes.md` |
| `docs/discovery/` | Informe y checklist de Discovery |
| `knowledge-base/` | Dominio: visión, stack, actores/RBAC, modelo de datos, reglas de negocio, funcionalidades, flujos, arquitectura, decisiones, preguntas abiertas, integraciones |
| `CHANGES.md` | Índice canónico de los 15 changes y su estado |

## Estado del ciclo C-05 (`turnos-anti-solape`)

- **Estado: archivado** el 2026-10-01 y **reimplementado en Python** el 2026-10-02 (spec intacto). En `CHANGES.md` figura `[x]` completado con nota de reimplementación.
- **Spec aprobado**: [`openspec/specs/turnos-anti-solape/spec.md`](openspec/specs/turnos-anti-solape/spec.md) — 6 requisitos (anti-solape por profesional/sillón con 409 + 3 alternativas, adyacencia exacta, cancelados/reprogramados que liberan hueco, sobreturno explícito auditado, cancelar/reprogramar con anticipación).
- **Tests**: [`tests/`](tests/) — 104/104 en verde con `py -m pytest tests/ -q`.
- **Desvíos documentados del ciclo**: sin PostgreSQL en el entorno (revisión 003 verificada por tests estructurales, no contra DB viva); tasks 4.1–4.3 green-first de aceptación (RED por módulo observado en 1.x–3.x, y 4.1 aportó un fallo real que se corrigió); sin chequeo automático de hints (para el CI de C-01). Detalle en `reimplementacion-python.md` del archive.
- **Siguiente**: `C-06 reserva-online-publica` (depende de C-05 archivado).

## Datos y secretos

- **Datos ficticios**: seed (`backend/seed_test.py`) y tests usan datos inventados (1 tenant demo, profesional/sillón/prestación de prueba). NUNCA usar datos reales de pacientes en desarrollo, tests ni demos; nada de PHI en logs.
- **Secretos**: nada commiteado. No hay `.env` ni `.env.example` en el repo; `.gitignore` excluye `.env`, `.env.local`, `__pycache__/` y `.pytest_cache/`. Las variables reales (`DATABASE_URL`, `JWT_SECRET`, `MP_*`, `WA_*`, etc.) se documentarán en el change que las necesite (C-01/C-10/C-11/C-13 según `CHANGES.md`).
