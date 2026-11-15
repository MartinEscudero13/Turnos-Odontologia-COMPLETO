# Proposal

## Why

C-08 (ficha clínica) y C-09 (odontograma y presupuesto) están implementados y probados, pero sus
routers no están montados en `create_app`. La demo ya cubre reserva, lista de espera, caja y señas;
falta la superficie clínica para que el núcleo interno quede completo antes de C-12.

## What Changes

- Extender el composition root de demo con adaptadores en memoria para ficha clínica, odontograma y
  presupuesto, compartiendo consentimiento, pacientes, profesionales y el repositorio de presupuestos.
- Sembrar profesionales, prestaciones y el vínculo profesional↔paciente del tenant demo.
- Montar en `create_app` los routers de C-08 y C-09.
- Agregar tests HTTP: consentimiento → ficha → evolución, hallazgo de odontograma y presupuesto
  (crear, agregar línea, emitir).
- Documentar que la imputación de C-09 hacia C-10 sigue simulada en memoria.

## Capabilities

### New Capabilities

- `demo-api` (delta): la app de demo expone ficha clínica, odontograma y presupuesto con datos ficticios.

### Modified Capabilities

- Ninguna capacidad de dominio cambia: se agrega composición y exposición HTTP.

## Impact

- `backend/app/demo.py`, `backend/app/app.py`, `tests/test_demo_api_clinica.py`.
- Sin migraciones nuevas.
- No cambia contratos de C-08 ni C-09.
