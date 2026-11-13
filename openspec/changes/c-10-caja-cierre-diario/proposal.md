# Proposal — C-10 `caja-cierre-diario`

> Governance **ALTO**: este change **no se implementa sin revisión y aprobación explícita
> del dueño**. Toca dinero, cierres y trazabilidad contable; un error acá no es un bug
> cosmético, es un descuadre que el consultorio descubre días después.

## Why

Hoy el sistema sabe **cobrar en teoría** pero no **registrar un peso**. C-09 (archivado el
2026-11-12) acepta líneas de presupuesto y llama a `ImputacionPort.imputar_caja(...)` contra un
adaptador en memoria que sólo guarda la llamada para los tests
(`backend/app/presupuesto/puertos.py`). No existen `movimientos_caja`, `cierres_diarios`,
`cobros_pendientes`, ajustes posteriores al cierre ni cuentas por cobrar de obras sociales.
RN-CJ-01 exige caja multi-medio con usuario, fecha y turno; RN-CJ-02 exige cierre diario por
tenant con totales por medio y diferencia 0 o motivo registrado; RN-CJ-03 exige anulaciones
trazables con motivo y nunca borrado físico; y el Flujo 5 agrega la corrección posterior al
cierre: **motivo + movimiento compensatorio, nunca editar el cierre**
(`07_flujos_principales.md:51`). Sin C-10 el presupuesto aceptado no llega a la caja y el
consultorio sigue cuadrando en una planilla aparte (US-040).

## What Changes

- **Movimientos de caja multi-medio**: `MovimientoCaja(tenant, fecha operativa, medio
  EFECTIVO/TRANSFERENCIA/MP/OS, monto centavos, tipo INGRESO/EGRESO, tramo PACIENTE/OS?,
  turno_id?, usuario_id NOT NULL, anulado + motivo_anulacion + anulado_por/en, origen
  MANUAL/IMPUTACION/COMPENSACION, compensa_a_id?)` con trazabilidad opcional a
  `presupuesto_id`/`linea_id`/`paciente_id`. Montos enteros en centavos y `monto > 0`; un
  movimiento es un hecho, no un saldo editable.
- **Día operativo y reloj**: `fecha DATE` es el día del consultorio y se deriva del reloj
  inyectado con el offset fijo `-03:00` (C10-OQ-8); los instantes siguen siendo `timestamptz`.
- **Estados explícitos**: el movimiento nace vigente y su única transición es `vigente →
  anulado` (motivo, actor y timestamp en la misma operación); no hay edición de
  monto/medio/tipo/fecha ni `DELETE`.
- **Día cerrado = día inmutable**: `POST /api/caja/movimientos` e imputaciones sobre una fecha
  con cierre responden `409 CIERRE_CERRADO`. Las únicas correcciones son la anulación con
  **compensatorio fechado el día del registro** y el cobro de un pendiente, ambas asentadas en
  `ajustes_post_cierre`.
- **Ajustes post-cierre (ledger `ajustes_post_cierre`)**: la anulación de un movimiento de un
  día cerrado y el cobro de un pendiente cuya fecha operativa ya tiene cierre se asientan en
  este ledger referenciado al `cierre_id`, con el movimiento que los materializa en el día
  abierto. **Nunca** se inserta nada en `movimientos_caja` de una fecha cerrada y el cierre
  **nunca** se recalcula.
- **Cierre diario obligatorio**: `CierreDiario UNIQUE(tenant, fecha)` con totales netos por
  medio, `efectivo_contado`, `diferencia = efectivo_contado − total_efectivo` (sólo efectivo,
  C10-OQ-2), `responsable_id` obligatorio del tenant, `motivo_diferencia` obligatorio cuando la
  diferencia no es 0 y `observacion` **opcional** y auditable, `cerrado_at`. El cierre es
  inmutable (sin `PATCH`/`DELETE` ni `UPDATE`/`DELETE` en DB) y reabrirlo no existe en v1
  (C10-OQ-1).
- **Devengado de obra social fuera de la caja**: el tramo `monto_os_centavos` se registra como
  **cuenta por cobrar informativa** en `cuentas_por_cobrar_os` (fuera de `movimientos_caja` y
  fuera de los totales de caja); el cierre muestra `total_os` como *informativo devengado* y
  `total_os_cobrado` como total real del medio OS. El cobro real de la OS lo crea C-12; nunca
  hay dos `INGRESO` por el mismo monto.
- **Cobros pendientes cuando no hay medio**: si `imputar_caja` llega con `medio=NULL` no se
  inventa un movimiento sin medio: se registra un `cobro_pendiente` (uno por línea, con
  `fecha` operativa) que no suma a los totales y se materializa cuando alguien elige el medio.
- **Idempotencia por tramo**: `movimientos_caja` lleva `tramo` obligatorio en las imputaciones y
  un UNIQUE parcial `(tenant_id, linea_id, tramo)` que **no** incluye `medio`; `cobros_pendientes`
  lleva UNIQUE `(tenant_id, linea_id)` sin condición de resolución. Un replay con otro medio
  responde `409 IMPUTACION_DUPLICADA` y un replay posterior al cobro no crea un segundo pendiente.
- **Carrera movimiento ↔ cierre**: toda escritura de movimiento toma
  `pg_advisory_xact_lock(hashtext(tenant_id || ':' || fecha))` en la misma transacción antes de
  validar el estado del día y de insertar; el cierre toma el mismo lock antes de leer los totales.
- **Adaptador real del puerto de C-09**: implementa `ImputacionPort.imputar_caja` **sin cambiar
  su firma**, importando `MedioPago` de `backend/app/presupuesto/puertos.py`; tramo paciente →
  INGRESO con el `medio` recibido (o pendiente si es `NULL`); tramo OS → cuenta por cobrar;
  `canal` **no** es `medio`; `actor_id` → `usuario_id`.
- **Snapshot vs vigentes**: `GET /api/caja/movimientos?fecha=` devuelve `totales_vigentes`,
  `totales_cierre` (`null` si está abierto) y `difieren_del_cierre`; `GET /api/caja/reportes`
  calcula sobre movimientos vigentes y declara `fuente: "movimientos_vigentes"`.
- **Endpoints**: `GET /api/caja/movimientos?fecha=`, `POST /api/caja/movimientos`,
  `POST /api/caja/movimientos/{id}/anular`, `GET/POST /api/caja/cierre`,
  `GET /api/caja/cierres?desde&hasta`, `GET /api/caja/pendientes`,
  `POST /api/caja/pendientes/{id}/cobrar`, `GET /api/caja/reportes?desde&hasta=`.
- **Migración 008**: `movimientos_caja`, `cierres_diarios`, `cobros_pendientes`,
  `ajustes_post_cierre` y `cuentas_por_cobrar_os`, con `tenant_id NOT NULL`, RLS
  `ENABLE`+`FORCE`, política fail-closed, CHECKs de dominio, UNIQUE del cierre y de idempotencia,
  grants por columna y `downgrade` reversible. **No** agrega columnas a `aceptaciones` ni toca 001–007.

## Capabilities

### New Capabilities

- `caja`: movimientos multi-medio con montos en centavos, tramo e idempotencia por línea,
  estados vigente/anulado, anulación con motivo, compensación y ajustes post-cierre, cobros
  pendientes sin medio, cuentas por cobrar OS informativas, adaptador real del puerto de
  imputación de C-09, consulta diaria con totales vigentes y del cierre, reportes por rango,
  RBAC, aislamiento multi-tenant, auditoría append-only y migración 008.
- `cierre-caja`: cierre diario obligatorio con totales por medio y devengado OS informativo,
  diferencia contra el efectivo contado, motivo obligatorio y observación opcional, responsable
  del tenant, unicidad por `(tenant, fecha)`, inmutabilidad, bloqueo de movimientos nuevos en
  días cerrados y serialización de la carrera movimiento ↔ cierre.

### Modified Capabilities

_(ninguna)_ — C-10 **consume** `presupuesto` (C-09, ya archivado en
`openspec/specs/presupuesto/spec.md`) y `turnos-anti-solape` (C-05), pero **no cambia el
contrato** de `ImputacionPort` ni la matriz de estados de turnos. C-10 no toca el modelo de C-09:
el `medio` de pago vive sólo en `movimientos_caja` y `aceptaciones` conserva sus columnas.

## Fuera de alcance (diferido explícito)

- **UI `/caja` (C-10-UI)**: ver §Diferido a C-10-UI.
- **Señas y Mercado Pago (C-11)**: C-10 no cobra señas, no habla con MP, no procesa webhooks y
  no crea `senas`/`pagos_mp`. La "seña aplicada" que menciona el Flujo 5 no se modela acá: C-11
  registrará la seña aplicada como movimiento `MP` usando el alta de C-10 (C10-OQ-6).
- **Obras sociales y liquidación (C-12)**: no hay `obras_sociales`/`coberturas` ni liquidación.
  El devengado del tramo OS es una cuenta por cobrar informativa; el cobro real lo crea C-12 al
  acreditar y por eso no existe una segunda `INGRESO` por el mismo monto.
- **Comisiones y aranceles de medios de pago**: no se modelan comisiones de MP/transferencia ni
  su neteo en el cierre; el `monto` es el importe cobrado al paciente.
- **Reportes de ocupación, ausentismo y facturación por profesional**: son de C-15.
- **Exportación de caja (CSV/JSON)**: es de `ADMIN` según `03_actores_y_roles.md:28` y vive en
  C-15 (`GET /api/exportacion`, `CHANGES.md:406`); C-10 no expone endpoint de exportación.
- **Reapertura de cierre**: no está en la KB y no se implementa (C10-OQ-1).
- **Cierre automático por job / bloqueo de operación por cierre vencido**: no hay scheduler ni
  regla de negocio que lo respalde en v1; se expone el estado del día (C10-OQ-3).
- **Conciliación bancaria de transferencias/MP/OS**: sólo el efectivo se cuenta físicamente
  (C10-OQ-2).
- **Multi-moneda, arqueo por cajero y caja chica por usuario**: fuera de v1.

## Diferido a C-10-UI

> **No ejecutable en C-10.** La SPA `/caja` fue diferida por decisión del dueño (2026-11-12) al
> change `C-10-UI`, que todavía no existe. C-10 v1 es **backend + contratos + migración 008 +
> tests**: no crea ni modifica archivos de `frontend/`, no crea mockups ni design system, y no
> declara requirements de UI ejecutables en `specs/`.

Criterios de aceptación que `C-10-UI` deberá cubrir contra los contratos de este change, sin
escenarios ejecutables acá:

- Movimientos del día por medio, anulados marcados, `totales_vigentes` calculados por el servidor.
- `totales_cierre` y `difieren_del_cierre` visibles en días cerrados, rotulando "anulación
  posterior al cierre"; `total_os` rotulado como devengado informativo.
- Alta de movimientos, cobro de pendientes, `409 CIERRE_CERRADO` visible como error y oferta de
  anulación con compensatorio.
- Cierre del día: efectivo contado, diferencia, motivo exigido con diferencia ≠ 0, observación
  opcional y cierre mostrado como inmutable (sin reapertura).
- Reportes base de caja sin exportación (C-15) y sin KPIs de agenda (C-15).

Detalle de tareas y gate de diseño: `tasks.md` §12 y `design.md` D13.

## Dependencias

| Dependencia | Estado | Qué aporta a C-10 |
|---|---|---|
| **C-03** `auth-rbac-auditoria` | Implementado | `Actor`/roles, matriz RBAC y auditoría append-only (`RN-AU-02`), `usuarios` como `usuario_id`/`responsable_id` |
| **C-05** `turnos-anti-solape` | Implementado | `turnos` para el `turno_id` opcional y jerarquía `TurnoError` (`Invalido` 422, `Prohibido` 403, `NoEncontrado` 404) |
| **C-09** `odontograma-presupuesto` | **Archivado** 2026-11-12 | Contrato `ImputacionPort.imputar_caja(...)`, `MedioPago`, tramos `monto_paciente_centavos`/`monto_os_centavos`, traducción a `503` (`servicio.py:516-519`) |
| **C-12** `obras-sociales-liquidacion` | **NO implementado** | Consumidor futuro: crea el cobro real de la OS contra la cuenta por cobrar informativa |
| **C-11** `senas-mercadopago` | **NO implementado** | Consumidor futuro: seña aplicada → movimiento `MP` (C10-OQ-6) |

## Decisiones del dueño (2026-11-12)

| ID | Decisión | Consecuencia en los artefactos |
|---|---|---|
| **D1** | La anulación de un movimiento y el cobro de un pendiente cuya fecha operativa ya tiene cierre se asientan en `ajustes_post_cierre`, referenciados al cierre. Nunca se inserta en `movimientos_caja` de una fecha cerrada y el cierre nunca se recalcula. **Reemplaza** la opción de responder `409` al anular en un día cerrado | `design.md` D3/D8, spec `caja` "Ajustes post-cierre", tareas §1 y §3 |
| **D2** | No se toca C-09: los `422`/`409` del adaptador se verifican contra el adaptador; vía `POST /api/presupuestos/:id/aceptar` C-09 responde `503` y no persiste la aceptación | `design.md` D6, spec `caja` "Punto de observación", tareas §5 |
| **D3** | `motivo_diferencia` obligatorio cuando `diferencia ≠ 0`; `observacion` opcional y auditable | `design.md` D4/D8, spec `cierre-caja` "Diferencia distinta de cero", CHECK de DB |
| **D4** | El tramo OS no es un ingreso de caja: el devengado es una cuenta por cobrar informativa fuera de `movimientos_caja` y de los totales; el cobro real lo crea C-12; nunca dos `INGRESO` por el mismo monto | `design.md` D4/D6/D8, spec `caja` "Imputación desde presupuesto", tareas §5 |

## Desviaciones del ERD (reconciliación con Martin)

`04_modelo_de_datos.md` §movimientos/cierres modela `movimientos_caja` y `cierres_diarios` de
forma más simple. C-10 se desvía con estas piezas, todas justificadas por una regla o una
garantía verificable:

- `movimientos_caja`: `tramo`, `presupuesto_id`, `linea_id`, `paciente_id`, `origen`,
  `compensa_a_id` (sin `linea_id` + `tramo` la imputación no es idempotente; sin `compensa_a_id`
  el compensatorio no es trazable, RN-CJ-03).
- `cierres_diarios`: `total_os_cobrado` (total real del medio OS) y `total_os` (devengado
  informativo), `motivo_diferencia`, `observacion`, `responsable_id`, `cerrado_at`.
- **Tablas nuevas no previstas en el ERD**: `cobros_pendientes`, `ajustes_post_cierre` y
  `cuentas_por_cobrar_os`.
- **Endpoints nuevos**: `/api/caja/cierres`, `/api/caja/pendientes*` y `/api/caja/reportes` no
  figuran en el ERD ni en `CHANGES.md:305`; se agregan porque sin ellos el cierre y la
  corrección post-cierre no son operables.

Se documentan para reconciliar con Martin (mismo criterio que C-09 con
`hallazgo_id`/`idempotency_key`).

## Risks / Trade-offs

- **Dinero mal registrado o descuadrado** → montos en centavos, `CHECK monto > 0`, totales en el
  servidor, cierre snapshot inmutable y auditoría con `antes`/`después`.
- **Anulación post-cierre que "arregla" el pasado** → prohibido: el día cerrado rechaza altas y
  la corrección es un compensatorio fechado hoy más un ajuste contra el cierre; el cierre
  conserva sus totales y la consulta muestra ambas cifras.
- **Doble imputación desde C-09** → C-10 no confía en el llamador: UNIQUE por
  `(tenant, linea, tramo)` sin `medio` y UNIQUE de pendientes sin condición de resolución; el
  replay idéntico es no-op y cualquier diferencia responde `409`.
- **Carrera movimiento ↔ cierre** → `pg_advisory_xact_lock` por `(tenant, fecha)` en la misma
  transacción; probado con dos conexiones reales, no con adaptadores en memoria.
- **`medio=NULL` de C-09 sin representación contable** → `cobros_pendientes` en vez de un
  movimiento con medio nulo (el enum de RN-CJ-01 no lo admite).
- **Devengado OS confundido con caja** → vive en `cuentas_por_cobrar_os` y `total_os` se rotula
  informativo; el cobro real llega con C-12 (C10-OQ-10).
- **Divergencia con el ERD** → ver §Desviaciones del ERD.
- **Un solo cierre por día sin reapertura** → costo aceptado de v1 (C10-OQ-1).
- **PHI en una caja** → sólo ids y montos; nunca nombre, DNI, teléfono ni texto clínico.
- **Zona horaria** → offset fijo `-03:00` en v1 (C10-OQ-8).
- **Gate de diseño** → sin sistema de diseño aprobado no hay UI; el change queda backend.

## Governance ALTO — condiciones de avance

1. Revisión de este proposal + `design.md` + las dos delta specs por el dueño y, si aplica, por
   quien lleve la contabilidad del consultorio piloto.
2. `C10-OQ-2`, `C10-OQ-8` y `C10-OQ-10` quedan **fijadas** por las decisiones del dueño; el resto
   sigue abierto y aceptado explícitamente como pendiente (`design.md` §Open Questions).
3. Correr `revisor-escenarios-turnos` sobre `specs/caja/spec.md` y `specs/cierre-caja/spec.md` y
   corregir los `BLOQUEANTE`/`MAYOR`.
4. Aprobación explícita del dueño antes de cualquier `/opsx:apply`. Sin ese paso el change queda
   en planificación aunque `openspec validate --strict` esté en verde.
