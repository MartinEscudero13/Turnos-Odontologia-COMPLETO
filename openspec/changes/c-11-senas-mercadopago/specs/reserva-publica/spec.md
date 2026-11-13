# Spec Delta — reserva-publica (C-11: seña al reservar)

## Purpose

Extender la reserva pública de C-06 para que una prestación con seña cree la seña y devuelva el
link de pago, dejando el turno `PENDIENTE` hasta la acreditación, sin cambiar la verificación
liviana, el rate-limit, el anti-solape ni el aislamiento ya contratados.

## ADDED Requirements

### Requirement: Seña obligatoria al reservar

Cuando la regla efectiva de la prestación exige seña, la reserva pública SHALL crear la seña
`PENDIENTE` y devolver en el `201` el bloque `sena` (`sena_id`, `estado`, `monto_centavos`,
`expira_at`, `token_sena`, `preferencia_estado`, `init_point`, `politica` con
`anticipacion_cancelacion_h`, `reembolsable` y `hay_pago_acreditado`); el turno SHALL quedar
`PENDIENTE` y un fallo de Mercado Pago SHALL NOT impedir la reserva.

#### Scenario: Reserva con seña devuelve el link de pago

- **GIVEN** el reloj en `2026-11-13T09:00:00-03:00`, T1 con la prestación PREST-1 de `precio_base=10000` y default de seña `PORCENTAJE=30`, y una verificación válida para reservar
- **WHEN** el paciente reserva un hueco libre de PREST-1
- **THEN** la respuesta `201` trae el turno `PENDIENTE` y `sena` con `monto_centavos=3000`, `estado=PENDIENTE`, `expira_at`, `token_sena` opaco, `preferencia_estado=CREADA`, `init_point` no vacío y `politica={anticipacion_cancelacion_h: 24, reembolsable: true, hay_pago_acreditado: false}`

#### Scenario: La reserva sin seña mantiene el contrato anterior

- **GIVEN** T1 con una prestación cuya regla efectiva es `SIN_SENA` y una verificación válida
- **WHEN** el paciente reserva un hueco libre
- **THEN** la respuesta `201` no incluye el bloque `sena`, no se crea ninguna seña y el turno queda `PENDIENTE` como hoy

#### Scenario: Mercado Pago caído no bloquea la reserva

- **GIVEN** T1 con una prestación con seña y la pasarela configurada para fallar, y una verificación válida
- **WHEN** el paciente reserva un hueco libre
- **THEN** la respuesta `201` trae el turno `PENDIENTE` y `sena.preferencia_estado=FALLIDA` con `init_point=null`, y el turno existe para poder reintentar el pago

#### Scenario: Los controles de C-06 siguen aplicándose

- **GIVEN** T1 con una prestación con seña y un hueco libre
- **WHEN** se intenta reservar sin `verificacion_id`, con una verificación vencida o superando el rate-limit
- **THEN** el sistema responde `403` o `429` como hoy, no crea turno ni seña y no llama a la pasarela

#### Scenario: Dos reservas del mismo hueco con seña dejan un solo turno

- **GIVEN** el reloj en `2026-11-13T09:00:00-03:00`, T1 con una prestación con seña y dos conexiones independientes a PostgreSQL
- **WHEN** ambas reservas confirman el mismo hueco a la vez con una verificación válida cada una
- **THEN** exactamente una responde `201`, la otra responde `409` con alternativas, y existe un solo turno y una sola seña

## MODIFIED Requirements

### Requirement: Reserva pública con token y confirmación inmediata

El sistema SHALL crear en `POST /api/publico/{tokenTenant}/reservas` un turno `PENDIENTE` con
`origen=RESERVA_ONLINE` y un `token_publico` UUID v4 único, y responder `201` con el turno propio
y, si la prestación exige seña, el bloque `sena`. El payload acepta sólo `prestacion`,
`profesional`, `inicio`, `nombre`, `telefono` y `verificacion_id`; el servidor deriva `fin` y elige
un sillón libre. `GET /api/publico/{tokenTenant}/reservas/{token}` SHALL devolver ese turno.

#### Scenario: Reserva creada con token público

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el tenant T1 con PREST-30 (`SIN_SENA`), el profesional P1, los sillones activos S1 y S2, S1 ocupado de 11:00 a 11:30 del 2026-10-06 y S2 libre, y una verificación válida para reservar
- **WHEN** "Paciente Demo" envía `POST /api/publico/T1/reservas` con `prestacion=PREST-30`, `profesional=P1`, `inicio=2026-10-06T11:00:00-03:00`, `nombre=Paciente Demo`, `telefono=+5491100000000`, `verificacion_id=VER-1`
- **THEN** la respuesta `201` trae `estado=PENDIENTE`, `origen=RESERVA_ONLINE`, `inicio=2026-10-06T11:00:00-03:00`, `fin=2026-10-06T11:30:00-03:00` calculado por el servidor, `sillon_id=S2` elegido por el servidor y un `token_publico` UUID v4 no vacío, sin bloque `sena`

#### Scenario: Cada reserva obtiene un token distinto

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y dos reservas consecutivas creadas en el mismo tenant T1
- **WHEN** se comparan sus `token_publico`
- **THEN** los dos tokens son distintos, cada uno es un UUID v4 parseable y ninguno coincide con el `turno_id` ni con el `tokenTenant`

#### Scenario: El fin nunca lo fija el cliente

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y el payload mínimo válido de reserva (`prestacion`, `profesional`, `inicio`, `nombre`, `telefono`, `verificacion_id`) al que se agrega el campo `fin` con `2026-10-06T11:15:00-03:00`
- **WHEN** el paciente envía la reserva a `POST /api/publico/T1/reservas`
- **THEN** el sistema responde `422` porque `fin` está fuera del payload declarado, y no crea el turno ni la seña

#### Scenario: Sin sillón libre responde 409 sin turno

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el profesional P1 libre y los únicos sillones activos S1 y S2 ocupados de 11:00 a 11:30 del 2026-10-06
- **WHEN** el paciente reserva con `inicio=2026-10-06T11:00:00-03:00`
- **THEN** el sistema responde `409` con alternativas reales, ningún turno ni seña quedan persistidos y `GET /api/publico/T1/disponibilidad` tampoco ofrecía ese inicio

#### Scenario: Un hueco del mismo día es reservable sin lead time adicional

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y un hueco libre el mismo día de 11:00 a 11:30
- **WHEN** el paciente consulta disponibilidad con `desde=2026-10-05T00:00:00-03:00` y reserva ese hueco
- **THEN** el hueco se ofrece y la reserva responde `201`: mientras `OQ-6` siga abierta, `C-06` no impone un lead time mínimo adicional al reloj del servidor

#### Scenario: Consulta del turno propio por token

- **GIVEN** una reserva `PENDIENTE` de T1 con `token_publico` TOK-B
- **WHEN** se pide `GET /api/publico/T1/reservas/TOK-B`
- **THEN** la respuesta `200` trae sólo `turno_id`, `estado`, `inicio`, `fin`, `prestacion` y `token_publico`, sin `tenant_id` ni `paciente_id`

#### Scenario: La reserva con seña informa el estado del pago

- **GIVEN** T1 con una prestación con seña y la pasarela disponible
- **WHEN** el paciente reserva un hueco libre
- **THEN** la respuesta `201` incluye `sena.estado=PENDIENTE` y `sena.politica.reembolsable=true` desde la creación, y el turno queda `PENDIENTE` hasta que llegue la acreditación

### Requirement: Privacidad de respuestas y logs

Las respuestas públicas SHALL contener sólo datos del hueco, del turno propio y de la seña propia
(`sena_id`, estado, monto, `expira_at`, token, `init_point` y política); SHALL NOT exponer nombre,
teléfono, DNI ni dato clínico de otros pacientes, y los logs SHALL NOT registrar PHI ni el token de
pago.

#### Scenario: La disponibilidad no expone pacientes

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y la disponibilidad de T1 con turnos activos de dos pacientes distintos
- **WHEN** el paciente consulta `GET /api/publico/T1/disponibilidad`
- **THEN** ninguna entrada incluye `paciente_id`, nombre, teléfono ni dato clínico

#### Scenario: La reserva sólo devuelve el turno propio

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, T1 con la reserva de "Paciente Demo" y otro turno activo de "Otro Paciente Demo" con teléfono `+5491100000001`
- **WHEN** se lee la respuesta `201` de la reserva de "Paciente Demo"
- **THEN** sus únicas claves son `turno_id`, `estado`, `inicio`, `fin`, `origen`, `prestacion`, `sillon_id`, `token_publico` y, si la prestación exige seña, `sena`, y no aparece el nombre ni el teléfono de "Otro Paciente Demo"

#### Scenario: El link de pago no expone datos del paciente

- **GIVEN** T1 con una seña de "Paciente Demo" con teléfono `+5491100000000`
- **WHEN** se lee el bloque `sena` de la reserva y la seña por su token
- **THEN** no aparece nombre, teléfono, DNI, `paciente_id` ni `tenant_id`, y el token no se escribe en los logs

#### Scenario: El 404 no filtra si el turno existe en otro tenant

- **GIVEN** un token inexistente y un token real de T1 usados en la ruta pública de T2
- **WHEN** se comparan ambas respuestas de `GET /api/publico/T2/reservas/{token}`
- **THEN** ambas son `404` con el mismo cuerpo, sin `tenant_id`, nombre ni teléfono

#### Scenario: Los logs no contienen PHI

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y una reserva pública exitosa en T1
- **WHEN** se inspecciona el registro estructurado de la operación
- **THEN** sólo aparecen identificadores (`tenant_id`, `turno_id`, `sena_id`), estado y horarios; no aparecen nombre, teléfono, token ni datos del pagador
