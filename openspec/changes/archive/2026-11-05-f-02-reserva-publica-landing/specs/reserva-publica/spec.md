# reserva-publica Specification (delta F-02)

## ADDED Requirements

### Requirement: Catálogo público de prestaciones y profesionales

El sistema SHALL exponer `GET /api/publico/{tokenTenant}/catalogo`, resolviendo
el tenant desde `{tokenTenant}`, con las prestaciones activas (`id`, `nombre`,
`duracion_min`) y los profesionales activos (`id`, `nombre`). La respuesta SHALL
NOT incluir `tenant_id`, precios, datos de pacientes ni horarios, y SHALL ser de
solo lectura: permite elegir `prestacion`/`profesional` antes de pedir huecos,
sin reemplazar el cálculo de disponibilidad.

#### Scenario: Catálogo del tenant con datos sembrados

- **GIVEN** el tenant T1 con las prestaciones `PREST-30` (`Consulta`, 30 min) y
  `PREST-45` (`Limpieza`, 45 min), y los profesionales activos `P1` (`Dra. Demo`)
  y `P2` (`Dr. Ejemplo`), y el tenant T2 con datos distintos
- **WHEN** el paciente pide `GET /api/publico/T1/catalogo`
- **THEN** la respuesta `200` incluye exactamente las dos prestaciones de T1 con
  `id`, `nombre` y `duracion_min`, y los dos profesionales de T1 con `id` y
  `nombre`, sin datos de T2

#### Scenario: Allow-list sin PHI ni claves internas

- **GIVEN** un catálogo sembrado con prestaciones y profesionales
- **WHEN** se inspeccionan las claves de la respuesta `200`
- **THEN** cada prestación expone solo `id`, `nombre` y `duracion_min`, cada
  profesional solo `id` y `nombre`, y no aparecen `tenant_id`, `precio_base`,
  `paciente_id`, nombre/teléfono de pacientes ni horarios

#### Scenario: tokenTenant inexistente responde 404 uniforme

- **GIVEN** un `tokenTenant` que no resuelve a ningún tenant activo
- **WHEN** se pide `GET /api/publico/NO-EXISTE/catalogo`
- **THEN** la respuesta es `404` con `detalle` uniforme y lista de alternativas
  vacía, sin listas de prestaciones ni profesionales

#### Scenario: Tenant sin catálogo devuelve listas vacías

- **GIVEN** el tenant T3 activo pero sin prestaciones ni profesionales sembrados
- **WHEN** el paciente pide `GET /api/publico/T3/catalogo`
- **THEN** la respuesta `200` es `{"prestaciones": [], "profesionales": []}` sin
  inventar datos
