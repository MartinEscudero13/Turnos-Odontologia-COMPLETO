# Proposal — C-08 `ficha-clinica-consentimiento`

## Why

C-04 ya persiste el paciente base, pero hoy no existe forma de registrar clínica:
no hay ficha, ni evoluciones, ni adjuntos, ni consentimiento informado. RN-AU-03
exige **consentimiento informado firmado (móvil, con timestamp) antes de registrar
clínica** (`knowledge-base/05_reglas_de_negocio.md:53`, Ley 26.529) y RN-CL-03 exige
**evoluciones fechadas, firmadas e inmutables** (`:34`, Ley 27.706). C-08 cierra ese
hueco con la ficha clínica mínima de US-030 (`knowledge-base/06_funcionalidades.md:53`),
sin tocar agenda: la regla "sin consentimiento → bloquea clínica, permite solo
agenda" (`knowledge-base/07_flujos_principales.md:35`) delimita el alcance.

## What Changes

- **Ficha clínica mínima 1—1 con paciente**: `Ficha(paciente 1—1)` como ancla del
  expediente clínico del paciente del tenant. En v1 sin campos clínicos estructurados:
  antecedentes/alergias de US-030 se capturan como la evolución inicial (append-only).
- **Evoluciones inmutables**: `Evolucion(tenant, paciente, profesional, fecha, texto,
  firma_hash?)` append-only — corrección = nueva evolución, NUNCA update/delete.
- **Adjuntos**: `Adjunto(ficha, tipo Rx/foto, storage ref)` con referencia opaca de
  almacenamiento, sin PHI en refs/logs (RN-CL-04).
- **Consentimiento**: `Consentimiento(paciente, timestamp, canal móvil)` como
  requisito previo registrable; re-firma = nuevo registro.
- **Endpoints**: `/api/pacientes/{id}/ficha`, `/api/evoluciones`, `/api/adjuntos`,
  `/api/consentimientos` (firma en móvil).
- **Gate de consentimiento**: sin consentimiento firmado → `409 CONSENTIMIENTO_REQUERIDO`
  sobre clínica, agenda (turnos) intacta.
- **Migración 006** (ver Hallazgo abajo): `fichas`, `evoluciones`, `adjuntos`,
  `consentimientos` + RLS; evoluciones/consentimientos append-only a nivel DB.

## Capabilities

### New Capabilities

- `ficha-clinica`: ficha clínica mínima 1—1 con paciente, evoluciones fechadas/firmadas
  e inmutables (append-only), adjuntos Rx/fotos scoped por tenant, consentimiento
  informado previo con timestamp y canal, gate de consentimiento (bloquea clínica,
  no agenda), RBAC clínico y aislamiento multi-tenant.

### Modified Capabilities

_(ninguna)_ — la agenda (turnos) y el catálogo de pacientes no cambian su
comportamiento: el gate es una precondición interna de `ficha-clinica`, no una
modificación de `turnos-anti-solape` ni de `catalogos-pacientes`.

## Impact

- **DB / migración**: `006_ficha_clinica` (`fichas`, `evoluciones`, `adjuntos`,
  `consentimientos`, FK, índices, RLS forzada; `GRANT SELECT, INSERT` + `REVOKE
  UPDATE, DELETE` sobre `evoluciones` y `consentimientos`). No toca turnos ni catálogos.
- **Backend**: nuevo módulo `backend/app/ficha_clinica/` (dominio, puertos,
  adaptadores en memoria); `backend/app/routers/ficha_clinica.py`; `backend/app/schemas/ficha_clinica.py`.
- **Consume C-04**: `Paciente`, `Profesional` (catálogos).
- **Consume C-03**: `core/audit` (auditoría append-only) y matriz RBAC `03_actores_y_roles.md`.
- **Consume C-05**: patrón `Actor`/`TurnoError` (reutiliza `Invalido`/`Prohibido`/
  `NoEncontrado`), y `turnos.profesional_id` para el alcance "pacientes que atiende" del odontólogo.
- **Config**: sin env var nueva (esquema de `firma_hash` y storage de adjuntos = OQ).

## Hallazgo (corrección al roadmap)

`CHANGES.md:265` dice "Migración 005" para C-08, pero la 005 ya la consumió C-07
(`backend/alembic/versions/005_lista_espera.py`, `down_revision = "004_auth_rbac"`).
La migración real de C-08 es **006** (`down_revision = "005_lista_espera"`). Se
documenta acá y en `design.md`; no se renumera lo ya aplicado (mismo criterio que C-07).
