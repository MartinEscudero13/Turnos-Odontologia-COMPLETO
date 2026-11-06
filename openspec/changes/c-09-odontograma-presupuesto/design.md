# Design — C-09 `odontograma-presupuesto`

> Estado: **preparado, no implementado**. Este documento decide el HOW; el QUÉ está en
> `specs/odontograma/spec.md` y `specs/presupuesto/spec.md`, y el porqué en `proposal.md`.

## UI Mockups

- Decision: **sí, code-first** — no hay archivo de Figma/Stitch asociado. La página
  `/odontograma` se diseña con la skill `visual-turnos` (modo Operate, audiencia
  odontólogo/recepción) y se verifica con screenshots 375/768/1440 en el apply.
- Fecha: 2026-11-06

## Context

Ver `proposal.md` §Dependencias. Estado real del repo que condiciona el diseño:

- **C-04 implementado**: `Prestacion.precio_base: int` en centavos y `Prestacion.activa`
  (`backend/app/models/catalogos.py:34-51`), `Paciente`, `Profesional`. Dinero en
  centavos es convención de C-03 (`CHANGES.md:160`).
- **C-08 implementado**: patrón dominio puro + puertos + adaptadores en memoria
  (`backend/app/ficha_clinica/puertos.py`), `ServicioFichaClinica` y
  `ConsentimientoRequerido(TurnoError)` con `codigo=409`
  (`backend/app/ficha_clinica/servicio.py:32`); `crear_router(svc)` +
  `actor_desde_headers` (`backend/app/routers/ficha_clinica.py:64`).
- **C-05 implementado**: `Actor`, `Invalido` (422), `Prohibido` (403),
  `NoEncontrado` (404) (`backend/app/turnos/servicio.py:71-96`); `TurnoPort.atiende`
  define "pacientes que atiende" en C-08.
- **C-10 y C-12 NO implementados**: no existen tablas ni servicios de caja ni de obras
  sociales. Por eso el diseño usa **puertos** y un fallback explícito.
- La migración head es `006_ficha_clinica`; la siguiente es **007** (coincide con
  `CHANGES.md:284`).
- Reglas duras (`AGENTS.md`): `tenant_id` + RLS forzada en toda tabla, SQLAlchemy para
  datos (SQL crudo sólo en Alembic), type hints, TS estricto, datos ficticios, sin PHI
  en logs/mensajes, migraciones reversibles con `timestamptz`/PK uuid/CHECK en DB.

## Goals / Non-Goals

**Goals:** hallazgo FDI con historial e inmutabilidad clínica; derivación atómica a
línea de presupuesto; presupuesto con estados, aceptación parcial/total e imputación
sólo de lo aceptado; cobertura OS y caja detrás de puertos; fallback 100 % particular;
RLS y auditoría; UI mínima operable.

**Non-Goals:** implementar C-10/C-12; validar cobertura en vivo; generar turnos con
fecha/sillón; calcular señas (C-11); anular presupuestos; odontograma gráfico avanzado o
dentición decidua (5x/6x/7x/8x); wiring SQLAlchemy real de los repositorios (follow-up
del proyecto, igual que C-06/C-07/C-08).

## Decisions

### D1 — Validación FDI estricta sobre la grilla permanente

RN-CL-01 dice "piezas 11–48" (`knowledge-base/05_reglas_de_negocio.md:32`) y el modelo
repite `pieza_fdi (11–48)` (`04_modelo_de_datos.md:64`); la notación FDI completa
(cuadrante 1–4 × diente 1–8) es la lectura correcta de ese rango. v1 valida:

- entero de dos dígitos: decena = cuadrante `1..4`, unidad = diente `1..8`;
- set válido = `{11–18, 21–28, 31–38, 41–48}` (32 posiciones);
- `19`, `29`, `39` (diente 9 inexistente), `10`, `49`, `00` y cualquier valor no
  entero ⇒ `422` con mensaje explícito
  `pieza FDI inválida: cuadrante 1–4 y diente 1–8 (11–18, 21–28, 31–38, 41–48)`;
- el rango se valida también a nivel DB con
  `CHECK ((pieza_fdi / 10) BETWEEN 1 AND 4 AND (pieza_fdi % 10) BETWEEN 1 AND 8)`
  (división entera de PostgreSQL), no con un simple `BETWEEN 11 AND 48`.

La **dentición decidua** (5x/6x/7x/8x), los supernumerarios y las superficies múltiples
quedan fuera de v1 y como OQ (C09-OQ-1); no se implementan.

Alternativas: (a) aceptar cualquier entero 11–48 → admite piezas inexistentes y viola la
notación FDI; (b) validar sólo en Pydantic → un INSERT directo podría saltarse la regla;
por eso el CHECK va también en DB.

### D2 — Historial por pieza: contenido clínico inmutable, `resuelto` como único estado mutable

Un hallazgo es un hecho clínico fechado; corregirlo es registrar otro hallazgo, igual
que RN-CL-03 con evoluciones (`05_reglas_de_negocio.md:34`). El historial de una pieza
es el conjunto ordenado por `fecha` de sus hallazgos. Para que `resuelto bool`
(`04_modelo_de_datos.md:64`) sea operable sin romper la trazabilidad:

- `GRANT SELECT, INSERT` sobre `odontograma_hallazgos`; **`GRANT UPDATE (resuelto)`**
  (grant por columna, PostgreSQL) y `REVOKE DELETE`.
- No hay endpoint que edite `pieza_fdi`, `superficie`, `hallazgo`, `fecha` ni
  `profesional_id`.
- `POST /api/odontograma/{id}/resolver` sólo permite `false → true`; un segundo intento
  sobre el mismo hallazgo responde `409`.

Alternativas: (a) append-only total y `resuelto` siempre `false` → deja el campo inútil;
(b) nuevo hallazgo "resuelve a aquel" → exige una columna que la KB no tiene;
(c) UPDATE libre → pierde historial clínico.

### D3 — Derivación hallazgo → presupuesto en una unidad de trabajo

"Hallazgo convertible en línea de presupuesto en 1 clic" (US-031 CA-2,
`06_funcionalidades.md:60`) y "DB (hallazgo + presupuesto, transacción)"
(`07_flujos_principales.md:32`). La derivación es **un caso de uso atómico**:

1. valida tenant, paciente, consentimiento, RBAC, FDI (D1) y `Idempotency-Key`;
2. busca la key en `presupuesto_lineas` del tenant:
   - existe y el payload coincide → responde `200` con el `hallazgo_id` y `linea_id`
     ya creados, **sin crear nada**;
   - existe y el payload difiere → `409`, sin mutación;
   - no existe → sigue;
3. crea el hallazgo;
4. crea o reutiliza el presupuesto `BORRADOR` del paciente;
5. crea la línea con `pieza_fdi` del hallazgo, `prestacion_id`, `monto`,
   `hallazgo_id` e `idempotency_key`;
6. si cualquier paso falla, no queda ni hallazgo ni línea (rollback de la unidad de
   trabajo).

El `monto` explícito gana; si se omite, se usa `Prestacion.precio_base` (C-04), que ya
está en centavos. No se inventa ningún precio.

**Idempotencia (D3.1)**: el header `Idempotency-Key` es obligatorio, UUID generado por
el cliente; ausente o no-UUID ⇒ `422`. La implementación más simple es una columna
`presupuesto_lineas.idempotency_key UUID NULL` con índice **UNIQUE parcial por tenant**
(`UNIQUE (tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL`): la línea ya
tiene `hallazgo_id`, así que una sola fila permite devolver ambos ids sin tabla nueva.
El "mismo payload" se compara contra los datos persistidos (hallazgo: `pieza_fdi`,
`superficie`, `hallazgo`, `fecha`, `profesional_id`; línea: `prestacion_id`, `monto`);
si todo coincide es replay (`200`), si algo difiere es `409`. La key es tenant-scoped.
Se descarta la tabla de deduplicación dedicada porque agrega una entidad y un TTL de
limpieza sin mejorar la garantía: el UNIQUE parcial ya la da. La primera creación
responde `201`; el replay, `200`.

**Desviación documentada**: `presupuesto_lineas.hallazgo_id UUID NULL` **no figura** en
la KB (`04_modelo_de_datos.md:66`), pero RN-CL-01 exige que cada hallazgo "pueda
derivar" en línea y sin FK la trazabilidad sólo viviría en auditoría (no consultable ni
verificable). Se agrega como columna nullable en la 007 y se anota para reconciliar el
ERD (mismo criterio que `adjuntos` en C-08 D11).

Alternativas: (a) sin FK, sólo auditoría → no se puede probar la derivación ni evitar
líneas huérfanas; (b) tabla intermedia hallazgo—línea → sobre-modela una relación 1—N
simple.

### D4 — Aceptación parcial: sólo líneas aceptadas imputan, una sola vez

`Aceptacion(linea_id, acepta bool, fecha, canal)` es un **ledger append-only** (el ERD
declara 1—N aceptaciones por línea, `04_modelo_de_datos.md:22`). Reglas:

- La decisión efectiva de una línea es su última `Aceptacion`; v1 **no permite cambiar
  una decisión ya tomada**: aceptar una línea con decisión previa `acepta=true`
  responde `409` (y una línea ya rechazada también queda cerrada en v1; reabrirla es
  C09-OQ-4).
- Sólo las líneas con `acepta=true` producen imputación; las rechazadas/pendientes no
  producen ningún efecto en agenda ni caja (RN-CL-02).
- La imputación es **idempotente por línea**: el evento lleva `linea_id` y una línea
  aceptada no se imputa dos veces; el segundo intento de aceptación ya falla en el
  paso anterior.
- La operación es atómica: se registran las aceptaciones, se recalcula el estado y se
  llama al puerto de imputación en la misma unidad de trabajo; si la imputación falla,
  **no** queda aceptación persistida (el adaptador en memoria implementa rollback).
- `canal` es texto no vacío; v1 usa valores documentados por el flujo ("CONSULTORIO",
  "LINK") y el enum completo es OQ (C09-OQ-5). El link público de aceptación es C-11/
  C-06-style follow-up; v1 registra el canal, no publica el link.
- La `fecha` de la aceptación la fija el **reloj del servidor** (inyectado), no el
  payload: es el timestamp del acto comercial que habilita la imputación.

Alternativas: (a) imputar el total del presupuesto al aceptar cualquier línea → viola
RN-CL-02; (b) permitir re-decisión libre → duplica imputaciones y rompe la trazabilidad
comercial.

### D5 — Estados y vencimiento sin TTL inventado

Estados de la KB: `BORRADOR, VIGENTE, PARCIAL, ACEPTADO, VENCIDO`
(`04_modelo_de_datos.md:66`). Transiciones:

```
BORRADOR ──emitir (≥1 línea)──► VIGENTE
VIGENTE  ──acepta algunas──────► PARCIAL
VIGENTE  ──acepta todas────────► ACEPTADO
PARCIAL  ──acepta las restantes► ACEPTADO
VIGENTE  ──vence_en < ahora────► VENCIDO   (evaluación perezosa al leer/aceptar)
```

- Se editan/eliminan líneas sólo en `BORRADOR`; en cualquier otro estado → `409`.
- No se acepta nada en `BORRADOR` ni en `VENCIDO` → `409`.
- `ACEPTADO` es final.
- `vence_en TIMESTAMPTZ NULL`: lo fija quien emite. **No hay plazo por defecto**: la KB
  no define días de vigencia. Si `vence_en` es `NULL`, el presupuesto no vence solo.
- El vencimiento se evalúa contra el reloj inyectado; no hay job en v1.
- Presupuesto sin ninguna línea no se puede emitir → `409`.
- Qué pasa si **todas** las líneas se rechazan (0 aceptadas) no está definido por la KB
  (no existe estado `RECHAZADO`): OQ C09-OQ-3, no se inventa.

Alternativas: (a) TTL por defecto de N días → valor inventado; (b) job de vencimiento →
infraestructura sin respaldo y sin valor en v1; (c) estado `ANULADO` → no está en la KB
(ver proposal, fuera de alcance).

### D6 — Puertos de cobertura OS y de imputación (C-12/C-10 diferidos)

**Estado v1 explícito**: no existe la tabla de coberturas del tenant. La dueña es C-12
(migración 010); C-09 **no** crea esa tabla ni una equivalente. Hasta que C-12 exista,
el adaptador por defecto devuelve `None` y **toda línea es 100 % particular visible**
(`origen_cobertura = SIN_COBERTURA`, `validada_en_vivo = false`). Es una limitación
declarada y aceptada, no un pendiente de C-09.

Contratos con type hints; v1 trae adaptadores en memoria y un adaptador "sin cobertura".

```python
# C-09 define; C-12 lo implementará contra obras_sociales/coberturas
@dataclass(frozen=True)
class CoberturaConfigurada:
    modo: Literal["PORCENTAJE", "MONTO"]
    valor: int                  # % (0–100) o centavos
    tope: int | None            # centavos, opcional

class CoberturaPort(Protocol):
    def cobertura(
        self, *, tenant_id: str, obra_social_id: str | None, prestacion_id: str
    ) -> CoberturaConfigurada | None: ...

# C-09 define; C-05/C-10 lo implementarán
class ImputacionPort(Protocol):
    def imputar_agenda(
        self, *, tenant_id: str, presupuesto_id: str, linea_id: str,
        paciente_id: str, prestacion_id: str, monto_centavos: int,
    ) -> None: ...

    def imputar_caja(
        self, *, tenant_id: str, presupuesto_id: str, linea_id: str,
        monto_centavos: int, canal: str,
    ) -> None: ...
```

Reglas del cálculo (D6):

- `monto`, `cobertura_os`, `a_cargo_paciente` son **enteros en centavos**.
- Sin `obra_social_id` en el paciente o sin fila de cobertura → `cobertura_os = 0`,
  `a_cargo_paciente = monto`, `origen_cobertura = SIN_COBERTURA` (fallback del Flujo 3,
  `07_flujos_principales.md:35`).
- **Validación defensiva de la configuración (D6.1)**: antes de usarla se exige
  `modo ∈ {PORCENTAJE, MONTO}`, `valor` entero, `PORCENTAJE` en `0..100`, `MONTO >= 0`
  y `tope IS NULL OR tope >= 0`. Cualquier violación ⇒ la cobertura **no se usa**, se
  aplica el fallback 100 % particular, se registra auditoría
  `COBERTURA_INVALIDA_DESCARTADA` (con `prestacion_id`, `obra_social_id` y `motivo`;
  sin PHI) y la respuesta expone `origen_cobertura = SIN_COBERTURA` y
  `validada_en_vivo = false`.
- Con cobertura válida: se calcula `cobertura_os` y **siempre** se cumple
  `cobertura_os + a_cargo_paciente = monto` (CHECK en DB). La cobertura se recorta a
  `min(calculado, tope, monto)`; el resto queda a cargo del paciente. Una cobertura
  mayor al monto nunca produce saldo negativo.
- **Guard de totales (D6.2)**: después de calcular se valida
  `cobertura_os >= 0`, `a_cargo_paciente >= 0` y `cobertura_os + a_cargo_paciente = monto`.
  Si el guard falla (bug o valor no entero), se descarta la cobertura, se aplica el
  fallback 100 % particular y se audita igual que D6.1. **Nunca se persiste una línea
  con totales inconsistentes**: el CHECK de DB es la última barrera. El guard es
  testeable inyectando una calculadora de cobertura de prueba que devuelva totales
  inconsistentes (seam de test, no contrato público).
- `origen_cobertura = CONFIGURADA` sólo cuando la configuración pasó D6.1/D6.2;
  `validada_en_vivo = false` siempre en v1 (RN-OS-01 / DD-04); la UI lo muestra.
- Porcentajes con fracción de centavo: el cociente se trunca y el resto va al paciente
  (nunca se crea dinero). La política exacta es OQ (C09-OQ-6); los escenarios usan
  valores divisibles para no fijarla.
- `ImputacionPort` recibe **una llamada por línea aceptada**; C-09 no crea tablas de
  caja ni de agenda. El adaptador en memoria registra las llamadas para test.
- Una línea con `monto = 0`: se acepta, `a_cargo_paciente = 0`, no genera deuda; la
  llamada a caja con 0 es responsabilidad del adaptador de C-10 (no se inventa aquí).

Alternativas: (a) crear ya `movimientos_caja`/`coberturas` → invade C-10/C-12 y duplica
migraciones; **la tabla `coberturas` del tenant llega con C-12 (migración 010), no con
C-09**, y hasta entonces no se inventa una tabla equivalente; (b) calcular
`cobertura_os` en el frontend → viola la regla de borde validado en servidor y
RN-OS-01; (c) dejar la imputación como TODO sin contrato → C-10 no tendría con qué
integrarse; (d) confiar en la configuración del puerto sin validarla → un dato inválido
podría romper el CHECK o producir un saldo negativo.

### D7 — RLS y aislamiento multi-tenant con hijos tenant-scoped

Las 4 tablas llevan `tenant_id UUID NOT NULL REFERENCES tenants(id)`, RLS
`ENABLE` + `FORCE`, política `USING/WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)`
(mismo patrón que 002/006; `backend/alembic/versions/006_ficha_clinica.py:87-97`).
`presupuesto_lineas` y `aceptaciones` **también** llevan `tenant_id` propio (regla dura:
toda tabla de negocio filtra por tenant), además de la FK al padre. Toda query del
dominio recibe `tenant_id` explícito y un id de T2 nunca resuelve en T1 → `404`.

Alternativas: (a) heredar el tenant sólo por join al padre → una query directa a la
tabla hija no quedaría cubierta por la política; (b) RLS sólo en el padre → fuga por
hijos.

### D8 — Migración 007 reversible, con CHECKs de dominio

`007_odontograma_presupuesto.py`, `down_revision = "006_ficha_clinica"`.

| Tabla | Columnas | Constraints |
|---|---|---|
| `odontograma_hallazgos` | `id uuid PK`, `tenant_id`, `paciente_id`, `pieza_fdi smallint`, `superficie text?`, `hallazgo text`, `fecha timestamptz`, `profesional_id`, `resuelto bool default false`, `creado_en timestamptz` | `CHECK ((pieza_fdi / 10) BETWEEN 1 AND 4 AND (pieza_fdi % 10) BETWEEN 1 AND 8)`; `CHECK hallazgo <> ''`; `CHECK superficie IS NULL OR superficie <> ''`; FK paciente/profesional |
| `presupuestos` | `id`, `tenant_id`, `paciente_id`, `estado text`, `vence_en timestamptz?`, `creado_en`, `actualizado_en` | `CHECK estado IN ('BORRADOR','VIGENTE','PARCIAL','ACEPTADO','VENCIDO')`; FK paciente |
| `presupuesto_lineas` | `id`, `tenant_id`, `presupuesto_id`, `hallazgo_id uuid?`, `pieza_fdi smallint?`, `prestacion_id`, `monto int`, `cobertura_os int`, `a_cargo_paciente int`, `idempotency_key uuid?`, `creado_en` | `CHECK pieza_fdi IS NULL OR ((pieza_fdi / 10) BETWEEN 1 AND 4 AND (pieza_fdi % 10) BETWEEN 1 AND 8)`; `CHECK monto >= 0`; `CHECK cobertura_os >= 0`; `CHECK a_cargo_paciente >= 0`; `CHECK cobertura_os + a_cargo_paciente = monto`; FK presupuesto/prestación/hallazgo (`ON DELETE RESTRICT`) |
| `aceptaciones` | `id`, `tenant_id`, `linea_id`, `acepta bool`, `fecha timestamptz`, `canal text`, `creado_en` | `CHECK canal <> ''`; FK línea |

- Índices: `(tenant_id, paciente_id, pieza_fdi)` en hallazgos; `(tenant_id, paciente_id,
  estado)` en presupuestos; `(tenant_id, presupuesto_id)` en líneas; `(tenant_id,
  linea_id)` en aceptaciones; **UNIQUE parcial `(tenant_id, idempotency_key) WHERE
  idempotency_key IS NOT NULL`** en líneas (D3.1).
- `GRANT SELECT, INSERT` + `REVOKE DELETE` en las 4 tablas; `UPDATE` sólo en
  `presupuestos`/`presupuesto_lineas` (edición en BORRADOR, controlada en dominio) y
  `GRANT UPDATE (resuelto)` en `odontograma_hallazgos` (D2). `aceptaciones` sin
  `UPDATE`/`DELETE` (ledger append-only).
- `timestamptz` en todas las fechas, PK uuid, CHECK en DB (no sólo Pydantic).
- `downgrade()` elimina sólo las 4 tablas/políticas de la 007 sin tocar 001–006.
- **No** se crean tablas de caja, obras sociales, coberturas ni movimientos.

### D9 — Estrategia de tests (TDD rojo primero, sin DB real para el dominio)

Dos niveles, como C-08:

1. **Dominio puro (sin DB, adaptadores en memoria)**: FDI inválida (19/29/39 y fuera de
   grilla), historial por pieza, resolución única, derivación atómica (fallo de línea ⇒
   no hay hallazgo), idempotencia de derivación (replay 200, payload distinto 409, key
   faltante 422), estados y transiciones, aceptación parcial, rechazo, aceptación sobre
   línea ya aceptada, vencimiento, monto 0, fallback 100 % particular, cobertura con
   tope, **cobertura inválida descartada** (porcentaje fuera de rango, monto/tope
   negativos, totales inconsistentes), idempotencia de imputación y rollback si el
   puerto falla, RLS por tenant, RBAC y auditoría sin PHI.
2. **Migración real (PostgreSQL de test)**: 007 upgrade/downgrade/re-upgrade, CHECKs
   (`pieza_fdi=19` y `49` rechazados en DB, `cobertura_os + a_cargo_paciente <> monto`
   rechazado), UNIQUE parcial de `idempotency_key`, RLS real con rol no-owner, `UPDATE`
   de contenido clínico y `DELETE` de hallazgos/aceptaciones rechazados,
   `UPDATE (resuelto)` permitido.

Cada escenario de los specs tiene una tarea con el nombre exacto del test en
`tasks.md` (el revisor lo verifica). Datos ficticios ("Paciente Demo", "Otro Paciente
Demo", P1/P2, prestación "Conducto Demo" con `precio_base` ficticio). Reloj siempre
inyectado; fechas en `-03:00`. Regresión C-04/C-05/C-08 en verde.

### D10 — RBAC literal de la matriz

| Operación | PACIENTE | ODONTOLOGO | RECEPCION | ADMIN |
|---|---|---|---|---|
| Leer odontograma/ficha | propio | pacientes que atiende | R | CRUD |
| Escribir hallazgo / resolver | — | propio, pacientes que atiende | — | sí |
| Crear/editar presupuesto (BORRADOR) | — | sí | sí | sí |
| Aceptar/rechazar líneas | propio (`user_id == paciente_id`) | — (matriz: sólo crear) | sí (registra aceptación) | sí |
| Anular | — | — | — | **fuera de v1** (sin estado) |

Lectura literal de `03_actores_y_roles.md:22-23`. Un rol sin permiso → `403`; un recurso
de otro tenant → `404`. Recepción no escribe hallazgos (la matriz sólo le da R + crear
ficha base). El odontólogo no acepta presupuestos (la matriz sólo le da "crear"); si en
la práctica debe hacerlo, es OQ C09-OQ-7.

Alternativas: (a) permitir al odontólogo aceptar → contradice la matriz; (b) recepción
escribe hallazgos → contradice la matriz y mezcla lo clínico con lo administrativo.

### D11 — Gate de consentimiento reutilizado, no reimplementado

Toda operación clínica de C-09 (registrar hallazgo, derivar, resolver y **agregar una
línea con `pieza_fdi` o `hallazgo_id`**) exige una fila de `consentimientos` con
`timestamp` válido para `(tenant, paciente)`, usando el mismo puerto/servicio de C-08;
sin él → `409 CONSENTIMIENTO_REQUERIDO`. Una línea sin pieza (consulta administrativa)
no queda sujeta al gate. La aceptación de un presupuesto es un acto comercial y **no**
vuelve a exigir consentimiento (el presupuesto clínico ya nació de un hallazgo o de una
línea con pieza que lo exigió). La agenda sigue sin bloquearse (RN-AU-03: "bloquea
clínica, permite solo agenda").

Alternativas: (a) reimplementar el gate → duplica la autoridad y puede desincronizarse;
(b) no gatear la derivación → permite crear presupuesto clínico sin consentimiento.

### D12 — Auditoría y ausencia de PHI

Acciones auditadas: `HALLAZGO_REGISTRADO`, `HALLAZGO_RESUELTO`, `PRESUPUESTO_CREADO`,
`PRESUPUESTO_EMITIDO`, `LINEA_PRESUPUESTADA`, `ACEPTACION_REGISTRADA`,
`IMPUTACION_REGISTRADA`, `COBERTURA_INVALIDA_DESCARTADA`. Cada entrada lleva `tenant_id`,
actor, entidad, `entidad_id`, `antes`/`despues` con ids, pieza FDI, estado y montos —
**nunca** el texto del hallazgo, nombre, DNI ni teléfono. Para
`COBERTURA_INVALIDA_DESCARTADA` se registran `prestacion_id`, `obra_social_id` y `motivo`
(código del D6.1/D6.2), sin datos del paciente. Se reutiliza `AuditoriaPort` de
C-08/C-03 (RN-AU-02).

## Seams

```python
# --- C-04/C-05/C-08 reales (se consumen; no se modifican) ---
# Actor, Invalido(422), Prohibido(403), NoEncontrado(404)  -> app.turnos.servicio
# ConsentimientoRequerido(409)                             -> app.ficha_clinica.servicio
# TurnoPort.atiende(tenant_id, profesional_id, paciente_id) -> app.ficha_clinica.puertos
# PacientePort.existe / ProfesionalPort.existe             -> app.ficha_clinica.puertos
# PrestacionPort.precio_base(tenant_id, prestacion_id)     -> nuevo adaptador C-04

# --- C-09 define ---
class HallazgoRepositorio(Protocol):
    def registrar(self, *, tenant_id, paciente_id, pieza_fdi, superficie,
                  hallazgo, fecha, profesional_id, ahora=None) -> Hallazgo: ...
    def listar_por_paciente(self, *, tenant_id, paciente_id) -> list[Hallazgo]: ...
    def listar_por_pieza(self, *, tenant_id, paciente_id, pieza_fdi) -> list[Hallazgo]: ...
    def obtener(self, *, tenant_id, hallazgo_id) -> Hallazgo | None: ...
    def marcar_resuelto(self, *, tenant_id, hallazgo_id, ahora=None) -> Hallazgo: ...

class PresupuestoRepositorio(Protocol):
    def crear(self, *, tenant_id, paciente_id, vence_en=None, ahora=None) -> Presupuesto: ...
    def obtener(self, *, tenant_id, presupuesto_id) -> Presupuesto | None: ...
    def listar(self, *, tenant_id, paciente_id) -> list[Presupuesto]: ...
    def actualizar_estado(self, *, tenant_id, presupuesto_id, estado) -> Presupuesto: ...

class LineaRepositorio(Protocol):
    def agregar(self, *, tenant_id, presupuesto_id, prestacion_id, monto,
                cobertura_os, a_cargo_paciente, pieza_fdi=None,
                hallazgo_id=None, idempotency_key=None, ahora=None) -> Linea: ...
    def listar(self, *, tenant_id, presupuesto_id) -> list[Linea]: ...
    def por_idempotency_key(self, *, tenant_id: str,
                            idempotency_key: str) -> Linea | None: ...

class AceptacionRepositorio(Protocol):
    def registrar(self, *, tenant_id, linea_id, acepta, fecha, canal,
                  ahora=None) -> Aceptacion: ...
    def ultima_por_linea(self, *, tenant_id, linea_id) -> Aceptacion | None: ...

class UnidadDeTrabajo(Protocol):
    def __enter__(self) -> "UnidadDeTrabajo": ...
    def __exit__(self, *exc) -> None: ...   # commit en éxito, rollback en error
```

## Risks / Trade-offs

- [C-12 cablea coberturas y cambia el cálculo] → el contrato `CoberturaPort` y el
  invariante `cobertura_os + a_cargo_paciente = monto` quedan testeados; C-12 sólo
  implementa el adaptador.
- [C-10 cablea caja y espera otro payload] → `ImputacionPort` es el contrato; test de
  contrato por puerto (mismo criterio que C-06/C-07/C-08).
- [Redondeo de porcentajes genera diferencias de 1 centavo] → invariante en DB y resto
  al paciente; política exacta OQ C09-OQ-6.
- [Re-decisión de líneas rechazadas (recupero)] → v1 cierra la línea; reabrir es
  C09-OQ-4.
- [Vencimiento sin TTL] → `vence_en` explícito evita inventar plazos; si el dueño define
  un default, se agrega sin cambiar el contrato.
- [Doble clic en "derivar" duplica el ítem] → `Idempotency-Key` obligatorio + UNIQUE
  parcial por tenant (D3.1): el replay devuelve los mismos ids y la UI reutiliza la key
  mientras el primer request está en vuelo.
- [Cobertura configurada inválida desde C-12] → validación defensiva D6.1/D6.2: la
  configuración se descarta, cae a 100 % particular visible, se audita y nunca se
  persiste una línea inconsistente. C-12 sigue siendo el dueño de validar al cargar la
  tabla de coberturas.
- [PHI en el texto del hallazgo] → schemas allow-list, auditoría sin texto, logs sólo
  con ids (RN-CL-04).
- [Drift entre dominio en memoria y SQLAlchemy] → wiring real es follow-up declarado;
  tests de migración cubren los CHECKs y RLS que el dominio no puede probar.

## Migration Plan

1. **DDL (007)**: crear `odontograma_hallazgos`, `presupuestos`, `presupuesto_lineas`,
   `aceptaciones` con FKs, CHECKs de D8, índices y RLS forzada; grants/revoques de D2/D8.
   Reversible.
2. **Modelos SQLAlchemy** en `backend/app/models/odontograma.py` y
   `backend/app/models/presupuesto.py` (type hints, `Mapped[...]`).
3. **Dominio**: `backend/app/odontograma/` y `backend/app/presupuesto/` (entidades,
   puertos, adaptadores en memoria, servicios, unidad de trabajo).
4. **Borde**: `backend/app/routers/odontograma.py`, `backend/app/routers/presupuesto.py`,
   `backend/app/schemas/odontograma.py`, `backend/app/schemas/presupuesto.py`
   (`extra="forbid"`, centavos, `AwareDatetime`).
5. **Frontend**: página `/odontograma` (React + TS estricto, sin `any`) con la skill
   `visual-turnos`; consume los endpoints; muestra "configurada, no validada en vivo".
6. Sin env var nueva, sin secretos, sin tablas de C-10/C-12.
7. Rollback = `alembic downgrade 006_ficha_clinica`; la 007 sólo crea tablas nuevas.
8. Verificación: `py -m pytest tests/ -q`, `npm run lint`, `npm run typecheck`,
   `npm test`, `npm run build`, `openspec validate c-09-odontograma-presupuesto --strict`.

## Open Questions

| OQ | Pregunta | Por qué no se fija acá | Respaldo |
|---|---|---|---|
| C09-OQ-1 | ¿Se incorpora la dentición decidua (5x/6x/7x/8x), supernumerarios o superficies múltiples en una fase posterior? | La grilla permanente 11–48 ya se valida; la decidua no está en la KB y queda fuera de v1 | `05_reglas_de_negocio.md:32`; `04_modelo_de_datos.md:64` |
| C09-OQ-2 | ¿Enum de `superficie` (M/D/V/L/O u otro) y si admite múltiples superficies por hallazgo? | La KB dice `superficie?` sin catálogo | `04_modelo_de_datos.md:64` |
| C09-OQ-3 | ¿Qué estado toma un presupuesto con **todas** las líneas rechazadas (0 aceptadas), y uno con líneas aceptadas + rechazadas? | El enum no tiene `RECHAZADO` y la KB no define el cierre con rechazos | `04_modelo_de_datos.md:66` |
| C09-OQ-4 | ¿Una línea rechazada puede reabrirse/aceptarse después (recupero/recall)? | US-032 CA-2 nombra "recupero" sin definir el mecanismo | `06_funcionalidades.md:65` |
| C09-OQ-5 | ¿Enum de canales de aceptación (consultorio, link, WhatsApp) y quién puede usar cada uno? | La KB sólo dice "en consultorio o por link" | `07_flujos_principales.md:29`; `03_actores_y_roles.md:23` |
| C09-OQ-6 | ¿Política de redondeo de cobertura (truncar/redondear, a favor de quién)? | La KB fija porcentaje/monto pero no la aritmética de centavos | `04_modelo_de_datos.md:76`; `05_reglas_de_negocio.md:39` |
| C09-OQ-7 | ¿El odontólogo puede registrar la aceptación o sólo crear el presupuesto? | La matriz le da sólo "crear" y a recepción "registrar aceptación" | `03_actores_y_roles.md:23` |
| C09-OQ-8 | ¿Default de vigencia del presupuesto (días), si el vencimiento debe ser automático (job) y si `PARCIAL` también vence? | La KB declara `VENCIDO` sin plazo y no define el vencimiento de un presupuesto con líneas ya aceptadas | `04_modelo_de_datos.md:66` |
| C09-OQ-9 | ¿"Anular" presupuesto (matriz Admin) requiere estado `ANULADO` y endpoint propios? | El enum de la KB no lo contempla; agregarlo es cambio de modelo | `03_actores_y_roles.md:23`; `04_modelo_de_datos.md:66` |
| C09-OQ-10 | ¿La aceptación por link público requiere token propio (estilo C-06) o login del paciente? | DD-06 asume paciente sin login; C-09 v1 sólo registra el canal | `09_decisiones_y_supuestos.md` DD-06 |
| C09-OQ-11 | ¿Qué pasa con una línea aceptada si luego se cancela el turno asociado (reverso de imputación)? | Depende de C-10/C-11 y de la política de anulación de caja | `05_reglas_de_negocio.md:33`; `CHANGES.md:303-307` |
| C09-OQ-12 | ¿La creación de un presupuesto vacío o de una línea sin pieza (consulta administrativa) es un acto comercial fuera del gate clínico? | RN-AU-03 gatea "registrar clínica"; la línea con pieza/hallazgo ya se gatea, pero la frontera comercial/clínica no está definida | `05_reglas_de_negocio.md:53`; `07_flujos_principales.md:26` |

> **Cerradas el 2026-11-06**: la idempotencia de la derivación (antes C09-OQ-13) se
> resolvió en **D3.1** con `Idempotency-Key` + UNIQUE parcial por tenant; el saneamiento
> de cobertura inválida (antes C09-OQ-14) se resolvió en **D6.1/D6.2** con descarte,
> fallback 100 % particular y auditoría.

## Notas de implementación (no vinculantes)

- Actor por headers (`actor_desde_headers`) igual que C-05/C-07/C-08; el JWT real de
  C-03 reemplaza la dependencia sin cambiar el contrato.
- Errores: `Invalido` 422 para FDI/monto/estado inválido; `Prohibido` 403 para RBAC;
  `NoEncontrado` 404 para cross-tenant; `ConsentimientoRequerido` 409; `Conflicto`
  409 para aceptación sobre línea ya decidida, presupuesto vencido o edición fuera de
  `BORRADOR`; `ServicioNoDisponible(TurnoError)` con `codigo=503` cuando falla el
  puerto de imputación (la transacción no deja aceptación).
- La UI no calcula cobertura: sólo muestra lo que devuelve el servidor.
- Datos ficticios: "Paciente Demo", "Otro Paciente Demo", P1/P2, prestación "Conducto
  Demo"; ningún arancel real.
