# Tasks — `demo-api-clinica`

## 1. RED — tests HTTP primero

- [x] 1.1 Escribir `tests/test_demo_api_clinica.py` con ficha (409 sin consentimiento → 201), evolución, odontograma (hallazgo + pieza inválida) y presupuesto (línea + emisión + emitir sin líneas); verificar que fallan por rutas ausentes antes de implementar.

## 2. Composition root

- [x] 2.1 Agregar a `backend/app/demo.py` los adaptadores de ficha clínica y sembrar pacientes, profesionales y el vínculo profesional↔paciente del tenant demo.
- [x] 2.2 Cablear odontograma con el mismo consentimiento, pacientes, profesionales y turnos; compartir `PresupuestoMemoria`/`LineaMemoria` con presupuesto.
- [x] 2.3 Cablear presupuesto con prestaciones, cobertura vacía e imputación en memoria; verificar que una línea toma el precio base y que la emisión exige líneas.

## 3. App wiring

- [x] 3.1 Montar los routers de C-08 y C-09 en `create_app`; verificar que health, C-05…C-07, C-10 y C-11 siguen respondiendo.
- [x] 3.2 Verificar que el handler global de `TurnoError` devuelve 409/422 en los escenarios clínicos.

## 4. Documentación y cierre

- [x] 4.1 Actualizar `README.md`, `CONTINUAR.md` y `CHANGES.md` con C-08/C-09 montados y las deudas (imputación C-09→C-10 simulada, estado en memoria).
- [x] 4.2 Escribir `docs/foundation/verification-demo-api-clinica.md` con evidencia y límites.
- [x] 4.3 Correr `pytest`, `ruff`, `mypy`, `openspec validate --all --strict`; archivar el change y dejar el árbol limpio.
