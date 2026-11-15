# Proposal

## Why

C-07 (lista de espera), C-10 (caja) y C-11 (señas) están implementados y probados, pero sus routers no
están montados en `create_app`. La demo actual solo cubre C-05/C-06: no se puede gestionar la lista de
espera, registrar un cobro ni ver el estado de una seña desde la API real. Antes de sumar C-12 conviene
que el núcleo operativo sea demostrable de punta a punta.

## What Changes

- Extender el composition root de demo (`backend/app/demo.py`) con adaptadores en memoria para
  lista de espera, caja y señas, compartiendo reloj, catálogo, pacientes y tenants.
- Cablear la seña en la reserva pública de C-06 (`sena_port`) y configurar la regla demo.
- Montar en `create_app` los routers de C-07, C-10 y C-11 (público, interno y webhook).
- Agregar un manejador global de `TurnoError` para que los errores de dominio de esos routers
  conserven su código HTTP al convivir en una sola app.
- Agregar tests HTTP del flujo de lista de espera, caja, seña pública e interna.
- Documentar que el estado sigue en memoria y que C-08/C-09 no se montan en este tramo.

## Capabilities

### New Capabilities

- `demo-api` (delta): la app de demo expone también lista de espera, caja y señas con datos ficticios.

### Modified Capabilities

- Ninguna capacidad de dominio cambia: se agrega composición y exposición HTTP.

## Impact

- `backend/app/demo.py`, `backend/app/app.py`, `tests/test_demo_api_dominios.py`.
- Sin migraciones nuevas.
- No cambia contratos de C-07, C-10 ni C-11.
