# obras-sociales Specification

## Purpose

Definir el catálogo de obras sociales por tenant, la cobertura configurable por
(obra social × prestación) con sus tramos OS/paciente, y la liquidación por período de los turnos
atendidos con exportación CSV. La cobertura es **configurada, no validada en vivo** (RN-OS-01,
DD-04); la validación realtime y los aranceles por OS quedan fuera de v1 (PO-04, PO-08).

## Requirements

### Requirement: Tenant-scoped health insurance catalog

The system SHALL let an `ADMIN` of a tenant create, list and activate/deactivate health insurance
providers (obras sociales). Names SHALL be unique per tenant. The catalog SHALL start with fictitious
providers seeded per tenant (RN-OS-03).

#### Scenario: Create a provider
- **DADO** un tenant sin la obra social "OS Demo"
- **CUANDO** un `ADMIN` envía `POST /api/obras-sociales` con el nombre "OS Demo"
- **ENTONCES** la respuesta es `201` con la obra social activa

#### Scenario: Duplicate name in the same tenant
- **DADO** una obra social "OS Demo" existente en el tenant
- **CUANDO** se intenta crear otra con el mismo nombre
- **ENTONCES** la respuesta es `409` y no se crea un duplicado

#### Scenario: Only admins configure the catalog
- **DADO** un actor con rol `RECEPCION`
- **CUANDO** intenta crear una obra social
- **ENTONCES** la respuesta es `403` y el catálogo no cambia

#### Scenario: Configuration is audited
- **DADO** un `ADMIN` que crea una obra social o configura una cobertura
- **CUANDO** la operación termina con `201`/`200`
- **ENTONCES** se agrega una entrada append-only en auditoría con tenant, actor, acción y entidad
- **Y** un intento rechazado (`403`/`422`) no agrega ninguna entrada

### Requirement: Configurable coverage per provider and service

The system SHALL store coverage by `(tenant, obra social, prestación)` with mode `PORCENTAJE` or `MONTO`,
a positive value and an optional cap. A `PORCENTAJE` SHALL be between 1 and 100. Repeating the same
pair SHALL update the existing coverage. Every response SHALL declare `validada_en_vivo = false`
(RN-OS-01, DD-04).

#### Scenario: Upsert coverage
- **DADO** una obra social y una prestación del tenant
- **CUANDO** un `ADMIN` configura `PORCENTAJE 50` con tope
- **ENTONCES** la respuesta es `200`/`201` con `modo`, `valor`, `tope` y `validada_en_vivo = false`
- **Y** una segunda configuración del mismo par reemplaza la anterior sin crear duplicados

#### Scenario: Invalid percentage is rejected
- **DADO** una cobertura con `modo = PORCENTAJE`
- **CUANDO** se envía `valor = 0` o `valor = 101`
- **ENTONCES** la respuesta es `422` y no se guarda configuración

#### Scenario: Coverage from another tenant is not visible
- **DADO** una cobertura configurada en el tenant A
- **CUANDO** un actor del tenant B lista coberturas
- **ENTONCES** la respuesta no incluye la cobertura de A

### Requirement: Coverage split calculation

The system SHALL calculate the split between the provider and the patient from the service base price,
the configured coverage and the cap. The provider amount SHALL never exceed the base price, and the
patient amount SHALL be the remainder.

#### Scenario: Percentage with cap
- **DADO** `precio_base = 10000` y cobertura `PORCENTAJE 80` con tope `7000`
- **CUANDO** se calcula el tramo
- **ENTONCES** `cobertura_os = 7000` y `a_cargo_paciente = 3000`

#### Scenario: Fixed amount capped by price
- **DADO** `precio_base = 5000` y cobertura `MONTO 8000`
- **CUANDO** se calcula el tramo
- **ENTONCES** `cobertura_os = 5000` y `a_cargo_paciente = 0`

#### Scenario: Patient without coverage pays the full price
- **DADO** un paciente sin obra social
- **CUANDO** se calcula el tramo de una prestación con cobertura configurada
- **ENTONCES** `cobertura_os = 0`, `a_cargo_paciente = precio_base` y `origen = SIN_COBERTURA`

#### Scenario: Service without configured coverage
- **DADO** un paciente con obra social y una prestación sin cobertura para esa OS
- **CUANDO** se calcula el tramo
- **ENTONCES** `cobertura_os = 0` y `origen = SIN_COBERTURA`

### Requirement: Period settlement of attended turns

The system SHALL generate a settlement for one provider and one period, grouping only turns with
`estado = PRESENTE`, `inicio` inside `[desde, hasta)` in the operational day (`-03:00`), patient with
that provider and service with configured coverage. Each settlement line SHALL record turn, patient,
service, date and the provider amount. The total SHALL be the sum of the lines (RN-OS-02). The base
amount SHALL be `prestaciones.precio_base`; provider-specific fee schedules (PO-08) are out of v1.

#### Scenario: Settlement includes only attended turns with coverage
- **DADO** turnos `PRESENTE`, `AUSENTE` y `CANCELADO` del período, con y sin obra social
- **CUANDO** se genera la liquidación de la OS y el período
- **ENTONCES** sólo aparece el turno `PRESENTE` con cobertura configurada
- **Y** el total es la suma de las coberturas OS de esas líneas

#### Scenario: Turn outside the period is excluded
- **DADO** un turno `PRESENTE` con cobertura pero con `inicio` fuera de `[desde, hasta)`
- **CUANDO** se genera la liquidación
- **ENTONCES** el turno no aparece y no suma al total

#### Scenario: Settlement without eligible turns is rejected
- **DADO** un período sin turnos atendidos con cobertura para esa OS
- **CUANDO** se intenta generar la liquidación
- **ENTONCES** la respuesta es `409` y no se crea la liquidación

#### Scenario: Two tenants cannot see each other's settlement
- **DADO** una liquidación del tenant A
- **CUANDO** un actor del tenant B pide el detalle, el cierre o el CSV de esa liquidación
- **ENTONCES** la respuesta es `404` y no se expone ningún dato

#### Scenario: Odontologist cannot generate settlements
- **DADO** un actor con rol `ODONTOLOGO`
- **CUANDO** intenta generar o cerrar una liquidación
- **ENTONCES** la respuesta es `403` y no se crea ni cierra nada

#### Scenario: Concurrent generation does not duplicate
- **DADO** dos pedidos simultáneos de la misma OS y período
- **CUANDO** ambos intentan crear la liquidación
- **ENTONCES** existe una sola liquidación para ese `(tenant, OS, período)`
- **Y** el segundo pedido devuelve la existente o `409`, nunca un duplicado

### Requirement: Draft regeneration and immutable closure

A settlement in `BORRADOR` SHALL be regenerable for the same provider and period, replacing its lines
and total. Once `CERRADA`, it SHALL be immutable and any regeneration SHALL be rejected with `409`.

#### Scenario: Regenerating a draft replaces its lines
- **DADO** una liquidación `BORRADOR` del período
- **CUANDO** se vuelve a generar el mismo período después de agregar un turno atendido
- **ENTONCES** la liquidación mantiene su id, reemplaza las líneas y actualiza el total

#### Scenario: Closed settlement cannot change
- **DADO** una liquidación cerrada
- **CUANDO** se intenta regenerar el período o cerrar de nuevo
- **ENTONCES** la respuesta es `409` y el snapshot no cambia

#### Scenario: Settlement operations are audited
- **DADO** una liquidación generada y luego cerrada
- **CUANDO** se consulta la auditoría del tenant
- **ENTONCES** existen entradas append-only para la generación y el cierre, con actor y entidad
- **Y** los intentos `409`/`403` no agregan entradas

### Requirement: Settlement export

The system SHALL export a settlement as CSV with one row per line (turn, date, patient, service and
provider amount) and SHALL declare the total. The export SHALL be tenant-scoped.

#### Scenario: Export a settlement
- **DADO** una liquidación con dos líneas
- **CUANDO** `GET /api/liquidaciones/{id}/export.csv`
- **ENTONCES** la respuesta es `200`, `text/csv` y contiene el encabezado y las dos líneas
- **Y** las columnas son `turno_id,fecha,paciente_id,prestacion_id,monto_centavos`
- **Y** los montos se exportan en centavos enteros, sin símbolo de moneda

#### Scenario: Export of another tenant is not found
- **DADO** una liquidación del tenant A
- **CUANDO** un actor del tenant B pide su exportación
- **ENTONCES** la respuesta es `404`

### Requirement: Tenant isolation for insurance data

Every insurance table SHALL be protected by row-level security scoped to the tenant, and every query
SHALL filter by `tenant_id`.

#### Scenario: No tenant context returns no rows
- **DADO** una sesión PostgreSQL sin `app.tenant_id`
- **CUANDO** se consultan obras sociales, coberturas o liquidaciones
- **ENTONCES** la consulta devuelve cero filas y no expone datos de ningún tenant
