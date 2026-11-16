# Proposal — Frontend interno

## Why

El backend expone C-05 a C-15 por API, pero el SPA sólo tenía la fundación visual, la reserva pública y
un shell vacío. El consultorio no podía operar agenda, pacientes, clínica, caja, señas, obras sociales,
calendario ni administración desde el navegador.

## What Changes

- Cliente HTTP tipado con actor por headers y JWT para catálogos.
- Sesión persistente con login real (`demo / admin@demo.test / <DEMO_PASSWORD>`).
- Seed demo idempotente (`backend/seed_demo.py`) y servicio `migrate` en Compose que corre migraciones y
  seed antes de la API.
- Pantallas internas: resumen, agenda, pacientes, clínica (ficha, consentimiento, evoluciones,
  odontograma y presupuesto), caja, señas, obras sociales, calendario y configuración.
- Componentes compartidos de tabla, formularios, métricas y errores; estilos responsive.
- Tests de rutas actualizados y build de producción verde.

## Capabilities

### New Capabilities

- `frontend-interno`: operación del consultorio desde el SPA.

### Modified Capabilities

- Ninguna del backend; sólo se agrega seed y orquestación de Compose.

## Impact

- `frontend/src/api.ts`, `hooks.ts`, `components/ui.tsx`, `pages/app/*`, `layouts/AppShell.tsx`,
  `auth/AuthContext.tsx`, `pages/LoginPage.tsx`, `App.tsx`, `styles.css`, tests.
- `backend/seed_demo.py`, `backend/Dockerfile`, `docker-compose.yml`.
- Sin cambios de contrato en la API.

## Governance

MEDIO: UI operativa sin PHI real (datos ficticios de demo).
