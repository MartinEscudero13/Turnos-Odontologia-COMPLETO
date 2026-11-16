# Proposal — C-16 Cierre operativo (UI, ocupación y herramientas)

## Why

El sistema tenía el núcleo de C-05…C-15 montado, pero la UI interna no exponía acciones que el dominio
ya soportaba (confirmar/asistencia, anular y cobrar en caja, aceptar/rechazar presupuesto, activar OS o
usuarios, desconectar calendario). Además, C-15 se había archivado como parcial: superadmin, respaldo y
KPI de ocupación seguían afuera. Para la entrega se necesita que todo lo demostrable esté cerrado y que
sólo queden pendientes el video y la validación real de Twilio.

## What Changes

- **Agenda**: transiciones `PENDIENTE → CONFIRMADO → PRESENTE/AUSENTE` expuestas por HTTP y en la UI,
  con auditoría.
- **Caja**: anulación con motivo, cobros pendientes con medio, cierres y reportes por rango en el SPA.
- **Presupuesto**: aceptar/rechazar líneas desde la UI; la aceptación imputa el tramo del paciente a
  caja (cobro pendiente si no hay medio).
- **Odontograma**: resolver hallazgos desde la UI.
- **Obras sociales**: activar/desactivar y ver el detalle de una liquidación.
- **Calendario**: desconectar un link.
- **Usuarios**: activar/desactivar desde configuración.
- **KPI de ocupación**: minutos de turnos que bloquean agenda sobre la capacidad semanal ofrecida.
- **Operación**: CLI `tools/superadmin.py` (cross-tenant fuera de la API) y `tools/backup.py` con
  `pg_dump`/`pg_restore`, más un servicio Compose `backup`.
- **Tests**: HTTP de las acciones nuevas y tests de componentes de las páginas internas.

## Capabilities

### Modified Capabilities

- `admin-tenant`: el KPI base suma `ocupacion_pct`.
- `frontend-interno`: las pantallas exponen las acciones operativas y WhatsApp.

### New Capabilities

- `operacion`: superadmin por CLI y respaldo/restauración.

## Impact

- `backend/app/turnos/servicio.py`, `backend/app/routers/turnos.py`.
- `backend/app/caja/adaptadores.py`, `backend/app/demo.py`.
- `backend/app/admin/{puertos,servicio,repositorios}.py`, `backend/app/schemas/admin.py`.
- `frontend/src/api.ts` y páginas de `frontend/src/pages/app/`.
- `tools/superadmin.py`, `tools/backup.py`, `docker-compose.yml`, `.gitignore`.
- Tests: `tests/test_demo_api_acciones.py`, `tests/test_turnos_estado.py`,
  `frontend/src/pages/app/accionesInternas.test.tsx`.

## Fuera de alcance

- Superadmin como rol HTTP: cada despliegue sigue siendo single-tenant y la operación cross-tenant va
  por CLI con la credencial de dueño.
- Respaldo programado por cron del host: se entrega el comando/servicio y el procedimiento documentado.
- Twilio de producción: la demo usa `WA_PROVIDER=fake` mientras la cuenta trial esté bloqueada.
