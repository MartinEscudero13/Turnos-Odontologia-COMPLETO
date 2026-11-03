# Verification report — C-04 `catalogos-pacientes-base`

**Fecha**: 2026-11-03 · **Entorno**: PostgreSQL 15 en Docker + SQLite para API tests
**Base de integración**: `postgresql+psycopg://turnos:test-password@localhost:5435/turnos`
**Cambio archivado**: `openspec/changes/archive/2026-11-03-c-04-catalogos-pacientes-base/`

## Resultado

| Gate | Comando | Resultado |
|---|---|---|
| Suite completa | `py -m pytest tests/ -q` | **159 tests**, exit 0 (3 RLS requieren `C02_DATABASE_URL`) |
| RLS catálogo | `pytest tests/test_rls_c04.py` con PostgreSQL | **1 passed** |
| API catálogos/pacientes | `pytest tests/test_catalogos_api.py` | **3 passed** |
| Modelos/migración | `pytest tests/test_modelos_c04.py` | **2 passed** |
| Seed catálogo | `pytest tests/test_seed_catalogo.py` | **1 passed** |
| Lint | `py -m ruff check .` | `All checks passed!` |
| Type check | `py -m mypy --config-file pyproject.toml` | Success, 40 archivos |
| Migración 002 | `alembic upgrade head`, `downgrade base`, `upgrade head` | exit 0 |
| OpenSpec | `openspec validate c-04-catalogos-pacientes-base --strict` | `is valid` |

## Cobertura

- `sillones`, `prestaciones`, `profesionales`, `profesional_prestacion`, `horarios_semanales`, `bloqueos` y `pacientes`.
- `tenant_id` NOT NULL, FK a `tenants`, índices y RLS forzada en todas.
- Admin escribe catálogos; Recepción/Odontólogo leen; Recepción crea pacientes.
- `duracion_min > 0`, `precio_base >= 0`, unicidad de sillón/prestación por tenant.
- Teléfono E.164 validado y `UNIQUE(tenant_id, telefono)`; mismo teléfono devuelve el paciente existente.
- `seed_catalogo` crea `Sillón 1` + `Consulta` + `Limpieza` una vez.
- RLS real: T1 ve sólo su catálogo; insertar T2 desde T1 falla.

## Desvíos y deuda

- La duración inicial de las prestaciones es **30 min provisional** hasta que el dueño defina el catálogo (PO-01 / preguntas abiertas).
- Los endpoints de horarios y bloqueos no se exponen todavía; los modelos y constraints están listos para C-05/C-06.
- C-05 conserva IDs escalares para profesional/sillón/paciente; los FKs de esas referencias quedan para una evolución expand-contract.
- Migración 002 ya no es placeholder; 003 (C-05) y 004 (C-03) siguen en orden.

