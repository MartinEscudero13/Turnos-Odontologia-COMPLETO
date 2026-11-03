# Revisión crítica — C-06 `reserva-online-publica` con `revisor-escenarios-turnos`

> Fecha: 2026-11-03 · Herramienta: la skill propia del repo (`.opencode/skills/revisor-escenarios-turnos/`)
> ejecutada en un contexto nuevo, sin indicársele cuál usar. Ver `docs/skills-mcp/evidencias/04-revision-critica.md`.
> Implementación: **no iniciada**. Este change sigue `[ ]` en `CHANGES.md`.

## 1. Salida de la skill (antes de corregir)

**Veredicto de la skill:** la spec **no era verificable tal como estaba**. `openspec validate --strict` pasaba,
pero había **4 bloqueantes**: datos de tenant ausentes en las rutas de la API, ningún contrato para emitir la
verificación liviana, escenarios de anticipación caducos contra el reloj real y el "queda auditado" de RN-RE-03
sin escenario ni tarea.

### Tabla de cobertura (salida de la skill, antes)

| RN | Requirement | Feliz | Error de negocio | Borde | Concurrencia/idempotencia |
|---|---|---|---|---|---|
| RN-RE-01 | Disponibilidad calculada en el servidor | vacuo (`:20`) | **HUECO** (`:17-18`) | `:31`, `:38`, `:45` | N/A |
| RN-RE-05 | Identificación liviana por teléfono | dos escenarios | uno | **HUECO** (formato/otro tenant) | **HUECO** (dos reservas concurrentes mismo teléfono) |
| RN-RE-02 | Reserva con token (fin no lo fija el cliente) | `:86` | `:101` incompleto | débil | **HUECO** |
| RN-RE-02 | Verificación liviana y rate-limit | sólo reservar | sólo reservar | `:122` | **HUECO** (reuso concurrente, TTL vencida) |
| RN-RE-03 | Cancelar y reprogramar | `:148` | `:155` sólo cancelar | **HUECO** reprogramar bajo umbral | **HUECO** |
| RN-GL-02 | Hueco tomado / concurrencia / sobreturno | `:196` | `:188`, `:204`, `:211` | parcial | `:196` |
| RN-AG-05 | Aislamiento multi-tenant | dos escenarios | uno | **HUECO** tenant inactivo | N/A |
| RN-CL-04 | Privacidad | `:259` | `:273` | **HUECO** un paciente propio | N/A |
| RN-AU-02 | Trazabilidad | dos escenarios | **HUECO** (rechazo sin auditar) | **HUECO** | N/A |

### Hallazgos (severidad | hallazgo | cita | RN)

**BLOQUEANTE**
- **B1 — El tenant de las rutas API no está definido**: el requirement exige resolverlo desde `/r/:tokenTenant`
  pero los endpoints eran `GET /api/disponibilidad` y `POST /api/reservas/publicas` sin ese segmento ⇒ los
  escenarios de aislamiento no se podían escribir. (`spec.md:14`, `spec.md:221-223`, `design.md:47-54`,
  `tasks.md:127-131` · RN-RE-01, RN-AG-05)
- **B2 — No hay contrato para obtener la verificación liviana**: la acción la exige en cada ruta pública pero
  ningún endpoint la emitía ⇒ el `201` del camino feliz sólo era ejercitable inyectando un mock.
  (`spec.md:110-113`, `spec.md:135-139`, `03_actores_y_roles.md:35` · RN-RE-02)
- **B3 — Los escenarios de anticipación caducan**: con `CANCEL_ANTICIPACION_H = 24` y un inicio fijo
  `2026-10-10`, evaluados contra el reloj real (2026-11-03) el delta es negativo ⇒ `403` cuando el escenario
  esperaba `200`. Los tests de C-05 siempre pasan `ahora=`; `tasks.md` no lo exigía.
  (`spec.md:148-162`, `tasks.md:87-93`, `backend/app/turnos/servicio.py:364-372` · RN-RE-03)
- **B4 — RN-RE-03 "queda auditado" sin escenario ni tarea**: el rechazo bajo umbral no dejaba auditoría
  verificable. (`knowledge-base/05_reglas_de_negocio.md:18`, `spec.md:288-291`, `tasks.md:170-179`
  · RN-RE-03, RN-AU-02)

**MAYOR**
- **M1** Escenarios de disponibilidad con `desde` en el pasado, sin reloj congelado ⇒ pasan vacíos (R5). (`spec.md:20-36`)
- **M2** "El fin nunca lo fija el cliente" sin decir el `inicio` ni la prestación ⇒ el `422` no era derivable. (`spec.md:101-107`)
- **M3** Faltaba el escenario feliz de **reprogramación exitosa** (implementada en tasks). (`spec.md:141-178`, `tasks.md:100-102`)
- **M4** Faltaba el borde **reprogramar bajo umbral** (sólo se probaba cancelación). (`spec.md:143-161`)
- **M5** Faltaba verificación **vencida (TTL)** y **reuso concurrente**; las tasks pedían un test que la spec no declaraba. (`spec.md:122-126`, `tasks.md:74-77`)
- **M6** Rate-limit exigido **por IP y por tenant**, pero el escenario probaba sólo "un mismo origen". (`spec.md:110-113`, `spec.md:128-133`)
- **M7** Ningún escenario de verificación en **cancelar/reprogramar**, pese a que el requirement dice "en cada acción pública". (`spec.md:110-113`, `05_reglas_de_negocio.md:17`)
- **M8** Deduplicación de paciente por teléfono sin borde ni concurrencia; la unicidad queda sólo en aplicación. (`spec.md:51-55`, `04_modelo_de_datos.md:53`, `tasks.md:33-46`)
- **M9** Fixture `0000-0000 ⇒ +540000000000` no es E.164 y la KB no define un prefijo/área por defecto: **valor inventado** en las tasks. (`tasks.md:37`, `08_arquitectura_propuesta.md:42`)
- **M10** "Exactamente 3 alternativas" es insostenible con menos de 3 huecos reales; la KB pide "oferta alternativa inmediata". (`spec.md:188-202`, `05_reglas_de_negocio.md:66`)
- **M11** `GET /api/reservas/publicas/{token}` no existía en ningún requirement (decisión tomada sólo en tasks). (`tasks.md:132-135`, `03_actores_y_roles.md:35`)
- **M12** Payload de la reserva sin especificar (campos, quién elige el sillón). (`spec.md:86-93`, `spec.md:211-217`)
- **M13** R1 exigía "nada fuera del cálculo SHALL aceptarse", sin escenario (`inicio` fuera de grilla). (`spec.md:17-18`)

**MENOR** — token no "no secuencial" como resultado observable (`spec.md:95-99`) · escenario vacuo de privacidad con un solo paciente (`spec.md:266-271`) · semántica de `desde` (día vs rango) sin fijar (`spec.md:14`, `design.md:176`) · `tenants.activo` ⇒ `404` sólo en el design, sin escenario (`design.md:156-163`) · vinculación por teléfono resuelve `OQ-8` por omisión · reservar el mismo día resuelve `OQ-6` por omisión (`spec.md:20-29`).

### Preguntas abiertas detectadas

`OQ-4` (`:tokenTenant`: slug público vs token aleatorio) fue **esquivada** por la spec inicial; `OQ-6` (lead time de reserva) y `OQ-8` (nombre al vincular) quedaron **resueltos por omisión**; `PO-01` (anticipación exacta) sobrevive — la spec la fija como default 24 h (respaldada por RN-RE-03 y `08_arquitectura_propuesta.md:57`) pero el override por tenant sigue sin dueño/contraparte; `OQ-1/2/3/5` y `PO-06` quedaron correctamente diferidas a config o sin valor.

## 2. Correcciones aplicadas

| Hallazgo | Fix | Archivo |
|---|---|---|
| B1 | Superficie pública coherente `/api/publico/{tokenTenant}/...` (mapea 1:1 con `/r/:tokenTenant`); tenant resuelto una vez por request; `/reservas`, `/verificacion`, `/reservas/{token}` la heredan. | `spec.md` (todos los requirements), `design.md` D2/D11 |
| B2 | Contrato del emisor `POST /api/publico/{tokenTenant}/verificacion` (`verificacion_id`, `expira_at`, `canal`), `201`, más escenarios de vencida / un solo uso / reuso concurrente. | `spec.md` req. "Verificación liviana de un solo uso", `tasks.md` 4.3a, 4.3b |
| B3 | Reformulación de TODOS los escenarios de tiempo relativos a un reloj congelado explícito; `tasks.md` (cabecera y §5) exige `ahora=` en cada test. | `spec.md`, `tasks.md`, `design.md` D6 |
| B4 | Escenario + tarea para la entrada append-only `CANCELACION_RECHAZADA` / `REPROGRAMACION_RECHAZADA` (`BAJO_ANTICIPACION`, `antes == despues`, sin PHI). | `spec.md` req. "Trazabilidad", `tasks.md` 9.3a |
| M1 | `desde` con reloj congelado en los 4 escenarios de disponibilidad; `desde ≥ ahora` (rango explicado en D11/OQ-5) + controles vacíos vs vacuos. | `spec.md` req. "Disponibilidad" |
| M2 | Payload declarado por completo (`prestacion`, `profesional`, `inicio`, `nombre`, `telefono`, `verificacion_id`; `fin` prohibido ⇒ `422`). | `spec.md` req. "Reserva pública" |
| M3 | Escenario feliz de reprogramación exitosa (original `REPROGRAMADO`, nuevo `PENDIENTE`, token transferido). | `spec.md` req. "Cancelar y reprogramar" |
| M4 | Borde de **reprogramar** bajo umbral con rechazo y auditoría. | `spec.md` ídem |
| M5 | Escenarios de verificación vencida y reuso concurrente (una 201, otra 403). | `spec.md` req. "Verificación" |
| M6 | Escenario de rate-limit por `(tenant, acción)`: IP nueva frenada tras el tope tenant-wide. | `spec.md` req. "Rate-limit" |
| M7 | Verificación exigida explícitamente en cancelar y reprogramar (dos escenarios de "sin verificación no muta"). | `spec.md` req. "Cancelar y reprogramar" |
| M8 | Escenario de dos reservas concurrentes con el mismo teléfono nuevo ⇒ un único paciente (garantía en aplicación + `PacientePort.buscar_o_crear_por_telefono` documentando que la unicidad real queda para `C-04`/migración). | `spec.md` req. "Identificación", `design.md` D4 |
| M9 | Fixture reemplazado por `+5491130551234` (formalmente válido, ficticio). | `tasks.md` (cabecera, §2) |
| M10 | Invariante corregido a "hasta 3 alternativas (las que existan)"; spec y tasks alineadas. | `spec.md` req. "Hueco tomado", `tasks.md` 5.4/6.1/6.4 |
| M11 | `GET /api/publico/{tokenTenant}/reservas/{token}` declarada como requirement con allow-list de claves. | `spec.md` req. "Reserva pública", `tasks.md` 7.3 |
| M12 | Payload de reserva especificado por completo (campos permitidos, elección de sillón por el servidor). | `spec.md` req. "Reserva pública", `design.md` D1 |
| M13 | Escenario `inicio` fuera de horario/grilla y dentro de bloqueo ⇒ `409` (sin mutación). | `spec.md` req. "Disponibilidad" |
| MENORES | resultado observable no secuencial removido; privacidad no vacuo; `desde` = día de apertura con `PUBLIC_DISPONIBILIDAD_HORIZONTE_D`; `tenants.activo` ⇒ `404` ahora exigido por un requisito de aislamiento; vinculación por teléfono sin tratar nombre (OQ-8 declarada); mismo día reservable sin lead time (OQ-6 declarada). | `spec.md` |

Conteos tras la corrección: **10 requirements · 48 escenarios · 50 tareas** (`openspec validate --strict`
⇒ `Change 'c-06-reserva-online-publica' is valid`, sin warnings). La suite de C-05 sigue intacta:
**104 passed**.

## 3. Hallazgos no aplicados / diferidos

- **RN-RE-04** (auto-oferta a lista de espera), **RN-SE-01..05** (seña/MP), **RN-AU-01** (RBAC interno) y
  **RN-AU-03** (consentimiento): están **fuera del alcance** de C-06 por dependencia (`C-07`, `C-11`, `C-03`,
  `C-08`). No se "resolvieron por omisión": quedaron declarados como deuda o como hook.
- **Unicidad real de paciente por teléfono**: la garantía hoy vive en la aplicación (falta la migración y la
  constraint única que atierra en `C-04`/`C-02`). Documentado, no fingido.
- **Contadores y desafíos** (rate-limit, verificación single-use): van a **Redis** (D10); no duplican DDL.
- `OQ-1/OQ-2/OQ-3/OQ-4/OQ-5/OQ-6/OQ-7/OQ-8/OQ-9` siguen **abiertas**; la spec usa nombres de config, nunca números.

## 4. Verificación

```
> openspec validate c-06-reserva-online-publica --strict
Change 'c-06-reserva-online-publica' is valid      (exit 0, sin warnings)
> py -m pytest tests/ -q
104 passed
> py docs\skills-mcp\vendor\skill-creator\scripts\quick_validate.py .opencode\skills\revisor-escenarios-turnos
Skill is valid!
```

La corrección fue aplicada por la misma skill (contexto limpio, sin indicársele cuál usar) y completada tras
corregir el bloqueante de cuota de ejecución; el delta respecto de la spec entregada está en
`docs/skills-mcp/evidencias/c-06-spec-antes-de-revision.md` vs
`specs/reserva-publica/spec.md` (306 → 524 líneas, 48 escenarios).
