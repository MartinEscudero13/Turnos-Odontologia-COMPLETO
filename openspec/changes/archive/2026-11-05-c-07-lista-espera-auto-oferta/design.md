# Design — C-07 `lista-espera-auto-oferta`

> Estado: **preparado, no implementado**. Este documento decide el HOW; el QUÉ
> está en `specs/lista-espera/spec.md` y `specs/reserva-publica/spec.md`, y el
> porqué en `proposal.md`.

## UI Mockups

- Decision: no (no UI) — C-07 es backend-only; la lista de espera no tiene
  superficie visual propia en v1 (la gestiona recepción desde la API; una futura
  pantalla `/lista-espera` es un follow-up de frontend fuera de este scope).
- Fecha: 2026-11-05

## Context

Stack real: Python + FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL 15 multi-tenant
con RLS. Ya implementados y archivados: C-05 (`backend/app/turnos/servicio.py`,
migración 003) con `ServicioTurnos.crear` aceptando `origen="LISTA_ESPERA"` (el
valor ya existe en `OrigenTurno`, `servicio.py:26`) y su anti-solape/`calcular_fin`/
`buscar_alternativas`; C-04 catálogos/pacientes (`backend/app/models/catalogos.py`:
`Paciente`, `Prestacion`, `Profesional`, `Sillon`); C-03 auth/auditoría
(`backend/app/core/audit`); C-06 reserva pública (`backend/app/reservas/`,
`ServicioReservasPublicas.disponibilidad`). Redis (`REDIS_URL`) está declarado para
workers/colas (DD-08).

Reglas duras aplicables (`AGENTS.md`): toda tabla filtra por `tenant_id` + RLS;
acceso a datos sólo vía SQLAlchemy (SQL crudo sólo en Alembic); type hints; datos
ficticios; sin secretos/PHI; anti-solape (RN-AG-02) y aislamiento se cumplen
siempre (RN-GL-01).

## Goals / Non-Goals

**Goals:** lista de espera por paciente/prestación con alta/baja/listar; auto-oferta
de hueco liberado a la lista compatible ordenada ANTES de publicarse; expiración
configurable con rotación; primer aceptante ocupa el hueco revalidando solape; hold
del hueco durante la oferta; aislamiento multi-tenant y trazabilidad append-only.

**Non-Goals:** envío de WA/email (C-13: se emite evento vía `NotificadorPort`
no-op); seña Mercado Pago (C-11); UI `/lista-espera` (follow-up de frontend);
reprogramar la entrada de la lista (sólo alta/baja/listar en v1); prioridad manual
de la lista (C07-OQ-2, fase 2).

## Decisions

- **D1 — Dos entidades, migración 005 (no 004).**
  `ListaEspera(tenant_id, paciente_id, prestacion_id, profesional_pref?,
  ventana_desde?, ventana_hasta?, estado PENDIENTE/OFRECIDO/CONVERTIDO/VENCIDO,
  creado_en)` y `Oferta(id, tenant_id, lista_espera_id, hueco_turno_id?,
  expira_at, estado PENDIENTE/ACEPTADA/VENCIDA/CANCELADA, token uuid, creado_en)`.
  La 004 ya la consumió C-03 (`004_auth_rbac.py`), así que la migración real es
  `005_lista_espera` con `down_revision="004_auth_rbac"`. Índices: `(tenant_id,
  paciente_id, prestacion_id)`, `(tenant_id, estado)`, `(tenant_id, expira_at)` y
  `UNIQUE(tenant_id, lista_espera_id, estado)` parcial para la oferta vigente.
  RLS en ambas. Alternativas descartadas: (a) reusar la 004 → colisión con auth;
  (b) una sola tabla `lista_espera` con columnas de oferta embebidas → no modela la
  cadena de ofertas ni la rotación; (c) denormalizar el slot en `ofertas` →
  duplica `inicio/fin` que ya deriva del `hueco_turno_id`.

- **D2 — El hueco ofrecido es el slot liberado tal cual (misma prestación).**
  La compatibilidad exige `entrada.prestacion_id == hueco.prestacion_id`, así que
  no hay desajuste de duración: el turno que se ofrece conserva la `duracion_min`
  de la prestación del turno liberado. `hueco_turno_id` referencia el turno
  cancelado/reprogramado; el slot (profesional, sillón, inicio, fin) se lee de
  ese turno. Alternativas: ofrecer "un hueco cualquiera que el paciente quiera" →
  contradice RN-RE-04 (el hueco liberado es el que se ofrece) y complica la
  revalidación.

- **D3 — Trigger por evento de hueco liberado, worker en Redis con idempotencia.**
  `ServicioTurnos.cancelar`/`reprogramar` ya son el único camino a `CANCELADO`/
  `REPROGRAMADO`; C-07 define un puerto `HuecoLiberadoPort.emitir(tenant_id,
  turno_id)` invocado tras la cancelación/reprogramación en el borde (router de
  turnos y servicio público de C-06). En producción encola un job en Redis con
  clave de idempotencia `auto_oferta:{turno_id}`; en tests es síncrono. El worker
  (`backend/app/lista_espera/worker.py`) procesa: busca compatibles ordenados →
  oferta al primero → notifica. La expiración se acota al inicio del slot:
  `expira_at = min(ahora + OFERTA_TTL_MIN, slot.inicio)` (la oferta nunca expira
  después de que arranca el slot); si `slot.inicio` ya pasó, el hueco se publica
  directo como disponible sin ronda de lista de espera. Alternativas descartadas:
  (a) polling que escanea
  turnos `CANCELADO/REPROGRAMADO` sin oferta → estado extra + carrera; (b) lógica
  inline en `cancelar` (bloquea la cancelación con I/O de notificación) → acopla
  C-05 a C-07; (c) outbox en DB → más fiel pero exige DDL extra no pedida.

- **D4 — Hold blando + revalidación dura (dos capas).**
  (1) `ServicioReservasPublicas.disponibilidad` resta los huecos con una oferta
  vigente consultando `OfertaPort.huecos_retenidos(tenant_id, desde, hasta)`: el
  público no ve el hueco mientras se ofrece (RN-RE-04 "antes de quedar libre
  general"). (2) Al aceptar, `ServicioTurnos.crear` revalida solape (fuente de
  verdad EXCLUDE 003): si recepción u otro canal ya tomó el hueco, `ConflictoSolape`
  → oferta `VENCIDA` y la entrada vuelve a `PENDIENTE` (no hay hueco que rotar:
  el hueco ya lo ocupó otro). Alternativas descartadas: (a) lock real
  en DB del hueco durante la oferta → reserva un hueco que puede quedar vacío y
  complica recepción; (b) sin hold (el hueco queda público de inmediato) → viola
  "antes de quedar libre general"; (c) hold en Redis sin revalidación → reabre el
  riesgo de doble reserva.

- **D5 — Aceptación por token de oferta, público y single-use.**
  Cada oferta lleva `token` UUID v4 (no secuencial). El paciente acepta por
  `POST /api/publico/{tokenTenant}/ofertas/{token}/aceptar` (o la respuesta WA
  "SI" de C-13 llama al mismo caso de uso). La aceptación valida: oferta
  `PENDIENTE` + `expira_at > ahora`, resuelve tenant por la ruta y token dentro de
  ese tenant, y en una transacción reclama la oferta (`PENDIENTE → ACEPTADA`) para
  que el doble-accept concurrente gane una sola vez, antes de `ServicioTurnos.crear`
  con `origen="LISTA_ESPERA"`. Alternativas: (a) aceptación sólo por recepción →
  pierde el "primer aceptante" autónomo de RN-RE-04; (b) sin token (id de oferta
  enumerable) → adivinable; (c) verificación captcha/OTP por aceptación → sobre-
  ingeniería (sólo el notificado posee el token; C07-OQ-4).

- **D6 — Orden = fecha de alta (FIFO); "prioridad" queda como OQ.**
  RN-RE-04 dice "orden: prioridad/fecha de alta" y el modelo de KB no define un
  campo `prioridad`. C-07 ordena por `creado_en` ascendente (fecha de alta),
  determinista y testeable. Un campo `prioridad` manual se difiere (C07-OQ-2).
  Alternativas: prioridad aleatoria → no testeable; prioridad por "más antigua
  prestación" → inventa una regla sin respaldo.

- **D7 — Puertos + adaptadores en memoria (mismo patrón que C-06).**
  `ListaEsperaRepositorio`, `OfertaRepositorio`, `HuecoLiberadoPort`, `OfertaPort`
  (consulta de huecos retenidos para la disponibilidad), `NotificadorPort`
  (reutiliza el concepto de C-06; no-op hasta C-13), `AuditoriaPort`. El dominio
  queda testeable sin DB ni Redis; el wiring real a SQLAlchemy/Redis es follow-up
  explícito. Alternativas: lógica pegada a SQLAlchemy → imposible de testear
  rápido y acopla.

- **D8 — Estados de oferta son decisión propia (la KB no los enumera).**
  La KB da `lista_espera.estado(PENDIENTE/OFRECIDO/CONVERTIDO/VENCIDO)` y
  `ofertas(... estado)` sin valores. Se fijan `oferta.estado ∈
  {PENDIENTE, ACEPTADA, VENCIDA, CANCELADA}`:
  - `PENDIENTE`: ofrecida, esperando respuesta.
  - `ACEPTADA`: aceptada y convertida en turno (terminal).
  - `VENCIDA`: expiró sin respuesta, o el hueco ya fue tomado por otro al intentar
    aceptar; en ambos casos la entrada vuelve a `PENDIENTE`.
  - `CANCELADA`: anulada por la baja de la entrada (terminal).
  Al vencer (o al fallar la revalidación por hueco tomado por otro), la entrada
  vuelve a `PENDIENTE` (sigue esperando un hueco futuro);
  `VENCIDO` en la entrada es terminal y sólo lo produce la baja o una política
  futura de limpieza. Alternativas: reusar el enum de la entrada en la oferta →
  `OFRECIDO` no describe un estado de oferta.

- **D9 — Config.** `OFERTA_TTL_MIN` (expiración de la oferta) se declara en
  `.env.example` con default **`120`** (min, configurable por tenant) — decisión
  aprobada por Lautaro (2026-11-05); coincide con el ejemplo "2 h" de la KB
  (`07_flujos_principales.md:41`). `VENTANA` sin valor inventado (C07-OQ-3).
  Orden FIFO confirmado (C07-OQ-2 resuelta, sin `prioridad` manual en v1).

## Seams

Interfaces que C-07 consume (C-05, C-06, C-04) y define. Firmas con type hints.

```python
# --- C-05 real (se consume tal cual; no se modifica) ---
# ServicioTurnos.crear(actor, *, profesional_id, sillon_id, paciente_id,
#                      prestacion_id, inicio, duracion_min, fin_cliente=None,
#                      sobreturno=False, motivo_sobreturno=None,
#                      origen="RECEPCION") -> Turno   # origen="LISTA_ESPERA" ya válido
# ServicioTurnos.cancelar / reprogramar -> disparan HuecoLiberadoPort en el borde

# --- C-06 (se consume y se amplía con un puerto) ---
# ServicioReservasPublicas.disponibilidad: resta oferta vigente vía OfertaPort

# --- C-07 define ---
class ListaEsperaRepositorio(Protocol):
    def alta(self, *, tenant_id, paciente_id, prestacion_id,
             profesional_pref=None, ventana_desde=None, ventana_hasta=None,
             ahora=None) -> Entrada: ...
    def baja(self, *, tenant_id, entrada_id, ahora=None) -> Entrada: ...
    def listar(self, *, tenant_id, prestacion_id=None,
               profesional_id=None) -> list[Entrada]: ...
    def compatibles(self, *, tenant_id, prestacion_id, profesional_id,
                    inicio, ahora=None) -> list[Entrada]: ...

class OfertaRepositorio(Protocol):
    def crear(self, *, tenant_id, entrada_id, hueco_turno_id,
              expira_at, token) -> Oferta: ...
    def vigente_para(self, *, tenant_id, hueco_turno_id) -> Oferta | None: ...
    def vencidas(self, *, tenant_id, ahora) -> list[Oferta]: ...
    def aceptar(self, *, tenant_id, token, ahora) -> Oferta: ...
    def cancelar(self, *, tenant_id, oferta_id) -> Oferta: ...

class OfertaPort(Protocol):
    def huecos_retenidos(self, *, tenant_id, desde, hasta) -> list[HuecoRetenido]: ...

class HuecoLiberadoPort(Protocol):
    def emitir(self, *, tenant_id, turno_id) -> None: ...

class NotificadorPort(Protocol):          # no-op hasta C-13
    def oferta_emitida(self, *, tenant_id, oferta_id) -> None: ...
```

## Risks / Trade-offs

- [Hueco retenido mucho tiempo si hay N compatibles y TTL alto] → cada oferta rota
  con su TTL; mitigación: `OFERTA_TTL_MIN` acotado y C07-OQ-1 (calibrar con el dueño);
  el hold es la contrapartida explícita de "antes de quedar libre general".
- [Carrera aceptar vs expirar] → la aceptación compara `expira_at > ahora` y reclama
  la oferta en transacción (D5); el que llega vencido recibe `409`.
- [Carrera aceptar vs hueco tomado por recepción] → revalidación de solape en
  `ServicioTurnos.crear` (D4); oferta `VENCIDA` y la entrada vuelve a `PENDIENTE`
  (no hay hueco que rotar: ya lo ocupó otro).
- [Doble evento de cancelación] → idempotencia `auto_oferta:{turno_id}` en Redis (D3).
- [Drift al cablear puertos a SQLAlchemy/Redis] → test de contrato por puerto y
  wiring explícito (mismo criterio que C-06 D9).
- [Zona horaria] → datetimes aware (`timestamptz`), escenarios en `-03:00` y reloj
  inyectado (ningún test usa el reloj real).

## Migration Plan

1. **DDL (005)**: `lista_espera` + `ofertas` con `tenant_id NOT NULL`, FK, índices
   y RLS. Reversible. No toca turnos ni catálogos.
2. Módulos nuevos: `backend/app/lista_espera/` (dominio, puertos, worker, tokens) +
   `backend/app/routers/lista_espera.py` + `backend/app/schemas/lista_espera.py`.
   Ajuste mínimo en `backend/app/reservas/servicio.py` (restar huecos retenidos) y
   en el borde de cancelación/reprogramación (emitir `HuecoLiberadoPort`).
3. Config: `OFERTA_TTL_MIN=120` en `.env.example` (default aprobado; C07-OQ-1
   resuelta).
4. Rollout: worker detrás de flag de config por tenant (apagado por defecto hasta
   cerrar C07-OQ-1 y el wiring Redis). Rollback = apagar flag; la 005 no borra datos
   preexistentes (tablas nuevas).
5. Verificación: `py -m pytest tests/ -q` (suite C-05+C-06 + nuevos) y
   `openspec validate c-07-lista-espera-auto-oferta --strict`.

## Open Questions

| OQ | Pregunta | Por qué no se fija acá | Respaldo |
|---|---|---|---|
| C07-OQ-1 ✅ resuelta | ¿Cuánto vale `OFERTA_TTL_MIN` (expiración de la oferta)? | Resuelta: `120` min default (configurable). Aprobado por Lautaro 2026-11-05 | `07_flujos_principales.md:41`; `CHANGES.md:241` |
| C07-OQ-2 ✅ resuelta | ¿Hay una `prioridad` manual además del FIFO por fecha de alta? | Resuelta: FIFO por `creado_en`; sin `prioridad` manual en v1 | `05_reglas_de_negocio.md:19`; `04_modelo_de_datos.md:61` |
| C07-OQ-3 | ¿`ventana_horaria` es un rango absoluto (desde/hasta) o una ventana recurrente por día? | La KB sólo nombra `ventana_horaria?` sin semántica | `04_modelo_de_datos.md:61` |
| C07-OQ-4 | ¿La aceptación exige verificación anti-spam (captcha/OTP) además del token? | Sólo el notificado posee el token; la KB no lo exige para ofertas | `03_actores_y_roles.md:35` |
| C07-OQ-5 ✅ resuelta | ¿Quién da de alta/baja (sólo recepción/admin, o también el paciente por el link)? | Resuelta: Recepción/Admin gestiona la lista de espera | `03_actores_y_roles.md:9,24` |

## Notas de implementación (no vinculantes)

- El actor del alta/baja/listar es `RECEPCION`/`ADMIN` (resuelto por
  `03_actores_y_roles.md:9,24`; antes C07-OQ-5); la aceptación es pública por token.
- `origen="LISTA_ESPERA"` ya es válido en `OrigenTurno` (`servicio.py:26`); no se
  toca el CHECK de la 003.
- La auditoría registra `OFRECIDO`, `OFERTA_VENCIDA`, `OFERTA_ACEPTADA`,
  `OFERTA_CANCELADA` como acciones append-only del tenant, sin PHI (sólo
  `tenant_id`, `entrada_id`, `oferta_id`, `turno_id`, estados).
