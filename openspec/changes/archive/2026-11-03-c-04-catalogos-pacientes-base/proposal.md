# Proposal

## Why

C-02 creó el tenant y C-03 la autenticación, pero todavía no existen los catálogos que la agenda necesita: profesionales, sillones, prestaciones, horarios, bloqueos y pacientes. Sin C-04, C-05 y C-06 no tienen entidades reales para operar.

## What Changes

- Modelos y migración 002 para catálogos base y pacientes.
- CRUD de profesionales, sillones y prestaciones con RBAC (Admin escribe, Recepción/Odontólogo leen).
- Pacientes con teléfono E.164, unicidad por tenant y vinculación sin duplicar.
- Horarios semanales y bloqueos modelados para la disponibilidad de C-05/C-06.
- Seed de catálogo demo a partir de los parámetros de C-02.
- RLS forzada y grants para `turnos_app` en todas las tablas nuevas.

## Capabilities

### New Capabilities

- `catalogos-pacientes`: catálogo operativo del tenant y ficha base de paciente.

### Modified Capabilities

- Ninguna capacidad existente cambia; C-05 conserva su contrato.

## Impact

- `backend/app/models/catalogos.py`, `backend/app/routers/catalogos.py`, `backend/app/schemas/catalogos.py`.
- Migración `002_catalogos_pacientes.py`, seed `seed_catalogo`.
- Tests de modelos, migración, API y seed.
