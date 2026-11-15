# Verification — `demo-api-clinica`

**Fecha**: 2026-11-15 · **Alcance**: C-08 y C-09 montados en la API real

## Resultado

| Gate | Resultado |
|---|---|
| Tests nuevos del tramo | **7 passed** (`tests/test_demo_api_clinica.py`) |
| Suite completa | exit 0 |
| `ruff` | `All checks passed!` |
| `mypy` | 102 archivos, 0 errores |
| OpenSpec | `demo-api-clinica` válido (`--strict`) |

## Rutas verificadas por HTTP

- `POST /api/pacientes/{id}/ficha` → `409` sin consentimiento y `201` después de firmarlo
- `GET /api/pacientes/{id}/ficha` → `200`
- `POST /api/consentimientos` → `201`
- `POST /api/evoluciones` → `201` · `GET /api/evoluciones?paciente_id=` → `200`
- `POST /api/odontograma` → `201` con `pieza_fdi = 36`
- `GET /api/odontograma?paciente_id=` → `200`
- `POST /api/odontograma` con FDI `99` → `422` sin persistir
- `POST /api/presupuestos` → `201` (`BORRADOR`)
- `POST /api/presupuestos/{id}/lineas` → `201` al precio base (`10000` centavos)
- `POST /api/presupuestos/{id}/emitir` → `200` (`VIGENTE`)
- `POST /api/presupuestos/{id}/emitir` sin líneas → `409`
- `GET /api/presupuestos?paciente_id=` → `200` con la línea

## Composición

`backend/app/demo.py` agrega al grafo existente:

- **C-08**: `ServicioFichaClinica` con fichas, evoluciones, adjuntos, consentimientos, pacientes,
  profesionales y turnos en memoria.
- **C-09 odontograma**: `ServicioOdontograma` con hallazgos, presupuestos, líneas, prestaciones,
  consentimientos y unidad de trabajo con rollback.
- **C-09 presupuesto**: `ServicioPresupuesto` con presupuestos/líneas/aceptaciones, prestaciones,
  pacientes con obra social, cobertura vacía e imputación en memoria.
- **Compartido**: un único `ConsentimientoMemoria` habilita ficha, evolución, hallazgos y líneas
  clínicas; `PresupuestoMemoria` y `LineaMemoria` se comparten entre odontograma y presupuesto.
- **Seed**: pacientes demo, profesionales demo, vínculo profesional↔paciente y precios
  `Consulta = 10000` / `Limpieza = 15000` centavos.

## Límites que siguen

- Todo el estado clínico es **en memoria**: se pierde al reiniciar.
- La persistencia SQL real sigue limitada a `auth` y `catalogos`.
- **La aceptación de presupuesto no escribe en caja**: `ImputacionMemoria` simula el puerto de C-09
  hacia C-10; el wiring real necesita un repositorio de líneas dinámico.
- Sin cobertura de obra social: el paciente demo no tiene OS y `a_cargo_paciente` es el monto completo
  (C-12).
- No hay UI clínica: ficha, odontograma y presupuesto son backend-only.
