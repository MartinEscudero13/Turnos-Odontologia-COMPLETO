# Proposal — C-07 `lista-espera-auto-oferta`

## Why

C-05 garantiza en DB que un hueco no quede doble-reservado y C-06 lo abre al
público, pero un hueco liberado por cancelación hoy simplemente vuelve a la
grilla general: el paciente que esperaba ser atendido antes se entera tarde o
nunca. RN-RE-04 exige que **todo hueco liberado se ofrezca automáticamente a la
lista de espera antes de quedar libre general**
(`knowledge-base/05_reglas_de_negocio.md:19`), con oferta que expira y rota al
siguiente (`knowledge-base/07_flujos_principales.md:37-43`, §Flujo 4). C-07 cierra
ese hueco: convierte el "sillón que se libera" en una oportunidad que se prioriza
a quien ya la pidió, sin violar anti-solape ni aislamiento por tenant.

## What Changes

- **Modelo de lista de espera**: `ListaEspera(tenant, paciente, prestacion,
  profesional_pref?, ventana_desde?, ventana_hasta?, estado PENDIENTE/OFRECIDO/CONVERTIDO/VENCIDO)`
  y `Oferta(lista_espera, hueco_turno_id?, expira_at, estado
  PENDIENTE/ACEPTADA/VENCIDA/CANCELADA)`. Migración **005** (ver Hallazgo abajo):
  `lista_espera` + `ofertas` + RLS (`tenant_id = current_setting('app.tenant_id')`).
- **Endpoints `/api/lista-espera`** (alta, baja, listar compatible), internos
  (recepción/admin) y scoped por tenant.
- **Worker auto-oferta**: ante un turno que pasa a `CANCELADO` o `REPROGRAMADO`
  (canal: recepción, link público o WA), el hueco liberado se ofrece a la lista
  compatible ordenada (fecha de alta) ANTES de publicarse general. La oferta
  expira (`OFERTA_TTL_MIN`, ejemplo 2 h); si vence, rota al siguiente; si nadie
  acepta, el hueco queda público.
- **Aceptación**: primer aceptante ocupa el hueco creando un turno
  `origen=LISTA_ESPERA` y **revalidando solape con C-05**; si el hueco ya fue
  tomado, la oferta pasa a `VENCIDA` y la entrada vuelve a `PENDIENTE` (no hay
  hueco que rotar).
- **Hold del hueco**: mientras hay una oferta vigente, el hueco no se ofrece al
  público (modifica la disponibilidad pública de C-06).

## Capabilities

### New Capabilities

- `lista-espera`: gestión de la lista de espera (alta/baja/listar), regla de
  compatibilidad entrada↔hueco, auto-oferta de huecos liberados con expiración y
  rotación, aceptación con revalidación de solape, y aislamiento multi-tenant.

### Modified Capabilities

- `reserva-publica`: la disponibilidad pública SHALL restar, además de turnos
  activos y bloqueos, los huecos retenidos por una oferta de lista de espera
  vigente (para cumplir "antes de quedar libre general").

## Impact

- **DB / migración**: `005_lista_espera` (`lista_espera`, `ofertas`, FK, índices,
  RLS). No toca turnos ni catálogos.
- **Backend**: nuevo módulo `backend/app/lista_espera/` (dominio, puertos,
  worker); `backend/app/routers/lista_espera.py`; schemas nuevos.
- **Consume C-05**: `ServicioTurnos.crear` con `origen="LISTA_ESPERA"` (ya válido
  en `OrigenTurno`) y su anti-solape/`calcular_fin`/`buscar_alternativas`.
- **Consume C-06**: `ServicioReservasPublicas.disponibilidad` pasa a restar los
  huecos retenidos por oferta vigente (nuevo puerto).
- **Redis**: cola/worker de auto-oferta (idempotencia por turno liberado).
- **Config**: `OFERTA_TTL_MIN` nuevo en `.env.example` (sin valor fijado; C07-OQ-1).

## Hallazgo (corrección al roadmap)

`CHANGES.md:243` dice "Migración 004" para C-07, pero la 004 ya la consumió
C-03 (`backend/alembic/versions/004_auth_rbac.py`, `down_revision =
003_turnos_anti_solape`). La migración real de C-07 es **005**
(`down_revision = "004_auth_rbac"`). Se documenta acá y en `design.md`; no se
renumera lo ya aplicado.
