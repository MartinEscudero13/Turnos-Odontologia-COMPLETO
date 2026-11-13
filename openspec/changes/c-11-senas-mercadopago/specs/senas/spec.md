# Spec Delta — senas

## Purpose

Cobrar una seña online al reservar, atada 1──1 al turno, con link de pago de Mercado Pago,
webhook idempotente y autenticado, liberación automática del turno vencido con auto-oferta (C-07),
aplicación al cobro a través de la caja de C-10 y devolución explícita, sin login de paciente, sin
PHI y con aislamiento por tenant. La UI (`/pagar/:tokenSena`, agenda) queda diferida a `C-11-UI`.

## ADDED Requirements

### Requirement: Regla efectiva de la seña

El sistema SHALL resolver la regla efectiva como `prestacion.sena_modo ?? tenant_parametros['sena_modo']`,
con `SIN_SENA` como override válido y `SIN_SENA` cuando no hay configuración o ésta es inválida;
`PORCENTAJE` SHALL ser un entero 1–100 y `MONTO_FIJO` centavos mayores que 0, y el monto SHALL
calcularse sobre `precio_base` truncando al centavo (C11-OQ-01).

#### Scenario: El override de la prestación gana al default del tenant

- **GIVEN** T1 con `tenant_parametros['sena_modo']="PORCENTAJE"` y valor `30`, y la prestación PREST-1 con `sena_modo="MONTO_FIJO"` y `sena_valor=5000`
- **WHEN** se resuelve la regla de PREST-1
- **THEN** la regla efectiva es `MONTO_FIJO` de `5000` centavos y no el 30 % del tenant

#### Scenario: SIN_SENA es un override válido

- **GIVEN** T1 con default `PORCENTAJE=30` y la prestación PREST-2 con `sena_modo="SIN_SENA"`
- **WHEN** se resuelve la regla de PREST-2
- **THEN** la regla efectiva es `SIN_SENA` y la reserva de PREST-2 no exige seña

#### Scenario: Sin override la prestación hereda el default del tenant

- **GIVEN** T1 con default `PORCENTAJE=30`, el `precio_base=10000` de PREST-3 y `sena_modo` nulo en la prestación
- **WHEN** se resuelve la regla de PREST-3
- **THEN** la regla efectiva es `PORCENTAJE` de `30` y el monto es `3000` centavos

#### Scenario: Sin configuración en ningún nivel no se cobra seña

- **GIVEN** T1 sin claves `sena_modo`/`sena_valor` y la prestación PREST-4 sin override
- **WHEN** se resuelve la regla de PREST-4
- **THEN** la regla efectiva es `SIN_SENA`, no se crea ninguna seña y la reserva responde `201` sin bloque `sena`

#### Scenario: Una configuración inválida no rompe la reserva

- **GIVEN** T1 con `tenant_parametros['sena_modo']="PORCENTAJE"` y `sena_valor=0`, o con el modo `"MITAD"`
- **WHEN** se resuelve la regla y se intenta reservar
- **THEN** la regla se trata como `SIN_SENA`, la reserva responde `201`, no se crea seña y se registra `REGLA_SENA_INVALIDA` con `tenant_id` y `prestacion_id`, sin datos del paciente

#### Scenario: Un monto calculado en cero no genera seña

- **GIVEN** T1 con default `PORCENTAJE=30`, la prestación PREST-5 con `precio_base=0` y sin override
- **WHEN** se reserva PREST-5
- **THEN** no se crea una seña de `0` centavos y la reserva responde `201` sin bloque `sena`

### Requirement: Alta de la seña atada a la reserva

Al crear una reserva cuya regla efectiva exige seña, el sistema SHALL crear una `Sena` `PENDIENTE`
con `monto_centavos > 0`, snapshots de regla, precio y anticipación, `expira_at = min(ahora + SENA_TTL_H, turno.inicio)`
y token opaco hasheado, atada 1──1 al turno; el turno SHALL quedar `PENDIENTE` y una segunda seña
del mismo turno SHALL responder `409`.

#### Scenario: Seña creada con el monto de la regla

- **GIVEN** el reloj en `2026-11-13T09:00:00-03:00`, T1 con default `PORCENTAJE=30`, PREST-1 de `precio_base=10000` y `SENA_TTL_H=24`, y el turno de `2026-11-20T10:00:00-03:00`
- **WHEN** un paciente reserva PREST-1 con una verificación válida
- **THEN** se persiste una seña `PENDIENTE` de `3000` centavos con `regla_modo=PORCENTAJE`, `regla_valor=30`, `precio_base_centavos=10000` y `expira_at=2026-11-14T09:00:00-03:00`

#### Scenario: La expiración se acota al inicio del turno

- **GIVEN** el reloj en `2026-11-13T09:00:00-03:00`, `SENA_TTL_H=24` y el turno de `2026-11-13T18:00:00-03:00`
- **WHEN** se reserva ese turno con seña
- **THEN** `expira_at` es `2026-11-13T18:00:00-03:00` y no `2026-11-14T09:00:00-03:00` (C11-OQ-08)

#### Scenario: El turno sigue PENDIENTE hasta acreditar

- **GIVEN** T1 con una reserva cuya prestación exige seña
- **WHEN** la reserva responde `201`
- **THEN** el turno queda `PENDIENTE` con `origen=RESERVA_ONLINE` y la seña queda `PENDIENTE`, sin ningún turno `CONFIRMADO`

#### Scenario: Dos reservas distintas generan dos señas

- **GIVEN** T1 con dos huecos libres distintos y la misma prestación con seña
- **WHEN** se crean las dos reservas
- **THEN** existen dos señas con `turno_id` distintos y tokens distintos

#### Scenario: Una segunda seña del mismo turno se rechaza

- **GIVEN** T1 con el turno TUR-1 que ya tiene una seña
- **WHEN** se intenta crear otra seña para TUR-1
- **THEN** el sistema responde `409` y sigue existiendo una sola seña para ese turno

### Requirement: Preferencia de pago y link de Mercado Pago

El sistema SHALL pedir la preferencia con `external_reference = sena_id`, metadata de tenant y turno,
vencimiento en `expira_at` y descripción fija `"Seña de turno"`, y SHALL exponer `init_point`; si la
pasarela falla SHALL conservar la reserva y la seña `PENDIENTE` con
`preferencia_estado=FALLIDA`, y si `expira_at <= ahora` SHALL responder `409 SENA_VENCIDA` sin
llamar a la pasarela.

#### Scenario: Preferencia creada tras persistir la seña

- **GIVEN** T1 con una reserva que exige seña y la pasarela disponible
- **WHEN** se completa la reserva
- **THEN** la seña queda con `mp_preference_id`, `mp_init_point` y `preferencia_estado=CREADA`, y la preferencia se pidió después de persistir la seña

#### Scenario: Mercado Pago caído no pierde la reserva

- **GIVEN** T1 con la pasarela configurada para fallar
- **WHEN** un paciente reserva una prestación con seña
- **THEN** la respuesta es `201`, el turno existe `PENDIENTE`, la seña existe `PENDIENTE` con `preferencia_estado=FALLIDA` y no se pierde ninguna fila (RN-IN-03)

#### Scenario: El reintento devuelve la preferencia existente

- **GIVEN** T1 con una seña `PENDIENTE` y `preferencia_estado=CREADA`
- **WHEN** el paciente pide de nuevo la preferencia con su token
- **THEN** el sistema responde `200` con el mismo `init_point`, no crea una segunda preferencia y `intentos_preferencia` no cambia

#### Scenario: El reintento respeta el backoff

- **GIVEN** T1 con una seña `PENDIENTE`, `intentos_preferencia=2` y `proximo_reintento_at` en el futuro
- **WHEN** el paciente pide la preferencia antes de `proximo_reintento_at`
- **THEN** el sistema responde `202` con `reintentar_en`, no llama a la pasarela y no incrementa los intentos (C11-OQ-05, provisional)

#### Scenario: Una seña vencida no pide una preferencia nueva

- **GIVEN** T1 con una seña que sigue `PENDIENTE` pero con `expira_at` en el pasado y la pasarela disponible
- **WHEN** el paciente pide la preferencia con su token
- **THEN** el sistema responde `409 SENA_VENCIDA` sin llamar a la pasarela, la seña no cambia y no se crea ningún `init_point` nuevo

#### Scenario: La preferencia no lleva datos de la prestación ni del paciente

- **GIVEN** T1 con una reserva de "Paciente Demo" para la prestación "Conducto Demo" y la pasarela disponible
- **WHEN** se crea la preferencia
- **THEN** la preferencia se pide con `descripcion="Seña de turno"` y no incluye el nombre de la prestación, del profesional ni dato alguno del paciente

### Requirement: Token público de pago

`GET /api/publico/{tokenTenant}/senas/{token}` SHALL resolver el tenant por slug y el token por
hash dentro de ese tenant, sin sesión ni login, y devolver sólo `sena_id`, `estado`,
`monto_centavos`, `expira_at`, `preferencia_estado`, `init_point` (sólo si sigue vigente),
`turno{inicio,fin,prestacion}` y `politica`; un token inexistente, de otro tenant o rotado SHALL
responder `404` uniforme, y ambas rutas públicas SHALL usar el rate-limit de C-06.

#### Scenario: Lectura de una seña pendiente

- **GIVEN** T1 con una seña `PENDIENTE` vigente y un token válido
- **WHEN** el paciente abre el link de pago
- **THEN** la respuesta `200` trae `estado=PENDIENTE`, el monto, `expira_at`, el `init_point` y la política, con sólo las claves declaradas

#### Scenario: El token de otro tenant responde 404

- **GIVEN** una seña de T1 con token TOK-S y la ruta pública de T2
- **WHEN** se pide `GET /api/publico/T2/senas/TOK-S`
- **THEN** la respuesta `404` es idéntica a la de un token inexistente y no revela la existencia de la seña

#### Scenario: Las rutas públicas respetan el rate-limit

- **GIVEN** T1 con una seña y un token válido, y el contador de C-06 agotado para esa ventana
- **WHEN** se pide la seña o se reintenta la preferencia
- **THEN** el sistema responde `429` sin devolver datos de la seña y sin llamar a la pasarela

#### Scenario: Un token rotado deja de servir

- **GIVEN** T1 con una seña cuyo token fue reemitido y `token_rotado_en` registrado
- **WHEN** se usa el token anterior
- **THEN** el sistema responde `404` y el token nuevo sigue funcionando

#### Scenario: Una seña vencida no ofrece link de pago

- **GIVEN** T1 con una seña `LIBERADA` o `expira_at` en el pasado
- **WHEN** se consulta su token
- **THEN** la respuesta `200` trae el estado y `init_point=null`, y no se puede iniciar un pago nuevo

#### Scenario: La respuesta no expone datos del paciente

- **GIVEN** T1 con una seña de "Paciente Demo" con teléfono `+5491100000000`
- **WHEN** se lee la seña por su token
- **THEN** la respuesta no contiene nombre, teléfono, DNI, `paciente_id` ni `tenant_id`, y el token no aparece en los logs

### Requirement: Webhook autenticado de Mercado Pago

`POST /api/webhooks/mercadopago` SHALL validar `x-signature` como HMAC-SHA256 del manifiesto
`id:{data.id};request-id:{x-request-id};ts:{ts};` con `MP_WEBHOOK_SECRET`, en tiempo constante;
sin firma válida SHALL responder `401` sin procesar, sin secreto configurado SHALL responder `503`,
y SHALL re-consultar el pago a la pasarela antes de aplicar cualquier efecto, tomando la metadata
del pago re-consultado y no del cuerpo.

#### Scenario: Firma válida procesa la notificación

- **GIVEN** T1 con una seña `PENDIENTE`, `MP_WEBHOOK_SECRET` configurado y un pago aprobado en la pasarela
- **WHEN** llega la notificación con la firma correcta
- **THEN** el sistema responde `200`, registra el `PagoMP` y acredita la seña

#### Scenario: Firma inválida no procesa nada

- **GIVEN** T1 con una seña `PENDIENTE` y un `MP_WEBHOOK_SECRET` configurado
- **WHEN** llega una notificación con `x-signature` ausente o con un `v1` distinto
- **THEN** el sistema responde `401`, no crea `PagoMP`, la seña sigue `PENDIENTE` y no se llama a la pasarela

#### Scenario: Sin secreto configurado el webhook falla cerrado

- **GIVEN** un entorno sin `MP_WEBHOOK_SECRET` y una notificación bien formada
- **WHEN** se invoca el webhook
- **THEN** el sistema responde `503 WEBHOOK_NO_CONFIGURADO` y no procesa, no persiste ni acredita nada

#### Scenario: El cuerpo de la notificación no alcanza para acreditar

- **GIVEN** T1 con una seña `PENDIENTE` y un cuerpo que declara `status=approved` con `monto=1`, mientras la pasarela informa un pago rechazado
- **WHEN** llega la notificación con firma válida
- **THEN** el sistema responde `200`, registra el estado real de la pasarela y la seña sigue `PENDIENTE`

#### Scenario: La metadata se toma del pago re-consultado

- **GIVEN** una notificación firmada cuyo cuerpo trae la metadata de T2 mientras el pago re-consultado en la pasarela pertenece a T1
- **WHEN** se procesa
- **THEN** el sistema acredita la seña de T1 y no usa en ningún momento la metadata del cuerpo ni de un header, porque la confianza viene de la re-consulta

#### Scenario: Una notificación que no es de pago se ignora

- **GIVEN** una notificación firmada con `type=merchant_order`
- **WHEN** se procesa
- **THEN** el sistema responde `200` sin consultar la pasarela y sin tocar ninguna seña

#### Scenario: La pasarela no responde al re-consultar

- **GIVEN** T1 con una seña `PENDIENTE` y la pasarela caída en `obtener_pago`
- **WHEN** llega una notificación firmada
- **THEN** el sistema responde `503`, no acredita y deja todo como estaba para que Mercado Pago reintente

### Requirement: Idempotencia del webhook

El sistema SHALL registrar cada pago en `PagoMP` con `mp_payment_id` único global y aplicar el
efecto una sola vez: `DUPLICADO` queda reservado al **mismo** `mp_payment_id`, un `APPROVED` de otro
pago sobre una seña ya no `PENDIENTE` SHALL registrar `PAGO_EXCEDENTE`, un monto o moneda distintos
SHALL registrar `MONTO_DISTINTO`, y ambos SHALL dejar obligación de devolución visible en
`GET /api/senas`; un `REFUNDED` SHALL registrarse con su propio resultado.

#### Scenario: Un webhook duplicado no duplica nada

- **GIVEN** T1 con una seña ya `ACREDITADA` por el pago PAG-1
- **WHEN** Mercado Pago reintenta la misma notificación de PAG-1
- **THEN** el sistema responde `200` con `resultado=DUPLICADO`, existe un solo `PagoMP` de PAG-1 y la seña sigue `ACREDITADA`

#### Scenario: Un estado no aprobado se registra sin acreditar

- **GIVEN** T1 con una seña `PENDIENTE` y un pago de PAG-2 en estado `PENDING`
- **WHEN** llega la notificación firmada de PAG-2
- **THEN** se registra el `PagoMP` con `estado=PENDING` y `resultado=IGNORADO`, y la seña sigue `PENDIENTE`

#### Scenario: Los eventos desordenados no degradan la acreditación

- **GIVEN** T1 con la seña ya `ACREDITADA` por PAG-3
- **WHEN** llega una notificación posterior de PAG-3 con estado `PENDING`
- **THEN** el `PagoMP` conserva `estado=APPROVED`, la seña sigue `ACREDITADA` y no se crea otro movimiento

#### Scenario: Un pago de monto distinto no acredita

- **GIVEN** T1 con una seña de `3000` centavos y un pago aprobado de `1000` con la misma referencia
- **WHEN** llega la notificación firmada
- **THEN** el sistema responde `200` con `resultado=MONTO_DISTINTO`, la seña queda como estaba y el pago deja una obligación de devolución visible en `GET /api/senas`

#### Scenario: Un pago en otra moneda no acredita

- **GIVEN** T1 con una seña en `ARS` y un pago aprobado en `USD`
- **WHEN** llega la notificación firmada
- **THEN** el sistema responde `200` con `resultado=MONTO_DISTINTO`, la seña no se acredita y el pago deja obligación de devolución (C11-OQ-12)

#### Scenario: Un segundo pago aprobado sobre la misma seña es excedente

- **GIVEN** T1 con una seña ya `ACREDITADA` por PAG-A
- **WHEN** llega un `APPROVED` de PAG-B, un pago **distinto**, por el mismo monto
- **THEN** el sistema responde `200` con `resultado=PAGO_EXCEDENTE`, **no** `DUPLICADO`, la seña no cambia y queda una obligación de devolución para PAG-B visible en `GET /api/senas`

#### Scenario: Un reembolso de MP cierra la obligación

- **GIVEN** T1 con una seña `ACREDITADA` y su pago PAG-C
- **WHEN** llega una notificación firmada de PAG-C en estado `REFUNDED`
- **THEN** el sistema responde `200` con `resultado=REEMBOLSADO`, la seña queda `DEVUELTA` con `motivo_devolucion=REEMBOLSO_MP` y `devuelta_por=null`, y la obligación deja de estar pendiente

#### Scenario: Un reembolso sobre una seña aplicada pide ajuste de caja

- **GIVEN** T1 con una seña `APLICADA` y su pago PAG-D
- **WHEN** llega una notificación firmada de PAG-D en estado `REFUNDED`
- **THEN** la seña sigue `APLICADA`, el pago se registra con `resultado=REEMBOLSO_AJUSTE_CAJA` y queda un ajuste de caja pendiente de `ADMIN` visible en `GET /api/senas`

#### Scenario: Un pago que no se puede asociar no se descarta

- **GIVEN** una notificación firmada cuyo `mp_payment_id` no resuelve a ninguna seña del tenant de la metadata
- **WHEN** se procesa
- **THEN** el sistema responde `500` sin persistir nada, deja un log estructurado con ids y motivo (sin fila de auditoría, porque no hay entidad ni actor) y Mercado Pago reintenta

### Requirement: Acreditación y confirmación del turno

Al procesar un pago aprobado con monto y moneda correctos sobre una seña `PENDIENTE` cuyo turno
está `PENDIENTE`, el sistema SHALL dejar la seña `ACREDITADA`, el turno `CONFIRMADO` y auditar
ambos hechos en una sola transacción; si el turno está `CANCELADO` o `REPROGRAMADO` SHALL dejar la
seña `DEVUELTA` sin confirmar nada.

#### Scenario: El pago acredita la seña y confirma el turno

- **GIVEN** T1 con la seña `PENDIENTE` de `3000` y su turno `PENDIENTE`
- **WHEN** se procesa el pago aprobado de `3000` en `ARS`
- **THEN** la seña queda `ACREDITADA` con `acreditada_en`, el turno queda `CONFIRMADO` y la auditoría registra `SENA_ACREDITADA` con el `mp_payment_id`

#### Scenario: Un pago sobre un turno cancelado se devuelve

- **GIVEN** T1 con la seña `PENDIENTE` de un turno ya `CANCELADO`
- **WHEN** se procesa el pago aprobado
- **THEN** la seña queda `DEVUELTA` con `motivo_devolucion` y `resultado=TURNO_NO_CONFIRMABLE`, el turno sigue `CANCELADO` y no se reabre el hueco

#### Scenario: Dos webhooks simultáneos acreditan una sola vez

- **GIVEN** T1 con una seña `PENDIENTE` y dos conexiones independientes a PostgreSQL
- **WHEN** ambas procesan el mismo pago aprobado a la vez
- **THEN** una acredita y la otra responde `200` con `DUPLICADO`, existe un solo `PagoMP`, la seña está `ACREDITADA` y el turno tiene una sola confirmación

### Requirement: Expiración y liberación del turno

El sistema SHALL liberar toda seña `PENDIENTE` **del tenant** con `expira_at <= ahora`: `LIBERADA` con
motivo `EXPIRACION`, turno `CANCELADO` con motivo `SENA_NO_ACREDITADA` y emisión del hueco a C-07 en
**una sola transacción**; el worker SHALL usar reloj inyectado, ser idempotente, SHALL NOT liberar
una seña no vencida y SHALL hacer rollback completo si la emisión falla.

#### Scenario: La seña vencida libera el turno y dispara la auto-oferta

- **GIVEN** el reloj en `2026-11-14T09:00:00-03:00`, T1 con una seña `PENDIENTE` con `expira_at=2026-11-14T09:00:00-03:00` y su turno `PENDIENTE`
- **WHEN** el worker procesa las expiraciones
- **THEN** la seña queda `LIBERADA` con `motivo_liberacion=EXPIRACION`, el turno queda `CANCELADO` con motivo `SENA_NO_ACREDITADA` y se emitió el hueco liberado a C-07

#### Scenario: Una seña vigente no se libera

- **GIVEN** el reloj en `2026-11-13T09:00:00-03:00` y una seña `PENDIENTE` con `expira_at=2026-11-14T09:00:00-03:00`
- **WHEN** el worker procesa las expiraciones
- **THEN** la seña sigue `PENDIENTE` y el turno sigue `PENDIENTE`

#### Scenario: Una segunda corrida no duplica la liberación

- **GIVEN** T1 con una seña ya `LIBERADA` por expiración
- **WHEN** el worker corre otra vez con el mismo reloj
- **THEN** no hay una segunda transición, no se emite un segundo evento de hueco liberado y no hay error

#### Scenario: Un turno ya cancelado no impide liberar la seña

- **GIVEN** T1 con una seña `PENDIENTE` vencida cuyo turno ya está `CANCELADO` por otro canal
- **WHEN** el worker procesa las expiraciones
- **THEN** la seña queda `LIBERADA`, el turno no cambia y no se emite un segundo evento de hueco

#### Scenario: Un pago tardío no reabre el turno

- **GIVEN** T1 con una seña `LIBERADA` por expiración y el hueco ya ofertado a lista de espera
- **WHEN** llega un pago aprobado después de la liberación
- **THEN** la seña queda `DEVUELTA` con `resultado=FUERA_DE_TIEMPO`, el turno sigue `CANCELADO` y el hueco sigue retenido por la oferta (C11-OQ-07)

#### Scenario: Si falla la emisión del hueco no se libera nada

- **GIVEN** T1 con una seña `PENDIENTE` vencida y el puerto de hueco liberado devolviendo error
- **WHEN** el worker procesa las expiraciones
- **THEN** no queda ninguna escritura parcial: la seña sigue `PENDIENTE`, el turno sigue `PENDIENTE` y el próximo barrido la vuelve a tomar

#### Scenario: El barrido de un tenant no toca las señas de otro

- **GIVEN** T1 y T2, cada uno con una seña `PENDIENTE` vencida
- **WHEN** el worker procesa las expiraciones de T1
- **THEN** sólo se libera la seña de T1; la de T2 sigue `PENDIENTE`, su turno no se cancela y no se emite ningún hueco en T2

### Requirement: Carrera entre acreditación y expiración

La acreditación y la expiración SHALL serializarse sobre la fila de la seña con transiciones
condicionales; SHALL ganar la primera transacción que commitea y la perdedora SHALL NOT escribir ni
responder `500`.

#### Scenario: La acreditación gana la carrera

- **GIVEN** T1 con una seña `PENDIENTE` vencida y dos conexiones independientes a PostgreSQL, una acreditando y otra expirando a la vez, con la acreditación commiteada primero
- **WHEN** ambas terminan
- **THEN** la seña queda `ACREDITADA`, el turno `CONFIRMADO`, el worker no la libera y no se emite auto-oferta

#### Scenario: La expiración gana la carrera

- **GIVEN** la misma situación con la expiración commiteada primero
- **WHEN** ambas terminan
- **THEN** tras la expiración la seña queda `LIBERADA` y el turno `CANCELADO`; cuando llega el pago tardío la seña pasa a `DEVUELTA` (la plata no puede quedar retenida) y el webhook responde `200` con `resultado=FUERA_DE_TIEMPO`, nunca `DUPLICADO` y nunca `500`, sin emitir un segundo evento de hueco

#### Scenario: El perdedor no pisa el estado del ganador

- **GIVEN** la carrera anterior resuelta por cualquiera de los dos lados
- **WHEN** se inspecciona la seña
- **THEN** su estado es exactamente uno de `ACREDITADA`/`LIBERADA`, tiene un solo instante de la transición ganadora y ninguna notificación escrita después la modifica

### Requirement: Aplicación de la seña al cobro

`POST /api/senas/{id}/aplicar` SHALL, sólo desde `ACREDITADA`, con el día de la aplicación abierto y
sin presupuesto aceptado vigente, crear el `INGRESO` `medio=MP` vía C-10 con `fecha` del día de la
aplicación y persistir `movimiento_caja_id`; un segundo aplicado SHALL responder `409` sin crear
movimientos, el día cerrado y el presupuesto vigente SHALL responder `409`, y
`concepto=CANCELACION_TARDIA` SHALL exigir `ADMIN`.

#### Scenario: Aplicar crea un movimiento MP del turno

- **GIVEN** T1 con una seña `ACREDITADA` de `3000` del turno TUR-1, el usuario U1 de recepción y el día abierto
- **WHEN** U1 aplica la seña
- **THEN** se crea un `INGRESO` de `3000` con `medio=MP` y `turno_id=TUR-1`, la seña queda `APLICADA` con `movimiento_caja_id` y `concepto_aplicacion=TRATAMIENTO`

#### Scenario: Un segundo aplicado no crea otro movimiento

- **GIVEN** T1 con una seña ya `APLICADA`
- **WHEN** se intenta aplicarla otra vez
- **THEN** el sistema responde `409 SENA_YA_APLICADA` y sigue habiendo un solo movimiento `MP` para esa seña

#### Scenario: Con el día cerrado la seña no se aplica

- **GIVEN** T1 con una seña `ACREDITADA` y el día de la aplicación cerrado en caja
- **WHEN** se intenta aplicar la seña
- **THEN** el sistema responde `409 CIERRE_CERRADO`, no se crea ningún movimiento y la seña sigue `ACREDITADA`

#### Scenario: El ingreso usa el día de la aplicación

- **GIVEN** T1 con una seña `ACREDITADA` el `2026-11-10` que se aplica el `2026-11-13` a las `15:00:00-03:00`
- **WHEN** se aplica la seña
- **THEN** el `INGRESO` queda con `fecha=2026-11-13` (el día de la aplicación, no el de la acreditación ni el del turno) y aparece en la caja de ese día

#### Scenario: Un presupuesto aceptado vigente bloquea aplicar

- **GIVEN** T1 con una seña `ACREDITADA` de un paciente que tiene un presupuesto `ACEPTADO` vigente en C-09
- **WHEN** se intenta aplicar la seña
- **THEN** el sistema responde `409 PRESUPUESTO_CON_SENA`, no crea ningún movimiento y la seña sigue `ACREDITADA` (C11-OQ-13)

#### Scenario: Una seña pendiente no se aplica

- **GIVEN** T1 con una seña `PENDIENTE`
- **WHEN** se intenta aplicarla
- **THEN** el sistema responde `409 ESTADO_INVALIDO` y no crea ningún movimiento

#### Scenario: La seña de un turno cancelado sólo la aplica ADMIN como cancelación tardía

- **GIVEN** T1 con una seña `ACREDITADA` de un turno `CANCELADO` y los usuarios U1 (RECEPCION) y U2 (ADMIN)
- **WHEN** U1 intenta aplicarla con `concepto=CANCELACION_TARDIA` y luego U2 la aplica con ese concepto
- **THEN** U1 recibe `403` sin movimiento, U2 recibe `200`, la seña queda `APLICADA` con `concepto_aplicacion=CANCELACION_TARDIA` y se crea el `INGRESO` `MP` del turno (C11-OQ-03)

#### Scenario: El movimiento entra en los totales del día

- **GIVEN** T1 con una seña `ACREDITADA` aplicada el `2026-11-13`
- **WHEN** se consultan los movimientos de caja del `2026-11-13`
- **THEN** el movimiento aparece con `medio=MP` y suma en `totales_vigentes.mp` según el contrato de C-10

### Requirement: Devolución de la seña

Una cancelación con anticipación mayor o igual al `anticipacion_cancelacion_h` **snapshot** de la
seña SHALL dejarla `DEVUELTA` con `motivo_devolucion='POLITICA_CANCELACION'` y sin actor;
`POST /api/senas/{id}/devolver` SHALL exigir `ADMIN` y motivo no vacío, registrar la obligación de
reintegro **manual** (sin API de reembolsos), no devolver una seña `APLICADA` y responder `409` en
una segunda devolución.

#### Scenario: Cancelar con anticipación deja la seña a devolver

- **GIVEN** el reloj en `2026-11-20T09:00:00-03:00`, T1 con una seña `ACREDITADA` de un turno del `2026-11-22T09:00:00-03:00` y `anticipacion_cancelacion_h=24`
- **WHEN** el paciente cancela con su token y una verificación válida
- **THEN** el turno queda `CANCELADO`, la seña queda `DEVUELTA` con `motivo_devolucion=POLITICA_CANCELACION` y `devuelta_por=null`

#### Scenario: La elegibilidad usa el snapshot y no la configuración actual

- **GIVEN** T1 con una seña creada con `anticipacion_cancelacion_h=48`, la configuración del tenant cambiada hoy a `12` y un turno a 24 h del reloj
- **WHEN** el paciente cancela
- **THEN** C-06 autoriza y C-11 devuelve la seña usando el snapshot `48`, no el valor configurado `12`, y la seña queda `DEVUELTA`

#### Scenario: Cancelar bajo el umbral no devuelve sola

- **GIVEN** el reloj en `2026-11-21T20:00:00-03:00` y un turno del `2026-11-22T09:00:00-03:00` con seña `ACREDITADA`
- **WHEN** el paciente intenta cancelar por el link público
- **THEN** el sistema responde `403` como hoy, el turno sigue `PENDIENTE` o `CONFIRMADO` y la seña sigue `ACREDITADA` hasta que `ADMIN` decida (C11-OQ-03)

#### Scenario: ADMIN devuelve con motivo

- **GIVEN** T1 con una seña `ACREDITADA`, el usuario U2 de ADMIN y el turno cancelado
- **WHEN** U2 devuelve la seña con `motivo="cancelación con aviso"`
- **THEN** la seña queda `DEVUELTA` con `devuelta_por=U2`, `devuelta_en` y el motivo, y la auditoría registra `SENA_DEVUELTA`

#### Scenario: La devolución queda como obligación manual visible

- **GIVEN** T1 con una seña `DEVUELTA` por devolución manual
- **WHEN** un usuario interno consulta `GET /api/senas`
- **THEN** la seña aparece como obligación de reintegro pendiente, no se llama a ninguna API de reembolsos de Mercado Pago y no se borra ninguna fila (C11-OQ-09)

#### Scenario: Recepción no puede devolver

- **GIVEN** T1 con una seña `ACREDITADA` y el usuario U1 de recepción
- **WHEN** U1 intenta devolverla
- **THEN** el sistema responde `403` y la seña sigue `ACREDITADA`

#### Scenario: Devolver sin motivo se rechaza

- **GIVEN** T1 con una seña `ACREDITADA` y el usuario U2 de ADMIN
- **WHEN** U2 devuelve sin `motivo` o con `motivo=""`
- **THEN** el sistema responde `422` y la seña sigue `ACREDITADA`

#### Scenario: Una seña aplicada no se devuelve

- **GIVEN** T1 con una seña `APLICADA` y el usuario U2 de ADMIN
- **WHEN** U2 intenta devolverla
- **THEN** el sistema responde `409` y la seña sigue `APLICADA`, porque después del cobro la corrección es una anulación de caja

### Requirement: Política de cancelación visible

La respuesta de reserva con seña y la consulta pública de la seña SHALL exponer
`politica={anticipacion_cancelacion_h, reembolsable, hay_pago_acreditado}`: la anticipación del
**snapshot**, `reembolsable=true` **desde la creación** (la promesa, independiente del estado) y
`hay_pago_acreditado` sólo si hoy hay plata retenida (`ACREDITADA`), sin texto inventado ni datos
personales.

#### Scenario: La reserva informa la política antes de pagar

- **GIVEN** T1 con `CANCEL_ANTICIPACION_H=24` y una reserva con seña recién creada en estado `PENDIENTE`
- **WHEN** la reserva responde `201`
- **THEN** el bloque `sena` incluye `politica={anticipacion_cancelacion_h: 24, reembolsable: true, hay_pago_acreditado: false}`

#### Scenario: La promesa de devolución no depende de que haya plata

- **GIVEN** T1 con una seña `PENDIENTE`, una `LIBERADA` y una `DEVUELTA`
- **WHEN** se consulta cada una por su token
- **THEN** `politica.reembolsable` es `true` en los tres casos, porque es la promesa de la política y no el estado de la seña

#### Scenario: Con plata retenida el hecho queda visible

- **GIVEN** T1 con una seña `ACREDITADA` de un turno a más de 24 h
- **WHEN** se consulta la seña por su token
- **THEN** `politica.hay_pago_acreditado` es `true`, `politica.reembolsable` sigue `true` y `anticipacion_cancelacion_h` es el snapshot de la seña

#### Scenario: Una seña aplicada ya no tiene plata retenida

- **GIVEN** T1 con una seña `APLICADA`
- **WHEN** se consulta la seña por su token
- **THEN** `politica.hay_pago_acreditado` es `false`, porque la plata ya está en caja y corregirla es una anulación de C-10

#### Scenario: La política no filtra datos del paciente

- **GIVEN** T1 con una seña de "Paciente Demo"
- **WHEN** se lee la política en la respuesta pública
- **THEN** no aparece nombre, teléfono, DNI ni `paciente_id`

### Requirement: Reprogramación con seña

Con anticipación suficiente, la reprogramación SHALL transferir la seña al turno nuevo,
recalcular `expira_at = min(ahora + SENA_TTL_H, nuevo.inicio)` si estaba `PENDIENTE`, conservar el
mismo token si no venció y reemitirlo si venció; una seña `APLICADA` o `DEVUELTA` SHALL NOT
transferirse ni exigir una segunda (C11-OQ-04).

#### Scenario: La seña pendiente acompaña al turno nuevo

- **GIVEN** el reloj en `2026-11-20T09:00:00-03:00`, T1 con una seña `PENDIENTE` con `expira_at=2026-11-21T09:00:00-03:00` y una reprogramación al `2026-11-25T10:00:00-03:00`
- **WHEN** el paciente reprograma con anticipación suficiente
- **THEN** la seña apunta al turno nuevo, `expira_at=2026-11-21T09:00:00-03:00` (el TTL ya vencía antes), el token es el mismo y no se crea una segunda seña (C11-OQ-04)

#### Scenario: La seña acreditada se transfiere sin cambiar de estado

- **GIVEN** T1 con una seña `ACREDITADA` y una reprogramación válida
- **WHEN** se reprograma
- **THEN** la seña queda `ACREDITADA` apuntando al turno nuevo, el turno nuevo no exige otra seña y la auditoría registra `SENA_TRANSFERIDA` (C11-OQ-04)

#### Scenario: Un token vencido se reemite al reprogramar

- **GIVEN** T1 con una seña `PENDIENTE` cuyo token venció y una reprogramación con anticipación suficiente
- **WHEN** se reprograma
- **THEN** la seña apunta al turno nuevo con `expira_at` recalculado, el token anterior responde `404`, se entrega un token nuevo y la auditoría registra `SENA_TRANSFERIDA` con `token_reemitido=true`

#### Scenario: Una seña aplicada no se transfiere

- **GIVEN** T1 con una seña `APLICADA`
- **WHEN** se reprograma el turno
- **THEN** la seña no cambia de turno, el turno nuevo no crea otra seña y la auditoría registra `SENA_NO_TRANSFERIDA`

#### Scenario: El webhook usa el turno vigente de la seña

- **GIVEN** T1 con una reprogramación y una acreditación simultáneas y dos conexiones a PostgreSQL
- **WHEN** ambas terminan
- **THEN** la seña queda apuntando al turno nuevo y el turno confirmado es ese, nunca el original

### Requirement: Aislamiento multi-tenant de señas y pagos

Toda operación sobre señas y pagos SHALL acotarse al `tenant_id`; una seña, un pago o un turno de
otro tenant SHALL responder `404` sin revelar su existencia, y el webhook SHALL resolver el tenant
sólo desde el pago re-consultado en Mercado Pago (no desde el cuerpo ni de un header).

#### Scenario: Una seña de T1 no se lee desde T2

- **GIVEN** T1 con una seña y T2 con un usuario interno
- **WHEN** un actor de T2 pide la seña por id
- **THEN** el sistema responde `404` y no devuelve ningún dato de T1

#### Scenario: Aplicar desde otro tenant falla

- **GIVEN** T2 y una seña `ACREDITADA` de T1
- **WHEN** un usuario de T2 intenta aplicarla
- **THEN** el sistema responde `404` y no se crea ningún movimiento en T2

#### Scenario: Devolver desde otro tenant falla

- **GIVEN** T2 con un usuario `ADMIN` y una seña `ACREDITADA` de T1
- **WHEN** el usuario de T2 llama a `POST /api/senas/{id}/devolver` con la seña de T1
- **THEN** el sistema responde `404`, la seña de T1 sigue `ACREDITADA` y no queda ninguna obligación de reintegro en T2

#### Scenario: El webhook no cruza tenants

- **GIVEN** una notificación firmada con metadata de T2 y un `sena_id` de T1
- **WHEN** se procesa
- **THEN** el sistema no acredita ninguna seña, responde `500` y registra el hecho sólo con ids

#### Scenario: El listado no mezcla tenants

- **GIVEN** T1 con dos señas y T2 con una en el mismo rango de fechas
- **WHEN** un actor de T1 pide `GET /api/senas?desde=&hasta=`
- **THEN** devuelve sólo las dos de T1

### Requirement: Visibilidad de la seña en agenda

`GET /api/senas?desde=&hasta=` SHALL devolver las señas del tenant con `turno_id`, `turno.inicio` y
`estado`, filtrando por **`turno.inicio`** en el rango `[desde, hasta)`, SHALL exigir
`ODONTOLOGO`, `RECEPCION` o `ADMIN` y SHALL NOT cambiar el payload de `GET /api/turnos`
(C11-OQ-10).

#### Scenario: El filtro es por inicio del turno

- **GIVEN** T1 con una seña creada el `2026-11-01` para un turno del `2026-11-20` y otra para un turno del `2026-12-01`
- **WHEN** se pide `GET /api/senas?desde=2026-11-15&hasta=2026-11-30`
- **THEN** devuelve sólo la seña del turno del `2026-11-20`, porque el rango se aplica sobre `turno.inicio` y no sobre la fecha de creación ni `expira_at` (C11-OQ-10)

#### Scenario: La agenda no cambia de contrato

- **GIVEN** T1 con turnos que tienen seña
- **WHEN** se pide `GET /api/turnos` como antes de C-11
- **THEN** el payload es el mismo de C-05 y la seña se obtiene por `GET /api/senas`, uniendo por `turno_id`

### Requirement: RBAC de señas

`ODONTOLOGO` SHALL sólo leer señas; `RECEPCION` y `ADMIN` SHALL aplicar, pero
`concepto=CANCELACION_TARDIA` SHALL exigir `ADMIN`; sólo `ADMIN` SHALL devolver; un rol sin permiso
SHALL recibir `403` y una petición con identidad de paciente SHALL recibir `401` en las rutas
internas.

#### Scenario: El odontólogo lee pero no aplica

- **GIVEN** T1 con una seña `ACREDITADA` y el odontólogo U3
- **WHEN** U3 consulta la seña y luego intenta aplicarla
- **THEN** la consulta responde `200` y la aplicación responde `403` sin crear movimientos

#### Scenario: Recepción aplica pero no devuelve

- **GIVEN** T1 con una seña `ACREDITADA` y el usuario U1 de recepción
- **WHEN** U1 aplica la seña y luego intenta devolverla
- **THEN** la aplicación responde `200` y la devolución responde `403`

#### Scenario: ADMIN aplica y devuelve

- **GIVEN** T1 con dos señas `ACREDITADAS` y el usuario U2 de ADMIN
- **WHEN** U2 aplica una y devuelve la otra con motivo
- **THEN** la primera queda `APLICADA` y la segunda `DEVUELTA`, ambas auditadas con actor U2

#### Scenario: Recepción no aplica una cancelación tardía

- **GIVEN** T1 con una seña `ACREDITADA` de un turno cancelado bajo el umbral y el usuario U1 de recepción
- **WHEN** U1 intenta aplicarla con `concepto=CANCELACION_TARDIA`
- **THEN** el sistema responde `403` sin crear ningún movimiento y la seña sigue `ACREDITADA`

#### Scenario: El paciente no tiene acceso a las rutas internas

- **GIVEN** T1 con señas y una petición con identidad de paciente
- **WHEN** se intenta listar, aplicar o devolver
- **THEN** el sistema responde `401` y no expone ni modifica nada

### Requirement: Migración 009 con RLS, CHECKs y backfill

La migración 009 SHALL crear `senas` y `pagos_mp` con `tenant_id NOT NULL`, RLS forzada
fail-closed, CHECKs de estado, UNIQUE `(tenant_id, turno_id)` y UNIQUE **globales** de
`mp_payment_id` y `token_hash`, y SHALL agregar `prestaciones.sena_modo`/`sena_valor` con backfill
conservador, de forma reversible y sin tocar 001–008.

#### Scenario: La base llega a head con las tablas de señas

- **GIVEN** una base con las revisiones 001–008 aplicadas
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existen `senas` y `pagos_mp` con RLS forzada, `prestaciones` tiene `sena_modo`/`sena_valor` y la versión vigente es 009

#### Scenario: El downgrade elimina sólo la 009

- **GIVEN** una base en la revisión 009
- **WHEN** se ejecuta `alembic downgrade 008_caja_cierre_diario`
- **THEN** las dos tablas y las columnas nuevas desaparecen, `requiere_sena`/`monto_sena` siguen intactas y 001–008 quedan re-upgradeables

#### Scenario: Sin tenant la RLS devuelve cero filas

- **GIVEN** la base en 009 con señas de T1 y el rol de aplicación sin `app.tenant_id` o con cadena vacía
- **WHEN** se consulta cualquiera de las dos tablas
- **THEN** la consulta devuelve 0 filas sin lanzar el error `42704`

#### Scenario: La base rechaza estados inválidos

- **GIVEN** la base en 009
- **WHEN** se intenta insertar una seña con `estado='PAGADA'`, con `monto_centavos=0`, con `estado='DEVUELTA'` sin motivo o con `estado='APLICADA'` sin movimiento
- **THEN** la base rechaza la fila por el CHECK correspondiente

#### Scenario: La idempotencia y la unicidad son de base

- **GIVEN** la base en 009 con una seña del turno TUR-1 de T1 y un `PagoMP` de `PAG-1`
- **WHEN** se intenta insertar otra seña de TUR-1, otro `PagoMP` de `PAG-1` o otra seña con el mismo `token_hash`
- **THEN** la base rechaza la segunda seña de TUR-1 sólo en el mismo tenant, y rechaza `mp_payment_id` y `token_hash` repetidos **en cualquier tenant**, porque esos dos UNIQUE son globales (RN-SE-03)

#### Scenario: Un pago homónimo en otro tenant se acepta, el mismo pago no

- **GIVEN** la base en 009 con el `PagoMP` `PAG-1` de T1 y una seña de T2 cuyo turno también se llama TUR-1
- **WHEN** T2 registra una seña nueva de su propio TUR-1 con otro `mp_payment_id` y otro `token_hash`
- **THEN** la seña se acepta, pero un `PagoMP` de T2 con `mp_payment_id=PAG-1` o una seña de T2 con el `token_hash` de T1 se rechazan por el UNIQUE global

#### Scenario: El backfill legacy es conservador

- **GIVEN** una base en 008 con tres prestaciones: una con `requiere_sena=true` y `monto_sena=5000`, una con `requiere_sena=true` y `monto_sena=null`, y una con `requiere_sena=false`
- **WHEN** se aplica la 009
- **THEN** la primera queda `sena_modo='MONTO_FIJO'`/`sena_valor=5000`, la segunda queda en `NULL` (hereda) y reportada para revisión, y la tercera queda en `NULL` sin inventar monto ni modo

### Requirement: Auditoría y ausencia de PHI en señas

Toda mutación de una seña SHALL dejar auditoría append-only con actor, antes/después e ids, y el
sistema SHALL NOT persistir ni loguear nombre, DNI, teléfono, email del pagador ni el link de pago;
`raw_json` SHALL ser un subconjunto allow-list del pago.

#### Scenario: Cada transición deja su auditoría

- **GIVEN** T1 con una seña que se crea, se acredita y se aplica
- **WHEN** se consulta la auditoría del tenant
- **THEN** existen `SENA_CREADA`, `SENA_ACREDITADA` y `SENA_APLICADA` con `sena_id`, monto, actor y `antes`/`después`

#### Scenario: El webhook rechazado no copia el cuerpo

- **GIVEN** una notificación con firma inválida
- **WHEN** se procesa y se rechaza
- **THEN** el rechazo queda en el log estructurado con el `mp_payment_id` y el motivo de dominio, sin fila de auditoría porque la firma se verifica antes de resolver el tenant y no se inventa uno, y no copia el cuerpo recibido ni datos del pagador

#### Scenario: El pago guardado está minimizado

- **GIVEN** un pago aprobado con datos del pagador en la respuesta de Mercado Pago
- **WHEN** se persiste el `PagoMP`
- **THEN** `raw_json` contiene sólo id, estado, detalle de estado, monto, moneda, fecha de aprobación, referencia y metadata de seña/turno/tenant, sin email, nombre ni datos de tarjeta

#### Scenario: Un error de seña no vuelca PHI

- **GIVEN** una seña de "Paciente Demo" con teléfono `+5491100000000`
- **WHEN** se produce un error de dominio al aplicarla
- **THEN** la respuesta y el log incluyen sólo código, `sena_id`, `tenant_id` y monto, sin nombre, teléfono ni DNI

#### Scenario: El schema rechaza campos extra

- **GIVEN** un payload que incluye `tenant_id`, `paciente_nombre` o `monto_centavos` en una ruta donde no corresponde
- **WHEN** se envía a la API
- **THEN** el sistema responde `422` y no procesa la operación
