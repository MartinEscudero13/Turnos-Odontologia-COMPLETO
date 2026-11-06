# Spec Delta — presupuesto

## Purpose

Convertir hallazgos odontológicos en un presupuesto por pieza con montos, cobertura de obra social y saldo a cargo del paciente, con aceptación parcial o total y con imputación únicamente de lo aceptado, dentro del tenant y sin inventar datos de cobertura.

## ADDED Requirements

### Requirement: Creación de presupuesto por paciente

El sistema SHALL crear presupuestos en estado `BORRADOR` para un paciente del tenant, con `vence_en` opcional; un paciente de otro tenant SHALL responder `404` y un presupuesto nuevo SHALL NOT tener líneas ni imputaciones.

#### Scenario: Crear un presupuesto en borrador

- **GIVEN** el tenant T1 con el paciente PACI-1
- **WHEN** recepción crea un presupuesto de PACI-1
- **THEN** se persiste un presupuesto de T1 con `estado=BORRADOR` y sin líneas

#### Scenario: Presupuesto para paciente de otro tenant se rechaza

- **GIVEN** el tenant T1 y el paciente PACI-9 del tenant T2
- **WHEN** un rol habilitado de T1 crea un presupuesto para PACI-9
- **THEN** el sistema responde `404` y no crea el presupuesto en T1

#### Scenario: Presupuesto nuevo no imputa nada

- **GIVEN** T1 con PACI-1
- **WHEN** se crea un presupuesto en `BORRADOR`
- **THEN** el puerto de imputación no recibe ninguna llamada y no existe movimiento asociado

### Requirement: Línea de presupuesto con monto, cobertura OS y saldo a cargo

El sistema SHALL calcular por línea `monto`, `cobertura_os` y `a_cargo_paciente` en centavos enteros, exigiendo `cobertura_os >= 0`, `a_cargo_paciente >= 0` y `cobertura_os + a_cargo_paciente = monto`; un monto negativo SHALL rechazarse con `422` y una `pieza_fdi` fuera de la grilla FDI permanente SHALL rechazarse con `422` sin persistir la línea.

#### Scenario: Línea con cobertura configurada

- **GIVEN** T1 con PACI-1 y la cobertura de PREST-1 al 50 % en el puerto de cobertura
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea se persiste con `cobertura_os=50000` y `a_cargo_paciente=50000`

#### Scenario: Línea con pieza FDI inválida se rechaza

- **GIVEN** T1 con un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea con `pieza_fdi=19`, `pieza_fdi=29` o `pieza_fdi=49`
- **THEN** el sistema responde `422`, no persiste la línea y el presupuesto sigue sin líneas

#### Scenario: Monto negativo se rechaza

- **GIVEN** T1 con un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea con `monto=-1`
- **THEN** el sistema responde `422`, no persiste la línea y el presupuesto sigue sin líneas

#### Scenario: Monto cero es válido y no genera deuda

- **GIVEN** T1 con PACI-1 y un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea con `monto=0` y sin cobertura
- **THEN** la línea se persiste con `cobertura_os=0` y `a_cargo_paciente=0`

#### Scenario: El invariante de la suma se rechaza en la base

- **GIVEN** una base con la migración 007 aplicada
- **WHEN** se intenta insertar una línea con `monto=100000`, `cobertura_os=60000` y `a_cargo_paciente=30000`
- **THEN** la base rechaza la fila por violar `cobertura_os + a_cargo_paciente = monto`

#### Scenario: Prestación de otro tenant no se puede presupuestar

- **GIVEN** el tenant T1 con un presupuesto en `BORRADOR` y la prestación PREST-9 del tenant T2
- **WHEN** un rol habilitado de T1 agrega una línea con `prestacion_id=PREST-9`
- **THEN** el sistema responde `404`, no persiste la línea y el presupuesto sigue sin líneas

### Requirement: Gate de consentimiento en líneas clínicas

El sistema SHALL exigir consentimiento con `timestamp` válido para agregar una línea con `pieza_fdi` o derivada de un hallazgo; sin él SHALL responder `409 CONSENTIMIENTO_REQUERIDO` y no persistir la línea. Una línea sin pieza (consulta administrativa) SHALL NOT quedar sujeta a este gate.

#### Scenario: Línea con pieza sin consentimiento se rechaza

- **GIVEN** T1 con PACI-1 sin consentimiento firmado y un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea con `pieza_fdi=36` y PREST-1
- **THEN** el sistema responde `409 CONSENTIMIENTO_REQUERIDO` y el presupuesto sigue sin líneas

#### Scenario: Línea con pieza y consentimiento válido se acepta

- **GIVEN** T1 con PACI-1 y consentimiento con `timestamp` válido
- **WHEN** se agrega una línea con `pieza_fdi=36` y PREST-1
- **THEN** la línea se persiste con `pieza_fdi=36`

#### Scenario: Línea sin pieza no exige consentimiento

- **GIVEN** T1 con PACI-1 sin consentimiento firmado y un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea de PREST-1 sin `pieza_fdi` ni `hallazgo_id`
- **THEN** la línea se persiste (`201`) sin error de consentimiento

### Requirement: Fallback de cobertura: 100 % particular visible

El sistema SHALL aplicar 100 % particular cuando el paciente no tenga obra social, el puerto de cobertura no devuelva una cobertura configurada o la configuración devuelta sea inválida, dejando `cobertura_os=0`, `a_cargo_paciente=monto` y declarando la cobertura como no validada en vivo.

#### Scenario: Paciente sin obra social paga el total

- **GIVEN** T1 con PACI-1 sin obra social y un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea de PREST-1 con `monto=150000`
- **THEN** la línea queda con `cobertura_os=0`, `a_cargo_paciente=150000`, `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`

#### Scenario: Cobertura inexistente para la prestación cae a particular

- **GIVEN** T1 con PACI-1 que tiene obra social, pero sin cobertura configurada para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=150000`
- **THEN** la línea queda con `cobertura_os=0` y `a_cargo_paciente=150000`

#### Scenario: Cobertura configurada nunca se reporta como validada en vivo

- **GIVEN** T1 con una cobertura configurada al 50 % para PREST-1
- **WHEN** se consulta el presupuesto que contiene esa línea
- **THEN** la respuesta declara `origen_cobertura=CONFIGURADA` y `validada_en_vivo=false`

### Requirement: Cobertura por porcentaje o monto, con tope como máximo

El sistema SHALL aceptar coberturas configuradas en modo `PORCENTAJE` (0–100) o `MONTO` (centavos), SHALL recortar `cobertura_os` al `tope` cuando exista y al `monto` de la línea en todos los casos, y SHALL asignar la diferencia a `a_cargo_paciente`.

#### Scenario: Cobertura por monto fijo

- **GIVEN** T1 con una cobertura en modo `MONTO` de `40000` centavos para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=40000` y `a_cargo_paciente=60000`

#### Scenario: La cobertura supera el tope

- **GIVEN** T1 con una cobertura al 80 % y `tope=50000` para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=50000` y `a_cargo_paciente=50000`

#### Scenario: La cobertura no alcanza el tope

- **GIVEN** T1 con una cobertura al 40 % y `tope=50000` para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=40000` y `a_cargo_paciente=60000`

#### Scenario: La cobertura mayor al monto se recorta al monto

- **GIVEN** T1 con una cobertura en modo `MONTO` de `200000` centavos para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=100000` y `a_cargo_paciente=0` (nunca un saldo negativo)

### Requirement: Cobertura inválida del puerto se descarta

El sistema SHALL validar la configuración devuelta por `CoberturaPort` antes de usarla; un porcentaje fuera de 0–100, un monto o tope negativo, o totales que no sumen el monto SHALL descartarse, aplicar el fallback 100 % particular, registrar auditoría y responder `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`, sin persistir nunca una línea inconsistente.

#### Scenario: Porcentaje fuera de 0–100 se descarta

- **GIVEN** T1 con una cobertura configurada al `150 %` (o `-10 %`) para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=0`, `a_cargo_paciente=100000`, `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`

#### Scenario: Monto de cobertura negativo se descarta

- **GIVEN** T1 con una cobertura en modo `MONTO` de `-50000` centavos para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=0` y `a_cargo_paciente=100000`, y la cobertura inválida no se usa

#### Scenario: Tope negativo se descarta

- **GIVEN** T1 con una cobertura al 50 % y `tope=-1` para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=0` y `a_cargo_paciente=100000`, y la cobertura inválida no se usa

#### Scenario: Totales inconsistentes se descartan antes de persistir

- **GIVEN** T1 con una cobertura que, al aplicarse, produce `cobertura_os=60000` y `a_cargo_paciente=30000` sobre `monto=100000`
- **WHEN** se agrega la línea de PREST-1
- **THEN** la cobertura se descarta, la línea se persiste con `cobertura_os=0` y `a_cargo_paciente=100000`, y nunca se guarda la combinación inconsistente

#### Scenario: La cobertura descartada deja auditoría

- **GIVEN** T1 con una cobertura inválida para PREST-1 y un paciente con obra social
- **WHEN** se agrega una línea de PREST-1
- **THEN** se escribe una entrada `COBERTURA_INVALIDA_DESCARTADA` con `prestacion_id`, `obra_social_id` y `motivo`, sin datos personales del paciente

### Requirement: Estados y vencimiento del presupuesto

El sistema SHALL manejar los estados `BORRADOR`, `VIGENTE`, `PARCIAL`, `ACEPTADO` y `VENCIDO`; SHALL exigir al menos una línea para emitir, SHALL permitir editar líneas sólo en `BORRADOR` y SHALL tratar como `VENCIDO` un presupuesto `VIGENTE` cuyo `vence_en` sea anterior al momento de la operación.

#### Scenario: Emitir un presupuesto con líneas

- **GIVEN** T1 con un presupuesto `BORRADOR` que tiene una línea
- **WHEN** se emite el presupuesto
- **THEN** pasa a `estado=VIGENTE`

#### Scenario: Emitir sin líneas se rechaza

- **GIVEN** T1 con un presupuesto `BORRADOR` sin líneas
- **WHEN** se intenta emitir el presupuesto
- **THEN** el sistema responde `409` y el presupuesto permanece en `BORRADOR`

#### Scenario: Editar líneas fuera de borrador se rechaza

- **GIVEN** T1 con un presupuesto en `VIGENTE`
- **WHEN** se intenta agregar o quitar una línea
- **THEN** el sistema responde `409` y las líneas del presupuesto no cambian

#### Scenario: Presupuesto vencido no admite aceptación

- **GIVEN** T1 con un presupuesto `VIGENTE` con `vence_en=2026-11-01T00:00:00-03:00` y una línea pendiente
- **WHEN** con `ahora=2026-11-10T10:00:00-03:00` se intenta aceptar la línea
- **THEN** el sistema responde `409`, el presupuesto se reporta `VENCIDO` y no se imputa nada

#### Scenario: Sin vencimiento el presupuesto no vence solo

- **GIVEN** T1 con un presupuesto `VIGENTE` y `vence_en=NULL`
- **WHEN** con `ahora=2026-12-31T10:00:00-03:00` se consulta el presupuesto
- **THEN** el estado sigue siendo `VIGENTE`

#### Scenario: No se acepta un presupuesto en borrador

- **GIVEN** T1 con un presupuesto `BORRADOR` con una línea
- **WHEN** se intenta aceptar esa línea
- **THEN** el sistema responde `409` y no se registra aceptación ni imputación

#### Scenario: Vencimiento sin zona horaria se rechaza

- **GIVEN** T1 con PACI-1
- **WHEN** se crea un presupuesto con `vence_en="2026-11-30T23:59:59"` (sin offset)
- **THEN** el sistema responde `422` y no persiste el presupuesto

### Requirement: Aceptación parcial y total por línea

El sistema SHALL registrar la aceptación o el rechazo de cada línea; con algunas líneas aceptadas y otras pendientes el presupuesto SHALL quedar `PARCIAL`, y con todas las líneas aceptadas SHALL quedar `ACEPTADO`; las líneas rechazadas o pendientes SHALL NOT imputarse.

#### Scenario: Aceptación parcial deja el presupuesto en PARCIAL

- **GIVEN** T1 con un presupuesto `VIGENTE` de dos líneas L1 y L2
- **WHEN** se acepta L1 y se deja L2 pendiente
- **THEN** el presupuesto queda `PARCIAL` y sólo se imputa L1

#### Scenario: Aceptación total deja el presupuesto en ACEPTADO

- **GIVEN** T1 con un presupuesto `VIGENTE` de dos líneas L1 y L2, con L1 ya aceptada
- **WHEN** se acepta L2
- **THEN** el presupuesto queda `ACEPTADO` y se imputan L1 y L2, una vez cada una

#### Scenario: Rechazar una línea no imputa

- **GIVEN** T1 con un presupuesto `VIGENTE` de dos líneas L1 y L2
- **WHEN** se rechaza L2 con `acepta=false`
- **THEN** la decisión de L2 queda registrada con `acepta=false` y el puerto de imputación no recibe ninguna llamada por L2

#### Scenario: Aceptar una línea ya aceptada se rechaza

- **GIVEN** T1 con la línea L1 ya aceptada en un presupuesto
- **WHEN** se intenta aceptar L1 nuevamente
- **THEN** el sistema responde `409` y no se registra una segunda aceptación ni una segunda imputación

#### Scenario: Aceptar una línea ya rechazada se rechaza en v1

- **GIVEN** T1 con la línea L2 ya rechazada en un presupuesto
- **WHEN** se intenta aceptar L2
- **THEN** el sistema responde `409` y la decisión de L2 no cambia

#### Scenario: La fecha de la aceptación la fija el servidor

- **GIVEN** T1 con la línea L1 pendiente y `ahora=2026-11-10T10:00:00-03:00` en el reloj del servidor
- **WHEN** se acepta L1 con un payload que no incluye `fecha`
- **THEN** la aceptación se persiste con `fecha=2026-11-10T10:00:00-03:00` (nunca con una fecha del cliente)

### Requirement: Imputación sólo de lo aceptado, atómica e idempotente

El sistema SHALL imputar cada línea aceptada exactamente una vez a través de los puertos de agenda y caja; si una imputación falla, SHALL NOT persistir la aceptación ni cambiar el estado del presupuesto.

#### Scenario: Una línea aceptada genera una imputación de agenda y una de caja

- **GIVEN** T1 con la línea L1 de `monto=100000` y `a_cargo_paciente=60000`
- **WHEN** se acepta L1
- **THEN** el puerto de agenda recibe una llamada por L1 y el puerto de caja recibe una llamada por L1 con `monto_centavos=60000`

#### Scenario: Las líneas pendientes no se imputan

- **GIVEN** T1 con un presupuesto de tres líneas donde sólo L1 se acepta
- **WHEN** se completa la aceptación
- **THEN** los puertos reciben exactamente una llamada por L1 y ninguna por L2 ni L3

#### Scenario: Si la imputación falla no queda aceptación

- **GIVEN** T1 con un presupuesto `VIGENTE` y el puerto de caja configurado para fallar
- **WHEN** se acepta la línea L1
- **THEN** el sistema responde `503`, no queda aceptación de L1, el presupuesto no cambia de estado y no se imputa agenda

#### Scenario: La aceptación repetida no duplica la imputación

- **GIVEN** T1 con L1 aceptada e imputada una vez
- **WHEN** se reintenta aceptar L1
- **THEN** el sistema responde `409` y los puertos siguen con una única llamada por L1

#### Scenario: Dos aceptaciones concurrentes de la misma línea imputan una sola vez

- **GIVEN** T1 con la línea L1 pendiente y dos solicitudes simultáneas para aceptarla
- **WHEN** ambas se procesan
- **THEN** exactamente una responde `200`, la otra responde `409`, y los puertos reciben una única llamada por L1

### Requirement: Líneas no aceptadas disponibles para recupero

El sistema SHALL conservar consultables las líneas pendientes y rechazadas de un presupuesto, con su decisión y sin imputación, para que puedan usarse en el recupero/recall comercial; la gestión de contacto posterior SHALL NOT ser parte de este cálculo.

#### Scenario: Línea pendiente queda consultable sin imputar

- **GIVEN** T1 con un presupuesto `PARCIAL` donde L1 se aceptó y L2 quedó pendiente
- **WHEN** se consulta el presupuesto
- **THEN** L2 aparece como pendiente, no figura imputada y los puertos no recibieron ninguna llamada por L2

#### Scenario: Línea rechazada queda consultable como recupero

- **GIVEN** T1 con un presupuesto donde L2 se rechazó con `acepta=false`
- **WHEN** se consultan las líneas no aceptadas del presupuesto
- **THEN** L2 aparece con `acepta=false` y sigue disponible para recupero, sin imputación

### Requirement: RBAC del presupuesto

El sistema SHALL permitir crear presupuestos a `ODONTOLOGO`, `RECEPCION` y `ADMIN`; SHALL permitir registrar aceptación a `RECEPCION`, `ADMIN` y al `PACIENTE` dueño del presupuesto; el `ODONTOLOGO` SHALL NOT aceptar y un rol sin permiso SHALL recibir `403`.

#### Scenario: Recepción crea y acepta

- **GIVEN** T1 con un usuario RECEPCION y PACI-1
- **WHEN** recepción crea un presupuesto de PACI-1 con una línea y registra su aceptación
- **THEN** el presupuesto se crea (`201`) y la aceptación se registra (`200`)

#### Scenario: Odontólogo crea pero no acepta

- **GIVEN** T1 con el odontólogo P1 y PACI-1
- **WHEN** P1 crea un presupuesto y luego intenta aceptar una línea
- **THEN** la creación responde `201` y la aceptación responde `403`

#### Scenario: Paciente acepta su presupuesto, no el ajeno

- **GIVEN** T1 con PACI-1 y PACI-2, cada uno con un presupuesto
- **WHEN** PACI-1 acepta su presupuesto y luego intenta aceptar el de PACI-2
- **THEN** el propio responde `200` y el ajeno responde `403`/`404`

#### Scenario: Paciente no crea presupuestos

- **GIVEN** T1 con PACI-1 y PACI-2
- **WHEN** PACI-1 intenta crear un presupuesto para PACI-2
- **THEN** el sistema responde `403` y no persiste el presupuesto

### Requirement: Aislamiento multi-tenant del presupuesto

Toda operación sobre presupuestos, líneas y aceptaciones SHALL acotarse al `tenant_id`; un presupuesto o una línea de otro tenant SHALL NOT poder leerse, aceptarse ni imputarse desde el tenant actual.

#### Scenario: Presupuesto de T1 no visible en T2

- **GIVEN** los tenants T1 y T2, con el presupuesto PRES-1 de PACI-1 en T1
- **WHEN** un actor de T2 intenta leer PRES-1
- **THEN** el sistema responde `404` y no expone datos de T1

#### Scenario: Aceptar una línea de otro tenant falla

- **GIVEN** T2 y la línea L1 del presupuesto PRES-1 de T1
- **WHEN** un actor de T2 intenta aceptar L1
- **THEN** el sistema responde `404`, no registra aceptación en T2 y no imputa nada

#### Scenario: Una aceptación de T1 no aplica en T2

- **GIVEN** una línea L1 aceptada en T1 con el mismo identificador usado en T2
- **WHEN** se consulta L1 desde T2
- **THEN** el sistema responde `404` (no hereda la aceptación de T1)

### Requirement: Migración 007 crea las tablas con RLS e inmutabilidad

El sistema SHALL aplicar la migración 007 creando `odontograma_hallazgos`, `presupuestos`, `presupuesto_lineas` y `aceptaciones` con `tenant_id NOT NULL`, RLS forzada, CHECKs de dominio, UNIQUE parcial de `idempotency_key` por tenant y como máximo `UPDATE` de `resuelto` en hallazgos, de forma reversible.

#### Scenario: Base vacía llega a head con las tablas nuevas

- **GIVEN** una base con las revisiones 001–006 aplicadas
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existen las cuatro tablas con RLS forzada y la versión vigente es 007

#### Scenario: Downgrade elimina sólo la 007

- **GIVEN** una base en la revisión 007
- **WHEN** se ejecuta `alembic downgrade 006_ficha_clinica`
- **THEN** las cuatro tablas se eliminan sin afectar turnos, catálogos, lista de espera ni ficha clínica

#### Scenario: Sin tenant la RLS no devuelve filas

- **GIVEN** la base en 007 con presupuestos de T1 y el rol de aplicación sin `app.tenant_id` fijado
- **WHEN** se consulta `presupuestos` como `turnos_app`
- **THEN** la consulta devuelve cero filas (fail-closed)

#### Scenario: El contenido clínico y las aceptaciones no se editan ni borran

- **GIVEN** la base en 007 con un hallazgo HAL-1 y una aceptación ACE-1
- **WHEN** como `turnos_app` se intenta `UPDATE` de `hallazgo` o `DELETE` de HAL-1, o `UPDATE`/`DELETE` de ACE-1
- **THEN** la base rechaza las operaciones y las filas permanecen intactas

#### Scenario: El CHECK de pieza FDI se aplica en la base

- **GIVEN** la base en 007 con PACI-1
- **WHEN** se intenta insertar un hallazgo con `pieza_fdi=19` (diente inexistente) o `pieza_fdi=49` (fuera de la grilla)
- **THEN** la base rechaza la fila por el CHECK de grilla FDI (cuadrante 1–4 × diente 1–8)

#### Scenario: El UNIQUE parcial de idempotency_key impide duplicados

- **GIVEN** la base en 007 con una línea de T1 que ya usa la key `550e8400-e29b-41d4-a716-446655440000`
- **WHEN** se intenta insertar otra línea de T1 con la misma `idempotency_key`
- **THEN** la base rechaza la segunda fila; la misma key en T2 se acepta por ser tenant-scoped

### Requirement: UI del presupuesto con cobertura y aceptación parcial

La interfaz SHALL mostrar por línea el monto, la cobertura OS, el saldo a cargo del paciente y el origen de la cobertura, SHALL permitir aceptar o rechazar líneas y SHALL reflejar el estado resultante (`PARCIAL`/`ACEPTADO`) sin recalcular la cobertura en el cliente.

#### Scenario: La UI muestra el saldo a cargo por línea

- **GIVEN** un presupuesto con una línea de `monto=100000`, `cobertura_os=50000` y `a_cargo_paciente=50000`
- **WHEN** el usuario abre el presupuesto
- **THEN** la UI muestra los tres importes y la etiqueta "configurada, no validada en vivo"

#### Scenario: Aceptar una línea actualiza el estado visible

- **GIVEN** un presupuesto `VIGENTE` de dos líneas abierto en la UI
- **WHEN** el usuario acepta una línea y el backend responde `PARCIAL`
- **THEN** la UI muestra el estado `PARCIAL` y sólo la línea aceptada como imputada

#### Scenario: El error de aceptación no se muestra como éxito

- **GIVEN** una línea ya aceptada abierta en la UI
- **WHEN** el usuario intenta aceptarla de nuevo y el backend responde `409`
- **THEN** la UI muestra el error y no marca una segunda aceptación

### Requirement: Sin PHI en respuestas ni logs del presupuesto

El sistema SHALL NOT incluir PHI (nombre, DNI, teléfono, texto clínico) en logs ni mensajes de error; los schemas de respuesta del odontograma y del presupuesto SHALL usar allow-list estricta y rechazar campos extra.

#### Scenario: Un error de presupuesto no vuelca PHI

- **GIVEN** un presupuesto de un paciente con datos personales
- **WHEN** se produce un error de dominio al aceptar una línea
- **THEN** la respuesta de error incluye sólo el mensaje de dominio, sin nombre, DNI ni teléfono

#### Scenario: El schema rechaza campos extra

- **GIVEN** un payload de línea con un campo `tenant_id` inyectado
- **WHEN** se envía a la API
- **THEN** el sistema responde `422` y no procesa la línea

#### Scenario: Los logs de aceptación sólo llevan identificadores y montos

- **GIVEN** una aceptación válida de una línea
- **WHEN** se escribe el log estructurado
- **THEN** el log contiene `tenant_id`, `presupuesto_id`, `linea_id` y montos, y NO datos personales ni texto clínico

### Requirement: Auditoría del presupuesto append-only sin PHI

Toda mutación de presupuesto (creación, emisión, línea, aceptación, imputación) SHALL escribir un registro de auditoría inmutable con actor, acción, `antes`/`después`, timestamp y `tenant_id`, sin PHI.

#### Scenario: Aceptar una línea deja auditoría

- **GIVEN** T1 con una línea L1 pendiente
- **WHEN** se acepta L1
- **THEN** se escribe una entrada `ACEPTACION_REGISTRADA` con `tenant_id`, actor, `linea_id`, `acepta=true` y montos

#### Scenario: La auditoría del presupuesto es append-only

- **GIVEN** una entrada de auditoría de aceptación
- **WHEN** se intenta un UPDATE o DELETE sobre esa entrada
- **THEN** el sistema rechaza la operación y la entrada original permanece intacta

#### Scenario: La auditoría no expone el nombre del paciente

- **GIVEN** una mutación de presupuesto de PACI-1
- **WHEN** se consulta la entrada de auditoría
- **THEN** la entrada identifica al paciente por `paciente_id` y no incluye su nombre, DNI ni teléfono
