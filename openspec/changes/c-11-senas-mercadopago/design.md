# Design — C-11 `senas-mercadopago`

> Estado: **preparado, no implementado**. Este documento decide el HOW; el QUÉ está en
> `specs/senas/spec.md`, `specs/reserva-publica/spec.md` y `specs/turnos-anti-solape/spec.md`,
> y el porqué en `proposal.md`.
> Governance **CRÍTICO**: no se implementa sin aprobación explícita del dueño.
> Regla de oro del change: **ningún número, plazo o umbral sin respaldo documental**. Lo que no
> está en la KB vive en §Open Questions (`C11-OQ-N`) con recomendación, y la spec lo cita.

## UI Mockups

- Decision: **no (UI diferida a change aparte `C-11-UI`, 2026-11-13)**.
- Design system revision: **no aplica** — no hay `design-system/README.md` y el estado del
  orquestador no registra `visual_design` (modo `deferred`). El primer work visual del proyecto
  será `C-11-UI`, y ahí corresponde invocar la skill `design-system` para fijar la política una
  sola vez.
- Alcance de C-11 v1: **backend + contratos + migración 009 + tests**. C-11 **no toca
  `frontend/`**: no hay páginas `/pagar/:tokenSena`, no hay agenda con estado de seña, no hay
  `/config` de la regla y no hay mockups. Las delta specs no declaran requirements de UI.
- Criterios que `C-11-UI` deberá cubrir están listados en `proposal.md` §Fuera de alcance y en
  `tasks.md` §12 (no ejecutables acá).

## Context

Estado real del repo que condiciona el diseño (verificado, no supuesto):

- **C-05 implementado**: `turnos` y `ServicioTurnos` (`backend/app/turnos/servicio.py:120-159`).
  La máquina de estados ya permite `PENDIENTE → CONFIRMADO` y `PENDIENTE → CANCELADO`
  (`backend/app/turnos/estados.py:16-23`), pero **no existe un caso de uso `confirmar`**: sólo
  `crear`, `actualizar`, `sobreturno`, `cancelar`, `reprogramar`
  (`servicio.py:134,193,209,224,242,263`). C-11 agrega esa transición como extensión mínima.
- **C-06 implementado**: `ServicioReservasPublicas.reservar` crea el turno `PENDIENTE` con
  `origen=RESERVA_ONLINE`, emite `token_publico` y audita
  (`backend/app/reservas/servicio.py:318-387`); `cancelar` aplica la anticipación y emite
  `HuecoLiberadoPort` (`:428-458`); `reprogramar` crea un turno nuevo y transfiere el token
  (`:460-496`). El `{tokenTenant}` de las rutas públicas es el **slug** del tenant
  (`backend/app/reservas/puertos.py:334-346`).
- **C-07 implementado**: `HuecoLiberadoPort.emitir(*, tenant_id, turno_id)` ya es idempotente
  por `auto_oferta:{turno_id}` (`backend/app/lista_espera/puertos.py:173-174,456-478`) y
  `ServicioAutoOferta.procesar_hueco_liberado` hace la oferta real
  (`backend/app/lista_espera/worker.py:68-74`). C-11 **sólo emite el evento**.
- **C-10 implementado**: `ServicioCaja.registrar_movimiento(actor, monto, medio, tipo, fecha,
  turno_id)` toma `uow.bloquear_dia`, rechaza día cerrado con `409 CIERRE_CERRADO` y valida el
  turno contra el tenant (`backend/app/caja/servicio.py:364-426`). La unidad de trabajo
  `TransaccionSQL` es **anidable**: la más externa commitea y las internas sólo hacen `flush`
  (`backend/app/core/transaccion.py:31-73`). C-11 se cuelga de ahí para que la seña `APLICADA`
  y el movimiento `MP` vivan en la misma transacción.
- **Configuración del tenant es clave/valor**: `tenant_parametros(tenant_id, clave, valor jsonb,
  actualizado_en)` (`backend/app/models/tenant.py:26-38`). **No** es una tabla ancha, así que
  PO-01 no puede implementarse "agregando columnas" ahí.
- **`prestaciones` ya tiene `requiere_sena` y `monto_sena`**
  (`backend/app/models/catalogos.py:49-50`): hay que reconciliar, no duplicar.
- **Settings fail-fast**: `backend/app/core/settings.py:21-84` valida secretos en production;
  los nombres de env de integraciones ya están en la KB
  (`knowledge-base/08_arquitectura_propuesta.md:53-57`): `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`,
  `SENA_TTL_H` (ejemplo `24`), `CANCEL_ANTICIPACION_H` (default `24`).
- **Migración head**: `008_caja_cierre_diario`; la siguiente es **009**. **No existe** ninguna
  tabla `senas`, `pagos_mp` ni `obras_sociales` (C-12).
- Reglas duras (`AGENTS.md`): `tenant_id` + RLS forzada, SQLAlchemy para datos (SQL crudo sólo en
  Alembic), type hints, sin PHI, migraciones reversibles, dinero en centavos, `mypy --strict`.

## Goals / Non-Goals

**Goals:** resolver la regla de seña de PO-01 sobre la base real; crear la seña atada 1──1 al
turno; pedir la preferencia a MP y devolver un link pagable sin login; procesar el webhook de
forma **idempotente y autenticada**; acreditar la seña y confirmar el turno una sola vez; liberar
el turno vencido y disparar la auto-oferta de C-07; aplicar la seña al cobro creando el movimiento
`MP` con el alta de C-10; registrar devoluciones de forma explícita; RLS, auditoría y cero PHI;
migración 009 reversible.

**Non-Goals:** UI (`C-11-UI`); reembolsos automáticos y conciliación bancaria; split de pagos;
otras pasarelas; cobro total online; cuotas; configuración por API (C-15); recordatorios de pago
(C-13); descuento automático contra la línea de presupuesto; facturación ARCA; reabrir un turno
ya liberado; reintentar preferencias con un scheduler propio (se hace on-demand + backoff).

## Decisions

### D1 — Configuración de la seña: PO-01 sobre la base real (KV + override)

PO-01 define `valor efectivo = prestacion.<campo> ?? tenant_parametros.<campo>`
(`docs/decisiones-po.md:20-44`). La base real tiene dos formas incompatibles con la letra de esa
decisión: `tenant_parametros` es **clave/valor** (`backend/app/models/tenant.py:26-38`) y
`prestaciones` ya trae `requiere_sena`/`monto_sena` (`catalogos.py:49-50`). La resolución queda:

| Nivel | Dónde vive | Tipo | Semántica |
|---|---|---|---|
| Prestación (override) | `prestaciones.sena_modo` (nueva) | `TEXT NULL` | `NULL` = hereda del tenant |
| | `prestaciones.sena_valor` (nueva) | `INTEGER NULL` | `%` entero 1–100 si `PORCENTAJE`; centavos si `MONTO_FIJO`; `NULL` si `SIN_SENA` |
| Tenant (default) | `tenant_parametros` fila `clave='sena_modo'` | `jsonb` string | `"SIN_SENA"` \| `"PORCENTAJE"` \| `"MONTO_FIJO"` |
| | `tenant_parametros` fila `clave='sena_valor'` | `jsonb` number | entero con la semántica de arriba |

Algoritmo (una sola función pura, `resolver_regla`):

1. `prestaciones.sena_modo IS NOT NULL` → gana la prestación, **aunque sea `SIN_SENA`** (PO-01).
2. Si es `NULL` → gana `tenant_parametros['sena_modo']`.
3. Si el tenant tampoco definió la clave → **`SIN_SENA`** (fail-open a no cobrar; nunca a cobrar
   de más, PO-01 regla 3).
4. Una configuración almacenada inválida (modo desconocido, `PORCENTAJE` fuera de 1–100,
   `MONTO_FIJO <= 0`, valor faltante) **no rompe la reserva**: se trata como `SIN_SENA`, se
   registra `REGLA_SENA_INVALIDA` en el log estructurado con `tenant_id`/`prestacion_id` y se
   audita el hecho sin PHI. Un error de configuración no puede dejar al paciente sin poder
   reservar ni cobrarle un monto inventado.
5. El monto se calcula con el `precio_base` vigente de la prestación (centavos):
   `MONTO_FIJO` → `sena_valor`; `PORCENTAJE` → truncar hacia abajo al centavo
   (`precio_base * valor // 100`, `C11-OQ-01`). Si el resultado es `0` (p. ej. `precio_base=0`)
   la reserva **no** exige seña: no se crea una seña de `0` centavos
   (`CHECK monto_centavos > 0`).

**Por qué KV y no columnas nuevas en `tenant_parametros`**: agregar `sena_modo`/`sena_valor` a una
tabla `(tenant_id, clave)` obligaría a que esas columnas fueran `NULL` en todas las demás filas y
crearía dos verdades para el mismo parámetro. La tabla es un almacén de parámetros por diseño
(`04_modelo_de_datos.md:85` ya siembra "parámetros (anticipación cancelación default 24 h,
política de seña)"). Se documenta como desviación de la **letra** de PO-01, preservando su
**semántica** exacta (override por prestación, `SIN_SENA` válido, fail-open).

Alternativas: (a) columnas en `tenant_parametros` → dos verdades y filas con columnas muertas;
(b) tabla nueva `tenant_config_sena` → duplica la tabla de parámetros que ya existe; (c) leer sólo
`requiere_sena`/`monto_sena` → no soporta porcentaje ni override con herencia, y contradice
PO-01.

### D2 — Modelo `Sena`: estados, snapshots y garantías en la base

La seña es la **obligación de pago de una reserva**, no un saldo editable. Se persiste el monto y
la regla que lo produjo, porque el `precio_base` de la prestación puede cambiar después y el monto
cobrado tiene que seguir siendo reproducible (RN-AU-02).

| Columna | Tipo | Regla |
|---|---|---|
| `id` | `uuid` PK | — |
| `tenant_id` | `uuid NOT NULL` FK `tenants` | RLS; toda query lo recibe explícito |
| `turno_id` | `uuid NOT NULL` FK `turnos` | **UNIQUE `(tenant_id, turno_id)`** = 1──1 con la reserva (RN-SE-02) |
| `monto_centavos` | `integer NOT NULL` | `CHECK > 0`; coincide con el pago acreditado (D8) |
| `estado` | `text NOT NULL` | `CHECK IN ('PENDIENTE','ACREDITADA','LIBERADA','APLICADA','DEVUELTA')` |
| `regla_modo` | `text NOT NULL` | `CHECK IN ('PORCENTAJE','MONTO_FIJO')` (nunca `SIN_SENA`: si no hay seña, no hay fila) |
| `regla_valor` | `integer NOT NULL` | `%` o centavos usados, snapshot |
| `precio_base_centavos` | `integer NOT NULL` | snapshot del `precio_base` al reservar (`CHECK >= 0`) |
| `anticipacion_cancelacion_h` | `integer NOT NULL` | snapshot de la política vigente al reservar (`>= 0`) |
| `mp_preference_id` | `text NULL` | UNIQUE parcial `(tenant_id, mp_preference_id)` |
| `mp_init_point` | `text NULL` | URL de checkout devuelta por MP (no es secreto) |
| `preferencia_estado` | `text NOT NULL DEFAULT 'POR_CREAR'` | `CHECK IN ('POR_CREAR','CREADA','FALLIDA')` |
| `intentos_preferencia` | `integer NOT NULL DEFAULT 0` | `CHECK >= 0`; backoff (D5) |
| `proximo_reintento_at` | `timestamptz NULL` | cuándo el paciente puede reintentar |
| `expira_at` | `timestamptz NOT NULL` | `min(ahora + SENA_TTL_H, turno.inicio)` (D6) |
| `token_hash` | `text NOT NULL` | SHA-256 hex del token de `/pagar/:tokenSena`; **UNIQUE global** |
| `token_rotado_en` | `timestamptz NULL` | cuándo se invalidó el token anterior |
| `acreditada_en` / `aplicada_en` / `liberada_en` / `devuelta_en` | `timestamptz NULL` | instante de cada estado alcanzado |
| `motivo_liberacion` | `text NULL` | `CHECK IN ('EXPIRACION','CANCELACION')`; no se agrega un valor para la reserva fallida porque el alta es atómica (D5) |
| `concepto_aplicacion` | `text NULL` | `CHECK IN ('TRATAMIENTO','CANCELACION_TARDIA')` |
| `devuelta_por` | `uuid NULL` FK `usuarios` | `NULL` cuando la devolución la registró el sistema por política |
| `motivo_devolucion` | `text NULL` | obligatorio si `estado='DEVUELTA'` |
| `movimiento_caja_id` | `uuid NULL` FK `movimientos_caja` | UNIQUE parcial; obligatorio si `estado='APLICADA'` |
| `creado_en` | `timestamptz NOT NULL` | — |

CHECKs de coherencia estado↔instante (la base no acepta un estado sin su hecho):

```sql
CHECK (estado <> 'ACREDITADA' OR acreditada_en IS NOT NULL)
CHECK (estado <> 'APLICADA'   OR (aplicada_en IS NOT NULL AND movimiento_caja_id IS NOT NULL
                                  AND concepto_aplicacion IS NOT NULL))
CHECK (estado <> 'LIBERADA'   OR (liberada_en IS NOT NULL AND motivo_liberacion IS NOT NULL))
CHECK (estado <> 'DEVUELTA'   OR (devuelta_en IS NOT NULL AND motivo_devolucion <> ''))
CHECK (preferencia_estado <> 'CREADA' OR (mp_preference_id IS NOT NULL AND mp_init_point IS NOT NULL))
```

`monto_centavos`, `turno_id`, `regla_*`, `precio_base_centavos`, `expira_at` y `token_hash` son
**inmutables** después del alta (sin endpoint que los edite; `REVOKE UPDATE` por columna deja
sólo las columnas de estado, preferencia y token). `REVOKE DELETE`: nunca se borra una seña
(RN-AU-02/RN-CJ-03 por analogía).

Alternativas: (a) un único `estado` sin instantes → imposible auditar cuándo se liberó o devolvió
sin leer la auditoría; (b) recalcular el monto desde la prestación al leer → el monto cambia si
sube el precio, y lo cobrado deja de ser reproducible; (c) guardar el token en claro → una fuga
de la base entrega links de pago vivos.

### D3 — Modelo `PagoMP`: idempotencia, resultado propio y payload minimizado

`pagos_mp` es el **libro de idempotencia** del webhook. Un pago de MP puede notificarse muchas
veces y con estados que llegan desordenados; el hecho de negocio (acreditar) se aplica una sola
vez, pero cada notificación relevante queda registrada.

| Columna | Tipo | Regla |
|---|---|---|
| `id` | `uuid` PK | — |
| `tenant_id` | `uuid NOT NULL` FK `tenants` | RLS |
| `mp_payment_id` | `text NOT NULL` | **UNIQUE global** (RN-SE-03: "`mp_payment_id` único") |
| `sena_id` | `uuid NOT NULL` FK `senas` | 1──N por ERD (`04_modelo_de_datos.md:23`): un intento rechazado y uno aprobado son dos filas |
| `monto_centavos` | `integer NOT NULL` | `CHECK > 0` |
| `moneda` | `text NOT NULL DEFAULT 'ARS'` | moneda **real** que informa la pasarela (`ARS`, `USD`, …), normalizada a mayúsculas; la acreditación exige `ARS` **y** monto exacto en la aplicación (corrección 2026-11-13: un `CHECK moneda='ARS'` haría inalcanzable el `MONTO_DISTINTO` de §6, C11-OQ-12) |
| `estado` | `text NOT NULL` | estado informado por MP (`APPROVED`,`PENDING`,`IN_PROCESS`,`REJECTED`,`CANCELLED`,`REFUNDED`,`OTHER`) |
| `resultado` | `text NOT NULL` | efecto propio: `ACREDITADA`,`DEVUELTA`,`IGNORADO`,`MONTO_DISTINTO`,`PAGO_EXCEDENTE`,`TURNO_NO_CONFIRMABLE`,`FUERA_DE_TIEMPO`,`DUPLICADO`,`REEMBOLSADO`,`REEMBOLSO_AJUSTE_CAJA` |
| `raw_json` | `jsonb NOT NULL` | **subconjunto allow-list** del pago, nunca el payload completo (D15) |
| `recibido_en` | `timestamptz NOT NULL` | primer recibo del `mp_payment_id` |
| `actualizado_en` | `timestamptz NOT NULL` | última notificación aplicada al registro |
| `aprobado_en` | `timestamptz NULL` | `date_approved` informado por MP |

- `UNIQUE (mp_payment_id)` es **global y sin RLS de por medio en el conflicto**: si T2 intenta
  registrar un pago ya visto en T1, el `INSERT ... ON CONFLICT (mp_payment_id) DO NOTHING` choca y
  la respuesta es `200` sin efecto. Es correcto: un mismo pago de MP no puede pertenecer a dos
  consultorios. **La unicidad global se garantiza con el `UNIQUE` de la tabla y `ON CONFLICT`,
  nunca con una lectura cross-tenant**; ninguna query de C-11 busca un pago sin `tenant_id`
  (F-04/F-05).
- `resultado=DUPLICADO` queda reservado al **mismo** `mp_payment_id` renotificado. Un **segundo pago
  distinto** sobre una seña que ya no está `PENDIENTE` es `PAGO_EXCEDENTE`; un pago con otro monto u
  otra moneda es `MONTO_DISTINTO`. Los tres son cosas distintas para operación y para la cola de
  devoluciones.
- `firma_verificada` **no** se persiste: sólo se llega al `INSERT` después de verificar la firma
  (D7), así que una columna que siempre vale `true` no distingue ningún caso (F-28).
- `estado` **no retrocede**: una notificación posterior con estado "menor" se guarda en
  `raw_json`/`actualizado_en` pero no degrada `APPROVED`. Se define un ranking
  `APPROVED > REFUNDED > IN_PROCESS > PENDING > REJECTED/CANCELLED` sólo para decidir si se
  actualiza la columna, nunca para revertir un efecto ya aplicado.
- `resultado` explica por qué una notificación válida no movió plata; sin esa columna, "no pasó
  nada" y "no pude asociar" son indistinguibles para operación.

Alternativas: (a) una fila por notificación → se pierde la clave de idempotencia; (b) guardar el
payload completo → PHI del pagador en la base; (c) una sola columna `estado` con valores propios →
se pierde el estado real de MP que operación necesita para hablar con el proveedor.

### D4 — Máquina de estados de la seña: quién dispara cada transición

```
                 webhook APPROVED (turno PENDIENTE, monto y moneda OK)
        ┌──────────────────────────────────────────────────────────────┐
        │                                                              ▼
   ┌───────────┐   job: expira_at <= ahora / cancelación       ┌──────────────┐
   │ PENDIENTE │─────────────────────────────────────────────► │   LIBERADA   │
   └───────────┘                                              └──────────────┘
        │                                                             │
        │ webhook APPROVED con turno CANCELADO/REPROGRAMADO           │ webhook APPROVED tardío
        ▼                                                             ▼
   ┌───────────┐   POST /api/senas/:id/aplicar (RECEPCION|ADMIN)  ┌──────────────┐
   │ ACREDITADA│─────────────────────────────────────────────────►│   APLICADA   │
   └───────────┘                                                  └──────────────┘
        │  cancelación con anticipación ≥ política (auto)
        │  o POST /api/senas/:id/devolver (ADMIN, motivo)
        ▼
   ┌───────────┐
   │  DEVUELTA │◄──── LIBERADA (pago tardío) — terminal
   └───────────┘
```

| Transición | Disparador | Guard | Efecto colateral | Idempotencia |
|---|---|---|---|---|
| `PENDIENTE → ACREDITADA` | webhook `APPROVED` | firma válida; `monto` y `ARS` coinciden; turno en `PENDIENTE` | turno `CONFIRMADO`; auditoría | renotificación del **mismo** pago: `resultado=DUPLICADO`, `200`, sin efecto |
| `PENDIENTE → LIBERADA` | worker de expiración | `expira_at <= ahora` | turno `CANCELADO` con motivo `SENA_NO_ACREDITADA`; `HuecoLiberadoPort.emitir` (C-07), todo en **una transacción** (D10) | segunda corrida: no encuentra filas `PENDIENTE` vencidas |
| `PENDIENTE → LIBERADA` | cancelación del turno (público o recepción) | turno cancelado | nada más (no se cobró) | idempotente por estado |
| `PENDIENTE → DEVUELTA` | webhook `APPROVED` | turno ya `CANCELADO`/`REPROGRAMADO` | obligación de devolución; **no** se toca el turno | renotificación del mismo pago: `DUPLICADO` |
| `LIBERADA → DEVUELTA` | webhook `APPROVED` tardío | — | obligación de devolución; **no** se reabre el turno | idem |
| `ACREDITADA → APLICADA` | `POST /api/senas/:id/aplicar` | día operativo abierto (C-10) y sin presupuesto aceptado vigente (`C11-OQ-13`) | movimiento `MP` vía C-10; `movimiento_caja_id` | segunda llamada: `409 SENA_YA_APLICADA`, cero movimientos nuevos |
| `ACREDITADA → DEVUELTA` | cancelación con anticipación ≥ política | seña `ACREDITADA` y turno cancelado con anticipación suficiente | obligación de devolución | idempotente por estado |
| `ACREDITADA → DEVUELTA` | `POST /api/senas/:id/devolver` | `ADMIN` + `motivo` no vacío | obligación de devolución | segunda llamada: `409` |
| `ACREDITADA → DEVUELTA` | webhook MP `REFUNDED` | seña `ACREDITADA` con ese `mp_payment_id` | `resultado=REEMBOLSADO`; obligación cerrada | idempotente por estado |
| `ACREDITADA → APLICADA` | aplicar con `concepto=CANCELACION_TARDIA` | decisión de `ADMIN` tras cancelación bajo el umbral | movimiento `MP` del turno | idem `APLICADA` |

**Segundo pago aprobado sobre una seña ya no `PENDIENTE`**: no cambia la seña y se registra con
`resultado=PAGO_EXCEDENTE`; deja **obligación de devolución** explícita en la misma cola que
`DEVUELTA` (`GET /api/senas`), porque entró plata que el consultorio no puede retener.

**Terminales**: `APLICADA` y `DEVUELTA`. Ninguna transición sale de ellas; un reintento responde
`409` con el código del estado actual. `LIBERADA` sólo puede ir a `DEVUELTA` (pago tardío) y nunca
vuelve a `PENDIENTE`/`ACREDITADA`: reabrir un turno ya liberado podría duplicar el hueco con una
oferta de C-07 en curso (`C11-OQ-07`).

Alternativas: (a) permitir `LIBERADA → ACREDITADA` si el hueco sigue libre → el turno pudo
ofertarse a lista de espera y se confirmaría un hueco ya comprometido (RN-GL-02: el último en
confirmar pierde); (b) un estado `RETENIDA` para la cancelación tardía → no está en el enum de
RN-SE-02 y agrega un estado sin regla; (c) `DEVUELTA` como borrador manual → deja la seña en limbo
(`07_flujos_principales.md:43`).

### D5 — Alta al reservar y puerto de pasarela (orden, caída de MP y backoff)

**Orden obligatorio** (elimina el "webhook antes de que exista la seña"):

1. C-06 crea el turno `PENDIENTE` (sin cambios).
2. C-11 resuelve la regla (D1); si `SIN_SENA` **no** crea nada y la reserva sigue como hoy.
3. C-11 crea la seña `PENDIENTE` con `monto_centavos`, snapshots, `expira_at` y `token_hash`, y
   **commitea**.
4. Recién después se pide la preferencia a la pasarela, en una transacción corta aparte que
   guarda `mp_preference_id`, `mp_init_point` y `preferencia_estado='CREADA'`.

La seña existe antes de que MP pueda notificar nada, así que el webhook siempre encuentra la fila.
Si el paso 4 falla, la seña queda `PENDIENTE`/`preferencia_estado='FALLIDA'` y la reserva
**existe**: MP caído no pierde el turno (RN-IN-03). El `200/201` de la reserva incluye
`sena.preferencia_estado='FALLIDA'` y `sena.token_sena` (el token opaco de D6), para que el
paciente abra `/pagar/:tokenSena` y reintente el pago.

**Puerto** `PasarelaPagosPort` (única frontera con la red):

```python
class PasarelaPagosPort(Protocol):
    def crear_preferencia(self, *, tenant_id: str, sena_id: str, turno_id: str,
                          monto_centavos: int, descripcion: str, expira_at: datetime,
                          url_pago: str, url_webhook: str) -> Preferencia: ...
    def obtener_pago(self, *, mp_payment_id: str) -> PagoExterno: ...
```

- `Preferencia(mp_preference_id, init_point)`; `PagoExterno(mp_payment_id, estado,
  monto_centavos, moneda, external_reference, metadata, aprobado_en)`.
- `AdaptadorPasarelaHTTP`: `POST https://api.mercadopago.com/checkout/preferences` y
  `GET https://api.mercadopago.com/v1/payments/{id}` con `Authorization: Bearer
  $MP_ACCESS_TOKEN`; la preferencia viaja con `external_reference=<sena_id>`,
  `metadata={sena_id, turno_id, tenant_id}`, `notification_url=<APP_URL>/api/webhooks/mercadopago`
  y `expires=true`/`expiration_date_to=expira_at` (el link muere con la seña; si MP rechaza la
  expiración, `expira_at` sigue mandando en nuestra base). Un `403/404` del pago se propaga como
  `PagoNoEncontrado`; timeouts y `5xx` como `PasarelaNoDisponible`.
- **Descripción neutra y fija** (`F-17`): `descripcion="Seña de turno"`. La preferencia **nunca**
  lleva el nombre de la prestación, del profesional ni ningún dato del paciente: el checkout de MP
  es una superficie de terceros y el título es visible para quien tenga el link.
- `AdaptadorPasarelaFake`: determinista, sin red, con preferencias y pagos programables
  (`aprobar(...)`, `rechazar(...)`, `demorar(...)`, `fallar(...)`). **Todos** los tests usan este
  adaptador; ningún test abre un socket (regla dura "sin credenciales reales").
- Selección: si `MP_ACCESS_TOKEN` está definido y `APP_ENV=production` → HTTP; en cualquier otro
  caso → fake. En production, `MP_ACCESS_TOKEN` o `MP_WEBHOOK_SECRET` ausentes **fallan el
  arranque** (extensión de `_production_secrets`, `backend/app/core/settings.py:65-80`).
- **Backoff del reintento** (`C11-OQ-05`, **provisional**): `intentos_preferencia` se incrementa en
  cada intento fallido y `proximo_reintento_at = ahora + min(2**intentos, 15) minutos`. El reintento
  es **on-demand**: `POST /api/publico/{tokenTenant}/senas/{token}/preferencia` responde `202` con
  `reintentar_en` mientras `proximo_reintento_at > ahora` y crea la preferencia cuando ya se puede.
  No hay scheduler propio de preferencias: no hay número en la KB que lo justifique y el paciente ya
  está en la página.
- **Guarda de vencimiento** (`F-09`): si `expira_at <= ahora`, `POST .../preferencia` responde
  `409 SENA_VENCIDA` **aunque** `estado` siga `PENDIENTE` y **no** llama a la pasarela. El `409` se
  decide antes de tocar la red: un link nuevo para una seña vencida sólo generaría plata que después
  hay que devolver.

Alternativas: (a) crear la preferencia antes de commitear la seña → un pago acreditado podría
llegar sin fila que acreditar; (b) bloquear la reserva cuando MP está caído → viola RN-IN-03 y
pierde el turno; (c) reintentar en background sin límite → martilla una API caída y no tiene
respaldo documental.

### D6 — Token de `/pagar/:tokenSena`: opaco, un solo vigente, atado a la expiración

- Token = `secrets.token_urlsafe(32)` (256 bits), **nunca** derivado de ids ni correlativo. Se
  persiste sólo `sha256(token)` en `senas.token_hash` (UNIQUE) y se busca por hash con
  comparación en tiempo constante del resultado del hash. El token en claro se entrega **una sola
  vez**, en la respuesta de la reserva (`sena.token_sena`); después sólo se acepta como path param.
- Un **solo token vigente por seña**. Regla (`F-16`): al **reprogramar**, si el token **no venció**
  (`expira_at > ahora` al momento de la transferencia) se **conserva el mismo token**; si venció o
  la seña se liberó, se **reemite** uno nuevo (nuevo `token_hash` + `token_rotado_en`) entregado una
  sola vez. No hay lista de tokens válidos: el anterior deja de existir. El token viejo de un turno
  viejo no puede pagar el turno nuevo sin pasar por esta regla.
- El token **no es un login** (PO-06 sigue abierta): no crea sesión, no identifica al paciente y
  no habilita ninguna otra ruta.
- **Unicidad global de `token_hash`**: la garantiza el `UNIQUE` de la tabla, nunca una lectura
  cross-tenant; `por_token` y `bloquear` reciben siempre `tenant_id`, y una colisión global se
  resuelve en el `INSERT` (mismo criterio que `mp_payment_id`, `F-05`).
- `GET /api/publico/{tokenTenant}/senas/{token}`: resuelve el tenant por el slug y el token por
  hash **dentro de ese tenant**; un token de otro tenant responde `404` idéntico al inexistente.
  Devuelve sólo `sena_id`, `estado`, `monto_centavos`, `expira_at`, `preferencia_estado`,
  `init_point` (sólo si `estado=PENDIENTE` y `expira_at > ahora`), `turno:{inicio,fin,prestacion}`
  y `politica:{anticipacion_cancelacion_h, reembolsable, hay_pago_acreditado}`. Nunca nombre,
  teléfono, DNI ni ids internos del paciente.
- Con `estado IN (LIBERADA, DEVUELTA, APLICADA)` o `expira_at <= ahora`: `200` con el estado y
  **sin** `init_point` (la página muestra el resultado; no se puede volver a pagar).
- `POST .../senas/{token}/preferencia`: misma resolución y **mismo rate-limit** que las demás rutas
  públicas (reusa `ContadorPort` de C-06, `F-30`); sólo actúa si `estado=PENDIENTE`,
  `expira_at > ahora` y `preferencia_estado='FALLIDA'` o no hay preferencia; si ya hay una vigente
  devuelve la misma (`200`) y **no** crea otra; si la seña venció, `409 SENA_VENCIDA` sin llamar a
  la pasarela (D5, `F-09`).

Alternativas: (a) token en claro → fuga de base = links de pago vivos; (b) JWT firmado con
`JWT_SECRET` → rota el secreto y mata todos los links vigentes, y un JWT de paciente es
exactamente el login que PO-06 no decidió; (c) token por `turno_id` → enumerable.

### D7 — Autenticidad del webhook: firma HMAC, sin secreto ⇒ fail-closed

`POST /api/webhooks/mercadopago` **no** tiene tenant en la ruta (MP notifica a una sola URL por
aplicación). La autenticidad se verifica con el mecanismo documentado por MP:

1. Leer `x-signature` (`ts=...,v1=...`), `x-request-id` y el `data.id` del **query string**
   (fallback: `body.data.id`).
2. Construir el manifiesto `id:{data.id};request-id:{x-request-id};ts:{ts};`.
3. `v1 == HMAC-SHA256(MP_WEBHOOK_SECRET, manifiesto)` en hexadecimal, comparado en **tiempo
   constante** (`hmac.compare_digest`).
4. Firma ausente o inválida ⇒ `401` y **nada** se persiste ni se procesa.

- **Sin `MP_WEBHOOK_SECRET` configurado** (dev/tests sin credenciales) el endpoint responde
  `503 WEBHOOK_NO_CONFIGURADO` y **nunca** acepta un payload sin firma. Fail-closed: un webhook de
  dinero no se procesa "porque estamos en dev". Los tests configuran un secreto **ficticio** por
  env, nunca uno real.
- **No se rechaza por antigüedad del `ts`**: no hay tolerancia en la KB y no hace falta, porque
  el efecto es idempotente y la fuente de verdad se re-consulta (paso 5). Inventar una ventana
  sólo agregaría un número sin respaldo y una causa de fallo silenciosa.
- **Re-consulta obligatoria**: el cuerpo de la notificación sólo aporta el id. El estado, el monto,
  la moneda y la metadata se leen con `GET /v1/payments/{id}` usando nuestro token: nadie puede
  "declarar" un pago aprobado enviando un JSON. **La metadata se considera confiable por la
  re-consulta, no por la firma** (`F-26`): la firma prueba que la notificación vino de MP, pero el
  `tenant_id`/`sena_id` que se usan son los que devuelve la API, no los del cuerpo ni los de un
  header. Si MP no responde, `503` (MP reintenta).
- Tipo de notificación: sólo se procesa `type=payment` (o `topic=payment`). Cualquier otro tipo se
  verifica y se responde `200` sin tocar nada.

Códigos de respuesta (contrato):

| Situación | Código | Efecto |
|---|---|---|
| Firma inválida o ausente | `401` | nada |
| Sin secreto configurado | `503` | nada (fail-closed) |
| No es `payment` | `200` | nada |
| Mismo `mp_payment_id` ya procesado | `200` | `resultado=DUPLICADO`, sin efecto |
| Pago ya registrado con otro estado/monto | `200` | se actualiza `raw_json`/`estado` sin revertir efectos |
| Pago distinto sobre seña ya no `PENDIENTE` | `200` | `resultado=PAGO_EXCEDENTE` + obligación de devolución |
| Pago válido que no se puede asociar a una seña del tenant | `500` | nada persistido; **log estructurado** con ids (no es auditoría: no hay actor ni entidad); MP reintenta |
| MP no disponible al re-consultar | `503` | nada; MP reintenta |

Alternativas: (a) confiar en el body → cualquiera con la URL acredita señas; (b) validar sólo por
IP de MP → las IPs cambian y no está en la KB; (c) `200` para todo → se pierden pagos reales sin
dejar rastro.

### D8 — Idempotencia del webhook: mismo pago, pagos distintos, desordenado y reembolso

Algoritmo del handler, en una transacción:

1. Verificar firma (D7) y filtrar tipo.
2. Resolver el pago por id (`obtener_pago`). Sin respuesta de MP → `503`.
3. Resolver tenant y seña desde la **respuesta de MP** (`metadata.tenant_id` +
   `external_reference`/`metadata.sena_id`), nunca desde headers ni desde el cuerpo sin re-consultar
   (`F-26`). Validar que la seña pertenece a ese tenant (RLS + filtro explícito); si no resuelve →
   `500` (D7).
4. `SELECT ... FOR UPDATE` sobre la seña (punto único de serialización, D11).
5. `INSERT ... ON CONFLICT (mp_payment_id) DO NOTHING` en `pagos_mp`; si la fila ya existía **es el
   mismo pago** y se actualiza `estado` (sólo si el ranking sube, D3), `raw_json` minimizado y
   `actualizado_en`.
6. **Mismo `mp_payment_id` ya aplicado** ⇒ `resultado=DUPLICADO`, `200`, sin efecto. `DUPLICADO`
   **sólo** significa renotificación del mismo pago, jamás "segundo pago sobre la misma seña".
7. **Pago distinto** (`mp_payment_id` nuevo) que entra en conflicto con el estado de la seña:
   - Monto o moneda distintos a los de la seña ⇒ `resultado=MONTO_DISTINTO`, la seña no cambia,
     `200`, y queda **obligación de devolución** visible en `GET /api/senas` (entró plata que no
     corresponde a esta seña).
   - Seña en `ACREDITADA`/`APLICADA`/`DEVUELTA` ⇒ `resultado=PAGO_EXCEDENTE`, la seña no cambia,
     `200`, y queda la misma obligación de devolución. Nunca se acredita dos veces ni se responde
     `DUPLICADO`.
8. **Aplicar el efecto sólo si `estado='APPROVED'`**, monto y moneda coinciden y la seña está en
   `PENDIENTE`/`LIBERADA`. Transición condicional con `UPDATE ... WHERE estado = <esperado>`:
   - `PENDIENTE` + turno `PENDIENTE` → `ACREDITADA` + turno `CONFIRMADO`.
   - `PENDIENTE` + turno no confirmable → `DEVUELTA` (`resultado=TURNO_NO_CONFIRMABLE`).
   - `LIBERADA` → `DEVUELTA` (`resultado=FUERA_DE_TIEMPO`).
9. Estado distinto de `APPROVED` (`PENDING`, `IN_PROCESS`, `REJECTED`, `CANCELLED`) ⇒ se registra la
   fila con `resultado=IGNORADO` y la seña no cambia.
10. **`REFUNDED` de MP** (`F-18`): se registra con su **propio** resultado y sí mueve la seña cuando
    corresponde:
    - Seña `ACREDITADA` ⇒ `DEVUELTA` con `resultado=REEMBOLSADO` (la obligación se cerró por API de
      MP; `devuelta_por=NULL`, `motivo_devolucion='REEMBOLSO_MP'`).
    - Seña `APLICADA` ⇒ **no** se revierte el estado; `resultado=REEMBOLSO_AJUSTE_CAJA` y queda un
      ajuste de caja pendiente de `ADMIN` (anulación con motivo en C-10), visible en `GET /api/senas`.
    - Seña `PENDIENTE`/`LIBERADA` ⇒ `resultado=IGNORADO` (no había plata nuestra).

**Desorden**: (a) `PENDING` después de `APPROVED` → no degrada el estado y no des-acredita;
(b) webhook antes de que se persista `mp_preference_id` → irrelevante, la clave del handler es
`sena_id` + `mp_payment_id`, nunca la preferencia (D5 garantiza que la seña existe antes);
(c) reintentos de MP con el mismo `mp_payment_id` → `DUPLICADO` sin efecto.

**Concurrencia**: dos webhooks simultáneos del mismo pago compiten por el `UNIQUE` y por el
`FOR UPDATE`; uno acredita, el otro lee `ACREDITADA` y responde `DUPLICADO`. Nunca hay dos
movimientos ni dos transiciones (test con dos conexiones reales, D16).

Alternativas: (a) idempotencia por `mp_preference_id` → una preferencia puede generar varios pagos
legítimos; (b) "si ya está ACREDITADA, re-aplicar" → duplicaría el movimiento de caja al aplicar;
(c) descartar notificaciones no aprobadas → se pierde la traza de un intento rechazado que
operación necesita ver; (d) responder `DUPLICADO` a un pago distinto → operación nunca se entera de
la plata que hay que devolver.

### D9 — Aplicación al cobro: movimiento `MP` creado con el alta de C-10

La seña acreditada se aplica al tratamiento (RN-SE-04) y esa plata **es caja**: el Flujo 5 lista
"señas aplicadas" en la consulta del día (`07_flujos_principales.md:48`) y C10-OQ-6 fija que el
movimiento `MP` lo crea **C-11** con el alta de C-10 (`docs/decisiones-po.md:129`).

`POST /api/senas/{id}/aplicar` (`RECEPCION`/`ADMIN`; `concepto=CANCELACION_TARDIA` sólo `ADMIN`):

1. Abrir la unidad de trabajo externa: `TransaccionSQL(session)`
   (`backend/app/core/transaccion.py:31-73`).
2. `SELECT ... FOR UPDATE` sobre la seña; exigir `estado='ACREDITADA'` (si no, `409` con el estado).
3. **Guarda de presupuesto** (`C11-OQ-13`, `F-12`): consultar con
   `PresupuestosPort.aceptado_vigente(tenant_id, paciente_id, ahora)` si el paciente del turno tiene
   un presupuesto `ACEPTADO` vigente (`vence_en` nulo o futuro, C-09). Si existe ⇒
   `409 PRESUPUESTO_CON_SENA` sin crear movimiento: el descuento automático de la seña contra el
   presupuesto queda **fuera de v1**, y aplicar sin descontar cobraría dos veces el mismo tramo.
4. Delegar en `AplicacionCajaPort.registrar_ingreso_mp(tenant_id, turno_id, monto_centavos, fecha,
   actor_id, concepto)`; el adaptador (`app/senas/adaptador_caja.py`) implementa el puerto llamando
   a `ServicioCaja.registrar_movimiento` con `uow_factory=lambda: TransaccionSQL(session)`:
   - `medio='MP'`, `tipo='INGRESO'`, `origen='MANUAL'` (C-10 no tiene `origen=SENA` y C-11 no
     cambia su enum), `turno_id=<turno de la seña>`, `usuario_id=<actor>`.
   - **`fecha` = el día de la aplicación** en offset `-03:00`, no la fecha del turno ni la de la
     acreditación (`F-13`): la plata entra a la caja del día en que se aplica.
   - C-10 toma `pg_advisory_xact_lock(hashtext(tenant||':'||fecha))`, valida el día y rechaza
     `409 CIERRE_CERRADO` si ese día está cerrado (C-10 D14). C-11 **no** reimplementa nada de eso.
5. Guardar `movimiento_caja_id`, `estado='APLICADA'`, `aplicada_en`, `concepto_aplicacion`.
6. Auditar `SENA_APLICADA` con el `movimiento_id`; commit de la transacción externa.

Consecuencias declaradas:

- **Un solo movimiento**: el `409` de estado y la transacción única impiden dos `INGRESO` por la
  misma seña; el UNIQUE parcial de `senas.movimiento_caja_id` lo impide incluso en la base.
- **Día cerrado** ⇒ `409 CIERRE_CERRADO`, **sin movimiento** y la seña sigue `ACREDITADA` (no se
  pierde nada; se aplica el día siguiente, cuando esté abierto). C-11 **no** crea compensatorios: no
  hay nada que compensar.
- **Presupuesto aceptado vigente** ⇒ `409 PRESUPUESTO_CON_SENA`, sin movimiento y sin cambio de
  estado; la seña se aplica cuando exista el descuento automático (`C11-OQ-13`) o cuando el
  presupuesto deje de estar vigente.
- **C-10 no se toca**: no se agregan columnas ni valores a `movimientos_caja`; la trazabilidad
  seña↔movimiento vive en `senas.movimiento_caja_id`. `specs/caja` y `specs/cierre-caja` no cambian.
- **Orden de locks**: siempre seña → día. Ningún camino toma el día antes de la seña, así que no
  hay ciclo de deadlock con las altas manuales de caja (que sólo toman el día).
- **Un `APLICADA` por seña**; una seña aplicada no se devuelve (si hay que devolver plata después
  del cobro, es una anulación con motivo en caja, que ya es de C-10/ADMIN).

Alternativas: (a) escribir `movimientos_caja` directo desde C-11 → duplica reglas de cierre y
rompe C10-OQ-6; (b) agregar `origen='SENA'` a C-10 → cambio de contrato ajeno sin necesidad;
(c) aplicar automáticamente al acreditar → el paciente pagó, pero el tratamiento puede no ocurrir;
la aplicación es un acto de recepción.

### D10 — Expiración: worker, reloj inyectado y `min(TTL, inicio)`

- `expira_at = min(ahora + SENA_TTL_H horas, turno.inicio)`. `SENA_TTL_H` ya existe en la KB con
  ejemplo `24` (`08_arquitectura_propuesta.md:56`); el tope por `turno.inicio` es la misma regla
  que C-07 aplica a las ofertas (`worker.py:168`) y evita una seña viva para un turno que ya
  pasó (`C11-OQ-08`).
- `ServicioSenasExpulsion` (dominio puro, espejo de `ServicioAutoOferta`):
  `procesar_expiraciones(tenant_id, ahora=None) -> list[Sena]`.
  1. Lista señas `PENDIENTE` **del tenant recibido** con `expira_at <= ahora`; nunca barre otro
     tenant (`F-20`).
  2. Por cada una: `SELECT ... FOR UPDATE`; revalidar `estado='PENDIENTE'` y `expira_at <= ahora`.
  3. `estado='LIBERADA'`, `liberada_en`, `motivo_liberacion='EXPIRACION'`.
  4. Turno `PENDIENTE → CANCELADO` con motivo `SENA_NO_ACREDITADA` (transición de C-05, vía
     `TurnoPort`); si el turno ya no está `PENDIENTE` (reprogramado/cancelado), se libera la seña
     igual y no se toca el turno.
  5. `HuecoLiberadoPort.emitir(tenant_id, turno_id)` — **el mismo** evento que usa C-06 al
     cancelar; C-07 hace la oferta. C-11 no reimplementa compatibilidad, orden ni expiración de
     ofertas.
  6. Auditar `SENA_LIBERADA` con motivo y `auto_oferta_emitida=true|false`.
- **Atomicidad del release** (`F-14`): los pasos 2–5 corren en **una sola transacción** por seña.
  `LIBERADA` + turno `CANCELADO` + emisión del hueco commitean juntos; si la emisión a C-07 falla, se
  hace **rollback completo**: la seña sigue `PENDIENTE` y el próximo barrido la vuelve a tomar. Nunca
  queda un turno cancelado sin evento de hueco ni una seña liberada con el turno vivo. El
  `HuecoLiberadoPort` es idempotente por `auto_oferta:{turno_id}`, así que reintentar el barrido es
  seguro.
- **Idempotencia**: la segunda corrida no encuentra filas `PENDIENTE` vencidas; el `HuecoLiberadoPort`
  es idempotente por `auto_oferta:{turno_id}` aunque se emitiera dos veces.
- **Reloj inyectado** en el worker y en el servicio; ningún test duerme.
- **Disparador del worker** (`F-15`): el barrido **no corre solo**. `tasks.md` incluye el wiring al
  runner de workers (cron/Redis, DD-08) como tarea y como **dependencia operativa** del change: sin
  ese registro, una seña vencida no libera el turno y RN-SE-01 no se cumple en producción. El
  intervalo es configuración del runner, no del dominio (`C11-OQ-08`); C-11 no inventa un número y
  documenta el contrato `procesar_expiraciones(tenant_id, ahora)`.
- Multi-tenant: el worker se invoca por tenant, igual que C-07 (`worker.py:68-74`). El barrido de
  tenants es del runner, no del dominio; el dominio **exige** `tenant_id` y no tiene una variante
  global (`F-20`).

Alternativas: (a) liberar en el momento de la lectura → un GET público mutaría estado;
(b) `expira_at = ahora + TTL` sin tope → seña pagable para un turno que ya empezó; (c) liberar sin
emitir el hueco → el turno queda `CANCELADO` y el slot no se reoferta (rompe RN-RE-04).

### D11 — Carreras: acreditación vs expiración, dos webhooks, y dos reservas con seña

El punto de serialización es **la fila de la seña** (`SELECT ... FOR UPDATE`) más transiciones
condicionales (`UPDATE ... WHERE estado = <esperado>`). No se usan timestamps para decidir quién
gana: gana la primera transacción que **commitea**.

| Carrera | Garantía | Cómo |
|---|---|---|
| Webhook acredita vs job expira, mismo segundo | exactamente una transición desde `PENDIENTE` | ambas toman `FOR UPDATE` sobre la seña y revalidan; la perdedora ve el estado nuevo y no escribe |
| Dos webhooks del mismo `mp_payment_id` | un `PagoMP`, una acreditación | `UNIQUE (mp_payment_id)` + `FOR UPDATE`; la segunda responde `DUPLICADO` |
| Dos webhooks de pagos distintos sobre la misma seña | una sola acredita; la otra queda con obligación de devolución | `FOR UPDATE` + guard de estado (D8): `MONTO_DISTINTO` si el monto o la moneda difieren, `PAGO_EXCEDENTE` si coinciden |
| Expiración commitea primero y el webhook llega después | el webhook responde `200` con `resultado=FUERA_DE_TIEMPO`; **nunca** `DUPLICADO`, **nunca** `500`, y no emite un segundo evento | la seña ya está `LIBERADA`; la transición condicional no escribe y el resultado se decide por el estado leído **después** del `FOR UPDATE` (`F-08`) |
| Dos `aplicar` simultáneos | un único movimiento `MP` | `FOR UPDATE` + guard `ACREDITADA` + UNIQUE de `movimiento_caja_id` |
| `aplicar` vs cierre del día | o el movimiento entra antes y el cierre lo cuenta, o el cierre gana y `aplicar` da `409 CIERRE_CERRADO` | lock de C-10 por `(tenant, fecha)` dentro de la misma transacción |
| Dos reservas compitiendo por el mismo turno con seña | un turno, una seña | el anti-solape de C-05 rechaza la segunda **antes** de crear la seña (`reservas/servicio.py:369-373`); si la seña ya se creó, la transacción revierte con el turno |
| Reprogramación vs webhook | la seña vive atada al turno vigente | el handler lee `senas.turno_id` **después** del `FOR UPDATE`, nunca el `turno_id` de la metadata |

Todo esto se prueba con **dos conexiones reales de PostgreSQL** (`C02_DATABASE_URL`), no con
adaptadores en memoria: los locks no existen en memoria y un test con fakes no prueba nada.

### D12 — Cancelación, reprogramación y política visible

**Política visible al reservar** (RN-SE-04, `F-01`): la respuesta de reserva y la página de pago
exponen `politica = {anticipacion_cancelacion_h: int, reembolsable: bool,
hay_pago_acreditado: bool}`.

- `anticipacion_cancelacion_h` es el **snapshot** guardado en la seña al crearla (tomado de
  `CANCEL_ANTICIPACION_H`, 24 h **provisional** según PO-01 sub-decisión,
  `docs/decisiones-po.md`; ya es el default de C-05/C-06). Un cambio de configuración no reescribe lo
  que se prometió, y **C-06 usa ese mismo snapshot** para autorizar la cancelación de un turno con
  seña (`F-19`): una sola fuente de verdad para la elegibilidad.
- `reembolsable` es **la promesa**, no el estado: vale `true` **desde la creación** de la seña, cuando
  la política promete devolución con anticipación suficiente. **No** depende de que la seña esté
  `ACREDITADA`; si dependiera, la reserva mostraría "no se devuelve" justo antes de pagar y la
  promesa quedaría invertida.
- `hay_pago_acreditado` es el hecho actual: `true` sólo cuando la seña está `ACREDITADA` (hay plata
  retenida bajo la promesa). En `PENDIENTE`, `LIBERADA` y `DEVUELTA` es `false`; en `APLICADA`
  también, porque la plata ya está en caja y corregirla es una anulación de C-10.
- El texto de la pantalla se deriva de esos tres datos; ningún copy se inventa por pantalla.

**Cancelación** (C-06 ya valida la anticipación usando el snapshot; C-11 agrega el efecto sobre la
seña):

| Caso | Seña | Turno | Notas |
|---|---|---|---|
| Anticipación ≥ umbral, seña `PENDIENTE` | `LIBERADA` (`motivo=CANCELACION`) | `CANCELADO` (C-06) | no se cobró nada |
| Anticipación ≥ umbral, seña `ACREDITADA` | `DEVUELTA` (`motivo_devolucion='POLITICA_CANCELACION'`, `devuelta_por=NULL`) | `CANCELADO` | obligación explícita, nunca limbo |
| Anticipación ≥ umbral, seña `APLICADA` | sin cambio | `CANCELADO` | la plata ya está en caja; devolver es anulación de C-10 (ADMIN) |
| Por debajo del umbral, seña `ACREDITADA` | queda `ACREDITADA` | `CANCELADO` sólo por recepción (C-06 `403` público) | decide **un humano** `ADMIN`: `DEVUELTA` con motivo o `APLICADA` con `concepto=CANCELACION_TARDIA` (`C11-OQ-03`, fijada 2026-11-13) |

**Devolución**: `POST /api/senas/{id}/devolver` sólo `ADMIN`, `motivo` no vacío, sólo desde
`ACREDITADA` (o desde `LIBERADA` en el pago tardío, que se resuelve solo por webhook). v1 **no**
llama a la API de reembolsos (`C11-OQ-09`, fijada 2026-11-13): `DEVUELTA` registra la obligación y el
reintegro se ejecuta en el panel de MP; **requiere un responsable operativo asignado** (proposal
§Governance). La misma cola (`GET /api/senas`) muestra `DEVUELTA`, `MONTO_DISTINTO`,
`PAGO_EXCEDENTE` y `REEMBOLSO_AJUSTE_CAJA` para que ninguna obligación quede invisible. La
conciliación de esa devolución queda fuera de v1 (`11_integraciones.md:10`).

**Reprogramación** (`C11-OQ-04`, fijada 2026-11-13): la seña acompaña a la reserva. Con anticipación
suficiente, C-06 crea el turno nuevo y C-11 **transfiere** la seña:
`UPDATE senas SET turno_id=<nuevo>` y, si estaba `PENDIENTE`, `expira_at = min(ahora + TTL,
nuevo.inicio)`, acotado al inicio del turno nuevo. **Token** (`F-16`): si no venció se conserva el
mismo; si venció o la seña se había liberado, se reemite uno nuevo (D6). Si estaba
`APLICADA`/`DEVUELTA`, no se transfiere y el turno nuevo no exige una segunda seña (ya está paga o ya
se devolvió), lo que se registra en la auditoría como `SENA_NO_TRANSFERIDA`. Bajo el umbral no hay
reprogramación pública (`403`), así que no hay caso de "mover una seña para escaparse de la
política".

Alternativas: (a) devolver siempre → el paciente puede reservar y cancelar gratis, y la seña deja
de prevenir el no-show; (b) no devolver nunca → viola RN-SE-04 y la política visible; (c) devolver
automático por API de MP → fuera de v1 y sin credenciales; (d) reprogramar creando una seña nueva →
el paciente paga dos veces y hay que devolver una.

### D13 — Superficie HTTP y RBAC

| Método y ruta | Quién | Códigos |
|---|---|---|
| `POST /api/publico/{tokenTenant}/reservas` (C-06, extendida) | público | `201` con bloque `sena` opcional; `403`/`409`/`422`/`429` como hoy |
| `GET /api/publico/{tokenTenant}/senas/{token}` | público (token) | `200`; `404` uniforme |
| `POST /api/publico/{tokenTenant}/senas/{token}/preferencia` | público (token) | `200` (ya existe), `202` (backoff), `201` (creada), `404`, `409 SENA_VENCIDA`, `429` |
| `POST /api/webhooks/mercadopago` | MP (firma) | `200`, `401`, `500`, `503` |
| `GET /api/senas?desde=&hasta=` | ODONTOLOGO `R`, RECEPCION, ADMIN | `200`; `403` sin rol; `401` identidad de paciente |
| `GET /api/senas/{id}` | idem | `200`; `404` cross-tenant |
| `POST /api/senas/{id}/aplicar` | RECEPCION, ADMIN (`concepto=CANCELACION_TARDIA`: sólo ADMIN) | `200`; `403`; `409 SENA_YA_APLICADA`/`CIERRE_CERRADO`/`ESTADO_INVALIDO`/`PRESUPUESTO_CON_SENA`; `404` |
| `POST /api/senas/{id}/devolver` | **sólo ADMIN** | `200`; `403`; `409`; `422` sin motivo; `404` |

- La matriz de `03_actores_y_roles.md:24` da "Caja / señas / cierre" a Recepción (CRUD) y a Admin
  "CRUD + anular con motivo": la devolución queda en **ADMIN**, con el mismo criterio que
  `C10-OQ-9` para anular movimientos. `ODONTOLOGO` sólo lee.
- **Excepción de `ADMIN` en `aplicar`** (`F-29`): `RECEPCION` aplica con
  `concepto=TRATAMIENTO`; `concepto=CANCELACION_TARDIA` (plata de un turno cancelado bajo el umbral)
  es una decisión de anulación y exige `ADMIN`, igual que devolver. Sin la excepción, recepción
  podría convertir una cancelación tardía en ingreso sin que nadie lo autorice.
- Identidad de paciente en rutas internas ⇒ `401` (DD-06/DD-07; `NoAutenticado`,
  `turnos/servicio.py:99-107`).
- **Seña visible en agenda** (RN-SE-02, `C11-OQ-10` fijada 2026-11-13): endpoint **propio**
  `GET /api/senas?desde=&hasta=`, sin tocar el payload de `GET /api/turnos`. El filtro es sobre
  **`turno.inicio`** (rango `[desde, hasta)`, ambos `timestamptz` en `-03:00`): `desde`/`hasta`
  acotan los turnos, no `senas.creado_en` ni `expira_at`, porque la agenda se consulta por franja de
  atención. Sin `desde`/`hasta` se aplica un rango por defecto del día operativo vigente. La UI
  futura une por `turno_id`.
- **Rate-limit en rutas públicas** (`F-30`): `GET .../senas/{token}` y
  `POST .../senas/{token}/preferencia` usan el mismo `ContadorPort` de C-06, con la misma ventana y
  el mismo `429`; el token no exime del límite y el webhook no lo usa (no es público).
- Sin rutas de reembolso automático, de conciliación ni de re-creación de preferencia por API
  interna: si se piden, son un change nuevo.

Alternativas: (a) agregar `sena` al payload de turnos → cambio de contrato de C-05 sin necesidad;
(b) dejar `aplicar` sólo en ADMIN → recepción es quien cobra en el mostrador; (c) permitir
devolución a recepción → mueve plata sin el rol que la matriz reserva para "anular con motivo".

### D14 — Migración 009: tablas nuevas, columnas de override y backfill conservador

`009_senas_mercadopago.py`, `down_revision = "008_caja_cierre_diario"`.

| Objeto | Contenido |
|---|---|
| `senas` | columnas y CHECKs de D2; `UNIQUE (tenant_id, turno_id)`; UNIQUE parcial `(tenant_id, mp_preference_id) WHERE mp_preference_id IS NOT NULL`; UNIQUE parcial `(tenant_id, movimiento_caja_id) WHERE movimiento_caja_id IS NOT NULL`; `UNIQUE (token_hash)` **global** (un token no puede existir en dos tenants); índice `(tenant_id, estado, expira_at)` para el job; `(tenant_id, turno_id)`; `(tenant_id, creado_en)` |
| `pagos_mp` | columnas y CHECKs de D3; `UNIQUE (mp_payment_id)` **global** (RN-SE-03); `UNIQUE (tenant_id, sena_id, mp_payment_id)` redundante **no** se agrega; índice `(tenant_id, sena_id)` y `(tenant_id, recibido_en)` |
| `prestaciones` | `sena_modo TEXT NULL` `CHECK IN ('SIN_SENA','PORCENTAJE','MONTO_FIJO')`; `sena_valor INTEGER NULL` `CHECK >= 0`; `CHECK (sena_modo <> 'SIN_SENA' OR sena_valor IS NULL)`; `CHECK (sena_modo IS NULL OR sena_modo = 'SIN_SENA' OR sena_valor IS NOT NULL)` |

- **RLS forzada fail-closed** en `senas` y `pagos_mp`, idéntica a 006/007/008:
  `USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)` y el mismo
  predicado en `WITH CHECK`. `NULLIF` evita el `42704` y devuelve 0 filas sin excepción.
- **Grants**: `senas` `SELECT, INSERT`; `REVOKE DELETE`; `GRANT UPDATE` sólo de
  (`estado`,`acreditada_en`,`aplicada_en`,`liberada_en`,`devuelta_en`,`motivo_liberacion`,
  `concepto_aplicacion`,`devuelta_por`,`motivo_devolucion`,`movimiento_caja_id`,
  `mp_preference_id`,`mp_init_point`,`preferencia_estado`,`intentos_preferencia`,
  `proximo_reintento_at`,`token_hash`,`token_rotado_en`). `pagos_mp` `SELECT, INSERT` y `GRANT
  UPDATE (estado, resultado, raw_json, actualizado_en, aprobado_en)`; `REVOKE DELETE` en ambas.
- **Backfill conservador de las columnas legacy** (no se inventa configuración):
  `prestaciones.sena_modo='MONTO_FIJO', sena_valor=monto_sena` **sólo** donde
  `requiere_sena = true AND monto_sena IS NOT NULL AND monto_sena > 0`.
  `requiere_sena = true AND (monto_sena IS NULL OR monto_sena <= 0)` queda en `NULL` (hereda del
  tenant) y se reporta en el upgrade como fila a revisar (`RAISE NOTICE`), porque inventar un
  monto sería peor que heredar. `requiere_sena = false` queda en `NULL`: no se puede distinguir
  "default del schema" de "decisión explícita", y el resultado efectivo sigue siendo `SIN_SENA`
  mientras el tenant no configure un default (D1 regla 3).
- **`requiere_sena`/`monto_sena` quedan como legacy de sólo lectura**: C-11 no las lee ni las
  escribe; se eliminan en un change de limpieza posterior. No se agrega un CHECK que las relacione
  con las columnas nuevas (sería una tercera verdad).
- `tenant_parametros` **no** se altera: las claves `sena_modo`/`sena_valor` son datos, no DDL (D1).
- `downgrade()`: elimina `senas` y `pagos_mp` (con sus políticas) y las cuatro constraints/columnas
  nuevas de `prestaciones`; no toca 001–008, `movimientos_caja`, `tenant_parametros`, `turnos` ni
  `prestaciones.requiere_sena`/`monto_sena`.
- **No** se crean `obras_sociales`, `coberturas`, `liquidaciones` (C-12) ni `mensajes_wa` (C-13).

**Desviaciones del ERD documentadas** (`04_modelo_de_datos.md:68-70`): ver `proposal.md`
§Desviaciones del ERD. Se reconcilian con Martin.

### D15 — Auditoría append-only y ausencia de PHI

Acciones auditadas con el `AuditoriaPort` existente (C-03/C-08, RN-AU-02), con `antes`/`después`:

| Acción | Cuándo | Datos (sin PHI) |
|---|---|---|
| `SENA_CREADA` | al reservar con seña | `sena_id`, `turno_id`, `monto_centavos`, `regla_modo`, `regla_valor`, `expira_at` |
| `SENA_PREFERENCIA_CREADA` | preferencia OK | `sena_id`, `mp_preference_id`, intento |
| `SENA_PREFERENCIA_FALLIDA` | MP caído | `sena_id`, intento, `motivo` de dominio (sin payload del proveedor) |
| `SENA_ACREDITADA` | webhook aprobado | `sena_id`, `mp_payment_id`, `monto_centavos`, `antes=PENDIENTE`, `despues=ACREDITADA` |
| `SENA_LIBERADA` | job o cancelación | `sena_id`, `motivo_liberacion`, `turno_id`, `auto_oferta_emitida` |
| `SENA_APLICADA` | aplicar | `sena_id`, `movimiento_caja_id`, `monto_centavos`, `concepto_aplicacion` |
| `SENA_DEVUELTA` | devolución manual o por política | `sena_id`, `motivo_devolucion`, actor (`NULL` = sistema), `antes`, `despues` |
| `SENA_REEMBOLSO_MP` | webhook `REFUNDED` | `sena_id`, `mp_payment_id`, `resultado`, `antes`, `despues` |
| `SENA_TRANSFERIDA` | reprogramación | `sena_id`, `turno_anterior`, `turno_nuevo`, `token_reemitido=true|false` |
| `SENA_WEBHOOK_RECHAZADO` | firma inválida o no asociable | ids y motivo de dominio; nunca el cuerpo recibido |

Nunca se registran nombre, DNI, teléfono, texto clínico, email del pagador ni el link de pago.
`raw_json` guarda **sólo** `{id, status, status_detail, transaction_amount, currency_id,
date_approved, external_reference, metadata.sena_id, metadata.turno_id, metadata.tenant_id}`; el
resto del payload de MP (pagador, tarjeta, cuotas, `payer.email`) se descarta antes de persistir
(`C11-OQ-11`). Los logs llevan `tenant_id`, `sena_id`, `mp_payment_id`, `monto_centavos`, `estado`
y códigos de dominio; nunca el token ni datos del pagador.

**Log estructurado vs auditoría** (`F-25`): la auditoría es append-only con actor y entidad
(`AuditoriaPort`), y sólo se escribe cuando hay una mutación o un rechazo atribuible a una seña. El
caso `500` de un pago **no asociable** no tiene entidad ni actor de tenant: se registra en el **log
estructurado** con `tenant_id` de la metadata (si vino), `mp_payment_id`, `motivo` y nivel `error`;
no se inventa una fila de auditoría ni se persiste el pago. Los rechazos de firma sí se auditan
porque hay un tenant resoluble (`SENA_WEBHOOK_RECHAZADO`).

### D16 — Estrategia de tests (TDD rojo primero, tres niveles)

1. **Dominio puro (sin DB ni red, `AdaptadorPasarelaFake` + reloj inyectado)**: resolución de la
   regla (override, herencia, default, configuración inválida), monto por porcentaje/monto fijo,
   creación de seña, `expira_at` acotado, caída de MP y backoff, preferencia vencida (`409
   SENA_VENCIDA`), cada transición de D4 con su guard, webhook (firma, mismo pago duplicado, pagos
   distintos, desordenado, monto distinto, moneda distinta, `REFUNDED`, turno no confirmable, pago
   tardío), token (hash, rotación, expirado, reemisión), expiración + emisión a C-07 con rollback
   ante fallo parcial, aplicación + movimiento vía puerto espía, presupuesto aceptado vigente,
   devolución, RBAC, auditoría y PHI.
2. **PostgreSQL real con dos conexiones independientes**: (a) dos webhooks del mismo pago ⇒ una
   acreditación, un `PagoMP`; (b) webhook vs job de expiración en ambos órdenes ⇒ una sola
   transición y la perdedora responde `200` de forma determinista (si gana el webhook, `ACREDITADA`;
   si gana la expiración, `FUERA_DE_TIEMPO`), nunca `DUPLICADO` ni `500`; (c) dos `aplicar` ⇒ un
   movimiento; (d) `aplicar` vs cierre del mismo día ⇒ o entra antes y el cierre lo cuenta, o `409
   CIERRE_CERRADO` sin movimiento huérfano; (e) dos reservas del mismo hueco con seña ⇒ un turno y
   una seña; (f) reprogramación vs webhook ⇒ la seña queda atada al turno que corresponde; (g) el
   barrido de T1 no toca señas de T2.
3. **Migración real (PostgreSQL de test)**: 009 upgrade/downgrade/re-upgrade, CHECKs, UNIQUE
   (turno por tenant, `mp_payment_id` y `token_hash` **globales**, `movimiento_caja_id`), RLS
   fail-closed (0 filas sin `42704`), grants por columna, backfill legacy en sus tres casos, y
   `prestaciones.requiere_sena` intacta.

**Gate de suite**: `py -m pytest tests/ -q` con `C02_DATABASE_URL` apuntando a PostgreSQL migrado y
**`skipped == 0`**; sin la variable el gate falla explícitamente (no se acepta un verde con tests
de integración salteados). Además `py -m mypy backend/app/senas` (config `strict`) y
`openspec validate c-11-senas-mercadopago --strict`.

**Ningún test llama a la red**: `AdaptadorPasarelaHTTP` no se instancia en tests; el secreto de
webhook de los tests es ficticio. Cada escenario de los specs tiene una tarea con el nombre exacto
del test en `tasks.md`.

Datos ficticios: "Paciente Demo", "Otro Paciente Demo", PACI-1/PACI-9, "Conducto Demo", usuarios
U1 (RECEPCION), U2 (ADMIN), U3 (ODONTOLOGO); montos ficticios (`precio_base=10000`, `30%` ⇒
`3000`). Reloj siempre inyectado; instantes en `-03:00`.

### D17 — UI diferida a `C-11-UI`

El repo exige sistema de diseño aprobado antes de UI y no hay `design-system/README.md` (modo
`deferred`). C-11 v1 es backend + contratos + migración 009 + tests: no hay mockups, no se toca
`frontend/` y las delta specs no declaran requirements de UI. `/pagar/:tokenSena` consume
`GET .../senas/{token}`; la agenda muestra el estado con `GET /api/senas`. Crear `C-11-UI` es una
decisión pendiente del dueño, igual que `C-10-UI`.

## Seams

```python
# --- C-05/C-06/C-07/C-10 reales (se consumen; C-10 no se modifica) ---
# Actor(tenant_id, rol, user_id, profesional_id)     -> app.turnos.servicio
# Invalido(422), Prohibido(403), NoEncontrado(404)   -> app.turnos.servicio
# NoAutenticado(401), ConflictoSolape(409)           -> app.turnos.servicio
# ServicioReservasPublicas.reservar/cancelar/reprogramar -> app.reservas.servicio
# HuecoLiberadoPort.emitir(tenant_id=, turno_id=)    -> app.lista_espera.puertos
# ServicioCaja.registrar_movimiento(actor, *, monto, medio, tipo, fecha, turno_id)
#                                                    -> app.caja.servicio
# TransaccionSQL(session)                            -> app.core.transaccion (anidable)
# ContadorPort (rate-limit público)                  -> app.reservas.puertos

# --- C-05 define; C-11 necesita (extensión mínima, misma máquina de estados) ---
class TurnoPort(Protocol):
    def confirmar_por_sena(self, *, tenant_id: str, turno_id: str,
                           ahora: datetime) -> None: ...      # sólo desde PENDIENTE
    def cancelar_por_sena(self, *, tenant_id: str, turno_id: str, motivo: str,
                          ahora: datetime) -> None: ...       # sólo desde PENDIENTE
    def turno_de(self, *, tenant_id: str, turno_id: str) -> TurnoRef | None: ...

# --- C-11 define: pasarela de pagos (única frontera con la red) ---
class PasarelaPagosPort(Protocol):
    def crear_preferencia(self, *, tenant_id: str, sena_id: str, turno_id: str,
                          monto_centavos: int, descripcion: str, expira_at: datetime,
                          url_pago: str, url_webhook: str) -> Preferencia: ...
    def obtener_pago(self, *, mp_payment_id: str) -> PagoExterno: ...
# `descripcion` es siempre "Seña de turno" (F-17): nunca prestación ni dato del paciente.

# --- C-11 define: aplicación al cobro (implementada con el alta de C-10) ---
class AplicacionCajaPort(Protocol):
    def registrar_ingreso_mp(self, *, tenant_id: str, turno_id: str,
                             monto_centavos: int, fecha: date, actor_id: str,
                             concepto: str) -> MovimientoRef: ...
# `fecha` = día de la aplicación en -03:00 (F-13): C-10 rechaza CIERRE_CERRADO si está cerrado.

# --- C-11 define: presupuesto vigente (sólo lectura, C-09 no cambia) ---
class PresupuestosPort(Protocol):
    def aceptado_vigente(self, *, tenant_id: str, paciente_id: str,
                         ahora: datetime) -> bool: ...   # C11-OQ-13: 409 PRESUPUESTO_CON_SENA

# --- C-11 define: repositorios y worker ---
class SenaRepositorio(Protocol):
    def crear(self, *, tenant_id, turno_id, monto_centavos, regla_modo, regla_valor,
              precio_base_centavos, anticipacion_cancelacion_h, expira_at,
              token_hash, ahora=None) -> Sena: ...
    def obtener(self, *, tenant_id, sena_id) -> Sena | None: ...
    def por_turno(self, *, tenant_id, turno_id) -> Sena | None: ...
    def por_token(self, *, tenant_id, token_hash) -> Sena | None: ...
    def por_mp_payment(self, *, tenant_id: str, mp_payment_id: str) -> PagoMP | None: ...
    def listar(self, *, tenant_id, desde=None, hasta=None) -> list[Sena]: ...  # por turno.inicio
    def vencidas(self, *, tenant_id, ahora) -> list[Sena]: ...
    def bloquear(self, *, tenant_id, sena_id) -> Sena: ...          # SELECT ... FOR UPDATE
    def transicionar(self, *, tenant_id, sena_id, desde, hacia, campos) -> Sena | None: ...
    def reemitir_token(self, *, tenant_id, sena_id, token_hash, ahora) -> Sena: ...

class PagoMPRepositorio(Protocol):
    def registrar_o_actualizar(self, *, tenant_id, sena_id, mp_payment_id, monto_centavos,
                               moneda, estado, resultado, raw_json,
                               aprobado_en=None, ahora=None) -> PagoMP: ...
```

## Risks / Trade-offs

- [Doble cobro de la seña] → UNIQUE `(tenant_id, turno_id)` + revalidación de la regla al reservar;
  probado con dos reservas concurrentes del mismo hueco.
- [Doble acreditación] → `mp_payment_id` global único + `FOR UPDATE` + transición condicional.
- [Plata cobrada de más o dos veces] → `MONTO_DISTINTO`/`PAGO_EXCEDENTE` dejan obligación de
  devolución visible en `GET /api/senas`; `DUPLICADO` nunca se usa para un pago distinto.
- [Webhook falsificado] → HMAC sobre el manifiesto de MP, comparación en tiempo constante,
  re-consulta del pago y `503` fail-closed sin secreto.
- [Pago real perdido] → nunca se descarta: `500` con log estructurado si no se asocia, `503` si MP no
  responde, y toda notificación relevante deja fila en `pagos_mp`.
- [Pago aprobado con turno ya liberado] → `DEVUELTA` sin reabrir el turno (`C11-OQ-07`); el hueco
  pudo ofertarse a C-07 y reabrirlo duplicaría la reserva.
- [Seña en limbo] → cada estado tiene su instante y su motivo; `DEVUELTA` es explícita y auditable.
- [MP caído deja la reserva sin link] → seña `PENDIENTE` con `preferencia_estado=FALLIDA`, reintento
  on-demand con backoff y el reloj de expiración no se pausa (`C11-OQ-06`).
- [Token de pago filtrado] → sólo se guarda el hash, hay un único token vigente y el link muere con
  la seña; la página no expone datos del paciente.
- [PHI del pagador] → `raw_json` minimizado, logs con ids, tests de PHI.
- [Día cerrado al aplicar] → `409 CIERRE_CERRADO`, sin movimiento y la seña sigue `ACREDITADA`; se
  aplica al día siguiente sin perder plata.
- [Seña y presupuesto aceptado] → `409 PRESUPUESTO_CON_SENA` hasta que exista el descuento
  automático (`C11-OQ-13`); evita cobrar dos veces el mismo tramo.
- [Seña vencida con link vivo] → `409 SENA_VENCIDA` en `POST .../preferencia` sin llamar a la
  pasarela (`F-09`).
- [Barrido sin disparador] → el wiring al runner de workers es tarea y dependencia operativa
  (`F-15`); sin él la seña vencida no libera el turno.
- [Divergencia con el ERD] → §Desviaciones del ERD del proposal.
- [Sin reintento automático de preferencias con scheduler] → aceptado: no hay intervalo en la KB y
  el paciente está en la página; `C11-OQ-05` deja el número y el camino.
- [Gate de diseño] → sin sistema de diseño aprobado no hay UI; el change queda backend.
- [Drift dominio en memoria vs SQLAlchemy] → igual que C-06…C-10: el wiring real es follow-up
  declarado; los tests de migración y de concurrencia cubren las garantías de base.

## Migration Plan

1. **DDL (009)**: crear `senas` y `pagos_mp` con CHECKs, UNIQUEs, índices, RLS forzada y grants por
   columna; agregar `prestaciones.sena_modo`/`sena_valor` con sus CHECKs; backfill legacy
   conservador (D14). Reversible.
2. **Modelos SQLAlchemy** en `backend/app/models/sena.py` (`Sena`, `PagoMP`) con `Mapped[...]`,
   `timestamptz`, PK uuid y CHECKs espejo; agregar las dos columnas a `Prestacion`
   (`backend/app/models/catalogos.py`) sin tocar las legacy.
3. **Dominio** en `backend/app/senas/`: entidades y `puertos.py` (protocolos + adaptadores en
   memoria y `AdaptadorPasarelaFake`), `regla.py` (D1), `servicio.py` (alta, preferencia, webhook,
   acreditación, aplicación, devolución, transferencia), `webhook.py` (firma), `worker.py`
   (expiración), `adaptador_caja.py` (D9) y `adaptador_pasarela.py` (D5).
4. **Borde**: `backend/app/routers/senas.py` y `backend/app/routers/webhooks_mp.py`;
   `backend/app/schemas/senas.py` con `extra="forbid"`, montos `int` estrictos y allow-list de
   respuesta. Sin `PATCH`/`DELETE` de señas.
5. **Enganche en C-06**: `ServicioReservasPublicas` recibe `SenaPort` opcional y llama a
   `crear_si_corresponde(...)` después de crear el turno; `cancelar` y `reprogramar` notifican a
   C-11. **Cuando el turno tiene seña, `cancelar` valida la anticipación con
   `senas.anticipacion_cancelacion_h` (snapshot) y no con la configuración vigente** (`F-19`), que es
   la misma regla que aplica la devolución automática; no cambian los códigos ni la verificación de
   C-06.
6. **Enganche en C-05**: `ServicioTurnos` gana `confirmar` (o el adaptador de `TurnoPort` reusa la
   máquina de estados y el registro de auditoría existente). Sin estados nuevos.
7. **Runner de workers** (dependencia operativa, `F-15`): registrar `app/senas/runner.py` en el
   scheduler (cron/Redis, DD-08) con el intervalo configurado ahí, invocando
   `procesar_expiraciones(tenant_id, ahora)` por tenant. Sin este paso el change está incompleto
   aunque el dominio funcione.
8. **Env**: se usan sólo los nombres de la KB (`MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`, `SENA_TTL_H`,
   `CANCEL_ANTICIPACION_H`, `APP_URL`); `.env.example` documenta las nuevas con valores de ejemplo
   **ficticios** y `SENA_TTL_H=24`. Sin secretos reales en el repo.
9. Rollback = `alembic downgrade 008_caja_cierre_diario` (la 009 sólo agrega tablas y columnas
   nullable).
10. Verificación: suite con `C02_DATABASE_URL` y `skipped == 0`, `mypy --strict` de `app/senas`,
    `ruff check .` y `openspec validate c-11-senas-mercadopago --strict`.

## Open Questions

| OQ | Estado | Pregunta | Respaldo / decisión | Comportamiento implementado |
|---|---|---|---|---|
| C11-OQ-01 | **Fijada 2026-11-13** | ¿Cómo se redondea el porcentaje? | PO-01 admite `%` (`docs/decisiones-po.md:34-35`); regla dura de montos enteros. Dueño: **truncar hacia abajo al centavo** | `precio_base * pct // 100`; nunca se redondea para arriba |
| C11-OQ-02 | **Provisional** (2026-11-13) | Anticipación mínima de cancelación para devolver la seña | `CANCEL_ANTICIPACION_H=24` (`08_arquitectura:57`); el dueño la acepta como **provisional** hasta el piloto | 24 h por env; snapshot en la seña; C-06 usa el mismo snapshot para autorizar la cancelación |
| C11-OQ-03 | **Fijada 2026-11-13** | ¿Qué pasa con la seña acreditada si cancelan **por debajo** del umbral? | `07_flujos:43` (nunca limbo); `03_actores:24` (Admin anula con motivo). Dueño: queda `ACREDITADA` y **decide un humano `ADMIN`** | `DEVUELTA` con motivo o `APLICADA` con `concepto=CANCELACION_TARDIA`; sin automatismo |
| C11-OQ-04 | **Fijada 2026-11-13** | Al reprogramar, ¿la seña se transfiere o se exige una nueva? | RN-SE-02 (atada a la reserva); RN-RE-02/03 (reprogramar es la misma reserva). Dueño: **se transfiere** | `UPDATE senas SET turno_id=<nuevo>`; `expira_at = min(ahora + TTL, nuevo.inicio)`; mismo token si no venció, si no se reemite (D6) |
| C11-OQ-05 | Abierta (no bloqueante) | Backoff del reintento de preferencia con MP caído | RN-IN-03; DD-08 (colas con backoff). **Provisional**: `min(2**intentos, 15)` minutos, máximo 5 intentos, después sólo reintento manual | `intentos_preferencia` + `proximo_reintento_at`; `202` con `reintentar_en` |
| C11-OQ-06 | Abierta (no bloqueante) | ¿La caída de MP pausa el reloj de expiración? | RN-SE-01 ("sin seña acreditada antes de `expira_at`, el turno se libera"). **Recomendación: no pausar** | El turno se libera igual; el paciente re-reserva |
| C11-OQ-07 | Abierta (no bloqueante) | Pago aprobado antes de `expira_at` cuyo webhook llega después de liberar: ¿se re-confirma el turno? | RN-GL-02 (el último en confirmar pierde); el hueco pudo ofertarse (C-07). **Recomendación: no reabrir; `DEVUELTA`** | `LIBERADA → DEVUELTA`, `resultado=FUERA_DE_TIEMPO`, turno intacto |
| C11-OQ-08 | Abierta (no bloqueante) | ¿`expira_at` se acota al inicio del turno? ¿Qué dispara el job? | C-07 acota la oferta con `min(..., slot.inicio)` (`worker.py:168`); no hay intervalo de job en la KB. **Recomendación: acotar**; el disparador es del runner (DD-08) y ahora es tarea + dependencia operativa | `min(ahora + SENA_TTL_H, turno.inicio)`; worker puro invocado por tenant |
| C11-OQ-09 | **Fijada 2026-11-13** | ¿La devolución se ejecuta por API de MP o a mano? | `11_integraciones.md:10` (devoluciones automáticas = post-v1). Dueño: **reembolso manual**, sin API de reembolsos | `DEVUELTA` = obligación registrada; el reintegro se hace en el panel de MP con responsable asignado |
| C11-OQ-10 | **Fijada 2026-11-13** | ¿La seña visible en agenda cambia el payload de turnos o usa endpoint propio? | C-10 evitó tocar contratos ajenos. Dueño: **endpoint propio** | `GET /api/senas?desde=&hasta=` filtrando por `turno.inicio`; `GET /api/turnos` no cambia |
| C11-OQ-11 | Abierta (no bloqueante) | ¿Se guarda el payload completo de MP en `raw_json`? | RN-CL-04 y regla dura "sin PHI"; el pago trae datos del pagador. **Recomendación: subconjunto allow-list** | Sólo los campos que el sistema consume |
| C11-OQ-12 | Abierta (no bloqueante) | ¿Sólo pesos? ¿Tope opcional del porcentaje? | PO-01 menciona "porcentaje con tope opcional" como provisional (`docs/decisiones-po.md:49`); el dominio es Argentina. **Recomendación: sólo `ARS` y sin tope en v1** | `pagos_mp.moneda` guarda la moneda real (`ARS`, `USD`, …) y la acreditación exige `ARS` + monto exacto; un pago en otra moneda queda `MONTO_DISTINTO` con obligación de devolución visible. Sin columna de tope |
| C11-OQ-13 | Abierta (no bloqueante, **fuera de v1**) | ¿Cómo se descuenta la seña contra un presupuesto aceptado (C-09)? | El descuento automático queda fuera de v1 por decisión del dueño (2026-11-13). Mientras no exista, aplicar con presupuesto aceptado vigente es un doble cobro | `409 PRESUPUESTO_CON_SENA` en `aplicar`, sin movimiento y sin cambio de estado |

**Cierre 2026-11-13** (decisiones del dueño aplicadas a este design, las specs y `tasks.md`):

- Fijadas: **OQ-01** (truncar al centavo), **OQ-03** (queda `ACREDITADA` y decide `ADMIN`), **OQ-04**
  (transferencia con el mismo token si no venció), **OQ-09** (reembolso manual) y **OQ-10**
  (endpoint propio filtrado por `turno.inicio`).
- Provisional: **OQ-02** (24 h) y el número de backoff de **OQ-05**; se revisan con el piloto.
- Abiertas no bloqueantes: **OQ-05, OQ-06, OQ-07, OQ-08, OQ-11, OQ-12 y OQ-13**.
- La única condición operativa que sigue abierta fuera del código es **quién** opera el panel de MP
  y ejecuta los reintegros (`OQ-09`) y **quién** corre el runner de workers (`OQ-08`).

> Ninguna de estas OQ habilita una implementación distinta sin modificar este design. Las que
> tocan plata ya están decididas (`OQ-01`, `OQ-03`, `OQ-09`) o marcadas provisionales con dueño
> (`OQ-02`); las abiertas no bloquean la implementación de v1.

## Notas de implementación (no vinculantes)

- Actor por headers (`actor_desde_headers`) igual que C-05/C-07/C-08/C-09/C-10; el JWT real de C-03
  reemplaza la dependencia sin cambiar el contrato.
- Errores de dominio: `Invalido` 422 (monto/regla/token/motivo), `Prohibido` 403 (RBAC),
  `NoEncontrado` 404 (cross-tenant y token inválido, incluido `devolver` desde otro tenant),
  `NoAutenticado` 401 (identidad de paciente), `Conflicto` 409 (`SENA_YA_APLICADA`,
  `SENA_NO_DEVOLUBLE`, `SENA_VENCIDA`, `PRESUPUESTO_CON_SENA`, `ESTADO_INVALIDO`, `CIERRE_CERRADO`
  heredado), `ServicioNoDisponible` 503 (`MP_WEBHOOK_SECRET` ausente o MP caído al re-consultar).
- El webhook **no** usa `actor`: su actor de auditoría es `"webhook-mp"` y el `tenant_id` sale de la
  **respuesta re-consultada** de Mercado Pago (metadata del pago), nunca de un header ni del cuerpo
  sin re-consultar (`F-26`).
- `bloquear` de la seña es `SELECT ... FOR UPDATE`; los adaptadores en memoria simulan el lock y
  **no** prueban la garantía: eso vive en los tests con dos conexiones a PostgreSQL.
- El monto se calcula **antes** de crear la seña y se persiste; ningún endpoint recalcula el monto
  de una seña existente.
