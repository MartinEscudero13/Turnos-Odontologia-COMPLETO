# tenant-core Specification

## Purpose
Provide the tenant, user, audit and configuration primitives that every business capability uses, with database-enforced isolation and idempotent setup.

## Requirements

### Requirement: Tenant identity and active state

The system SHALL persist a tenant with a unique slug and an explicit active flag. An inactive or unknown tenant SHALL NOT authenticate users nor allow business operations.

#### Scenario: Tenant created with unique slug
- **GIVEN** que no existe un tenant con slug `demo`
- **WHEN** se crea el tenant con nombre `Consultorio Demo`, slug `demo`, plan `BASICO` y `activo=true`
- **THEN** el tenant queda persistido con id UUID y una segunda creación con el mismo slug es rechazada

#### Scenario: Tenant inactivo no opera
- **GIVEN** un tenant existente con `activo=false`
- **WHEN** un usuario intenta iniciar una operación de negocio en ese tenant
- **THEN** el sistema responde `403` sin crear ni modificar datos

### Requirement: Tenant-scoped users with unique email

The system SHALL persist users with `tenant_id` NOT NULL, rol válido (`ADMIN`, `RECEPCION`, `ODONTOLOGO`) y `UNIQUE(tenant_id, email)`. El email SHALL normalizarse a minúsculas.

#### Scenario: Email unique inside tenant
- **GIVEN** un usuario `admin@demo.test` en el tenant T1
- **WHEN** se intenta crear otro usuario con el mismo email y `tenant_id=T1`
- **THEN** la operación es rechazada por la restricción única

#### Scenario: Same email allowed in another tenant
- **GIVEN** los tenants T1 y T2
- **WHEN** cada uno crea un usuario `admin@demo.test`
- **THEN** ambas creaciones son válidas y cada usuario pertenece a su tenant

### Requirement: Database-enforced tenant isolation

The system SHALL enable and force Row-Level Security on every tenant-scoped table, SHALL require `app.tenant_id`, and SHALL deny reads/writes outside that tenant.

#### Scenario: Query without tenant context fails closed
- **GIVEN** una conexión con `app.tenant_id` sin configurar
- **WHEN** se consulta `usuarios`
- **THEN** la consulta falla por contexto de tenant faltante y no devuelve filas

#### Scenario: Tenant A cannot read tenant B users
- **GIVEN** usuarios de T1 y T2 y una conexión con `app.tenant_id=T1`
- **WHEN** se listan usuarios
- **THEN** sólo aparece el usuario de T1

#### Scenario: Tenant A cannot write into tenant B
- **GIVEN** una conexión con `app.tenant_id=T1`
- **WHEN** se intenta insertar un usuario con `tenant_id=T2`
- **THEN** la política RLS rechaza la escritura y no deja filas

### Requirement: Append-only audit log

The system SHALL record audit entries with tenant, actor, action, entity, before/after and timestamp. `UPDATE` and `DELETE` SHALL be denied for the application role.

#### Scenario: Audit insert accepted
- **GIVEN** un tenant y un actor válidos
- **WHEN** se inserta una entrada `CREADO` para una entidad
- **THEN** la entrada queda persistida con su JSON antes/después

#### Scenario: Audit mutation rejected
- **GIVEN** una entrada de auditoría existente
- **WHEN** el rol de aplicación intenta `UPDATE` o `DELETE`
- **THEN** la operación es rechazada y la entrada permanece intacta

### Requirement: Idempotent tenant seed

The system SHALL provide a seed that, for a given tenant, inserts roles, turn states, payment methods, cancellation/notice parameters, WhatsApp templates and initial catalog values once, and SHALL be safe to run twice.

#### Scenario: First seed creates defaults
- **GIVEN** un tenant nuevo sin configuración
- **WHEN** se ejecuta el seed
- **THEN** quedan registrados los roles, estados, medios, parámetros, plantillas y catálogo demo

#### Scenario: Second seed is a no-op
- **GIVEN** un tenant ya sembrado
- **WHEN** se ejecuta el seed otra vez
- **THEN** no se duplican filas y los valores existentes no cambian

### Requirement: Migration 001 creates the tenant core

The system SHALL apply migration 001 from an empty database, creating tenants, usuarios, auditoria and tenant parameters with indexes, RLS policies and dependencies ordered before migration 002/003.

#### Scenario: Empty database reaches head
- **GIVEN** una base vacía y disponible
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** las tablas del núcleo existen y la versión vigente es la última revisión

#### Scenario: Downgrade removes only this migration
- **GIVEN** una base en la revisión 001
- **WHEN** se ejecuta `alembic downgrade base`
- **THEN** las tablas de 001 se eliminan sin errores de dependencias
