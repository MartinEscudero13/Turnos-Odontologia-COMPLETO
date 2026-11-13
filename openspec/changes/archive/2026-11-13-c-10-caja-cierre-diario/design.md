# Design — C-10 `caja-cierre-diario`

> Estado: **preparado, no implementado**. Este documento decide el HOW; el QUÉ está en
> `specs/caja/spec.md` y `specs/cierre-caja/spec.md`, y el porqué en `proposal.md`.
> Governance **ALTO**: no se implementa sin revisión y aprobación del dueño.
> Decisiones del dueño del 2026-11-12 incorporadas: **D1** ledger `ajustes_post_cierre`,
> **D2** C-09 intacto y `503` como punto de observación, **D3** motivo obligatorio/observación
> opcional, **D4** tramo OS como cuenta por cobrar informativa.

## UI Mockups

- Decision: **no (UI diferida a change aparte `C-10-UI`, 2026-11-12, por decisión del
  dueño)**.
- Design system revision: **no aplica** — este change no produce trabajo visual.
- Alcance de C-10 v1: **backend + contratos + migración 008 + tests**. C-10 **no toca
  `frontend/`**: no hay páginas, componentes, estilos, mockups ni tests de UI.
- El detalle de la postergación y sus criterios futuros vive en `proposal.md` §Diferido a
  C-10-UI y en `tasks.md` §12; **no** hay requirements de UI en las delta specs.

## Context

Ver `proposal.md` §Dependencias. Estado real del repo que condiciona el diseño:

- **C-03 implementado**: `usuarios` con `tenant_id`/`rol` (`backend/app/models/usuario.py`) y
  auditoría append-only (`RN-AU-02`); el `Actor` de C-05 trae `tenant_id`, `rol`, `user_id`,
  `profesional_id` (`backend/app/turnos/servicio.py:30-36`).
- **C-05 implementado**: tabla `turnos` (`backend/app/models/turno.py`) y jerarquía
  `TurnoError` → `Invalido` 422 / `Prohibido` 403 / `NoEncontrado` 404
  (`backend/app/turnos/servicio.py:71-96`); `presupuesto` agrega `Conflicto` 409.
- **C-09 archivado el 2026-11-12**: el puerto real es
  `ImputacionPort.imputar_caja(*, tenant_id, presupuesto_id, linea_id, paciente_id,
  prestacion_id, monto_paciente_centavos, monto_os_centavos, actor_id, turno_id, medio)`
  (`backend/app/presupuesto/puertos.py:286-316`) y `MedioPago` se define en
  `puertos.py:35`. El servicio invoca **caja primero y agenda después**
  (`backend/app/presupuesto/servicio.py:611-637`) y traduce cualquier excepción del puerto a
  `ServicioNoDisponible` 503 (`servicio.py:516-519`).
- **`aceptaciones` no tiene columna `medio`**: la tabla de la 007 tiene
  `(id, tenant_id, linea_id, acepta, fecha, canal, creado_en)`
  (`backend/alembic/versions/007_odontograma_presupuesto.py:102-114`) y el modelo coincide
  (`backend/app/models/presupuesto.py:121-139`). `Aceptacion.medio` existe sólo en el dominio
  en memoria (`puertos.py:123-140`) y C-10 **no** lo persiste ni toca C-09.
- La migración head es `007_odontograma_presupuesto`; la siguiente es **008**.
- Reglas duras (`AGENTS.md`): `tenant_id` + RLS forzada, SQLAlchemy para datos (SQL crudo sólo en
  Alembic), type hints, sin PHI, migraciones reversibles, dinero en centavos, `mypy --strict`.
- **No existe** ninguna tabla de caja, ni `senas`/`pagos_mp` (C-11), ni
  `obras_sociales`/`liquidaciones` (C-12).

## Goals / Non-Goals

**Goals:** registrar todo movimiento de caja con medio, tipo, usuario y fecha; anular con motivo
sin borrar; compensar y asentar ajustes sin editar un cierre; cerrar el día con totales por medio,
diferencia explicada y responsable; implementar el adaptador real del puerto de C-09 con
idempotencia por tramo y sin doble ingreso de OS; consultar el día con snapshot vs vigentes y
reportar caja por rango; RLS, auditoría y cero PHI. **La UI queda fuera** (`C-10-UI`).

**Non-Goals:** cobrar señas o hablar con Mercado Pago (C-11); liquidar obras sociales o cobrar la
OS (C-12); reportes de agenda (C-15); reabrir un cierre; conciliación bancaria; comisiones de
medios de pago; job de cierre automático; arqueo por cajero; multi-moneda; exportación 1-clic
(C-15); **toda pantalla, componente o test de frontend**.

## Decisions

### D1 — Fecha operativa (DATE), instantes (timestamptz) y offset `-03:00`

La KB define `movimientos_caja.fecha` y `cierres_diarios UNIQUE(tenant_id, fecha)`
(`04_modelo_de_datos.md` §senas/pagos_mp/movimientos/cierres). Un cierre que se compara contra
"el día" no puede depender de un instante:

- `movimientos_caja.fecha`, `cierres_diarios.fecha`, `cobros_pendientes.fecha`,
  `ajustes_post_cierre` (vía su cierre) y `cuentas_por_cobrar_os.fecha` son `DATE` = **día
  operativo** del consultorio.
- Todos los **instantes** son `timestamptz`: `creado_en`, `anulado_en`, `cerrado_at`,
  `resuelto_en`.
- El día operativo se calcula con el **reloj inyectado** en el offset fijo **`-03:00`**
  (**C10-OQ-8 fijada por el dueño**): `ahora=2026-11-11T01:30:00Z` ⇒ `fecha=2026-11-10`. No se
  agrega columna de timezone por tenant.

Esto no contradice la regla dura de "fechas aware": aplica a instantes; una fecha operativa es un
día calendario y convertirla a `timestamptz` haría que `UNIQUE(tenant, fecha)` dejara de significar
"un cierre por día". Los instantes nunca se derivan de la fecha: los pone el reloj.

Alternativas: (a) `fecha TIMESTAMPTZ` + rango → exige una zona por tenant que la KB no define y
rompe el UNIQUE del cierre; (b) `fecha TEXT` → pierde orden y comparación; (c) sólo `creado_en` →
no hay día operativo ni cierre posible.

### D2 — Estados y transiciones del movimiento: vigente → anulado, una sola vez

Un movimiento es un **hecho** (entró/salió plata en un medio, un día, por un usuario), no un saldo
editable.

```
                    POST /api/caja/movimientos
                              │
                              ▼
                        ┌───────────┐   anular (motivo, actor, ahora)
                        │  VIGENTE  │ ─────────────────────────────┐
                        └───────────┘                              ▼
                              │                            ┌──────────────┐
                              │ anular en día CON cierre   │   ANULADO    │
                              └───────────────────────────►│ (+ motivo,   │
                                        y crea            │  actor, fecha)│
                                        compensatorio +   └──────────────┘
                                        ajuste                    │
                                                         segunda anulación ⇒ 409
```

- Única transición: `vigente → anulado`. `anulado → vigente` no existe; una segunda anulación
  responde `409 ANULADO` (no hay segundo compensatorio ni segundo ajuste).
- `anulado` sólo cambia con motivo, actor e instante en la **misma** operación (CHECK en DB:
  `anulado = false OR (motivo_anulacion <> '' AND anulado_por IS NOT NULL AND anulado_en IS NOT NULL)`).
- `monto`, `medio`, `tipo`, `fecha`, `tramo`, `turno_id`, `usuario_id`, `linea_id` son
  **inmutables**: no hay endpoint que los edite y el `GRANT UPDATE` es por columna sólo para las
  cuatro columnas de anulación. `REVOKE DELETE` (RN-CJ-03).
- Un compensatorio sigue exactamente las mismas reglas: se puede anular y, si su día está cerrado,
  genera otro compensatorio (N7).

### D3 — Anulación pre/post cierre, compensatorio y ledger `ajustes_post_cierre`

Flujo 5 es explícito: "anulación post-cierre → requiere motivo + nuevo movimiento compensatorio
(nunca edita el cierre)" (`07_flujos_principales.md:51`). El dueño fijó además que la corrección y
el cobro de un pendiente de un día ya cerrado **se asientan en un ledger propio** (`D1`), nunca
insertando en la fecha cerrada y nunca recalculando el cierre.

| Situación | Efecto |
|---|---|
| Día **sin** cierre | `anulado=true` + motivo + actor + instante. Sin compensatorio ni ajuste. El movimiento sale de los totales vigentes del día. |
| Día **con** cierre | `anulado=true` (sobre la fila original, sólo las 4 columnas permitidas) **y** un `MovimientoCaja(origen=COMPENSACION, tipo inverso, mismo medio, mismo monto, compensa_a_id=original, fecha=día del registro)` **y** un `ajustes_post_cierre(tipo=AJUSTE_ANULACION, cierre_id, movimiento_original_id, monto, medio, motivo, actor, compensatorio_id)`. |
| Alta o imputación con `fecha` de un día con cierre | `409 CIERRE_CERRADO`. No hay excepción "porque es un ajuste": el ajuste va por el camino de anulación/cobro, que deja motivo y trazabilidad. |
| Cobro de pendiente cuya `fecha` tiene cierre | `201`: `MovimientoCaja(origen=IMPUTACION, tramo=PACIENTE, fecha=día del registro)` + `ajustes_post_cierre(tipo=COBRO_PENDIENTE, cierre_id, cobro_pendiente_id, monto, medio, compensatorio_id=<ese ingreso>)` + pendiente resuelto. |
| Día del registro también cerrado | `409 CIERRE_CERRADO`: no hay día abierto donde materializar el ajuste; no se toca el día cerrado. |

**Modelo del ledger** (`ajustes_post_cierre`): `id`, `tenant_id`, `cierre_id` (FK
`cierres_diarios`), `tipo` ∈ {`AJUSTE_ANULACION`, `COBRO_PENDIENTE`}, `movimiento_original_id?`
(FK `movimientos_caja`, obligatorio en `AJUSTE_ANULACION`), `cobro_pendiente_id?` (FK
`cobros_pendientes`, obligatorio en `COBRO_PENDIENTE`), `monto > 0`, `medio`, `motivo?`
(obligatorio en `AJUSTE_ANULACION`, nulo en `COBRO_PENDIENTE`), `actor_id`, `creado_en` y
`compensatorio_id` (el movimiento que materializa el ajuste en el día abierto; nombre conservado
de la decisión del dueño). El ledger **no suma** en los totales de caja ni en `diferencia`: sólo
explica por qué los totales vigentes de un día cerrado difieren de su snapshot.

**Por qué el compensatorio va con la fecha del registro**: el cierre es un snapshot inmutable. Si
se fechara en el día cerrado, ese día tendría un movimiento que su cierre no cuenta. Fechado hoy,
el efecto contable cae donde corresponde y el cierre anterior sigue siendo reproducible. Es una
decisión de diseño (el dueño puede revertirla sin cambiar el modelo, sólo la fecha).

**Consecuencia declarada (H6)**: los `totales_vigentes` de un día cerrado pueden diferir de los
`totales_cierre` persistidos. La consulta diaria devuelve **ambos** y `difieren_del_cierre: bool`;
el cierre nunca se recalcula y la UI futura rotula la diferencia como "anulación posterior al
cierre". `difieren_del_cierre` compara sólo los cuatro totales de caja (`total_efectivo`,
`total_transferencia`, `total_mp`, `total_os_cobrado`), nunca el devengado informativo `total_os`.
`totales_vigentes` usa las claves de respuesta `efectivo`, `transferencia`, `mp` y `os`;
`totales_cierre` devuelve los nombres persistidos (`total_efectivo`, …).

Alternativas: (a) prohibir la anulación post-cierre → el error queda sin remedio; (b) editar el
cierre → viola Flujo 5 y RN-CJ-02; (c) bloquear la anulación post-cierre con `409` → reemplazado por D1 del
dueño; (d) fechar el compensatorio en el día cerrado → rompe la reproducibilidad.

### D4 — Cierre diario: fórmula, totales, devengado OS y día sin responsable

`CierreDiario` `UNIQUE (tenant_id, fecha)` con:

- `total_efectivo`, `total_transferencia`, `total_mp`, `total_os_cobrado` **enteros en centavos**:
  neto por medio = Σ INGRESOS vigentes − Σ EGRESOS vigentes de ese medio. Pueden ser negativos
  (un día con más egresos que ingresos) → sin `CHECK >= 0` en los totales; sí `monto > 0` por
  movimiento.
- `total_os` = **informativo devengado** (D4 del dueño): Σ `cuentas_por_cobrar_os.monto_centavos`
  del día. No sale de `movimientos_caja`, no entra en `diferencia` ni en `difieren_del_cierre`.
  `total_os_cobrado` es el total real del medio OS (cobros efectivos, creados por C-12 o
  manualmente) y sí es comparable con los movimientos.
- `efectivo_contado INTEGER NOT NULL CHECK (efectivo_contado >= 0)`.
- `diferencia INTEGER NOT NULL CHECK (diferencia = efectivo_contado - total_efectivo)`. **Sólo el
  efectivo se cuenta físicamente** (Flujo 5 paso 2; **C10-OQ-2 fijada por el dueño**): el resto son
  totales informativos del sistema y no se concilian en v1.
- `responsable_id UUID NOT NULL REFERENCES usuarios(id)`; `cerrado_at TIMESTAMPTZ NOT NULL`.
- `motivo_diferencia TEXT NULL`, `observacion TEXT NULL`;
  `CHECK (diferencia = 0 OR (motivo_diferencia IS NOT NULL AND motivo_diferencia <> ''))`.
  **D3 del dueño**: el motivo es obligatorio con diferencia ≠ 0 y la **observación es opcional** y
  auditable (la auditoría registra su presencia, no su contenido). El servicio normaliza
  `motivo_diferencia=""` y `observacion=""` a `NULL` antes de persistir, para que el CHECK no
  convierta un campo vacío del cliente en un `500`.

**Responsable obligatorio** (`07_flujos_principales.md:51`, "día con movimientos sin responsable →
no cierra"): el payload exige `responsable_id` y debe ser un usuario **del tenant**; ausente ⇒
`422` sin persistir y el día sigue abierto; de otro tenant ⇒ `404`. Se elimina el error
`MOVIMIENTOS_SIN_RESPONSABLE` y su rama de "movimiento importado sin usuario": no es verificable
(la columna es `NOT NULL` y no hay importador) y una defensa no testeable no es una garantía.

**Obligatoriedad (RN-CJ-02)**: v1 no tiene scheduler. Se implementa como: (i) el estado del día es
consultable; (ii) el cierre es inmutable; (iii) un día cerrado rechaza altas. Un día anterior sin
cerrar **no** bloquea operar y su cierre atrasado **sí** se permite (interpretación de C10-OQ-3,
M3). Un día **futuro** no se cierra: lo dejaría inmutable antes de operar (interpretación
declarada, N9). Un día sin movimientos se cierra en 0 (C10-OQ-4).

Alternativas: (a) diferencia por cada medio → no hay conteo físico de transferencias/MP; (b)
`diferencia = contado − total general` → mezcla efectivo con devengado OS; (c) cerrar sin
responsable → contradice Flujo 5; (d) bloquear el día siguiente → bloqueo operativo inventado.

### D5 — `medio = NULL` de C-09: cobros pendientes con fecha operativa

C-09 admite `medio=None` y su spec lo declara: la aceptación se registra (`200`) con
`medio=NULL`, el puerto recibe `NULL` y **C-10 lo completa al cobrar**
(`openspec/specs/presupuesto/spec.md`, "El medio de pago es opcional al registrar la
aceptación"). C-10 **no puede fallar** con `medio=NULL`: la aceptación respondería `503` y su test
de contrato quedaría roto.

RN-CJ-01 fija el enum de medios: no existe un "movimiento sin medio"; un cargo no cobrado no es un
movimiento. Por eso:

- `cobros_pendientes(id, tenant_id, fecha, presupuesto_id, linea_id, paciente_id, monto_centavos,
  actor_id, turno_id?, creado_en, resuelto_en?, movimiento_id?)`.
- UNIQUE pleno `(tenant_id, linea_id)` — **sin** condición de resolución (H1): un replay posterior
  al cobro no crea un segundo pendiente.
- **No suma a los totales** y no aparece como movimiento; aparece en la consulta diaria en una
  sección aparte.
- `POST /api/caja/pendientes/{id}/cobrar` con `medio` válido crea el `MovimientoCaja`
  (`origen=IMPUTACION`, `tramo=PACIENTE`, `fecha` = la del pendiente si el día está abierto; si
  está cerrado, `fecha` = día del registro + ajuste, ver D3), marca `resuelto_en`/`movimiento_id`
  y audita ambos hechos. Segundo cobro ⇒ `409 COBRO_YA_RESUELTO`.
- Un tramo en 0 no genera pendiente ni movimiento.

Alternativas: (a) movimiento con `medio NULL` + estado PENDIENTE → agrega valores que RN-CJ-01 no
tiene; (b) rechazar `NULL` con `422` → rompe C-09; (c) imputar a `EFECTIVO` por defecto → inventa
un medio y descuadra el arqueo.

### D6 — Adaptador real del puerto de C-09 (contrato intacto, OS fuera de la caja)

C-10 implementa `ImputacionPort.imputar_caja` **con la firma exacta** de
`backend/app/presupuesto/puertos.py:303-316` y reutiliza `MedioPago` importado de
`app.presupuesto.puertos` (**no** redeclara el `Literal`). No se toca el protocolo, ni el servicio
de C-09, ni su spec. `imputar_agenda` no es de C-10: el adaptador compuesto mantiene la intención
como no-op (C-09 M10) y C-05 sigue siendo el dueño del turno.

| Campo del puerto | Destino | Regla |
|---|---|---|
| `tenant_id`, `presupuesto_id`, `linea_id`, `paciente_id` | `movimientos_caja` | RLS + filtro explícito; trazabilidad sin PHI |
| `prestacion_id` | **no se persiste** | derivable por `linea_id → presupuesto_lineas.prestacion_id` |
| `monto_paciente_centavos` | `INGRESO(medio=medio, tramo='PACIENTE')` o `cobros_pendientes` si `medio IS NULL` | `0` ⇒ no se crea nada |
| `monto_os_centavos` | `cuentas_por_cobrar_os(monto_centavos, fecha)` | `0` ⇒ no se crea nada; **nunca** un `INGRESO` |
| `actor_id` | `usuario_id` / `actor_id` del pendiente | quien registró la aceptación |
| `turno_id` | `turno_id` | FK nullable; `NULL` en v1 (el turno es de C-05) |
| `medio` | medio del **tramo del paciente** | describe cómo paga el paciente, no el tramo OS |
| (servidor) reloj `-03:00` | `fecha`, `creado_en` | día del registro, no la fecha del turno |

Reglas del adaptador:

1. **Dos tramos, dos hechos distintos**: el tramo paciente es caja; el tramo OS es una cuenta por
   cobrar informativa. La invariante `paciente + os = linea.monto` sigue en la línea de
   presupuesto, pero la suma de **movimientos** del día es sólo el tramo paciente.
2. **`canal` no es `medio`**: `canal` (`CONSULTORIO`/`LINK`) queda en `aceptaciones` y no se copia
   a la caja.
3. **`medio='OS'` en el tramo del paciente ⇒ `422 MEDIO_OS_RESERVADO`** (C10-OQ-5).
4. **`medio` inválido ⇒ `422`** (defensa: C-09 ya valida, C-10 no confía).
5. **Idempotencia por tramo (H1)**: UNIQUE parcial
   `(tenant_id, linea_id, tramo) WHERE linea_id IS NOT NULL AND origen = 'IMPUTACION'`. El `medio`
   **no** forma parte de la clave: un replay con otro medio responde `409 IMPUTACION_DUPLICADA` y
   nunca duplica el ingreso. Para el tramo OS, `cuentas_por_cobrar_os` tiene
   `UNIQUE (tenant_id, linea_id)`.
6. **Sin doble ingreso de OS**: el devengado se registra una sola vez en
   `cuentas_por_cobrar_os`; C-12 creará el `INGRESO(medio='OS')` real al acreditar y podrá usar
   `tramo='OS'` con el mismo UNIQUE, de modo que jamás existan dos ingresos por el mismo monto.
7. **Atomicidad (M4)**: los dos tramos y la aceptación de C-09 viven en la **misma unidad de
   trabajo** (`servicio.py:442` + `puertos.py:349-361`). Si la caja falla, C-09 no persiste la
   aceptación; se prueba contra PostgreSQL real, no sólo con adaptadores en memoria.
8. **Aislamiento**: `linea_id`/`presupuesto_id` se validan contra el tenant; un id de T2 no crea
   nada en T1 (`404`).

**Punto de observación de errores (D2 del dueño/H5)**: el adaptador expone `422/409/404` con
`codigo` HTTP cuando se lo invoca directamente. A través de `POST /api/presupuestos/:id/aceptar`,
`_imputar_linea` captura **cualquier** excepción y lanza `_FalloImputacion`, que el servicio
traduce a `ServicioNoDisponible` (`servicio.py:516-519`, 611-637). Por eso los escenarios declaran
el código correcto según el punto de observación: `422/409/404` contra el adaptador y `503` (sin
persistir la aceptación) vía C-09. C-10 **no** modifica C-09 para "mejorar" esa traducción.

Alternativas: (a) persistir `prestacion_id` → columna derivable sin uso contable; (b) un solo
movimiento con el monto total → mezcla caja con devengado y hace imposible conciliar la cuenta por
cobrar; (c) crear el `INGRESO` de OS en la aceptación → dos ingresos por el mismo monto cuando
C-12 acredite (prohibido por D4).

### D7 — RLS y aislamiento multi-tenant

Las **cinco** tablas nuevas llevan `tenant_id UUID NOT NULL REFERENCES tenants(id)`, RLS
`ENABLE` + `FORCE`, y la política fail-closed idéntica a la 006/007:

```sql
USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
```

`NULLIF(...)` evita el `42704` cuando el parámetro no existe y convierte la cadena vacía en `NULL`:
la comparación no es verdadera para ninguna fila ⇒ 0 filas sin excepción. Es el mismo predicado
corregido de C-09 (`backend/alembic/versions/007_odontograma_presupuesto.py:144-158`).

Toda query del dominio recibe `tenant_id` explícito y un id de T2 nunca resuelve en T1 ⇒ `404`.
Los hijos lógicos (`cobros_pendientes`, `ajustes_post_cierre`, `cuentas_por_cobrar_os`) llevan
`tenant_id` propio además de las FKs, para que una consulta directa siga cubierta.

Alternativas: (a) heredar el tenant sólo por join → fuga por consulta directa a la tabla hija; (b)
RLS sólo en movimientos → cierres, pendientes y ajustes quedarían abiertos; (c) `::uuid` sin
`NULLIF` → `42704` en vez de 0 filas.

### D8 — Migración 008 reversible, sin tocar `aceptaciones`

`008_caja_cierre_diario.py`, `down_revision = "007_odontograma_presupuesto"`.

| Tabla | Columnas | Constraints |
|---|---|---|
| `movimientos_caja` | `id uuid PK`, `tenant_id`, `fecha date`, `medio text`, `monto int`, `tipo text`, `tramo text?`, `turno_id uuid?`, `usuario_id uuid`, `anulado bool default false`, `motivo_anulacion text?`, `anulado_por uuid?`, `anulado_en timestamptz?`, `compensa_a_id uuid?` (self-FK), `presupuesto_id uuid?`, `linea_id uuid?`, `paciente_id uuid?`, `origen text default 'MANUAL'`, `creado_en timestamptz` | `CHECK medio IN ('EFECTIVO','TRANSFERENCIA','MP','OS')`; `CHECK tipo IN ('INGRESO','EGRESO')`; `CHECK monto > 0`; `CHECK tramo IS NULL OR tramo IN ('PACIENTE','OS')`; `CHECK (origen <> 'IMPUTACION' OR tramo IS NOT NULL)`; `CHECK origen IN ('MANUAL','IMPUTACION','COMPENSACION')`; `CHECK (anulado = false OR (motivo_anulacion <> '' AND anulado_por IS NOT NULL AND anulado_en IS NOT NULL))`; `CHECK (origen <> 'COMPENSACION' OR compensa_a_id IS NOT NULL)`; FKs `ON DELETE RESTRICT` |
| `cierres_diarios` | `id`, `tenant_id`, `fecha date`, `total_efectivo int`, `total_transferencia int`, `total_mp int`, `total_os_cobrado int`, `total_os int`, `efectivo_contado int`, `diferencia int`, `responsable_id uuid`, `motivo_diferencia text?`, `observacion text?`, `cerrado_at timestamptz`, `creado_en` | `UNIQUE (tenant_id, fecha)`; `CHECK diferencia = efectivo_contado - total_efectivo`; `CHECK efectivo_contado >= 0`; `CHECK (diferencia = 0 OR (motivo_diferencia IS NOT NULL AND motivo_diferencia <> ''))`; `CHECK (motivo_diferencia IS NULL OR motivo_diferencia <> '')`; `CHECK (observacion IS NULL OR observacion <> '')`; FK `responsable_id` `ON DELETE RESTRICT` |
| `cobros_pendientes` | `id`, `tenant_id`, `fecha date`, `presupuesto_id`, `linea_id`, `paciente_id`, `monto_centavos int`, `actor_id uuid`, `turno_id uuid?`, `creado_en`, `resuelto_en timestamptz?`, `movimiento_id uuid?` | `CHECK monto_centavos > 0`; `CHECK (resuelto_en IS NULL) = (movimiento_id IS NULL)`; **UNIQUE `(tenant_id, linea_id)` sin condición de resolución**; FKs `ON DELETE RESTRICT` |
| `ajustes_post_cierre` | `id`, `tenant_id`, `cierre_id`, `tipo text`, `movimiento_original_id uuid?`, `cobro_pendiente_id uuid?`, `monto int`, `medio text`, `motivo text?`, `actor_id uuid`, `compensatorio_id uuid NOT NULL`, `creado_en` | `CHECK tipo IN ('AJUSTE_ANULACION','COBRO_PENDIENTE')`; `CHECK monto > 0`; `CHECK medio IN (...)`; `CHECK ((tipo='AJUSTE_ANULACION' AND movimiento_original_id IS NOT NULL AND cobro_pendiente_id IS NULL) OR (tipo='COBRO_PENDIENTE' AND cobro_pendiente_id IS NOT NULL AND movimiento_original_id IS NULL))`; `CHECK (tipo <> 'AJUSTE_ANULACION' OR (motivo IS NOT NULL AND motivo <> ''))`; UNIQUE parcial `(tenant_id, movimiento_original_id)` y `(tenant_id, cobro_pendiente_id)`; FKs `ON DELETE RESTRICT` |
| `cuentas_por_cobrar_os` | `id`, `tenant_id`, `fecha date`, `presupuesto_id`, `linea_id`, `paciente_id`, `monto_centavos int`, `creado_en` | `CHECK monto_centavos > 0`; `UNIQUE (tenant_id, linea_id)`; FKs `ON DELETE RESTRICT` |

- Índices: `(tenant_id, fecha)` y `(tenant_id, fecha, medio)` en movimientos;
  `(tenant_id, turno_id)`; `(tenant_id, resuelto_en)` en pendientes; `(tenant_id, fecha)` en
  ajustes y en cuentas por cobrar.
- **UNIQUE parcial de idempotencia por tramo**:
  `CREATE UNIQUE INDEX movimientos_caja_tenant_linea_tramo_unique ON movimientos_caja
  (tenant_id, linea_id, tramo) WHERE linea_id IS NOT NULL AND origen = 'IMPUTACION'`.
- **Grants**: `movimientos_caja` `SELECT, INSERT`; `REVOKE DELETE`; `GRANT UPDATE (anulado,
  motivo_anulacion, anulado_por, anulado_en)`. `cierres_diarios` `SELECT, INSERT` y **`REVOKE
  UPDATE, DELETE`**. `cobros_pendientes` `SELECT, INSERT`, `GRANT UPDATE (resuelto_en,
  movimiento_id)`, `REVOKE DELETE`. `ajustes_post_cierre` y `cuentas_por_cobrar_os` `SELECT,
  INSERT` y `REVOKE UPDATE, DELETE` (C-12 ampliará la cuenta por cobrar cuando cobre).
- **Sin addendum**: la 008 **no** agrega ninguna columna a `aceptaciones`. El medio de pago vive
  sólo en `movimientos_caja`; C-09 no se toca y su `medio` sigue existiendo únicamente en el
  dominio en memoria.
- `downgrade()` elimina sólo lo de la 008 (drop de las 5 tablas y sus políticas) sin tocar 001–007
  ni `aceptaciones`.
- **No** se crean `senas`, `pagos_mp`, `obras_sociales`, `coberturas` ni `liquidaciones`.

**Desviaciones del ERD documentadas** (`04_modelo_de_datos.md`): `movimientos_caja.tramo`,
`presupuesto_id`, `linea_id`, `paciente_id`, `origen` y `compensa_a_id`; en `cierres_diarios`
`total_os_cobrado`, `total_os` (devengado informativo), `motivo_diferencia`, `observacion` y
`responsable_id`; y las tablas nuevas `cobros_pendientes`, `ajustes_post_cierre` y
`cuentas_por_cobrar_os`. Se agregan porque sin `tramo`/`linea_id` la imputación no es idempotente,
sin `compensa_a_id` el compensatorio no es trazable (RN-CJ-03) y sin el ledger de ajustes la
corrección post-cierre no tendría dónde vivir sin editar el cierre. Se reconcilian con Martin.

### D9 — Estrategia de tests (TDD rojo primero, tres niveles)

1. **Dominio puro (sin DB, adaptadores en memoria)**: registro con los 4 medios y ambos tipos,
   montos inválidos, anulación con/sin motivo, segunda anulación, totales netos, día cerrado,
   compensatorio, ajustes, pendientes, adaptador de imputación (dos tramos, tramo 0, `medio=NULL`,
   replay idéntico/con otro medio/con otro monto, `medio='OS'` en tramo paciente), RBAC,
   auditoría y PHI.
2. **PostgreSQL real con dos conexiones independientes**: (a) dos cierres simultáneos ⇒ `201`/`409`
   y un solo cierre; (b) dos imputaciones simultáneas de la misma línea y tramo ⇒ un solo
   movimiento, nunca `500`; (c) dos anulaciones simultáneas ⇒ `200`/`409`, un compensatorio y un
   ajuste; (d) **carrera movimiento ↔ cierre**: o el movimiento entra antes y se cuenta, o el
   cierre gana y el alta da `409 CIERRE_CERRADO`, nunca un movimiento del día fuera del cierre;
   (e) **atomicidad multi-tabla**: un fallo de caja revierte la aceptación de C-09.
3. **Migración real (PostgreSQL de test)**: 008 upgrade/downgrade/re-upgrade, CHECKs (`monto=0`,
   `diferencia` inconsistente, `efectivo_contado<0`, motivo obligatorio con diferencia ≠ 0,
   `tramo` obligatorio en imputación, `medio` inválido), UNIQUE del cierre, UNIQUE por
   `(tenant, linea, tramo)`, UNIQUE del pendiente sin condición de resolución, RLS fail-closed
   (0 filas sin `42704`), `DELETE`/`UPDATE` rechazados según grants, y **`aceptaciones` sin columna
   `medio`**.

**Gate de suite (M8)**: `py -m pytest tests/ -q` con `C02_DATABASE_URL` apuntando a PostgreSQL
migrado y exigiendo **`skipped == 0`**. Si la variable no está configurada, el gate **falla
explícitamente**: no se acepta un verde con tests de integración salteados. Además
`py -m mypy backend/app/caja` (config `strict`, `pyproject.toml`) en el mismo gate.

**Cada escenario de los specs tiene una tarea con el nombre exacto del test en `tasks.md`.**
La UI no se testea en C-10: sus criterios quedan en `proposal.md` §Diferido a C-10-UI y en
`tasks.md` §12.

Datos ficticios: "Paciente Demo", "Otro Paciente Demo", PACI-1/PACI-9, "Conducto Demo", usuarios
U1 (RECEPCION), U2 (ADMIN), U3 (ODONTOLOGO). Reloj siempre inyectado; fechas operativas
`2026-11-10`; instantes `-03:00`. Regresión C-03/C-05/C-09 en verde.

### D10 — RBAC literal de la matriz

| Operación | PACIENTE | ODONTOLOGO | RECEPCION | ADMIN |
|---|---|---|---|---|
| Leer movimientos / cierres / pendientes | — (paga seña por link, C-11) | **R** | R | R |
| Registrar movimiento | — | — | sí | sí |
| Cobrar un pendiente (elige medio) | — | — | sí | sí |
| Anular con motivo | — | — | **no** (`403`) | **sí** |
| Cerrar el día | — | — | sí | sí |
| Reabrir un cierre | — | — | — | **no existe** (C10-OQ-1) |
| Leer reportes de caja | — | R | R | R |
| Exportar caja (CSV/JSON) | — | — | **no** | **sí, en C-15** |

`03_actores_y_roles.md:24` da "Recepción: CRUD movimientos, cierre" y "Admin: CRUD + anular con
motivo"; la anulación queda reservada a **ADMIN** (C10-OQ-9). `03_actores_y_roles.md:28` separa
"Auditoría / exportación 1-clic" con **Recepción: R** y **Admin: R + exportar**: la **exportación
es de ADMIN** y no se implementa en C-10 (vive en C-15, `GET /api/exportacion`), así que
`GET /api/caja/reportes/export` no existe (`404`). Recepción **sí lee** `GET /api/caja/reportes` y
`GET /api/caja/cierres`. Un rol sin permiso ⇒ `403`; recurso de otro tenant ⇒ `404`; identidad de
paciente ⇒ `401` (DD-06/DD-07).

### D11 — Auditoría append-only y ausencia de PHI

Acciones auditadas con `AuditoriaPort` (C-03/C-08, RN-AU-02), siempre con `antes`/`después`:

| Acción | Cuándo | Datos (sin PHI) |
|---|---|---|
| `MOVIMIENTO_CAJA_REGISTRADO` | alta manual o por imputación | `tenant_id`, actor, `movimiento_id`, `fecha`, `medio`, `tipo`, `monto`, `turno_id`, `linea_id`, `antes=null`, `después=<fila>` |
| `MOVIMIENTO_CAJA_ANULADO` | anulación | `movimiento_id`, `motivo_anulacion`, actor, `compensatorio_id` (si aplica), `antes={"anulado": false}`, `después={"anulado": true, "motivo_anulacion": ...}` |
| `MOVIMIENTO_COMPENSATORIO_REGISTRADO` | post-cierre | `movimiento_id`, `compensa_a_id`, `medio`, `tipo`, `monto`, `fecha` |
| `AJUSTE_POST_CIERRE_REGISTRADO` | anulación o cobro post-cierre | `ajuste_id`, `cierre_id`, `tipo`, `monto`, `medio`, `compensatorio_id` |
| `COBRO_PENDIENTE_REGISTRADO` | `medio=NULL` | `pendiente_id`, `linea_id`, `fecha`, `monto`, actor |
| `COBRO_PENDIENTE_RESUELTO` | cobro del pendiente | `pendiente_id`, `movimiento_id`, `medio`, `ajuste_id?`, actor |
| `CIERRE_DIARIO_REGISTRADO` | cierre | `cierre_id`, `fecha`, los totales, `efectivo_contado`, `diferencia`, `responsable_id`, `motivo_diferencia`, `observacion_cargada` |

Nunca se registran nombre, DNI, teléfono, texto clínico ni el contenido libre de una observación:
la auditoría registra sólo su presencia (`observacion_cargada: true`). No hay acción de reapertura
porque la reapertura no existe.

### D12 — Reportes base: caja acá, KPIs de agenda en C-15

`CHANGES.md:305` menciona "reportes base (ocupación, ausentismo, facturación por profesional)"
dentro de la UI de `/caja`, pero `CHANGES.md:405` asigna esos KPIs a **C-15**. C-10 expone sólo lo
que la caja puede calcular sola:

- `GET /api/caja/reportes?desde=&hasta=` ⇒ facturación neta **sobre movimientos vigentes** por
  medio y por día, `fuente: "movimientos_vigentes"`, cantidad de cierres y de movimientos anulados
  del período. Si un día cerrado tuvo una anulación posterior, el reporte muestra el valor vigente
  y no el snapshot (H6).
- `GET /api/caja/cierres?desde=&hasta=` ⇒ listado de cierres con totales, `efectivo_contado`,
  `diferencia` y responsable.
- **No** se expone ocupación, ausentismo, facturación por profesional (C-15) ni exportación
  (C-15/ADMIN).
- La "seña aplicada" del Flujo 5 no se expone en C-10: no hay `senas`; C-11 la registrará como
  movimiento `MP` (C10-OQ-6).

### D13 — UI diferida a `C-10-UI`

El repo exige sistema de diseño aprobado antes de cualquier UI (política `design-mockups`,
`AGENTS.md`) y C-09 sentó el precedente. C-10 v1 es backend + contratos + migración 008 + tests: no
hay mockups, no hay `design-system/` nuevo y no se toca `frontend/`. La SPA `/caja` se planifica y
aprueba en `C-10-UI`, que consume estos endpoints. Es una decisión pendiente del dueño (crear
`C-10-UI` antes o después de aplicar C-10), declarada en `proposal.md` §Diferido a C-10-UI.

### D14 — Carrera movimiento ↔ cierre: advisory lock por `(tenant, fecha)`

Todo camino que escribe un movimiento o un hecho de caja de un día toma, **en la misma
transacción**, `pg_advisory_xact_lock(hashtext(tenant_id || ':' || fecha::text))` **antes** de
validar el estado del día y de insertar:

- alta manual de movimiento;
- cobro de pendiente (sobre la fecha objetivo);
- compensatorio y ajuste (sobre la fecha del registro);
- creación de pendiente y de cuenta por cobrar desde el adaptador (sobre la fecha operativa);
- cierre del día (antes de leer totales y de insertar la fila).

Sin el lock, un movimiento puede leer "día abierto", el cierre leer totales sin ese movimiento y
ambos commitear: el día queda cerrado con un movimiento fuera del cierre. Con el lock, el orden es
total: o el movimiento entra antes y el cierre lo cuenta, o el cierre gana y el alta responde
`409 CIERRE_CERRADO`. Una colisión de `hashtext` sólo serializa de más (seguro). El lock es
`xact`: se libera solo al commit/rollback y no requiere unlock explícito.

## Seams

```python
# --- C-03/C-05 reales (se consumen; no se modifican) ---
# Actor(tenant_id, rol, user_id, profesional_id)      -> app.turnos.servicio
# Invalido(422), Prohibido(403), NoEncontrado(404)    -> app.turnos.servicio
# Conflicto(409), ServicioNoDisponible(503)           -> app.presupuesto.servicio
# turnos / usuarios (FK)                              -> modelos C-05 / C-03
# AuditoriaPort / UnidadDeTrabajo                     -> C-03 / C-09

# --- C-09 define; C-10 IMPLEMENTA (firma intacta) ---
from app.presupuesto.puertos import MedioPago

class ImputacionPort(Protocol):
    def imputar_agenda(...) -> None: ...
    def imputar_caja(
        self, *, tenant_id: str, presupuesto_id: str, linea_id: str,
        paciente_id: str, prestacion_id: str,
        monto_paciente_centavos: int, monto_os_centavos: int,
        actor_id: str, turno_id: str | None,
        medio: MedioPago | None,
    ) -> None: ...

# --- C-10 define ---
class MovimientoCajaRepositorio(Protocol):
    def registrar(self, *, tenant_id, fecha, medio, monto, tipo, usuario_id,
                  tramo=None, turno_id=None, presupuesto_id=None, linea_id=None,
                  paciente_id=None, origen="MANUAL", compensa_a_id=None,
                  ahora=None) -> Movimiento: ...
    def obtener(self, *, tenant_id, movimiento_id) -> Movimiento | None: ...
    def listar_por_fecha(self, *, tenant_id, fecha) -> list[Movimiento]: ...
    def buscar_imputacion(self, *, tenant_id, linea_id, tramo) -> Movimiento | None: ...
    def anular(self, *, tenant_id, movimiento_id, motivo, actor_id, ahora=None) -> Movimiento: ...

class CierreRepositorio(Protocol):
    def cerrar(self, *, tenant_id, fecha, efectivo_contado, responsable_id,
               motivo_diferencia=None, observacion=None, ahora=None) -> Cierre: ...
    def obtener(self, *, tenant_id, fecha) -> Cierre | None: ...
    def listar(self, *, tenant_id, desde, hasta) -> list[Cierre]: ...

class CobroPendienteRepositorio(Protocol):
    def registrar(self, *, tenant_id, fecha, presupuesto_id, linea_id, paciente_id,
                  monto_centavos, actor_id, turno_id=None, ahora=None) -> CobroPendiente: ...
    def obtener(self, *, tenant_id, pendiente_id) -> CobroPendiente | None: ...
    def buscar_por_linea(self, *, tenant_id, linea_id) -> CobroPendiente | None: ...
    def listar(self, *, tenant_id, fecha=None) -> list[CobroPendiente]: ...
    def resolver(self, *, tenant_id, pendiente_id, movimiento_id, ahora=None) -> CobroPendiente: ...

class AjustePostCierreRepositorio(Protocol):
    def registrar(self, *, tenant_id, cierre_id, tipo, monto, medio, actor_id,
                  compensatorio_id, movimiento_original_id=None,
                  cobro_pendiente_id=None, motivo=None, ahora=None) -> Ajuste: ...
    def listar_por_cierre(self, *, tenant_id, cierre_id) -> list[Ajuste]: ...

class CuentaPorCobrarOSRepositorio(Protocol):
    def registrar(self, *, tenant_id, fecha, presupuesto_id, linea_id, paciente_id,
                  monto_centavos, ahora=None) -> CuentaPorCobrarOS: ...
    def buscar_por_linea(self, *, tenant_id, linea_id) -> CuentaPorCobrarOS | None: ...
    def total_devengado(self, *, tenant_id, fecha) -> int: ...

class TotalesCajaPort(Protocol):
    def totales_por_medio(self, *, tenant_id, fecha) -> dict[MedioPago, int]: ...

class UnidadDeTrabajo(Protocol):
    def __enter__(self) -> "UnidadDeTrabajo": ...
    def __exit__(self, *exc) -> None: ...   # commit en éxito, rollback en error
    def bloquear_dia(self, *, tenant_id: str, fecha: date) -> None: ...  # advisory xact lock
    def bloquear_movimiento(self, *, tenant_id: str, movimiento_id: str) -> Movimiento: ...
```

## Risks / Trade-offs

- [Snapshot vs vigentes] → se declara (D3): la consulta muestra ambas cifras y
  `difieren_del_cierre`; el cierre nunca se recalcula. Reabrir es C10-OQ-1.
- [Compensatorio y cobro fechados el día del registro] → decisión explícita (D3), reversible sin
  cambiar el modelo; el auditor ve `compensa_a_id`, el ajuste y el motivo.
- [Doble imputación por reintento del puerto] → UNIQUE por `(tenant, linea, tramo)` sin `medio` y
  UNIQUE de pendientes sin condición; probado con dos conexiones reales.
- [C-09 cambia su adaptador y rompe la firma] → test de contrato de anotaciones reales
  (`tests/test_contrato_imputacion_caja.py`) con `MedioPago` importado, más `mypy --strict`.
- [Medio `OS` en el tramo del paciente] → `422 MEDIO_OS_RESERVADO`; copago por OS es C10-OQ-5.
- [Devengado OS confundido con caja] → `cuentas_por_cobrar_os` + `total_os` informativo; el cobro
  real llega con C-12 (C10-OQ-10).
- [Recepción no puede anular] → lectura literal de la matriz (C10-OQ-9).
- [Cierre sin scheduler que no se hace] → v1 expone estado y bloquea altas post-cierre
  (C10-OQ-3/C10-OQ-4).
- [PHI en observaciones] → la observación vive en el cierre; la auditoría registra sólo su
  presencia.
- [Drift entre dominio en memoria y SQLAlchemy] → wiring real es follow-up declarado (igual que
  C-06/C-07/C-08/C-09); los tests de migración cubren CHECKs, UNIQUE, locks y RLS.
- [Zona horaria] → offset fijo `-03:00` en v1 (C10-OQ-8 fijada).

## Migration Plan

1. **DDL (008)**: crear `movimientos_caja`, `cierres_diarios`, `cobros_pendientes`,
   `ajustes_post_cierre` y `cuentas_por_cobrar_os`; FKs, CHECKs de D8, índices, UNIQUE del cierre,
   UNIQUE por tramo, RLS forzada y grants por columna. **Sin** tocar `aceptaciones`. Reversible.
2. **Modelos SQLAlchemy** en `backend/app/models/caja.py` (`MovimientoCaja`, `CierreDiario`,
   `CobroPendiente`, `AjustePostCierre`, `CuentaPorCobrarOS`) con `Mapped[...]`, `Date` para la
   fecha operativa, `timestamptz` para instantes, PK uuid y CHECKs espejo.
3. **Dominio** en `backend/app/caja/`: entidades, `puertos.py` (protocolos + adaptadores en
   memoria), `servicio.py` (movimientos, anulación, compensación, ajustes, pendientes, cierre,
   reportes) y `adaptador_imputacion.py` (implementa `imputar_caja` de C-09).
4. **Borde**: `backend/app/routers/caja.py`, `backend/app/schemas/caja.py` (`extra="forbid"`,
   montos `int` estrictos, `date` para la fecha operativa, `AwareDatetime` para instantes). Sin
   `PATCH`/`DELETE` de movimientos ni de cierres y sin endpoint de exportación.
5. **Sin frontend**: la SPA `/caja` es `C-10-UI`; C-10 no crea ni modifica archivos de
   `frontend/`.
6. Sin env var nueva y sin secretos; `.env.example` intacto.
7. Rollback = `alembic downgrade 007_odontograma_presupuesto` (la 008 sólo agrega tablas).
8. Verificación: `py -m pytest tests/ -q` **con `C02_DATABASE_URL`** y `skipped == 0`,
   `py -m mypy backend/app/caja` y `openspec validate c-10-caja-cierre-diario --strict`.

## Open Questions

| OQ | Estado | Pregunta | Respaldo | Comportamiento implementado |
|---|---|---|---|---|
| C10-OQ-1 | **Fijada 2026-11-12** | ¿Se puede reabrir un cierre? ¿Quién, con qué motivo? | `07_flujos_principales.md:51`; RN-CJ-02 | No en v1; no hay endpoint. Si alguna vez hace falta, cierre de ajuste que no borra el original |
| C10-OQ-2 | **Fijada 2026-11-12** | ¿La diferencia se mide sólo contra efectivo? | Flujo 5 paso 2 | Sí, sólo efectivo (marcado en `specs/cierre-caja`) |
| C10-OQ-3 | **Fijada 2026-11-12** (interpretación) | ¿Retro-fecha? ¿Se bloquea operar si ayer no se cerró? | RN-CJ-02 | Se permite mientras el día no esté cerrado y **no** se bloquea operar; el cierre atrasado se permite (M3) |
| C10-OQ-4 | **Fijada 2026-11-12** | ¿Un día sin movimientos puede cerrarse? | RN-CJ-02 | Sí, cierre en 0 |
| C10-OQ-5 | **Fijada 2026-11-12** | ¿Copago del paciente con medio `OS`? | C-09 D6 | `422 MEDIO_OS_RESERVADO` |
| C10-OQ-6 | **Fijada 2026-11-12** | ¿La seña aplicada se registra como movimiento `MP` y quién lo crea? | `07_flujos_principales.md:48`; `CHANGES.md:325` | C-11 crea el movimiento `MP`; C-10 no modela señas |
| C10-OQ-7 | **Fijada 2026-11-12** | ¿Un pendiente impago se cancela sin movimiento? | RN-CL-02; C-09 `C09-OQ-11` | No en v1: queda visible e impago |
| C10-OQ-8 | **Fijada 2026-11-12** (provisional) | ¿Zona horaria configurable por tenant o offset fijo? | `02_descripcion_general.md` | Offset fijo `-03:00` (marcado en `specs/caja`); configurable post-v1 |
| C10-OQ-9 | **Fijada 2026-11-12** (provisional) | ¿Recepción puede anular o sólo ADMIN? | `03_actores_y_roles.md:24` | Sólo ADMIN |
| C10-OQ-10 | **Fijada 2026-11-12** | ¿La OS es caja o cuenta por cobrar y quién cobra? | `04_modelo_de_datos.md`; `CHANGES.md:343` | `total_os` informativo devengado; el cobro real lo crea C-12 |

> Las 10 OQ quedaron resueltas por el dueño el 2026-11-12 y se registran en `docs/decisiones-po.md`
> §C-10 (esa es la fuente de verdad). Se marcan en la spec con su `C10-OQ-N` donde fijan
> comportamiento observable. Las marcadas *provisional* (OQ-8, OQ-9) se revisan en el piloto; no
> habilitan otra implementación sin cambiar este design.

## Notas de implementación (no vinculantes)

- Actor por headers (`actor_desde_headers`) igual que C-05/C-07/C-08/C-09; el JWT real de C-03
  reemplaza la dependencia sin cambiar el contrato.
- Errores: `Invalido` 422 (monto/medio/tipo/fecha/responsable/motivo faltante con diferencia ≠ 0,
  `OS` en el tramo del paciente, día futuro); `Prohibido` 403 (RBAC); `NoEncontrado` 404
  (cross-tenant); `Conflicto` 409 (`CIERRE_CERRADO`, `ANULADO`, `IMPUTACION_DUPLICADA`,
  `CIERRE_EXISTENTE`, `COBRO_YA_RESUELTO`); `401` si la petición trae identidad de paciente.
  `MOVIMIENTOS_SIN_RESPONSABLE` **no existe** (M1).
- `bloquear_dia` implementa `pg_advisory_xact_lock(hashtext(tenant_id || ':' || fecha::text))`;
  los adaptadores en memoria sólo simulan el lock y **no** prueban la garantía: eso vive en los
  tests con dos conexiones a PostgreSQL.
- Los totales del cierre se calculan en el servidor desde `movimientos_caja` (4 totales de caja) y
  desde `cuentas_por_cobrar_os` (`total_os` informativo); el cliente sólo envía
  `efectivo_contado`, `responsable_id`, `motivo_diferencia?` y `observacion?`.
- Datos ficticios: "Paciente Demo", "Otro Paciente Demo", PACI-1/PACI-9, "Conducto Demo",
  U1/U2/U3; ningún monto ni nombre real (RN-GL-03).
