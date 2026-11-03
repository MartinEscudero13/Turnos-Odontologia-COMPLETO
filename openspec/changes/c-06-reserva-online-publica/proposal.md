# Proposal — C-06 `reserva-online-publica`

## Why

El Discovery ubicó la coordinación manual por WhatsApp/teléfono como problema #1:
huecos que nadie ve, dobles reservas y sillón ocioso. C-05 ya garantiza en DB que
no exista solape ni doble asignación de sillón, pero ese motor sólo lo usa
recepción. Sin un link público el paciente sigue llamando y el consultorio pierde
la demanda fuera de horario (`knowledge-base/06_funcionalidades.md:24-27`, §US-010).
C-06 abre ese motor a un paciente sin login, con la misma integridad de C-05 y sin
convertir el link público en una puerta a datos de otros tenants ni de otros
pacientes.

## What Changes

- **Disponibilidad pública server-side**: `GET /api/disponibilidad?prestacion=&profesional=&desde=`
  calcula huecos reales (profesional × sillón × `duracion_min` − turnos activos −
  bloqueos), scoped por el tenant resuelto en la ruta. Nada de grilla armada por el
  cliente (RN-RE-01, `knowledge-base/05_reglas_de_negocio.md:16`).
- **Reserva pública**: `POST /api/reservas/publicas` crea un turno `PENDIENTE` con
  `origen=RESERVA_ONLINE` y `token_publico`, identificando al paciente sólo con
  nombre + teléfono E.164; teléfono existente vincula la ficha en vez de duplicarla
  (RN-RE-05, `:20`; DD-06, `knowledge-base/09_decisiones_y_supuestos.md:38-42`).
- **Gestión con token**: consultar, cancelar y reprogramar con `token_publico`,
  respetando la anticipación mínima configurable `CANCEL_ANTICIPACION_H`
  (default 24 h, RN-RE-03, `:18`); debajo del umbral la ruta pública rechaza sin
  mutar y deriva a recepción auditada.
- **Anti-spam**: rate-limit por IP + tenant y verificación liviana de un solo uso en
  cada acción pública (RN-RE-02, `:17`; `knowledge-base/03_actores_y_roles.md:35`).
- **Conflicto y concurrencia**: slot tomado entre pasos → `409` + 3 alternativas
  reusando `ConflictoSolape`/`buscar_alternativas` de C-05; dos reservas
  concurrentes del mismo hueco → exactamente una persiste (RN-GL-02, `:66`).
- **Aislamiento y privacidad**: tenant resuelto por la ruta, `404` uniforme para
  tokens ajenos/inexistentes, respuestas públicas con allow-list de campos y logs
  sin PHI (RN-AG-05 `:11`, RN-CL-04 `:35`).
- **Auditoría**: reserva/cancelación/reprogramación públicas dejan entrada
  append-only sin PHI (RN-AU-02, `:52`).

## Capabilities

### New Capabilities

- `reserva-publica`: disponibilidad pública server-side, reserva con token e
  identificación liviana, gestión (cancelar/reprogramar) con anticipación mínima,
  anti-spam, aislamiento multi-tenant y privacidad en las rutas públicas.

### Modified Capabilities

(none — C-05 `turnos-anti-solape` se consume tal cual; no cambia ningún
requirement existente de `openspec/specs/turnos-anti-solape/spec.md`.)

## Actores

| Actor | Interacción en C-06 |
|---|---|
| Paciente | Link público `/r/:tokenTenant`, sin login: ve huecos, reserva con nombre + teléfono, gestiona su turno con token |
| Recepción / Admin | No cambia su flujo (C-05); recibe las derivaciones por debajo del umbral de anticipación |
| Sistema | Calcula disponibilidad, aplica rate-limit/verificación, audita, libera huecos y emite evento de notificación |

## US cubiertas

| US | Criterios cubiertos acá | Criterios diferidos |
|---|---|---|
| US-010 — Reserva por link sin llamar (`06_funcionalidades.md:24-27`) | CA-1 slots servidor-side; CA-2 nombre + teléfono con vinculación por teléfono | CA-3 confirmación por WA/email → C-13 (se emite evento, no se envía) |
| US-011 — Cancelar / reprogramar con anticipación (`:29-32`) | CA-1 anticipación configurable (default 24 h); CA-2 derivación a recepción auditada | — |
| US-012 — Lista de espera (`:34-37`) | Sólo el hook: el hueco liberado queda libre (RN-RE-04) | Toda la auto-oferta → C-07 |

## Dependencia explícita con C-05

C-06 **no reimplementa** anti-solape, cálculo de `fin`, estados ni alternativas:
consume `backend/app/turnos/` (`ServicioTurnos.crear|cancelar|reprogramar`,
`ConflictoSolape`, `buscar_alternativas`, `calcular_fin`, `intervalos_solapan`) y
el contrato archivado `openspec/changes/archive/2026-10-01-c-05-turnos-anti-solape/`
(6 requisitos, 12 escenarios, suite 104 en verde). Si C-06 necesitara cambiar el
comportamiento de C-05, sería otro change: acá el spec de C-05 queda intacto.

## Deuda declarada (explícita, no oculta)

| # | Deuda | Estado real en el repo | Mitigación en C-06 |
|---|---|---|---|
| D-A | **C-03 auth no existe** | Las rutas internas toman el actor de headers (`backend/app/routers/turnos.py:37-49`), sin JWT | Las rutas públicas **no** leen headers de actor: derivan tenant de la ruta y paciente del teléfono/token. JWT real reemplaza la dependencia sin cambiar el contrato |
| D-B | **C-04 catálogos/pacientes no existe** | Sólo hay tabla `turnos` (`backend/alembic/versions/003_turnos_anti_solape.py`); `CHANGES.md:171-180` sigue `[ ]` | C-06 programa contra puertos (`CatalogoPort`, `PacientePort`) con adaptadores en memoria para tests; el wiring SQLAlchemy queda como tarea bloqueada por C-04 |
| D-C | **C-13 WhatsApp no existe** | No hay envío de mensajes | Se emite evento vía `NotificadorPort` (no-op en tests); confirmación inmediata sólo en pantalla/respuesta HTTP |
| D-D | **C-11 señas no existe** | Sin preferencia MP ni expiración por pago | La reserva queda `PENDIENTE`; `RESERVA_TTL_H` se declara como config (valor en OQ-1), la liberación por falta de seña es C-11 |
| D-E | **C-07 lista de espera no existe** | Sin auto-oferta | La cancelación sólo libera el hueco (estado `CANCELADO`); el worker de oferta es C-07 |
| D-F | **UI `/r/:tokenTenant` no existe** | No hay `frontend/` en el árbol (C-01 pendiente) | C-06 congela el contrato API y deja la landing mobile-first como follow-up, igual que C-05 hizo con la UI de agenda |
| D-G | **Revisión de escenarios** | Pendiente | Antes de `/opsx:apply`, correr `revisor-escenarios-turnos` (exigido por `AGENTS.md`) |

## Criterios de aceptación globales

- [ ] CA-G1 La disponibilidad pública coincide con el motor de C-05 (test de paridad: mismo predicado de solape/bloqueo, mismo cálculo de `fin`).
- [ ] CA-G2 `POST /api/reservas/publicas` responde `201` con turno `PENDIENTE`, `origen=RESERVA_ONLINE`, `fin` calculado y `token_publico` no vacío.
- [ ] CA-G3 Slot tomado entre pasos y reservas concurrentes devuelven `409` con exactamente 3 alternativas reales, sin turno duplicado.
- [ ] CA-G4 Anticipación: exactamente `CANCEL_ANTICIPACION_H` acepta; un minuto menos rechaza sin mutar estado y deriva a recepción.
- [ ] CA-G5 Cross-tenant: token/pedido de otro tenant responde `404` uniforme y no lee ni escribe filas ajenas.
- [ ] CA-G6 Sin PHI: respuestas públicas y logs sólo con IDs, estados y horarios; nunca nombre/teléfono ajenos ni dato clínico.
- [ ] CA-G7 Regresión: `py -m pytest tests/ -q` sigue en 104 passed + los tests nuevos en verde.
- [ ] CA-G8 `openspec validate c-06-reserva-online-publica --strict` sin errores ni warnings.
