# Proposal — C-14 Google Calendar sync

## Why

US-050 pide que el odontólogo vea su agenda en Google Calendar sin dejar de usar el sistema. Hoy no
existe vínculo por profesional ni reconciliación: si la GCal cae o el token se revoca, no hay contrato
explícito de degradación. C-14 agrega la sincronización bidireccional con el sistema como fuente de
verdad (RN-IN-02/03).

## What Changes

- Modelo `calendar_links`, `calendar_eventos` y `calendar_envios` (migración **011**, renumerada porque
  C-13 sigue bloqueado) con RLS por tenant.
- Dominio `app/calendario/` con puertos, servicio, adaptador fake de Google y repositorios SQL.
- Push de turnos creados/modificados/cancelados; pull de eventos externos como bloqueo informativo.
- Conflicto: gana el turno interno; el evento externo se guarda como `CONFLICTO_SISTEMA` y no es
  reservable.
- Cola de reintentos con backoff (1, 2, 4 min, máximo 3 intentos) y estado `AGOTADO`.
- Token revocado: el link pasa a `TOKEN_REVOCADO` y la agenda interna sigue operando.
- Endpoints `/api/calendar/oauth`, `/api/calendar/links`, `/api/calendar/push`,
  `/api/calendar/webhook`, `/api/calendar/bloqueos` y `/api/calendar/cola/procesar`.

## Capabilities

### New Capabilities

- `google-calendar`: vínculo OAuth por profesional, push/pull, conflictos y degradación con reintentos.

### Modified Capabilities

- Ninguna: C-05 conserva su contrato; el calendario externo es informativo.

## Impact

- `backend/app/models/calendario.py`, migración `011_calendar_sync.py`.
- `backend/app/calendario/`, router y schemas.
- `backend/app/demo.py`, `backend/app/app.py`.
- Tests de dominio, HTTP demo y PostgreSQL.
- Sin credenciales reales: adaptador fake y `oauth_ref` ficticio; la conexión real queda por env.

## Governance

MEDIO: integración externa que no escribe dinero ni PHI, pero afecta agenda. La agenda interna no se
bloquea si GCal falla (RN-IN-03).
