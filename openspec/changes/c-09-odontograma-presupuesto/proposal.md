# Proposal — C-09 `odontograma-presupuesto`

## Why

C-04 persiste el paciente y C-08 la ficha clínica con evoluciones inmutables, pero hoy
no existe forma de registrar **qué pieza tiene qué hallazgo** ni de convertir ese
hallazgo en **un presupuesto que el paciente acepte y que se cobre**. RN-CL-01 exige
odontograma FDI con historial por pieza y que cada hallazgo pueda derivar en línea de
presupuesto (`knowledge-base/05_reglas_de_negocio.md:32`); RN-CL-02 exige aceptación
parcial y que **solo lo aceptado impute a agenda/caja** (`:33`); RN-OS-01 exige
cobertura OS **configurable**, no validada en vivo (`:39`). Sin C-09 el flujo clínico
muere en la evolución y el presupuesto queda como un papel suelto — exactamente lo que
RN-CL-02 prohíbe ("el odontograma nunca es un dibujo suelto").

## What Changes

- **Odontograma FDI con historial por pieza**: `OdontogramaHallazgo(tenant, paciente,
  pieza_fdi, superficie?, hallazgo, fecha, profesional, resuelto bool)`. `pieza_fdi`
  se valida contra la grilla FDI permanente (cuadrantes 1–4 × dientes 1–8: 11–18,
  21–28, 31–38, 41–48); `19/29/39` y cualquier posición fuera de la grilla se rechazan.
  El historial es la secuencia de hallazgos de la pieza; el contenido clínico es
  inmutable y sólo `resuelto` puede pasar de `false` a `true` (auditado).
- **Derivación en 1 clic**: un hallazgo se deriva a una línea de presupuesto
  (`pieza + prestación + monto`) en la **misma transacción**; si la línea no es válida,
  el hallazgo tampoco se persiste. El `POST` de derivación exige un header
  `Idempotency-Key` (UUID del cliente): mismo key + mismo payload devuelve el mismo
  par `hallazgo_id`/`linea_id` sin crear nada; mismo key + payload distinto responde
  `409`.
- **Presupuesto por pieza**: `Presupuesto(tenant, paciente, estado BORRADOR/VIGENTE/
  PARCIAL/ACEPTADO/VENCIDO, vence_en?)` + `PresupuestoLinea(pieza_fdi?, prestacion,
  monto, cobertura_os, a_cargo_paciente)` + `Aceptacion(linea, acepta, fecha, canal)`.
- **Cobertura OS como puerto**: el cálculo de `cobertura_os`/`a_cargo_paciente` se pide
  a un `CoberturaPort`; C-12 (obras sociales) todavía NO existe, así que v1 usa un
  adaptador que devuelve **sin cobertura** y cae al fallback documentado: **100 %
  particular** (`a_cargo_paciente = monto`, `cobertura_os = 0`), visible y honesto
  ("configurada, no validada en vivo", RN-OS-01 / DD-04). Una configuración de
  cobertura inválida devuelta por el puerto se **descarta** (nunca se usa), cae al
  mismo fallback, se audita y jamás se persiste una línea con totales inconsistentes.
- **Imputación como puerto**: aceptar líneas produce un evento de imputación a agenda
  (C-05) y caja (C-10) a través de `ImputacionPort`. **C-10 no está implementado**:
  v1 no crea tablas de caja ni movimientos; deja el hook y el adaptador en memoria. La
  imputación es idempotente por línea aceptada (una línea aceptada no se vuelve a
  imputar).
- **Aceptación parcial/total**: el paciente (o recepción en su nombre) acepta o rechaza
  líneas; el estado del presupuesto pasa a `PARCIAL` o `ACEPTADO`. Lo no aceptado queda
  para recupero/recall (US-032 CA-2) sin imputar nada.
- **Endpoints**: `/api/odontograma` (registro y derivación en un POST; la derivación
  exige header `Idempotency-Key`), `/api/odontograma/{id}/resolver`, `/api/presupuestos`,
  `/api/presupuestos/{id}/lineas`, `/api/presupuestos/{id}/emitir`,
  `/api/presupuestos/{id}/aceptar`.
- **UI**: página `/odontograma` con las 32 piezas de la grilla FDI (11–18, 21–28,
  31–38, 41–48), historial por pieza, botón "derivar a presupuesto" y vista del
  presupuesto con totales por cobertura y a cargo.
- **Migración 007**: `odontograma_hallazgos`, `presupuestos`, `presupuesto_lineas`
  (con `idempotency_key` y UNIQUE parcial por tenant), `aceptaciones` + RLS forzada,
  CHECK de grilla FDI, CHECKs de montos e inmutabilidad clínica, reversible.

## Capabilities

### New Capabilities

- `odontograma`: hallazgos FDI por pieza/superficie con historial, validación de la
  grilla FDI permanente (cuadrante 1–4 × diente 1–8), inmutabilidad del contenido
  clínico, gate de consentimiento, derivación atómica e idempotente hallazgo → línea de
  presupuesto y RBAC clínico.
- `presupuesto`: presupuesto por pieza con líneas (monto, cobertura OS, a cargo
  paciente), estados, aceptación parcial/total, imputación sólo de lo aceptado a
  través de puertos de agenda/caja, fallback 100 % particular, descarte auditado de
  cobertura inválida y aislamiento multi-tenant.

### Modified Capabilities

_(ninguna)_ — C-09 **consume** `ficha-clinica` (gate de consentimiento y ficha) y
`turnos-anti-solape` (existencia/atención del profesional y agenda como destino de
imputación), pero no cambia sus requirements: no se modifica la matriz de estados de
turnos ni el gate de C-08.

## Fuera de alcance (diferido explícito)

- **Caja (C-10)**: no hay tablas `movimientos_caja`/`cierres_diarios`, ni medios de
  pago, ni cierre diario. C-09 sólo define `ImputacionPort.imputar_caja(...)` y lo deja
  cableado a un adaptador en memoria. El movimiento real, su anulación y el cierre son
  de C-10.
- **Obras sociales (C-12) — limitación declarada**: no hay `obras_sociales` ni
  `coberturas` persistidas. **La tabla de coberturas del tenant llega con C-12
  (migración 010)**; C-09 **NO** crea esa tabla ni una equivalente. C-09 define
  `CoberturaPort.cobertura(...)`; el cálculo por porcentaje/monto/tope se implementa
  cuando C-12 exista. Hasta entonces el adaptador devuelve `None` ⇒ **toda línea es
  100 % particular visible** (`origen_cobertura = SIN_COBERTURA`,
  `validada_en_vivo = false`). Esta es una limitación aceptada del v1, no un pendiente
  de C-09.
- **Validación OS en vivo**: explícitamente fuera de v1 (RN-OS-01 / DD-04). El
  presupuesto declara `validada_en_vivo = false` y `origen_cobertura = CONFIGURADA |
  SIN_COBERTURA`.
- **Generación automática de turnos con fecha/sillón**: C-09 emite la intención de
  imputación; elegir slot y crear el turno sigue siendo C-05 / Flujo 1.
- **Señas (C-11)**: el presupuesto no calcula ni cobra señas. Si una línea aceptada
  deriva en un turno con seña, el monto/porcentaje y la política son de C-11
  (`docs/decisiones-po.md` PO-01); C-09 no fija ningún valor de seña.
- **Anulación de presupuesto**: la matriz RBAC dice "Admin: crear, anular"
  (`03_actores_y_roles.md:23`) pero el enum de estados de la KB no tiene `ANULADO`
  (`04_modelo_de_datos.md:66`). No se inventa estado ni endpoint: queda como pregunta
  abierta.
- **Odontograma gráfico 3D, superficies múltiples por pieza y dentición decidua
  (5x/6x/7x/8x)**: fuera de v1. La dentición decidua queda como pregunta abierta
  (C09-OQ-1) y no se implementa.

## Dependencias

| Dependencia | Estado | Qué aporta a C-09 |
|---|---|---|
| **C-04** `catalogos-pacientes-base` | Archivado/implementado | `Paciente`, `Prestacion` (con `precio_base` en centavos), `Profesional`; base del `monto` por defecto y del RBAC por tenant |
| **C-08** `ficha-clinica-consentimiento` | Archivado/implementado | Ficha 1—1, patrón puertos/adaptadores, jerarquía `TurnoError` y **gate de consentimiento con `timestamp` válido** (`409 CONSENTIMIENTO_REQUERIDO`) |
| **C-05** `turnos-anti-solape` | Implementado | `Actor`, `TurnoPort.atiende(...)` ("pacientes que atiende") y destino de la imputación de agenda |
| **C-03** `auth-rbac-auditoria` | Implementado | Matriz RBAC y auditoría append-only (`RN-AU-02`) |
| **C-10** `caja-cierre-diario` | **NO implementado** | Hook `ImputacionPort.imputar_caja`; implementación diferida |
| **C-12** `obras-sociales-liquidacion` | **NO implementado** | Hook `CoberturaPort`; v1 cae a 100 % particular |

## Risks / Trade-offs

- **Cobertura calculada con datos que aún no existen** → el contrato del puerto y el
  fallback 100 % particular se testean; ningún porcentaje/tope se hardcodea y la UI
  declara "configurada, no validada en vivo". Una configuración inválida se descarta
  (fallback + auditoría), nunca se usa para calcular.
- **Derivación duplicada por doble clic/reintento** → `Idempotency-Key` obligatorio,
  UNIQUE por tenant y replay con el mismo par `hallazgo_id`/`linea_id`; key distinta de
  payload ⇒ `409`.
- **Imputación a caja/agenda sin C-10** → se define el puerto y la idempotencia por
  línea; C-10 sólo tiene que implementar el adaptador. Riesgo residual: el día que C-10
  cablee, el contrato debe conservarse (test de contrato por puerto).
- **Redondeo de porcentajes de cobertura** → invariante `cobertura_os +
  a_cargo_paciente = monto` a nivel DB y centavos enteros; el resto va al paciente
  (nunca se crea dinero). La política exacta de redondeo es OQ.
- **Deriva entre hallazgo y línea** → `hallazgo_id` FK + transacción atómica; sin ella
  el presupuesto pierde trazabilidad clínica.
- **PHI en respuestas/logs** → allow-list en schemas, auditoría con ids y montos, nunca
  el texto del hallazgo ni nombre/teléfono.
- **Vencimiento sin plazo definido en la KB** → `vence_en` explícito por presupuesto;
  no se inventa un TTL por defecto.
