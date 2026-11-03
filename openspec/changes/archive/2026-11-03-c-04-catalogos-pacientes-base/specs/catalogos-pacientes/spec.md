# Spec Delta — catalogos-pacientes

## Purpose

Provide the tenant-scoped operational catalog (professionals, chairs, services, schedules, blocks) and patient base record used by agenda and booking.

## ADDED Requirements

### Requirement: Tenant-scoped catalog records

The system SHALL persist profesionales, sillones, prestaciones, horarios, bloqueos and pacientes with `tenant_id` NOT NULL and RLS; every read/write SHALL be limited to the authenticated tenant.

#### Scenario: Create and list a chair in the tenant
- **DADO** un Admin autenticado en T1
- **CUANDO** crea el sillón `Sillón 1` y luego lista sillones
- **ENTONCES** la respuesta incluye el sillón creado y una consulta de T2 no lo ve

#### Scenario: Other tenant cannot see the catalog
- **DADO** un sillón de T1
- **CUANDO** un usuario de T2 lista catálogos con `app.tenant_id=T2`
- **ENTONCES** no ve el sillón de T1

### Requirement: Catalogs are writable by Admin and readable by operational roles

The system SHALL allow `ADMIN` to create catálogos, SHALL allow `ADMIN`, `RECEPCION` and `ODONTOLOGO` to read them, and SHALL return `403` for a role without permission.

#### Scenario: Reception reads but cannot write catalogs
- **DADO** una recepcionista autenticada
- **CUANDO** lista prestaciones y luego intenta crear un sillón
- **ENTONCES** la lectura responde `200` y la escritura responde `403`

### Requirement: Service duration and price invariants

The system SHALL reject a prestación with `duracion_min <= 0` or `precio_base < 0`, and SHALL store integer durations and centavos amounts.

#### Scenario: Invalid duration is rejected
- **DADO** un payload de prestación con duración `0`
- **CUANDO** un Admin intenta crearla
- **ENTONCES** la respuesta es `422` y no se persiste la prestación

### Requirement: Patient phone is canonical and unique per tenant

The system SHALL normalize patient phone to E.164, SHALL reject invalid numbers, and SHALL link an existing patient when the same normalized phone is submitted in the same tenant instead of creating a duplicate.

#### Scenario: Same phone links the existing patient
- **DADO** un paciente de T1 con teléfono `+5491130551234`
- **CUANDO** se intenta crear otro paciente en T1 con el mismo teléfono
- **ENTONCES** la respuesta referencia el mismo id y existe un solo paciente con ese teléfono

#### Scenario: Invalid phone does not create
- **DADO** un teléfono `123`
- **CUANDO** se intenta crear un paciente
- **ENTONCES** la respuesta es `422` y no se crea fila

### Requirement: Seed materializes the demo catalog

The system SHALL provide an idempotent `seed_catalogo` that creates `Sillón 1` and the configured base prestaciones once per tenant.

#### Scenario: First seed creates and second is no-op
- **DADO** un tenant con los parámetros de C-02
- **CUANDO** se ejecuta `seed_catalogo` dos veces
- **ENTONCES** la primera crea un sillón y dos prestaciones; la segunda no crea filas nuevas

### Requirement: Migration 002 is ordered and reversible

The system SHALL create the catalog tables in migration 002 after migration 001, with indexes, RLS policies and a working downgrade.

#### Scenario: Upgrade and downgrade the catalog migration
- **DADO** una base en la revisión 001
- **CUANDO** se ejecuta `upgrade head` y luego `downgrade base`
- **ENTONCES** las tablas de catálogo aparecen y luego se eliminan sin errores de FK
