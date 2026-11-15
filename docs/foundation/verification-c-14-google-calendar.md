# Verification — C-14 Google Calendar sync

**Fecha**: 2026-11-15 · **Alcance**: vínculo OAuth, push/pull, conflictos y degradación

## Resultado

| Gate | Resultado |
|---|---|
| Tests de dominio | **17 passed** (`tests/test_calendario.py`) |
| Tests HTTP demo | **6 passed** (`tests/test_demo_api_calendario.py`) |
| Tests PostgreSQL | **2 passed** (`tests/test_calendario_pg.py`, con `C02_DATABASE_URL`) |
| Suite completa con DB | **800 passed, 0 skipped** |
| `ruff` | `All checks passed!` |
| `mypy` | 117 archivos, 0 errores |
| OpenSpec | `c-14-google-calendar-sync` válido (`--strict`) |

La migración se validó contra PostgreSQL 16 efímero: `upgrade head` → suite completa → `downgrade base`,
incluyendo el ciclo downgrade/re-upgrade de `test_migracion_009.py` con head en `011_calendar_sync`.

## Rutas verificadas por HTTP

- `POST /api/calendar/oauth` → `201 CONECTADO` · duplicado → `409 LINK_DUPLICADO`
- `GET /api/calendar/links` → `200` sin exponer `oauth_ref`
- `DELETE /api/calendar/links/{id}` → `200 DESCONECTADO`
- `POST /api/calendar/push` → `200 SINCRONIZADO` o `SIN_LINK`
- `POST /api/calendar/webhook` → `200 BLOQUEADO` / `CONFLICTO_SISTEMA`; token inválido → `401`
- `GET /api/calendar/bloqueos?desde=&hasta=` → `200` con los bloqueos del rango
- `POST /api/calendar/cola/procesar` → `200` con contadores
- `PACIENTE` → `401`; `RECEPCION` conectando → `403`; odontólogo ajeno → `403`

## Modelo y persistencia

Migración **011** (renumerada: C-13 conserva el 011 del roadmap y sigue bloqueado; C-15 tomará 012):

- `calendar_links`: UNIQUE `(tenant, profesional)`, estados `CONECTADO/DESCONECTADO/TOKEN_REVOCADO`.
- `calendar_eventos`: `UNIQUE(tenant, link, gcal_event_id)` parcial, origen `SISTEMA/EXTERNO`,
  estados de sincronización y conflicto, CHECK `fin > inicio`.
- `calendar_envios`: acción `PUSH/DELETE`, intentos y próximo intento, estados
  `PENDIENTE/PROCESADO/AGOTADO`.
- RLS `ENABLE + FORCE` en las tres tablas y grants por columna (sin `DELETE`).
- `LinkSQL`, `EventoSQL`, `ColaCalendarioSQL` y `TurnosSolapadosSQL` fijan `app.tenant_id`.

## Reglas aplicadas

- **RN-IN-02**: el sistema es fuente de verdad; el evento externo solapado queda
  `CONFLICTO_SISTEMA` y el turno interno no cambia.
- **RN-IN-03**: GCal caído encola el envío y la agenda sigue operando; backoff 1, 2 y 4 minutos hasta
  `AGOTADO`; token revocado marca el link y no rompe nada.
- **RN-AU-02**: altas, pushes, degradaciones, eventos externos y desconexiones se auditan.
- **RN-AU-01**: RBAC por rol y por profesional.

## Límites que siguen

- **OAuth y GCal simulados**: `PasarelaGoogleFake` y `oauth_ref` ficticio; no hay credenciales reales.
- **Los bloqueos externos no alteran C-06**: se guardan y consultan, pero el motor de reservas todavía
  no los lee (follow-up que toca C-05/C-06).
- **Sin cron**: la cola se procesa por endpoint; el worker programado queda para C-15.
- **Sin UI** de conexión ni de bloqueos (`C-14-UI` no creado).
- La demo sigue en memoria; la persistencia SQL está probada pero no cableada al arranque.
