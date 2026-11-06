# Spec Delta — odontograma

## Purpose

Registrar hallazgos odontológicos por pieza en notación FDI con historial por pieza, conservarlos como hecho clínico inmutable y derivarlos en un clic a una línea de presupuesto, siempre dentro del tenant y con consentimiento previo.

## ADDED Requirements

### Requirement: Registro de hallazgo FDI por pieza

El sistema SHALL registrar un hallazgo clínico con `pieza_fdi`, `superficie?`, `hallazgo`, `fecha` y `profesional` para un paciente del tenant, aceptando sólo posiciones FDI válidas de la dentición permanente (cuadrantes 1–4 × dientes 1–8); `19/29/39`, cualquier posición fuera de la grilla o un valor no entero SHALL rechazarse con `422` y mensaje explícito, sin persistir el hallazgo.

#### Scenario: Hallazgo válido en una pieza de la grilla FDI

- **GIVEN** el tenant T1 con el paciente PACI-1, consentimiento firmado y el profesional P1
- **WHEN** P1 registra un hallazgo de PACI-1 con `pieza_fdi=36`, `superficie="O"`, `hallazgo="caries oclusal"` y `fecha=2026-11-10T10:00:00-03:00`
- **THEN** se persiste el hallazgo de T1 con `pieza_fdi=36`, `superficie="O"`, `profesional_id=P1` y `resuelto=false`

#### Scenario: Las 32 posiciones de la grilla FDI se aceptan

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se registra un hallazgo para cada posición válida (`11–18`, `21–28`, `31–38`, `41–48`)
- **THEN** las 32 posiciones se persisten y ninguna es rechazada

#### Scenario: FDI con diente inexistente (x9) se rechaza

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se registra un hallazgo con `pieza_fdi=19`, `pieza_fdi=29` o `pieza_fdi=39`
- **THEN** el sistema responde `422` con el mensaje "pieza FDI inválida: cuadrante 1–4 y diente 1–8" y no persiste ningún hallazgo para PACI-1

#### Scenario: FDI fuera de la grilla se rechaza

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se registra un hallazgo con `pieza_fdi=10`, `pieza_fdi=49` o `pieza_fdi=00`
- **THEN** el sistema responde `422` con el mensaje de FDI inválida y no persiste ningún hallazgo para PACI-1

#### Scenario: FDI no numérica se rechaza

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se registra un hallazgo con `pieza_fdi="36a"` o con un valor no entero
- **THEN** el sistema responde `422` y no persiste ningún hallazgo para PACI-1

#### Scenario: Hallazgo sobre paciente de otro tenant se rechaza

- **GIVEN** el tenant T1 y un paciente PACI-9 que pertenece al tenant T2
- **WHEN** un rol clínico de T1 registra un hallazgo de PACI-9 en T1
- **THEN** el sistema responde `404` y no crea el hallazgo en T1

#### Scenario: Fecha sin zona horaria se rechaza

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se registra un hallazgo con `fecha="2026-11-10T10:00:00"` (sin offset)
- **THEN** el sistema responde `422` y no persiste el hallazgo

### Requirement: Superficie opcional no vacía

El sistema SHALL aceptar `superficie` ausente o `NULL` y, cuando venga informada, SHALL exigir un texto no vacío; una superficie vacía SHALL rechazarse con `422` sin persistir el hallazgo.

#### Scenario: Hallazgo sin superficie

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se registra un hallazgo con `pieza_fdi=11` y sin `superficie`
- **THEN** el hallazgo se persiste con `superficie=NULL`

#### Scenario: Superficie vacía se rechaza

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se registra un hallazgo con `superficie=""`
- **THEN** el sistema responde `422` y no persiste el hallazgo

### Requirement: Historial de hallazgos por pieza

El sistema SHALL exponer el historial de hallazgos de un paciente agrupable por `pieza_fdi`, ordenado por `fecha`, incluyendo hallazgos resueltos y no resueltos; la consulta de una pieza SHALL NOT mezclar hallazgos de otras piezas.

#### Scenario: Varios hallazgos de la misma pieza se listan en orden

- **GIVEN** T1 con PACI-1 y dos hallazgos de la pieza 36 con `fecha=2026-11-01T10:00:00-03:00` y `fecha=2026-11-10T10:00:00-03:00`
- **WHEN** se consulta el historial de PACI-1 para `pieza_fdi=36`
- **THEN** el sistema devuelve ambos hallazgos ordenados por `fecha` ascendente, sin alterar ninguno

#### Scenario: Una pieza sin hallazgos devuelve historial vacío

- **GIVEN** T1 con PACI-1 que sólo tiene hallazgos en la pieza 36
- **WHEN** se consulta el historial de PACI-1 para `pieza_fdi=11`
- **THEN** el sistema responde `200` con una lista vacía

#### Scenario: El historial de una pieza no mezcla otras piezas

- **GIVEN** T1 con PACI-1 y hallazgos en las piezas 36 y 37
- **WHEN** se consulta el historial de PACI-1 para `pieza_fdi=36`
- **THEN** la respuesta contiene sólo los hallazgos de la pieza 36

### Requirement: Inmutabilidad del contenido clínico del hallazgo

El contenido clínico de un hallazgo (`pieza_fdi`, `superficie`, `hallazgo`, `fecha`, `profesional_id`) SHALL ser inmutable: SHALL NOT permitirse editarlo ni eliminar el hallazgo; una corrección SHALL registrarse como un hallazgo nuevo.

#### Scenario: Editar el texto de un hallazgo se rechaza

- **GIVEN** T1 con el hallazgo HAL-1 ya persistido
- **WHEN** se intenta modificar el `hallazgo` o la `pieza_fdi` de HAL-1
- **THEN** el sistema responde `405 Method Not Allowed` (no existe endpoint de edición) y HAL-1 permanece intacto

#### Scenario: Eliminar un hallazgo se rechaza

- **GIVEN** T1 con el hallazgo HAL-1 ya persistido
- **WHEN** se intenta eliminar HAL-1
- **THEN** el sistema responde `405 Method Not Allowed` y HAL-1 sigue presente

#### Scenario: Corregir agrega un hallazgo nuevo

- **GIVEN** T1 con el hallazgo HAL-1 de la pieza 36 con texto erróneo
- **WHEN** el profesional registra un hallazgo HAL-2 en la pieza 36 con el texto correcto
- **THEN** HAL-1 permanece intacto y HAL-2 se agrega al historial de la pieza 36

### Requirement: Resolución única de un hallazgo

El sistema SHALL permitir marcar un hallazgo como resuelto sólo una vez, pasando `resuelto` de `false` a `true`; un segundo intento sobre el mismo hallazgo SHALL responder `409` sin alterar el estado.

#### Scenario: Marcar un hallazgo como resuelto

- **GIVEN** T1 con el hallazgo HAL-1 con `resuelto=false`
- **WHEN** un rol clínico marca HAL-1 como resuelto en `POST /api/odontograma/{id}/resolver`
- **THEN** HAL-1 queda con `resuelto=true` y el historial lo sigue mostrando

#### Scenario: Resolver dos veces el mismo hallazgo se rechaza

- **GIVEN** T1 con el hallazgo HAL-1 ya con `resuelto=true`
- **WHEN** se intenta resolver HAL-1 nuevamente
- **THEN** el sistema responde `409` y HAL-1 permanece con `resuelto=true`

#### Scenario: No se puede volver un hallazgo a no resuelto

- **GIVEN** T1 con el hallazgo HAL-1 con `resuelto=true`
- **WHEN** se intenta un `PATCH`/`PUT` que ponga `resuelto=false`
- **THEN** el sistema responde `405 Method Not Allowed` (no existe endpoint de edición) y HAL-1 permanece `resuelto=true`

### Requirement: Derivación atómica de hallazgo a línea de presupuesto

El sistema SHALL registrar un hallazgo y derivarlo a una línea de presupuesto en una sola operación atómica, copiando `pieza_fdi` y vinculando `hallazgo_id`; si la línea no es válida, SHALL NOT persistir ni el hallazgo ni la línea.

#### Scenario: Derivación válida en un clic

- **GIVEN** T1 con PACI-1, consentimiento firmado, la prestación PREST-1 con `precio_base=150000` y P1 habilitado
- **WHEN** P1 registra un hallazgo de la pieza 36 derivándolo a PREST-1 sin indicar `monto`
- **THEN** se persisten el hallazgo de la pieza 36 y una línea de presupuesto con `prestacion_id=PREST-1`, `pieza_fdi=36`, `monto=150000` y `hallazgo_id` del hallazgo creado

#### Scenario: Monto explícito reemplaza al precio base

- **GIVEN** T1 con PACI-1, consentimiento firmado y la prestación PREST-1 con `precio_base=150000`
- **WHEN** P1 deriva un hallazgo indicando `monto=120000`
- **THEN** la línea se persiste con `monto=120000` (no con `precio_base`)

#### Scenario: Prestación inexistente o de otro tenant aborta la derivación

- **GIVEN** T1 con PACI-1 y consentimiento firmado, sin la prestación PREST-9 en T1
- **WHEN** P1 intenta derivar un hallazgo a PREST-9
- **THEN** el sistema responde `404` y no persiste ni el hallazgo ni la línea de presupuesto

#### Scenario: Monto negativo aborta la derivación

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** P1 deriva un hallazgo con `monto=-1`
- **THEN** el sistema responde `422`, no persiste el hallazgo y no crea la línea

### Requirement: Idempotencia de la derivación con Idempotency-Key

La derivación SHALL exigir el header `Idempotency-Key` (UUID generado por el cliente); la primera solicitud SHALL crear hallazgo + línea y responder `201`; el replay con la misma key y el mismo payload SHALL responder `200` con los mismos `hallazgo_id`/`linea_id` sin crear nada; la misma key con payload distinto SHALL responder `409`.

#### Scenario: Primera derivación con key válida crea una sola vez

- **GIVEN** T1 con PACI-1, consentimiento firmado y la key `550e8400-e29b-41d4-a716-446655440000`
- **WHEN** se deriva un hallazgo de la pieza 36 a PREST-1 con esa key
- **THEN** el sistema responde `201`, persiste un hallazgo y una línea, y devuelve `hallazgo_id` y `linea_id`

#### Scenario: Replay con la misma key y payload devuelve los mismos ids

- **GIVEN** la derivación anterior ya persistida con su key
- **WHEN** se repite exactamente el mismo POST con la misma key y el mismo payload
- **THEN** el sistema responde `200` con el mismo `hallazgo_id` y `linea_id`, y no crea un segundo hallazgo ni una segunda línea

#### Scenario: Misma key con payload distinto se rechaza

- **GIVEN** la derivación anterior ya persistida con su key
- **WHEN** se repite el POST con la misma key pero con `pieza_fdi=37` o `monto=120000`
- **THEN** el sistema responde `409`, no crea nada y la derivación original queda intacta

#### Scenario: Key ausente o inválida se rechaza

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se deriva un hallazgo sin header `Idempotency-Key` o con un valor que no es UUID
- **THEN** el sistema responde `422` y no persiste hallazgo ni línea

#### Scenario: La misma key en otro tenant es independiente

- **GIVEN** T1 y T2 con la misma key `550e8400-e29b-41d4-a716-446655440000` usada en una derivación de cada tenant
- **WHEN** se consulta la línea creada en cada tenant
- **THEN** cada tenant conserva su propia derivación y ninguna ve la del otro

### Requirement: Gate de consentimiento en la clínica del odontograma

El sistema SHALL exigir un consentimiento con `timestamp` válido para registrar hallazgos, resolverlos o derivarlos; sin consentimiento SHALL responder `409 CONSENTIMIENTO_REQUERIDO` y SHALL NOT bloquear la agenda del mismo paciente.

#### Scenario: Con consentimiento el odontograma queda habilitado

- **GIVEN** T1 con PACI-1 y un consentimiento con `timestamp=2026-11-09T09:00:00-03:00`
- **WHEN** un rol clínico registra un hallazgo de PACI-1
- **THEN** el hallazgo se persiste (`201`) sin error de consentimiento

#### Scenario: Sin consentimiento no se registra ni se deriva

- **GIVEN** T1 con PACI-1 sin consentimiento firmado
- **WHEN** un rol clínico intenta registrar un hallazgo o derivarlo a presupuesto
- **THEN** el sistema responde `409 CONSENTIMIENTO_REQUERIDO` y no persiste hallazgo ni línea

#### Scenario: Una fila de consentimiento sin timestamp válido no habilita el odontograma

- **GIVEN** T1 con PACI-1 y una fila de consentimiento con `timestamp` inválido (NULL)
- **WHEN** un rol clínico intenta registrar un hallazgo de PACI-1
- **THEN** el sistema responde `409 CONSENTIMIENTO_REQUERIDO` y no persiste el hallazgo

#### Scenario: La falta de consentimiento no bloquea la agenda

- **GIVEN** T1 con PACI-1 sin consentimiento firmado
- **WHEN** recepción crea un turno de agenda para PACI-1
- **THEN** el turno se crea (`201`) sin error de consentimiento

### Requirement: RBAC del odontograma

El sistema SHALL permitir escribir hallazgos a `ADMIN` y al `ODONTOLOGO` acotado a los pacientes que atiende, SHALL dar a `RECEPCION` sólo lectura y al `PACIENTE` lectura de su propio odontograma; un rol o alcance sin permiso SHALL recibir `403`.

#### Scenario: Odontólogo escribe el hallazgo de un paciente que atiende

- **GIVEN** T1 con el odontólogo P1 y un paciente con turno `profesional_id=P1`
- **WHEN** P1 registra un hallazgo de ese paciente
- **THEN** el hallazgo se crea (`201`)

#### Scenario: Odontólogo no escribe sobre un paciente ajeno

- **GIVEN** T1 con el odontólogo P1 y un paciente sin turno de P1
- **WHEN** P1 intenta registrar un hallazgo de ese paciente
- **THEN** el sistema responde `403` y no persiste el hallazgo

#### Scenario: Recepción sólo lee el odontograma

- **GIVEN** T1 con un usuario RECEPCION y PACI-1 con hallazgos
- **WHEN** recepción lee el odontograma de PACI-1 y luego intenta registrar un hallazgo
- **THEN** la lectura responde `200` y la escritura responde `403`

#### Scenario: Paciente lee su odontograma, no el ajeno

- **GIVEN** T1 con PACI-1 y PACI-2, ambos con hallazgos
- **WHEN** PACI-1 lee su odontograma y luego intenta leer el de PACI-2
- **THEN** el propio responde `200` y el ajeno responde `403`/`404`

#### Scenario: Paciente no escribe hallazgos

- **GIVEN** T1 con PACI-1 con consentimiento firmado
- **WHEN** PACI-1 intenta registrar un hallazgo de su propia pieza 36
- **THEN** el sistema responde `403` y no persiste el hallazgo

#### Scenario: El odontólogo no firma un hallazgo de otro profesional

- **GIVEN** T1 con los odontólogos P1 y P2, y un paciente que ambos atienden
- **WHEN** P1 registra un hallazgo con `profesional_id=P2`
- **THEN** el sistema responde `403` y no persiste el hallazgo

### Requirement: Aislamiento multi-tenant del odontograma

Toda lectura y escritura de hallazgos SHALL acotarse al `tenant_id`; un hallazgo o paciente de un tenant SHALL NOT poder leerse, mutarse ni resolverse desde otro tenant.

#### Scenario: Hallazgos de T1 no son visibles en T2

- **GIVEN** los tenants T1 y T2, con hallazgos de PACI-1 en T1
- **WHEN** un rol clínico de T2 intenta leer el odontograma de PACI-1
- **THEN** el sistema responde `404` y no expone datos de T1

#### Scenario: Resolver un hallazgo de otro tenant falla

- **GIVEN** T2 con el hallazgo HAL-1 de T1
- **WHEN** un rol clínico de T2 intenta resolver HAL-1
- **THEN** el sistema responde `404` y HAL-1 permanece sin cambios

### Requirement: UI del odontograma FDI con derivación en un clic

La interfaz SHALL mostrar las 32 piezas de la grilla FDI permanente (11–18, 21–28, 31–38, 41–48), el historial de la pieza seleccionada y una acción "derivar a presupuesto" que registre el hallazgo y muestre la línea creada; un error de dominio SHALL mostrarse sin dejar la UI en estado de éxito.

#### Scenario: Registrar un hallazgo desde la UI

- **GIVEN** la página `/odontograma` con PACI-1 y consentimiento firmado
- **WHEN** el usuario selecciona la pieza 36, escribe el hallazgo y confirma
- **THEN** la UI llama a `POST /api/odontograma` y muestra el hallazgo en el historial de la pieza 36

#### Scenario: Derivar en un clic muestra la línea y el a cargo

- **GIVEN** un hallazgo de la pieza 36 visible en la UI y PACI-1 sin obra social
- **WHEN** el usuario pulsa "derivar a presupuesto" y elige PREST-1
- **THEN** la UI muestra la línea con `monto=150000`, `cobertura_os=0` y `a_cargo_paciente=150000`

#### Scenario: FDI inválida no se muestra como hallazgo creado

- **GIVEN** la página `/odontograma` de PACI-1
- **WHEN** el usuario envía una pieza fuera de la grilla FDI (por ejemplo `19` o `49`) y el backend responde `422`
- **THEN** la UI muestra el error y el historial de la pieza no cambia

### Requirement: Auditoría del odontograma sin PHI

Toda mutación de hallazgos (registro, resolución, derivación) SHALL escribir auditoría append-only con actor, acción, `entidad_id`, `antes`/`después`, timestamp y `tenant_id`, sin el texto clínico del hallazgo ni datos personales del paciente.

#### Scenario: Registrar un hallazgo deja auditoría

- **GIVEN** T1 con PACI-1 y consentimiento firmado
- **WHEN** se registra un hallazgo válido
- **THEN** se escribe una entrada `HALLAZGO_REGISTRADO` con `tenant_id`, actor, `entidad_id`, `pieza_fdi` y fecha

#### Scenario: La auditoría no contiene el texto del hallazgo

- **GIVEN** T1 con un hallazgo cuyo texto contiene un dato clínico sensible
- **WHEN** se registra la mutación y se consulta su auditoría
- **THEN** la entrada no contiene el texto del hallazgo, ni nombre, DNI o teléfono del paciente

#### Scenario: La auditoría es append-only

- **GIVEN** una entrada de auditoría de un hallazgo
- **WHEN** se intenta un UPDATE o DELETE sobre esa entrada
- **THEN** el sistema rechaza la operación y la entrada original permanece intacta
