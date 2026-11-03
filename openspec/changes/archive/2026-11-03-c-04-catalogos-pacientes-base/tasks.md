# Tasks — C-04 `catalogos-pacientes-base`

> TDD rojo-primero en constraints, RBAC, RLS y E.164.

## 1. Modelos y migración

- [x] 1.1 Crear modelos `Sillon`, `Prestacion`, `Profesional`, `ProfesionalPrestacion`, `HorarioSemanal`, `Bloqueo`, `Paciente`; verificar con `tests/test_modelos_c04.py`.
- [x] 1.2 Implementar migración 002 con tablas, FKs, índices, RLS y grants; verificar upgrade/downgrade en PostgreSQL de Compose.
- [x] 1.3 Verificar constraints de duración/precio, unicidad de sillón/prestación/teléfono y CHECK de bloqueo/horario.

## 2. API y RBAC

- [x] 2.1 Agregar schemas Pydantic y router de catálogos/pacientes; verificar `tests/test_catalogos_api.py` para Admin/Recepción y validaciones.
- [x] 2.2 Implementar normalización E.164 y vinculación por teléfono sin duplicar; verificar el test de mismo teléfono.
- [x] 2.3 Integrar el router en `create_app` sin romper auth/health/C-05 y correr la suite completa.

## 3. Seed y documentación

- [x] 3.1 Implementar `seed_catalogo` idempotente y verificar con `tests/test_seed_catalogo.py`.
- [x] 3.2 Crear `docs/foundation/verification-c04.md` con suite, migración, RLS y salidas reales.
- [x] 3.3 Actualizar `README.md`/`CHANGES.md` con el estado del change.

## 4. Verificación y cierre

- [x] 4.1 Ejecutar `py -m pytest tests/ -q`, `ruff`, `mypy`, `openspec validate c-04-catalogos-pacientes-base --strict`.
- [x] 4.2 Archivar el change y verificar `openspec validate --all --strict`.

## Workflow follow-up

- No commitear ni pushear sin pedido explícito.
- C-05/C-06 pueden consumir estos modelos sin redefinirlos.
