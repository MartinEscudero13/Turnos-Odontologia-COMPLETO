# ficha-clinica Specification

## Purpose
Registrar la ficha clínica mínima de un paciente, sus evoluciones fechadas y firmadas de forma inmutable, los adjuntos Rx/fotos y el consentimiento informado previo, todo acotado al tenant y sin exponer PHI en logs ni mensajes.

## Requirements

### Requirement: Ficha clínica 1—1 con paciente

El sistema SHALL mantener una única ficha clínica por paciente (`Ficha` 1—1) dentro del tenant, creable y legible por roles clínicos; una segunda creación para el mismo paciente SHALL ser rechazada.

#### Scenario: Crear la ficha de un paciente del tenant

- **GIVEN** el tenant T1 con el paciente PACI-1 sin ficha
- **WHEN** un rol clínico crea la ficha de PACI-1 en `POST /api/pacientes/{id}/ficha`
- **THEN** se persiste una ficha de T1 ligada 1—1 a PACI-1 (`paciente_id=PACI-1`)

#### Scenario: Una segunda ficha para el mismo paciente se rechaza

- **GIVEN** T1 con PACI-1 que ya tiene ficha
- **WHEN** un rol clínico intenta crear otra ficha para PACI-1
- **THEN** el sistema responde `409` y no crea una segunda ficha (1—1)

#### Scenario: Paciente de otro tenant no tiene ficha creable

- **GIVEN** el tenant T1 y un paciente PACI-1 que pertenece al tenant T2
- **WHEN** un rol clínico de T1 intenta crear u obtener la ficha de PACI-1 (de T2)
- **THEN** el sistema responde `404` y no crea ni lee ninguna ficha en T1

### Requirement: Registro de evolución fechada y firmada

El sistema SHALL registrar una evolución (`profesional`, `fecha`, `texto`, `firma_hash?`) para un paciente del tenant sólo si existe consentimiento firmado; la evolución SHALL quedar fechada y asociada al profesional que la registra.

#### Scenario: Evolución válida con consentimiento

- **GIVEN** T1 con PACI-1 que tiene consentimiento firmado y el profesional P1
- **WHEN** un rol clínico registra una evolución de PACI-1 con `fecha=2026-11-10T10:00:00-03:00`, texto y profesional P1
- **THEN** se persiste la evolución de T1 con `fecha=2026-11-10T10:00:00-03:00`, `texto` y `profesional_id=P1`

#### Scenario: Sin consentimiento no se registra evolución

- **GIVEN** T1 con PACI-1 sin consentimiento firmado
- **WHEN** un rol clínico intenta registrar una evolución de PACI-1
- **THEN** el sistema responde `409 CONSENTIMIENTO_REQUERIDO` y no persiste la evolución

#### Scenario: Paciente o profesional de otro tenant se rechaza

- **GIVEN** el tenant T1 y un paciente o profesional que pertenece al tenant T2
- **WHEN** un rol clínico de T1 registra una evolución referenciando a ese paciente o profesional
- **THEN** el sistema responde `404` y no crea la evolución en T1

### Requirement: Evoluciones inmutables (append-only)

Las evoluciones SHALL ser inmutables: SHALL NOT permitirse UPDATE ni DELETE sobre una evolución existente; corregir SHALL significar agregar una nueva evolución, nunca editar la original.

#### Scenario: Un UPDATE sobre una evolución se rechaza

- **GIVEN** T1 con una evolución EVO-1 ya persistida
- **WHEN** se intenta modificar el `texto` de EVO-1
- **THEN** el sistema responde `403`/`405` y EVO-1 permanece intacta

#### Scenario: Un DELETE sobre una evolución se rechaza

- **GIVEN** T1 con una evolución EVO-1 ya persistida
- **WHEN** se intenta eliminar EVO-1
- **THEN** el sistema responde `405 Method Not Allowed` (o `403`) y EVO-1 sigue presente

#### Scenario: Corregir agrega una nueva evolución, no edita la original

- **GIVEN** T1 con una evolución EVO-1 con un error en su texto
- **WHEN** un rol clínico corrige el contenido registrando una nueva evolución EVO-2
- **THEN** EVO-1 permanece intacta y EVO-2 se agrega como la evolución más reciente del paciente

### Requirement: Consentimiento informado firmado con timestamp y canal

El sistema SHALL registrar el consentimiento informado de un paciente con `timestamp` NOT NULL y `canal` (móvil) como requisito previo (RN-AU-03); una re-firma SHALL crear un nuevo registro sin editar el anterior.

#### Scenario: Registrar consentimiento con timestamp y canal móvil

- **GIVEN** T1 con PACI-1
- **WHEN** se registra el consentimiento de PACI-1 con `timestamp=2026-11-10T10:00:00-03:00` y `canal` móvil
- **THEN** se persiste un consentimiento de T1 con `timestamp=2026-11-10T10:00:00-03:00` (NOT NULL) y el `canal` indicado

#### Scenario: Re-firma crea un nuevo registro

- **GIVEN** T1 con PACI-1 que ya tiene un consentimiento firmado
- **WHEN** se registra un segundo consentimiento para PACI-1
- **THEN** se crea un nuevo registro (sin editar el primero) y el más reciente es el que cuenta

#### Scenario: Paciente de otro tenant se rechaza

- **GIVEN** el tenant T1 y un paciente PACI-1 que pertenece al tenant T2
- **WHEN** se intenta registrar el consentimiento de PACI-1 (de T2) en T1
- **THEN** el sistema responde `404` y no crea el consentimiento en T1

### Requirement: Consentimientos inmutables (append-only)

Los consentimientos SHALL ser inmutables: SHALL NOT permitirse UPDATE ni DELETE sobre un consentimiento existente; una re-firma SHALL agregar un nuevo registro, nunca editar el original (trazabilidad del acto firmado, Ley 26.529).

#### Scenario: Un UPDATE sobre un consentimiento se rechaza

- **GIVEN** T1 con un consentimiento CONS-1 ya persistido
- **WHEN** se intenta modificar el `timestamp` o `canal` de CONS-1
- **THEN** el sistema responde `403`/`405` y CONS-1 permanece intacto

#### Scenario: Un DELETE sobre un consentimiento se rechaza

- **GIVEN** T1 con un consentimiento CONS-1 ya persistido
- **WHEN** se intenta eliminar CONS-1
- **THEN** el sistema responde `405 Method Not Allowed` (o `403`) y CONS-1 sigue presente

### Requirement: Gate de consentimiento: bloquea clínica, no agenda

El sistema SHALL exigir un consentimiento con `timestamp` válido presente (no la mera existencia de fila) para habilitar clínica; sin él SHALL rechazar toda operación clínica (ficha, evoluciones, adjuntos) con `409 CONSENTIMIENTO_REQUERIDO`, y SHALL permitir la agenda (turnos) del mismo paciente sin restricción.

#### Scenario: Con consentimiento la clínica queda habilitada

- **GIVEN** T1 con PACI-1 que tiene un consentimiento con `timestamp` válido
- **WHEN** un rol clínico registra una evolución o adjunto de PACI-1
- **THEN** la operación clínica se acepta sin error de consentimiento

#### Scenario: Sin consentimiento la clínica se bloquea

- **GIVEN** T1 con PACI-1 sin consentimiento firmado
- **WHEN** un rol clínico intenta crear la ficha, una evolución o un adjunto de PACI-1
- **THEN** el sistema responde `409 CONSENTIMIENTO_REQUERIDO` en cada operación clínica

#### Scenario: Fila de consentimiento sin timestamp válido no desbloquea clínica

- **GIVEN** T1 con PACI-1 que tiene una fila de consentimiento sin `timestamp` válido (NULL o inválido)
- **WHEN** un rol clínico intenta registrar una evolución o adjunto de PACI-1
- **THEN** el sistema responde `409 CONSENTIMIENTO_REQUERIDO` y no habilita la clínica

#### Scenario: La falta de consentimiento no bloquea la agenda

- **GIVEN** T1 con PACI-1 sin consentimiento firmado
- **WHEN** recepción crea un turno de agenda para PACI-1
- **THEN** el turno se crea normalmente (`201`) sin error de consentimiento

### Requirement: Adjuntos scoped por tenant con referencia opaca

El sistema SHALL registrar adjuntos (tipo Rx/foto, referencia de almacenamiento) de la ficha del paciente del tenant (RN-CL-04); la referencia SHALL ser opaca (sin PHI) y todo adjunto SHALL estar acotado al tenant.

#### Scenario: Adjunto válido de tipo RX

- **GIVEN** T1 con la ficha FICHA-1 de PACI-1 (con consentimiento firmado)
- **WHEN** un rol clínico registra un adjunto de tipo `RX` con una referencia de almacenamiento para FICHA-1
- **THEN** se persiste el adjunto de T1 con `tipo=RX` y la referencia indicada

#### Scenario: Ficha de otro tenant se rechaza

- **GIVEN** el tenant T1 y una ficha FICHA-1 que pertenece al tenant T2
- **WHEN** un rol clínico de T1 registra un adjunto para FICHA-1 (de T2)
- **THEN** el sistema responde `404` y no crea el adjunto en T1

#### Scenario: Tipo de adjunto inválido se rechaza

- **GIVEN** T1 con la ficha FICHA-1
- **WHEN** se intenta registrar un adjunto con un `tipo` distinto de Rx/foto
- **THEN** el sistema responde `422` y no persiste el adjunto

### Requirement: Aislamiento multi-tenant de la clínica

Toda operación de ficha, evolución, adjunto y consentimiento SHALL acotarse al `tenant_id`; un recurso de un tenant SHALL NOT poder leerse ni mutarse desde otro tenant.

#### Scenario: Ficha y evoluciones de un tenant no son visibles en otro

- **GIVEN** los tenants T1 y T2, con la ficha y las evoluciones de PACI-1 en T1
- **WHEN** un rol clínico de T2 intenta leer la ficha o las evoluciones de PACI-1 (de T1)
- **THEN** el sistema responde `404` y no expone datos de T1

#### Scenario: El consentimiento de un tenant no aplica en otro

- **GIVEN** PACI-1 con consentimiento firmado en T1 y el mismo identificador usado en T2
- **WHEN** se consulta si PACI-1 tiene consentimiento en T2
- **THEN** el sistema responde que NO hay consentimiento en T2 (no hereda el de T1)

### Requirement: RBAC clínico

El sistema SHALL restringir las escrituras clínicas a roles clínicos (ADMIN, ODONTOLOGO, RECEPCION), con el odontólogo acotado a sus pacientes, recepción limitada a crear la ficha base y registrar el consentimiento, y PACIENTE sólo de lectura de su propia ficha; un rol sin permiso SHALL recibir `403`.

#### Scenario: Odontólogo escribe la evolución de un paciente que atiende

- **GIVEN** T1 con el odontólogo P1 y un paciente que P1 atiende (turno con `profesional_id=P1`)
- **WHEN** P1 registra una evolución de ese paciente
- **THEN** la evolución se crea (`201`)

#### Scenario: Odontólogo no escribe sobre un paciente ajeno

- **GIVEN** T1 con el odontólogo P1 y un paciente que P1 NO atiende
- **WHEN** P1 intenta registrar una evolución de ese paciente
- **THEN** el sistema responde `403` y no crea la evolución

#### Scenario: Recepción no registra evoluciones

- **GIVEN** T1 con un usuario RECEPCION
- **WHEN** recepción intenta registrar una evolución
- **THEN** el sistema responde `403` (recepción sólo crea ficha base y registra consentimiento)

#### Scenario: Recepción crea la ficha base y registra el consentimiento

- **GIVEN** T1 con un usuario RECEPCION autenticado y PACI-1 sin ficha ni consentimiento
- **WHEN** recepción crea la ficha base de PACI-1 y registra su consentimiento con `timestamp` válido
- **THEN** la ficha se crea (`201`) y el consentimiento se persiste con `timestamp` válido

#### Scenario: Paciente lee su propia ficha, no la ajena

- **GIVEN** T1 con PACI-1
- **WHEN** PACI-1 lee su propia ficha y luego intenta leer la ficha de PACI-2
- **THEN** la propia responde `200` y la ajena responde `403`/`404`

#### Scenario: Paciente lee su propia evolución y adjunto, no los ajenos

- **GIVEN** T1 con PACI-1 (dueño de su ficha, evolución EVO-1 y adjunto ADJ-1) y PACI-2
- **WHEN** PACI-1 lee su propia evolución EVO-1 y adjunto ADJ-1, y luego intenta leer la evolución o adjunto de PACI-2
- **THEN** las propias responden `200` y las ajenas responden `403`/`404`

### Requirement: Sin PHI en logs ni mensajes

El sistema SHALL NOT registrar PHI (nombres, teléfonos, texto de evolución) en logs ni mensajes; los schemas de respuesta SHALL usar allow-list estricto sin exponer datos clínicos ajenos.

#### Scenario: Un error de evolución no vuelca PHI en la respuesta

- **GIVEN** T1 con una evolución cuyo `texto` contiene PHI
- **WHEN** se produce un error de dominio al procesar esa evolución
- **THEN** la respuesta de error no incluye el `texto` ni otro dato clínico del paciente

#### Scenario: El schema de evolución sólo expone los campos permitidos

- **GIVEN** T1 con una evolución EVO-1
- **WHEN** se serializa EVO-1 en la respuesta
- **THEN** la respuesta incluye sólo los campos allow-list (id, profesional, fecha, …) y rechaza (`422`) campos extra como `tenant_id` o `firma_hash` ajeno

#### Scenario: Los logs de una mutación clínica sólo llevan identificadores

- **GIVEN** T1 con una mutación clínica válida (registro de evolución con texto)
- **WHEN** se escribe el log estructurado de esa mutación
- **THEN** el log contiene sólo identificadores (`tenant_id`, `paciente_id`, `ficha_id`) y NO el `texto` de la evolución ni nombre/teléfono del paciente

### Requirement: Auditoría clínica append-only sin PHI

Toda mutación clínica (ficha, evolución, adjunto, consentimiento) SHALL escribir un registro de auditoría inmutable (RN-AU-02) con actor, acción, `antes`/`después`, timestamp y `tenant_id`, sin PHI; los registros SHALL ser append-only.

#### Scenario: Mutación clínica válida escribe auditoría

- **GIVEN** T1 y una mutación clínica válida (ficha, evolución, adjunto o consentimiento)
- **WHEN** la mutación se ejecuta
- **THEN** se escribe un registro de auditoría con actor, acción, `antes`/`después`, timestamp y `tenant_id` (sin PHI)

#### Scenario: La auditoría clínica es append-only

- **GIVEN** un registro de auditoría clínica existente
- **WHEN** se intenta un UPDATE o DELETE sobre ese registro
- **THEN** el sistema rechaza la operación y el registro original permanece intacto

### Requirement: Migración 006 crea las tablas clínicas con RLS

El sistema SHALL aplicar la migración 006 creando `fichas`, `evoluciones`, `adjuntos` y `consentimientos` con `tenant_id NOT NULL`, RLS forzada y append-only para `evoluciones`/`consentimientos`, reversible sin errores.

#### Scenario: Base vacía llega a head

- **GIVEN** una base disponible con las revisiones 001–005 aplicadas
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existen `fichas`, `evoluciones`, `adjuntos` y `consentimientos` con RLS y la versión vigente es 006

#### Scenario: Downgrade elimina sólo la 006

- **GIVEN** una base en la revisión 006
- **WHEN** se ejecuta `alembic downgrade 005_lista_espera`
- **THEN** las tablas clínicas se eliminan sin afectar turnos, catálogos ni lista de espera
