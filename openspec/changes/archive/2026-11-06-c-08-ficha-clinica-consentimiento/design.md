# Design — C-08 `ficha-clinica-consentimiento`

> Estado: **preparado, no implementado**. Este documento decide el HOW; el QUÉ está
> en `specs/ficha-clinica/spec.md` y el porqué en `proposal.md`.

## UI Mockups

- Decision: no (no UI) — C-08 es backend-only; la ficha/evoluciones/adjuntos no
  tienen superficie visual propia en v1 (una futura pantalla `/ficha` es follow-up
  de frontend fuera de este scope, igual que C-07).
- Fecha: 2026-11-05

## Context

Stack real: Python + FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL 15 multi-tenant
con RLS. Ya implementados y archivados: C-04 catálogos/pacientes
(`backend/app/models/catalogos.py`: `Paciente`, `Profesional`; el paciente ya tiene
`consentimiento_ok BOOLEAN DEFAULT false` desde la 002), C-03 auth/auditoría
(`backend/app/core/audit`, matriz `03_actores_y_roles.md`), C-05 turnos
(`backend/app/turnos/servicio.py`: `Actor`, `TurnoError`, `NoEncontrado`, `Invalido`,
`Prohibido`; `turnos.profesional_id`), C-07 (`backend/app/lista_espera/` como patrón
de dominio puro + puertos + adaptadores en memoria + `crear_router(svc)`).

Reglas duras aplicables (`AGENTS.md`): toda tabla filtra por `tenant_id` + RLS; acceso
a datos sólo vía SQLAlchemy (SQL crudo sólo en Alembic); type hints; datos ficticios;
sin secretos/PHI en logs ni mensajes; evoluciones append-only (RN-CL-03); sin
consentimiento firmado → clínica bloqueada, agenda permitida (RN-AU-03).

## Goals / Non-Goals

**Goals:** ficha 1—1 con paciente; evoluciones fechadas/firmadas append-only con
corrección = nueva evolución; adjuntos Rx/foto scoped por tenant con referencia
opaca; consentimiento informado con timestamp + canal como gate previo; gate que
bloquea clínica sin tocar agenda; RBAC clínico; aislamiento multi-tenant y auditoría
append-only sin PHI.

**Non-Goals:** odontograma FDI y presupuesto (C-09); UI de ficha; captura self-service
de firma móvil por link tokenizado (OQ); campos estructurados de antecedentes/alergias
en la ficha (v1 = evolución inicial); validación criptográfica de `firma_hash` (OQ);
eliminación física de adjuntos (OQ).

## Decisions

- **D1 — Migración 006 (no 005).** La 005 ya la consumió C-07
  (`005_lista_espera.py`, `down_revision="004_auth_rbac"`). La migración real de C-08
  es `006_ficha_clinica` con `down_revision="005_lista_espera"`. Se corrige el
  `CHANGES.md:265` (mismo Hallazgo que C-07 documentó para la suya).

- **D2 — Ficha = ancla 1—1 mínima, sin campos clínicos estructurados en v1.**
  `Ficha(id, tenant_id, paciente_id UNIQUE, creado_en)` con `UNIQUE(tenant_id,
  paciente_id)` (1—1). US-030 nombra "antecedentes/alergias" en el *Quiero* pero NO
  en los criterios de aceptación (CA-1 consentimiento, CA-2 evoluciones); capturarlos
  como campos estructurados sería inventar schema sin respaldo en la KB. En v1 los
  antecedentes/alergias se registran como la **evolución inicial** (texto libre,
  append-only). Alternativas descartadas: (a) columnas `antecedentes`/`alergias`
  TEXT → agrega superficie editable fuera del append-only y sin respaldo en CA; (b)
  no crear `fichas` y colgar todo del paciente → pierde el ancla 1—1 que referencia
  adjuntos y C-09.

- **D3 — Evoluciones append-only a nivel DB (garantía dura).** `evoluciones` nace con
  `GRANT SELECT, INSERT` + `REVOKE UPDATE, DELETE` al rol `turnos_app` (mismo patrón
  que `auditoria` en la 001) y **sin endpoints** de update/delete. La corrección es
  una nueva evolución (`RN-CL-03`). El vínculo explícito "esta corrige aquella" es
  OQ (C08-OQ-8); en v1 la corrección se distingue por `fecha`/orden y por el texto.
  Alternativas: (a) sólo rechazar en el servicio (sin revoke DB) → no sobrevive a
  acceso directo; (b) trigger que reescribe → innecesario con revoke + no-endpoints.

- **D4 — El gate consulta `consentimientos`, no `pacientes.consentimiento_ok`.**
  RN-AU-03 exige "firmado con timestamp": la autoridad es una fila de `consentimientos`
  con `timestamp NOT NULL` válido para `(tenant_id, paciente_id)` — no la mera existencia
  de fila. El boolean `pacientes.consentimiento_ok` (C-04) se mantiene como **espejo
  desnormalizado** (se pone `true` al registrar el consentimiento) pero NO es la fuente
  del gate. Alternativas: (a) gate por el boolean → no prueba timestamp ni canal (viola
  RN-AU-03); (b) eliminar el boolean → migración invasiva sobre C-04 fuera de scope.
  La sincronización boolean↔tabla es C08-OQ-4.

- **D5 — Consentimientos append-only.** El consentimiento es un acto legal con
  timestamp (Ley 26.529); editar/borrar un consentimiento firmado es un riesgo legal.
  `consentimientos` nace con `GRANT SELECT, INSERT` + `REVOKE UPDATE, DELETE`. Re-firma
  = nueva fila. Alternativas: permitir update → rompe trazabilidad del acto firmado.

- **D6 — RBAC clínico según matriz.** Escrituras de evolución/adjunto: `ADMIN` y
  `ODONTOLOGO`; el odontólogo acotado a "pacientes que atiende" = pacientes con al
  menos un turno cuyo `turno.profesional_id == actor.profesional_id` (lectura literal
  de `03_actores_y_roles.md:22`). `RECEPCION`: crear ficha base + registrar
  consentimiento (NO evoluciones). `PACIENTE`: lectura de su propia ficha. Un rol sin
  permiso → `403`. Alternativas: (a) odontólogo sobre todo el tenant → relaja PHI
  (matriz dice "que atiende"); (b) recepción crea evoluciones → contradice la matriz.

- **D7 — Adjuntos: referencia opaca + tipo enum {RX, FOTO}.** `Adjunto(ficha_id,
  tipo, storage_ref, creado_en)`. `tipo` es CHECK `IN ('RX','FOTO')` (valores directos
  del scope "Rx/foto"). `storage_ref` es una referencia opaca (texto) a un objeto de
  almacenamiento; los bytes NUNCA viven en DB y la ref no porta PHI (RN-CL-04). El
  backend de almacenamiento real (S3/local/otro) y el formato de `storage_ref` son OQ
  (C08-OQ-2). Alternativas: (a) guardar bytes en DB → anti-patrón + PHI en DB grande;
  (b) `tipo` libre → pierde la validación de dominio.

- **D8 — Canal móvil: v1 registra el único canal documentado.** La KB sólo nombra
  "móvil" (`03_actores_y_roles.md:7`, `05_reglas:53`). `Consentimiento(paciente_id,
  timestamp NOT NULL, canal)` con `canal TEXT NOT NULL CHECK (canal <> '')`; en v1 el
  valor es "móvil". `timestamp NOT NULL` es la fuente del gate (D4): una fila sin
  `timestamp` válido no desbloquea clínica. El enum completo de canales
  (¿presencial/web/WA?) es OQ (C08-OQ-3). Alternativas: inventar canales extra → sin
  respaldo.

- **D9 — Gate = `409 CONSENTIMIENTO_REQUERIDO` (precondición de estado, no 403).**
  "Sin consentimiento → bloquea clínica" es una precondición de estado de negocio,
  no un problema de permisos/autenticación; se usa `409` con detalle
  `CONSENTIMIENTO_REQUERIDO` (análogo a `ConflictoSolape`). Se agrega
  `ConsentimientoRequerido(TurnoError)` con `codigo=409` reutilizando la jerarquía de
  C-05 (`Invalido`/`Prohibido`/`NoEncontrado`). Alternativas: (a) `403` → confunde con
  RBAC y no expresa "falta un paso previo"; (b) `422` → es estado, no payload inválido.

- **D10 — Puertos + adaptadores en memoria (mismo patrón que C-06/C-07).**
  Dominio puro + Protocol + adaptadores en memoria; `crear_router(svc)` inyectable;
  actor por headers (`actor_desde_headers`) igual que C-05/C-07. El wiring real a
  SQLAlchemy es follow-up explícito. El dominio queda testeable sin DB.

- **D11 — `adjuntos`: tabla nueva, ausente del ERD de la KB (decisión explícita).**
  RN-CL-04 exige "Adjuntos (Rx/fotos) pertenecen a la ficha del paciente del tenant",
  pero `adjuntos` NO figura en el ERD de `04_modelo_de_datos.md:21` (que lista bajo
  `fichas 1──N` a `evoluciones, odontograma_hallazgos, presupuestos, consentimientos`
  — sin `adjuntos`) ni tiene entrada de entidad propia en la KB. C-08 la introduce
  como **tabla nueva** en la migración 006 (no modificación de una existente). Se deja
  una nota para reconciliar el modelo con Martin antes de cerrar C-08. `storage_ref`
  se mantiene opaco (sin PHI) y el backend/formato de `storage_ref` sigue siendo
  C08-OQ-2.

## Seams

Interfaces que C-08 consume (C-04, C-05, C-03) y define. Firmas con type hints.

```python
# --- C-05 real (se reutiliza; no se modifica) ---
# Actor, TurnoError, Invalido, Prohibido, NoEncontrado (app.turnos.servicio)
# turnos.profesional_id -> "pacientes que atiende" del odontólogo (D6)

# --- C-08 define ---
class FichaRepositorio(Protocol):
    def crear(self, *, tenant_id, paciente_id, ahora=None) -> Ficha: ...
    def por_paciente(self, *, tenant_id, paciente_id) -> Ficha | None: ...

class EvolucionRepositorio(Protocol):
    def registrar(self, *, tenant_id, paciente_id, profesional_id,
                  fecha, texto, firma_hash=None, ahora=None) -> Evolucion: ...
    def listar(self, *, tenant_id, paciente_id) -> list[Evolucion]: ...

class AdjuntoRepositorio(Protocol):
    def registrar(self, *, tenant_id, ficha_id, tipo, storage_ref,
                  ahora=None) -> Adjunto: ...
    def listar(self, *, tenant_id, ficha_id) -> list[Adjunto]: ...

class ConsentimientoRepositorio(Protocol):
    def registrar(self, *, tenant_id, paciente_id, timestamp, canal,
                  ahora=None) -> Consentimiento: ...
    def firmado(self, *, tenant_id, paciente_id) -> bool: ...

class AuditoriaPort(Protocol):          # reutiliza el concepto de C-03/C-07 (RN-AU-02)
    def registrar(self, *, tenant_id, accion, actor,
                  entidad, entidad_id, antes=None, despues=None, ...) -> None: ...
```

## Risks / Trade-offs

- [Gate desalineado si `consentimiento_ok` se desincroniza de `consentimientos`] →
  el gate SIEMPRE lee `consentimientos` (D4); el boolean es sólo espejo. C08-OQ-4.
- [Carrera: registrar evolución mientras se registra el consentimiento] → el gate se
  evalúa en la transacción del caso de uso (reloj inyectado); sin consentimiento
  previo a la mutación → `409`.
- [Odontólogo sin turno previo no puede abrir ficha de un paciente nuevo] → borde
  documentado (D6); recepción crea la ficha base. C08-OQ-6.
- [PHI en logs por error no controlado] → logger estructurado sin PHI (C-01) + schemas
  allow-list; ningún texto de evolución viaja en mensajes de error (spec R9).
- [`firma_hash` sin esquema criptográfico definido] → nullable en v1; no se valida su
  contenido (sólo se almacena). C08-OQ-1 / PO-10.
- [Drift al cablear puertos a SQLAlchemy] → test de contrato por puerto + wiring
  explícito (mismo criterio que C-06/C-07).
- [Zona horaria] → `timestamptz` siempre; escenarios en `-03:00` con reloj inyectado.

## Migration Plan

1. **DDL (006)**: `fichas`, `evoluciones`, `adjuntos`, `consentimientos` con
   `tenant_id NOT NULL`, FK, índices `(tenant_id, paciente_id)` y `(tenant_id, ficha_id)`,
   RLS forzada (fail-closed), `UNIQUE(tenant_id, paciente_id)` en `fichas`, y
   `GRANT SELECT, INSERT` + `REVOKE UPDATE, DELETE` sobre `evoluciones` y
   `consentimientos`. Reversible. No toca turnos ni catálogos.
2. Módulos nuevos: `backend/app/ficha_clinica/` (dominio, puertos, adaptadores) +
   `backend/app/routers/ficha_clinica.py` + `backend/app/schemas/ficha_clinica.py`.
3. Sin env var nueva (D7/D8; `firma_hash` y storage = OQ).
4. Rollback = `alembic downgrade 005_lista_espera`; la 006 no borra datos preexistentes
   (tablas nuevas).
5. Verificación: `py -m pytest tests/ -q` (suite C-05/C-06/C-07 + nuevos) y
   `openspec validate c-08-ficha-clinica-consentimiento --strict`.

## Open Questions

| OQ | Pregunta | Por qué no se fija acá | Respaldo |
|---|---|---|---|
| C08-OQ-1 | ¿Esquema criptográfico de `firma_hash` (algoritmo, qué se firma)? | Sólo se almacena como texto opaco; la KB no define el esquema | `04_modelo_de_datos.md:65`; `05_reglas:34`; PO-10 |
| C08-OQ-2 | ¿Backend y formato de `storage_ref` para adjuntos (S3/local/URI)? | RN-CL-04 sólo exige "nada de PHI en logs"; el storage es infraestructura | `05_reglas:35` |
| C08-OQ-3 | ¿Enum completo de `canal` (hoy sólo "móvil")? | La KB sólo nombra "móvil"; ampliarlo es inventar | `03_actores_y_roles.md:7`; `05_reglas:53` |
| C08-OQ-4 | ¿`pacientes.consentimiento_ok` se mantiene como espejo o se depreca a favor de `consentimientos`? | El boolean viene de C-04; deprecarlo es una migración fuera de scope | `04_modelo_de_datos.md:52`; `002_catalogos_pacientes.py` |
| C08-OQ-5 | ¿Campos estructurados de antecedentes/alergias en la ficha (v1 = evolución inicial)? | US-030 los nombra en el *Quiero*, no en los CA | `06_funcionalidades.md:53-56` |
| C08-OQ-6 | Alcance exacto de "pacientes que atiende" del odontólogo (¿turno previo, o todo el tenant en práctica unipersonal)? | La matriz dice "que atiende" sin definir el predicado | `03_actores_y_roles.md:22`; PO-05 |
| C08-OQ-7 | ¿Firma móvil self-service por link tokenizado (paciente sin login, DD-06) o captura presencial por recepción? | Afecta el borde del endpoint `/api/consentimientos`; v1 = captura por rol clínico | `03_actores_y_roles.md:7`; PO-06 |
| C08-OQ-8 | ¿Vínculo explícito "esta evolución corrige aquella" (FK `corrige_evolucion_id`) o sólo orden por fecha? | RN-CL-03 exige trazabilidad pero no define el campo de corrección | `05_reglas:34` |

## Notas de implementación (no vinculantes)

- El actor clínico se resuelve por headers (`actor_desde_headers`), igual que C-05/C-07;
  el JWT real de C-03 reemplaza la dependencia sin cambiar el contrato.
- `ConsentimientoRequerido` hereda de `TurnoError` con `codigo=409` (D9); el router
  mapea `TurnoError` a `{detalle, ...}` sin trazas.
- La auditoría registra acciones `FICHA_CREADA`, `EVOLUCION_REGISTRADA`,
  `ADJUNTO_REGISTRADO`, `CONSENTIMIENTO_REGISTRADO` como append-only sin PHI
  (`tenant_id`, actor, acción, `antes`/`después` jsonb, ids y estados; nunca el
  `texto` de la evolución ni nombre/teléfono del paciente).
- Datos ficticios en tests: "Paciente Demo"/"Otro Paciente Demo", profesional P1/P2.
