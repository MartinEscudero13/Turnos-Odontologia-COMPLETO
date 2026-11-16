# admin-tenant Specification

## Purpose

Dar al `ADMIN` del consultorio control sobre su propio tenant: configuración validada, gestión de
usuarios, exportación 1-clic sin secretos y KPIs base con definiciones explícitas —incluida la
ocupación—. Todo queda aislado por `tenant_id` y auditado. El superadmin cross-tenant y el respaldo se
operan fuera de la API, con las herramientas de `operacion`.

## Requirements

### Requirement: Tenant configuration with whitelist

The system SHALL let an `ADMIN` read and partially update the configuration of its own tenant. Only
known keys SHALL be accepted; unknown keys or invalid types SHALL be rejected without persisting.

#### Scenario: Read configuration
- **DADO** un tenant con `anticipacion_cancelacion_h = 24`
- **CUANDO** un `ADMIN` consulta `GET /api/tenant/config`
- **ENTONCES** la respuesta `200` incluye la clave y su valor

#### Scenario: Partial update
- **DADO** la configuración actual del tenant
- **CUANDO** se envía `PUT /api/tenant/config` con `anticipacion_cancelacion_h = 48`
- **ENTONCES** la respuesta `200` refleja el cambio y conserva las demás claves

#### Scenario: Unknown key is rejected
- **DADO** un pedido con la clave `descuento_secreto`
- **CUANDO** se intenta actualizar
- **ENTONCES** la respuesta es `422` y la configuración no cambia

#### Scenario: Configuration is audited
- **DADO** una actualización exitosa
- **CUANDO** se consulta la auditoría
- **ENTONCES** existe una entrada con actor, antes y después
- **Y** un intento rechazado no agrega entradas

### Requirement: Tenant user management

The system SHALL let an `ADMIN` list, create and activate/deactivate users of its tenant. Passwords
SHALL be hashed with Argon2, emails SHALL be unique per tenant and `password_hash` SHALL never be
returned.

#### Scenario: Create a user
- **DADO** un email libre en el tenant
- **CUANDO** un `ADMIN` crea un usuario con rol `RECEPCION` y password de 8+ caracteres
- **ENTONCES** la respuesta es `201` sin `password_hash`

#### Scenario: Duplicate email
- **DADO** un usuario con el email `recepcion@demo.test`
- **CUANDO** se intenta crear otro con el mismo email en el tenant
- **ENTONCES** la respuesta es `409` y no se crea un duplicado

#### Scenario: Admin cannot deactivate self
- **DADO** un `ADMIN` autenticado como el usuario objetivo
- **CUANDO** intenta desactivarse
- **ENTONCES** la respuesta es `409` y el usuario sigue activo

#### Scenario: Invalid role
- **DADO** un rol fuera de `ADMIN`/`RECEPCION`/`ODONTOLOGO`
- **CUANDO** se intenta crear el usuario
- **ENTONCES** la respuesta es `422` y no se crea

### Requirement: One-click tenant export

The system SHALL export the tenant data as JSON or CSV. The export SHALL include only the requesting
tenant, SHALL exclude secrets and SHALL be audited.

#### Scenario: Export JSON
- **DADO** un tenant con pacientes y turnos
- **CUANDO** un `ADMIN` pide `GET /api/exportacion?formato=json`
- **ENTONCES** la respuesta `200` incluye las secciones con sus filas

#### Scenario: Export CSV
- **DADO** la misma exportación en CSV
- **CUANDO** se pide `formato=csv`
- **ENTONCES** la respuesta es `text/csv` con encabezado y una fila por registro

#### Scenario: Export excludes secrets
- **DADO** un usuario con `password_hash` y un link con `oauth_ref`
- **CUANDO** se exporta el tenant
- **ENTONCES** ningún secreto aparece en el JSON ni en el CSV

#### Scenario: Export is tenant-scoped
- **DADO** datos de dos tenants
- **CUANDO** el tenant A exporta
- **ENTONCES** no aparece ningún registro del tenant B

### Requirement: Base KPIs

The system SHALL expose base KPIs for a period with explicit definitions: turns by state, absenteeism,
online reservation share, billing by professional, slots reassigned in under two hours and occupancy.
Occupancy SHALL be the share of booked minutes over the capacity offered by professionals in the
period, with a `0.0` result when the denominator is zero.

#### Scenario: Absenteeism
- **DADO** 2 turnos `PRESENTE` y 2 `AUSENTE` en el período
- **CUANDO** se consultan los KPIs
- **ENTONCES** `ausentismo_pct = 50.0`

#### Scenario: Online reservation share
- **DADO** 1 turno `RESERVA_ONLINE` y 3 de otros orígenes
- **CUANDO** se consultan los KPIs
- **ENTONCES** `reservas_online_pct = 25.0`

#### Scenario: Reassigned under two hours
- **DADO** un turno `LISTA_ESPERA` creado 30 minutos antes de su inicio y otro 3 horas antes
- **CUANDO** se consultan los KPIs
- **ENTONCES** `reasignados_2h = 1`

#### Scenario: Occupancy
- **DADO** 540 minutos ocupados y 1440 minutos de capacidad en el período
- **CUANDO** se consultan los KPIs
- **ENTONCES** `ocupacion_pct = 37.5`

#### Scenario: Occupancy without capacity
- **DADO** un período sin horarios cargados y sin turnos
- **CUANDO** se consultan los KPIs
- **ENTONCES** `ocupacion_pct = 0.0`

#### Scenario: Invalid period
- **DADO** `desde` posterior a `hasta`
- **CUANDO** se consultan los KPIs
- **ENTONCES** la respuesta es `422`

### Requirement: RBAC and tenant isolation for admin

Admin endpoints SHALL be restricted by role and every query SHALL filter by `tenant_id` with RLS.

#### Scenario: Reception cannot export
- **DADO** un actor `RECEPCION`
- **CUANDO** intenta exportar el tenant
- **ENTONCES** la respuesta es `403`

#### Scenario: Patient has no session
- **DADO** un actor `PACIENTE`
- **CUANDO** consulta la configuración
- **ENTONCES** la respuesta es `401`

#### Scenario: Config of another tenant is isolated
- **DADO** dos tenants con configuraciones distintas
- **CUANDO** cada uno consulta la suya
- **ENTONCES** ninguno ve la configuración del otro
