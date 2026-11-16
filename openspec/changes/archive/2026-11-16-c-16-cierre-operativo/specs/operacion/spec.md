# Spec Delta — operacion

## Purpose

Operar la plataforma fuera del request HTTP: administrar tenants cross-tenant con la credencial de
dueño de la base y respaldar/restaurar PostgreSQL sin exponer secretos ni PHI en logs.

## ADDED Requirements

### Requirement: Cross-tenant administration by CLI

The system SHALL provide a command-line tool that lists, creates, activates and deactivates tenants
using the database owner credential. It SHALL fail clearly when the schema is missing or the tenant
does not exist.

#### Scenario: List tenants
- **DADO** la base migrada con tenants
- **CUANDO** se ejecuta `py tools/superadmin.py list`
- **ENTONCES** imprime slug, id, nombre, plan, estado y fecha de creación

#### Scenario: Create a tenant
- **DADO** un slug libre
- **CUANDO** se ejecuta `py tools/superadmin.py create clinica-norte "Clínica Norte"`
- **ENTONCES** el tenant queda creado y activo

#### Scenario: Deactivate a tenant
- **DADO** un tenant activo
- **CUANDO** se ejecuta `py tools/superadmin.py deactivate clinica-norte`
- **ENTONCES** el tenant queda inactivo

#### Scenario: Unknown tenant
- **DADO** un slug inexistente
- **CUANDO** se intenta activarlo
- **ENTONCES** el comando falla con un mensaje explícito

### Requirement: Database backup and restore

The system SHALL provide a command-line tool that dumps the database in custom format and restores it,
reading the connection string from the environment and never persisting credentials.

#### Scenario: Create a backup
- **DADO** `DATABASE_URL` y `pg_dump` disponibles
- **CUANDO** se ejecuta `py tools/backup.py`
- **ENTONCES** se crea un archivo `.dump` en `backups/`

#### Scenario: Restore a backup
- **DADO** un archivo de respaldo
- **CUANDO** se ejecuta `py tools/backup.py --restore backups/turnos.dump`
- **ENTONCES** `pg_restore` recrea el esquema y los datos

#### Scenario: Missing pg_dump
- **DADO** un entorno sin `pg_dump`
- **CUANDO** se ejecuta el respaldo
- **ENTONCES** el comando explica la alternativa con Docker y no deja un archivo vacío

### Requirement: Compose backup service

The Compose file SHALL expose an optional `backup` service that writes a dump into `backups/` and does
not start with the default stack.

#### Scenario: Run the backup service
- **DADO** el stack con la base healthy
- **CUANDO** se ejecuta `docker compose run --rm backup`
- **ENTONCES** el dump queda en `backups/`
