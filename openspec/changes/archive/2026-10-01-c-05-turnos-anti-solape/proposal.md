# Proposal — C-05 `turnos-anti-solape`

## Why

Las dobles reservas son el problema #1 detectado en el Discovery: coordinar por
WhatsApp/teléfono genera solapes, confirmaciones manuales y sillón ocioso. Este
change es el corazón del MVP, el ejemplo recomendado por la consigna del curso y
sus reglas son verificables directamente en base de datos.

## What Changes

- Modelo `Turno` (tenant, profesional, sillón, paciente, prestación, inicio,
  fin calculado, estado, `sobreturno=false`, origen, `token_publico?`) con
  constraint EXCLUDE anti-solape por `(tenant, profesional)` y
  `(tenant, sillón)` en `[inicio, fin)`, excluyendo `CANCELADO`/`REPROGRAMADO`
  y `sobreturno=true`.
- Migración 003: tabla `turnos` + EXCLUDE + índices `(tenant, profesional,
  inicio)`, `(tenant, sillón, inicio)`, `(tenant, estado)` + RLS por `tenant_id`.
- API: `CRUD /api/turnos`, `POST /api/turnos/:id/sobreturno` (motivo
  obligatorio + auditoría), `POST /api/turnos/:id/cancelar|reprogramar`;
  slot tomado → `409` + 3 alternativas.
- Lógica de dominio standalone (sin UI) testeable con Node 24: cálculo de fin
  desde `prestacion.duracion_min`, detección de solape, adyacencia exacta
  permitida, cancelados/reprogramados que no bloquean.
- La UI de agenda (`(app)/agenda`: vista día/semana, drag&drop) queda **fuera**
  de este change y se anota como follow-up.

## Capabilities

### New Capabilities

- `turnos-anti-solape`: creación/reprogramación de turnos con anti-solapamiento
  real en DB, sobreturno explícito auditado, cancelación/reprogramación y
  errores 409 con alternativas.

### Modified Capabilities

(none — no hay specs previas; `openspec list --specs` → vacío.)

## Impact

- Afecta: dominio agenda (`Turno`), migración 003, API `/api/turnos/*`,
  auditoría append-only (sobreturnos, cancelaciones, reprogramaciones).
- Depende de: C-03 (RBAC + `lib/audit`), C-04 (Profesional, Sillón, Paciente,
  Prestación, Bloqueos). La implementación asume esas entidades; el contrato de
  este change no las redefine.
- Desbloquea: C-06 (reserva online), C-10 (caja), C-12 (OS), C-14 (GCal).
- Governance: **CRÍTICO** (RN-GL-01: anti-solape y auditoría no se negocian).
- Follow-up explícito (fuera de alcance): UI `(app)/agenda` día/semana por
  profesional y sillón con drag&drop.

## Addendum — reimplementación Python (2026-10-02, no reescribe historia)

Lo arriba dicho vale igual salvo el stack: donde dice "testeable con Node 24",
"tipado estricto TS (zod en borde API)" y "Migración 003 Prisma/SQL", léase
Python 3.14 + FastAPI + SQLAlchemy + Pydantic + revisión Alembic 003
(`backend/`, `tests/`, `py -m pytest`). El QUÉ (modelo, EXCLUDE, endpoints,
409+3, sobreturno auditado) no cambió; ver `reimplementacion-python.md`.
