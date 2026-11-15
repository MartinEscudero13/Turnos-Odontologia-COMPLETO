# Design — C-14 Google Calendar sync

## Context

C-05 expone turnos con `estado`, `inicio` y `fin`; C-07 ya modela huecos liberados. No hay integración
con GCal. Ver `proposal.md`.

## Goals / Non-Goals

**Goals:** vincular un calendario por profesional, pushear altas/cambios/cancelaciones, recibir eventos
externos como bloqueo informativo, resolver conflictos a favor del sistema y degradar con cola.

**Non-Goals:** OAuth real (se usa `oauth_ref` y adaptador fake), multi-calendario por sillón, crear
turnos desde GCal, editar eventos externos, UI de configuración y credenciales reales en el repo.

## Decisions

**D1 — Sistema fuente de verdad.**
Si un evento externo se solapa con un turno interno vigente, el turno **no se toca** y el evento se
guarda como `CONFLICTO_SISTEMA` (no reservable). El hueco externo nunca cancela ni reprograma la agenda.

**D2 — Push idempotente por turno.**
`calendar_eventos` guarda el `gcal_event_id` por `(tenant, link, turno)`. Un segundo push del mismo
turno actualiza el evento, no crea otro.

**D3 — Degradación con cola.**
Si la pasarela falla, el push se guarda como `PENDIENTE` y se encola. El procesamiento reintenta con
backoff 1, 2 y 4 minutos; al tercer fallo queda `AGOTADO`. La API responde éxito de negocio (el turno
sigue creado) y la agenda interna no se rompe.

**D4 — Token revocado.**
`TokenRevocado` marca el link como `TOKEN_REVOCADO`, encola lo pendiente y devuelve el estado; no
propaga una excepción al flujo de agenda.

**D5 — Webhook con token del link.**
`POST /api/calendar/webhook` recibe `link_id` y `token`; si no coincide con `oauth_ref`, responde `401`.
No hay firma HMAC porque no hay proveedor real en v1; se declara en los límites.

**D6 — RBAC.**
`ADMIN` administra cualquier link del tenant; `ODONTOLOGO` sólo el suyo (`X-Profesional-Id`).
`RECEPCION` puede leer estado y bloqueos; `PACIENTE` recibe `401`.

**D7 — Migración 011.**
El roadmap asignaba 012 a C-14, pero 011 pertenece a C-13 (bloqueado). Se renumera a **011** y se deja
constancia en `CHANGES.md`; C-15 tomará 012.

## Risks / Trade-offs

- Sin OAuth real no se prueba el flujo de Google: el contrato y la degradación sí.
- El evento externo se guarda pero no altera la disponibilidad de C-06 en v1; se declara como deuda.
- La cola es por tenant y se procesa por endpoint/worker; no hay cron en esta entrega.
- `oauth_ref` es una referencia, nunca el token en claro.

## Verification

- Dominio: push/idempotencia/cancelación, cola con backoff, token revocado, conflicto y aislamiento.
- HTTP: link, push, webhook con token válido/ inválido, bloqueos, RBAC.
- PostgreSQL: RLS sin tenant y roundtrip de link/evento/envío.
- Suite completa, `ruff`, `mypy`, `openspec validate --all --strict`.
