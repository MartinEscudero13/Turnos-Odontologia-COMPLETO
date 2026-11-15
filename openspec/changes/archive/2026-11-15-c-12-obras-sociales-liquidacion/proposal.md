# Proposal — C-12 obras sociales y liquidación

## Why

El sistema ya calcula presupuestos y cobra, pero la cobertura de obra social es una tabla en memoria
vacía: el paciente demo paga siempre el 100%. US-042 pide cobertura configurable por (OS × prestación) y
una liquidación presentable por período. Sin C-12, el circuito de facturación a obras sociales queda
incompleto y C-15 no puede exportar datos reales de facturación.

## What Changes

- Modelo `obras_sociales`, `coberturas`, `liquidaciones` y `liquidacion_lineas` (migración 010, RLS por
  tenant, FK opcional `pacientes.obra_social_id`).
- Dominio `app/obras_sociales/` con puertos, servicio, adaptadores en memoria y repositorios SQL.
- Cálculo de tramos (cobertura OS / a cargo paciente) por (OS × prestación) con modo `PORCENTAJE` o
  `MONTO` y tope opcional.
- Liquidación por período de turnos **atendidos** (`PRESENTE`) con obra social, detalle por turno y
  exportación CSV. Regenerable mientras está en `BORRADOR`; inmutable al cerrar.
- Endpoints `/api/obras-sociales`, `/api/coberturas`, `/api/liquidaciones` y
  `/api/liquidaciones/{id}/export.csv`.
- Seed demo de 3 obras sociales y coberturas ficticias; el presupuesto demo usa la cobertura real.
- Marca explícita `validada_en_vivo: false` en las respuestas (RN-OS-01/DD-04).

## Capabilities

### New Capabilities

- `obras-sociales`: configuración de obras sociales y coberturas por tenant, cálculo de tramos y
  liquidación por período con exportación.

### Modified Capabilities

- Ninguna: C-09 conserva su contrato y sólo gana un adaptador de cobertura real.

## Impact

- `backend/app/models/obras_sociales.py`, `backend/alembic/versions/010_obras_sociales_liquidacion.py`.
- `backend/app/obras_sociales/`, `backend/app/routers/obras_sociales.py`, `backend/app/schemas/obras_sociales.py`.
- `backend/app/demo.py`, `backend/app/app.py`.
- Tests de dominio, HTTP demo y PostgreSQL.
- Sin UI: la pantalla de configuración queda declarada como deuda (`C-12-UI`).

## Governance

MEDIO: dominio de facturación (configuración y reportes). No toca PHI; sí montos y datos de facturación.
