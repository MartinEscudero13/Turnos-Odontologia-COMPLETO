# Proposal

## Why

C-05 y C-06 están implementados y probados, pero sus routers no están montados en `create_app`. La app real solo expone health, auth y catálogos; la landing F-02 no puede completar una reserva contra el backend. Antes de agregar C-12 necesitamos una demo end-to-end honesta del núcleo.

## What Changes

- Montar en `create_app` los routers de C-05 (`/api/turnos`) y C-06 (`/api/publico/...`).
- Crear un composition root de demo con adaptadores en memoria para turnos/reservas, catálogo, pacientes, tenants, tokens, verificación y auditoría.
- Sembrar catálogo demo tenant-scoped (`demo`) sin PHI.
- Agregar tests HTTP del flujo catálogo → disponibilidad → reserva.
- Documentar que la demo C-05/C-06 es en memoria; C-07…C-11 y la persistencia SQL de esos dominios siguen como follow-up.

## Capabilities

### New Capabilities

- `demo-api`: composición y exposición HTTP del núcleo C-05/C-06 para una demo reproducible.

### Modified Capabilities

- Ninguna capacidad de dominio cambia; se agrega wiring y seed demo.

## Impact

- `backend/app/app.py`, `backend/app/demo.py`, tests de wiring.
- No requiere migración nueva.
- No cambia contratos de C-05 ni C-06.
