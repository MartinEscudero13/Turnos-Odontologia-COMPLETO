# Proposal — C-11 `senas-mercadopago`

> Governance **CRÍTICO**: este change **no se implementa sin aprobación explícita del dueño**.
> Cobra dinero real de pacientes contra un proveedor externo y libera turnos solo. Un error acá
> no es un bug cosmético: es plata de un tercero cobrada dos veces, perdida o devuelta tarde.
> Este documento es planificación: **no hay código ni tests** en el change.

## Why

El consultorio pierde sillón por no-show y no tiene forma de exigir una garantía al reservar
online. RN-SE-01 pide que la reserva pueda exigir seña con liberación automática si no se
acredita antes de `expira_at`; RN-SE-02 que la seña esté atada 1──1 a la reserva y sea visible
en la agenda con su estado; RN-SE-03 que los webhooks de Mercado Pago sean idempotentes por
`mp_payment_id`; RN-SE-04 que la seña acreditada se aplique al cobro o se devuelva según la
política **visible al reservar**; y US-041 lo pide con tres criterios de aceptación
(`06_funcionalidades.md:75-78`).

Hoy no existe nada de eso: no hay `senas` ni `pagos_mp`, `ServicioReservasPublicas.reservar`
crea el turno `PENDIENTE` y termina ahí (`backend/app/reservas/servicio.py:318-387`), C-10 no
modela señas y la fila "seña aplicada" del Flujo 5 quedó explícitamente en manos de C-11
(C10-OQ-6, `docs/decisiones-po.md:129`). PO-01 ya resolvió el modelo de configuración
(default por tenant + override por prestación), así que el único bloqueo de producto que
quedaba está cerrado.

## What Changes

- **Regla efectiva de seña (PO-01)**: `valor efectivo = prestacion.sena_modo ?? tenant_parametros.sena_modo`;
  el override `SIN_SENA` es válido y sin configuración en ninguno de los dos niveles la
  prestación **no** exige seña (fail-open a no cobrar). `tenant_parametros` es clave/valor
  (`clave`, `valor jsonb`) en la base real, así que el default del consultorio vive en las
  claves `sena_modo`/`sena_valor`, no en columnas nuevas.
- **Modelo `Sena`**: `(tenant, turno 1──1, monto_centavos, estado PENDIENTE/ACREDITADA/
  LIBERADA/APLICADA/DEVUELTA, regla_aplicada + valor + precio_base snapshot,
  mp_preference_id, preferencia_estado POR_CREAR/CREADA/FALLIDA + intentos,
  expira_at, token_hash opaco, instantes por estado, motivo/concepto y
  movimiento_caja_id)`. Montos enteros en centavos.
- **Modelo `PagoMP`**: `(mp_payment_id UNIQUE global, sena, monto_centavos, moneda ARS, estado MP,
  resultado propio, payload minimizado, recibido_en, aprobado_en)`. Es el registro de idempotencia:
  un `mp_payment_id` se procesa una sola vez. `resultado` distingue `DUPLICADO` (mismo pago),
  `MONTO_DISTINTO`, `PAGO_EXCEDENTE`, `FUERA_DE_TIEMPO` y los reembolsos de MP.
- **Alta al reservar**: `POST /api/publico/{tokenTenant}/reservas` crea el turno `PENDIENTE`
  (C-06, sin cambios) y, si la regla efectiva exige seña, crea la seña `PENDIENTE`, pide la
  preferencia a Mercado Pago y devuelve el link de pago. El turno **no** se confirma hasta
  que la seña se acredite.
- **Pago público**: `GET /api/publico/{tokenTenant}/senas/{tokenSena}` (estado, monto, política
  de cancelación, link si sigue vigente) y `POST .../senas/{tokenSena}/preferencia` para
  reintentar la preferencia cuando MP falló. Token opaco, un solo vigente a la vez, sin login
  de paciente (PO-06 sigue abierta).
- **Webhook idempotente**: `POST /api/webhooks/mercadopago` verifica firma HMAC, re-consulta el
  pago en MP como fuente de verdad y aplica el efecto una sola vez. Duplicado del **mismo**
  `mp_payment_id` ⇒ `200` sin efecto; sin firma válida ⇒ `401`; sin secreto configurado ⇒ `503`
  (fail-closed); pago que no se puede asociar ⇒ `500` para que MP reintente y el hecho no se
  pierda. Un pago **distinto** sobre una seña ya acreditada ⇒ `resultado=PAGO_EXCEDENTE` con
  obligación de devolución explícita, nunca `DUPLICADO`.
- **Acreditación**: seña `PENDIENTE → ACREDITADA` y turno `PENDIENTE → CONFIRMADO`, en una
  transición condicional con la fila de la seña bloqueada; dos webhooks simultáneos acreditan
  una sola vez.
- **Expiración**: worker con reloj inyectado libera las señas `PENDIENTE` vencidas
  (`expira_at = min(ahora + SENA_TTL_H, turno.inicio)`), deja la seña `LIBERADA`, cancela el
  turno con motivo y dispara el caso de uso de auto-oferta ya existente de C-07
  (`HuecoLiberadoPort.emitir`), todo en una sola transacción (si la emisión falla, rollback y la
  seña sigue `PENDIENTE`). Si el worker commitea primero, el webhook posterior responde `200` con
  `resultado=FUERA_DE_TIEMPO`, nunca `DUPLICADO` ni `500`, y no emite un segundo evento. El barrido
  corre por tenant y necesita un disparador (cron/Redis) declarado como dependencia operativa.
- **Aplicación al cobro (C-10)**: `POST /api/senas/{id}/aplicar` deja la seña `APLICADA` y crea
  el movimiento `medio=MP` **a través del alta de movimientos de C-10** (mismo
  `pg_advisory_xact_lock` por `(tenant, fecha)` y mismo `409 CIERRE_CERRADO`), con `fecha` = el
  día de la aplicación en `-03:00`, guardando `movimiento_caja_id` para que un reintento no cobre
  dos veces. Con un presupuesto aceptado vigente en C-09 ⇒ `409 PRESUPUESTO_CON_SENA`
  (`C11-OQ-13`). C-11 no escribe `movimientos_caja` por su cuenta y no toca el contrato de `caja`.
- **Devolución**: `POST /api/senas/{id}/devolver` (solo `ADMIN`, motivo obligatorio) deja la seña
  `DEVUELTA`. v1 **no** llama a la API de reembolsos (`C11-OQ-09`): registra la obligación y el
  reintegro se ejecuta a mano en el panel de MP (conciliación fuera de alcance,
  `11_integraciones.md:10`). Una cancelación con anticipación suficiente deja la seña `DEVUELTA`
  automáticamente, para que nunca quede en limbo (`07_flujos_principales.md:43`). La **misma cola
  de obligaciones** (`GET /api/senas`) muestra los pagos con `MONTO_DISTINTO`, `PAGO_EXCEDENTE` y
  los `REFUNDED` de MP que requieren devolución o ajuste.
- **Política visible al reservar**: la respuesta de reserva y la página de pago exponen
  `anticipacion_cancelacion_h` (snapshot de `CANCEL_ANTICIPACION_H`, 24 h provisional),
  `reembolsable: true` **desde la creación** (es la promesa, no el estado actual) y
  `hay_pago_acreditado: bool` (si hoy hay plata retenida); el texto de política se deriva de esos
  datos, no se inventa por pantalla.
- **Migración 009**: `senas`, `pagos_mp`, `prestaciones.sena_modo`/`sena_valor`, RLS forzada
  fail-closed en las dos tablas nuevas y backfill conservador de las columnas legacy
  `requiere_sena`/`monto_sena`. Reversible; no toca 001–008 ni C-10.

## Capabilities

### New Capabilities

- `senas`: regla efectiva de seña (PO-01), alta atada al turno, preferencia y link de pago,
  token público de un solo uso, webhook idempotente con firma verificada, acreditación que
  confirma el turno, expiración que libera y dispara auto-oferta, aplicación al cobro vía C-10,
  devolución registrada, RBAC, aislamiento multi-tenant, auditoría append-only, migración 009.

### Modified Capabilities

- `reserva-publica`: la reserva pública puede exigir seña; la respuesta suma el bloque `sena`
  (id, estado, monto, expira_at, token, link) y la política de cancelación, y el turno queda
  `PENDIENTE` hasta la acreditación. El resto del contrato (verificación, rate-limit,
  anti-solape, aislamiento, privacidad) no cambia.
- `turnos-anti-solape`: se explicita la transición `PENDIENTE → CONFIRMADO` disparada por la
  seña acreditada y la `PENDIENTE → CANCELADO` con motivo disparada por la expiración; no se
  agregan estados ni se relaja el anti-solape.

## Fuera de alcance (diferido explícito)

- **UI** (`/pagar/:tokenSena`, agenda con estado de seña, `/config` de la regla): diferida a
  `C-11-UI`. C-11 v1 es **backend + contratos + migración 009 + tests**; no toca `frontend/`
  y no declara requirements de UI (mismo criterio que `C-10-UI`).
- **Conciliación automática y reembolsos automáticos**: la API de reembolsos de MP y la
  conciliación bancaria no están en v1 (`11_integraciones.md:10`); `DEVUELTA` es la obligación
  registrada y el reintegro se ejecuta en el panel de MP.
- **Split de pagos, otras pasarelas (Stripe/Transferencia), cuotas y cobro total online**: fuera
  de v1; MP sólo cobra la seña.
- **Configuración de la regla por API**: `POST/PATCH /api/tenants/*` y la pantalla `/config` son
  de C-15 (`CHANGES.md:408`). C-11 lee la configuración y falla abierto a `SIN_SENA` si no existe.
- **Reconciliación de señas huérfanas / conciliación diaria MP**: no hay job de conciliación en
  v1; un pago que no se puede asociar responde `500` y queda para operación.
- **Recordatorios de pago (WhatsApp/email)**: C-13, que sigue diferido por PO-03.
- **Descuento automático de la seña contra una línea de presupuesto**: la seña aplicada es un
  ingreso `MP` del turno en caja; el saldo del tratamiento se cobra en el mostrador. El descuento
  automático queda fuera de v1 como `C11-OQ-13`: mientras no exista, aplicar la seña de un turno
  con presupuesto aceptado vigente responde `409 PRESUPUESTO_CON_SENA`.
- **Facturación/ARCA de la seña**: fuera de v1 (`11_integraciones.md:13`).

## Dependencias

| Dependencia | Estado | Qué aporta a C-11 |
|---|---|---|
| **C-05** `turnos-anti-solape` | Archivado 2026-10-01 | `turnos`, `Actor`, `ServicioTurnos`, máquina de estados (`PENDIENTE → CONFIRMADO`, `→ CANCELADO`) y jerarquía `TurnoError` |
| **C-06** `reserva-online-publica` | Archivado 2026-11-05 | `ServicioReservasPublicas.reservar/cancelar/reprogramar`, `token_publico`, rate-limit y verificación single-use; C-11 se engancha ahí |
| **C-07** `lista-espera-auto-oferta` | Archivado 2026-11-05 | `HuecoLiberadoPort.emitir(tenant_id, turno_id)` idempotente y `ServicioAutoOferta.procesar_hueco_liberado` |
| **C-10** `caja-cierre-diario` | Archivado 2026-11-13 | `ServicioCaja.registrar_movimiento` (alta de movimientos, lock por día, `409 CIERRE_CERRADO`) y `movimientos_caja` para el movimiento `MP` |
| **C-09** `odontograma-presupuesto` | Archivado 2026-11-12 | `MedioPago`, `presupuestos` (`estado='ACEPTADO'`, `vence_en`) y el patrón de puerto con adaptador en memoria; no se modifica |
| **Runner de workers** (DD-08) | **Dependencia operativa** | Sin un disparador (cron/Redis) el barrido de expiración de C-11 no corre y las señas vencidas no liberan el turno. C-11 registra el job y documenta el contrato; el runner es infraestructura |
| **C-15** `admin-plataforma-exportacion` | **NO implementado** | Consumidor futuro: configura la regla de seña del tenant y exporta las señas |

## Decisiones de producto aplicadas

| ID | Decisión | Consecuencia en los artefactos |
|---|---|---|
| **PO-01** | Seña con **default por tenant + override opcional por prestación**; `SIN_SENA` es override válido; sin configuración ⇒ `SIN_SENA` | `design.md` D1/D2, `specs/senas` §"Regla efectiva", migración 009 con `prestaciones.sena_modo`/`sena_valor` |
| **PO-03** | WhatsApp diferido | C-11 no depende de mensajería: la confirmación de la reserva es HTTP + el link de pago. Ningún requirement de C-11 depende de C-13 |
| **PO-06** | Paciente sin acceso/login en v1 | El pago se hace con un token opaco en `/pagar/:tokenSena`, sin sesión ni identidad de paciente |
| **C10-OQ-6** | La seña aplicada es un movimiento `MP` **creado por C-11** con el alta de C-10 | `design.md` D9, `specs/senas` §"Aplicación al cobro"; C-10 y su spec no cambian |
| **C11-OQ-01…04, 09, 10, 13** | Redondeo truncado, anticipación 24 h provisional, cancelación tardía decidida por `ADMIN`, transferencia en reprogramación, reembolso manual, endpoint propio de señas y descuento contra presupuesto fuera de v1 | `design.md` D1/D9/D12/D13 y §Open Questions; `docs/decisiones-po.md` §C-11 |

## Desviaciones del ERD (reconciliación con Martin)

`04_modelo_de_datos.md:68-70` modela `senas` y `pagos_mp` de forma mínima. C-11 se desvía con:

- `senas.monto` → `monto_centavos` (nombre explícito, regla dura de dinero en centavos) y
  columnas nuevas: `regla_modo`, `regla_valor`, `precio_base_centavos` (monto reproducible y
  auditable), `preferencia_estado`, `intentos_preferencia`, `proximo_reintento_at`,
  `token_hash`, `acreditada_en`/`aplicada_en`/`liberada_en`/`devuelta_en`, `devuelta_por`,
  `motivo_devolucion`, `concepto_aplicacion`, `movimiento_caja_id`, `anticipacion_cancelacion_h`.
- `pagos_mp`: `monto_centavos`, `moneda`, `resultado`, `aprobado_en` y
  `raw_json` **minimizado** (sólo los campos que se consumen; el pago de MP trae datos del
  pagador y guardar el payload completo metería PHI en la base).
- `prestaciones`: se agregan `sena_modo`/`sena_valor`; `requiere_sena`/`monto_sena` quedan
  como columnas **legacy de sólo lectura** (backfill conservador, ver `design.md` D14).
- `tenant_parametros` no recibe columnas: es clave/valor en la base real, así que el default
  del consultorio vive en las claves `sena_modo`/`sena_valor` (`design.md` D1).
- **Endpoints nuevos**: `/api/webhooks/mercadopago`, `/api/publico/{tokenTenant}/senas/{token}`,
  `/api/senas*`. Se agregan porque sin ellos no hay cobro ni pago recuperable.

## Risks / Trade-offs

- **Doble cobro o doble acreditación** → `mp_payment_id UNIQUE` + transición condicional de la
  seña con la fila bloqueada; probado con dos conexiones reales.
- **Webhook falsificado** → HMAC-SHA256 sobre el manifiesto de MP, comparación en tiempo
  constante, re-consulta del pago a MP y `503` fail-closed si no hay secreto configurado.
- **Pago aprobado y turno ya liberado** → no se reabre el turno (el hueco pudo ofertarse a C-07):
  la seña pasa a `DEVUELTA` y queda la obligación registrada (`C11-OQ-07`).
- **Seña en limbo tras cancelar** → cancelación con anticipación suficiente deja `DEVUELTA`
  explícita; por debajo del umbral queda `ACREDITADA` y decide `ADMIN` con motivo.
- **MP caído** → la reserva se crea igual (`PENDIENTE`), la preferencia queda `FALLIDA` con
  reintento y el reloj de expiración no se pausa (`C11-OQ-06`).
- **Plata cobrada sin registro** → un pago no asociable responde `500` (MP reintenta) y se
  loguea sólo con ids; nunca se descarta en silencio.
- **PHI en el payload de MP** → se guarda un subconjunto allow-list; logs con ids y montos.
- **Divergencia con el ERD** → ver §Desviaciones del ERD.
- **Gate de diseño** → sin sistema de diseño aprobado no hay UI; el change queda backend.

## Governance CRÍTICO — condiciones de avance

1. Revisión y aprobación explícita del dueño sobre este proposal, `design.md`, las tres delta
   specs y `tasks.md`. Sin ese paso el change queda en planificación aunque
   `openspec validate --strict` esté en verde.
2. Estado de las `C11-OQ-01…13` de `design.md` §Open Questions: **fijadas** OQ-01, OQ-03, OQ-04,
   OQ-09 y OQ-10 (2026-11-13); **provisional** OQ-02 (24 h) y el backoff de OQ-05; **abiertas** las
   no bloqueantes OQ-05, OQ-06, OQ-07, OQ-08, OQ-11, OQ-12 y OQ-13. Las que tocan plata ya no se
   implementan con un default silencioso porque están decididas o marcadas provisionales con dueño.
3. Correr `revisor-escenarios-turnos` sobre `specs/senas/spec.md` y corregir los
   `BLOQUEANTE`/`MAYOR` antes de aplicar.
4. La devolución es **manual** (`C11-OQ-09`): asignar el responsable operativo que opera el panel de
   MP y ejecuta los reintegros; sin eso `DEVUELTA`, `MONTO_DISTINTO` y `PAGO_EXCEDENTE` son
   obligaciones sin dueño. Declarar además quién corre el runner de workers (dependencia operativa).
5. **Nada de `backend/`, `tests/`, `frontend/` ni migraciones hasta la aprobación.** El punto de
   parada exacto es: `openspec validate --strict` en verde + este documento aprobado.
