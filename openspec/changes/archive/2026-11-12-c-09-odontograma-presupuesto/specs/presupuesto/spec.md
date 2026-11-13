# Spec Delta — presupuesto

## Purpose

Convertir hallazgos odontológicos en un presupuesto por pieza con montos, cobertura de obra social y saldo a cargo del paciente, con aceptación parcial o total y con imputación únicamente de lo aceptado, dentro del tenant y sin inventar datos de cobertura.

## ADDED Requirements

### Requirement: Creación de presupuesto por paciente

El sistema SHALL crear presupuestos en estado `BORRADOR` para un paciente del tenant; el `vence_en` SHALL NOT fijarse al crear (se fija al emitir, ver "Estados y vencimiento del presupuesto"); un paciente de otro tenant SHALL responder `404` y un presupuesto nuevo SHALL NOT tener líneas ni imputaciones.

#### Scenario: Crear un presupuesto en borrador

- **GIVEN** el tenant T1 con el paciente PACI-1
- **WHEN** recepción crea un presupuesto de PACI-1
- **THEN** se persiste un presupuesto de T1 con `estado=BORRADOR`, `vence_en=NULL` y sin líneas

#### Scenario: Crear no fija el vencimiento

- **GIVEN** T1 con PACI-1 y `ahora=2026-11-10T10:00:00-03:00`
- **WHEN** se crea un presupuesto incluyendo `vence_en` en el payload
- **THEN** el sistema responde `422` (campo no admitido en la creación) y no persiste el presupuesto; el vencimiento sólo se fija al emitir

#### Scenario: Presupuesto para paciente de otro tenant se rechaza

- **GIVEN** el tenant T1 y el paciente PACI-9 del tenant T2
- **WHEN** un rol habilitado de T1 crea un presupuesto para PACI-9
- **THEN** el sistema responde `404` y no crea el presupuesto en T1

#### Scenario: Presupuesto nuevo no imputa nada

- **GIVEN** T1 con PACI-1
- **WHEN** se crea un presupuesto en `BORRADOR`
- **THEN** el puerto de imputación no recibe ninguna llamada y no existe movimiento asociado

### Requirement: Línea de presupuesto con monto, cobertura OS y saldo a cargo

El sistema SHALL calcular por línea `monto`, `cobertura_os` y `a_cargo_paciente` en centavos enteros (`cobertura_os + a_cargo_paciente = monto`, ambos `>= 0`); SHALL rechazar con `422` un `monto` negativo o no entero y una `pieza_fdi` fuera de grilla. La cobertura SHALL buscarse por `(tenant_id, paciente.obra_social_id, prestacion_id)`, sin `obra_social_id` no se consulta cobertura, y `origen_cobertura`/`validada_en_vivo` SHALL persistirse al crear y devolverse sin recalcular.

#### Scenario: Línea con cobertura configurada

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y la cobertura de OS-1 para PREST-1 al 50 % en el puerto de cobertura
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea se persiste con `cobertura_os=50000`, `a_cargo_paciente=50000`, `origen_cobertura=CONFIGURADA` y `validada_en_vivo=false`

#### Scenario: La cobertura de otra obra social no aplica

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura configurada al 50 % para `OS-2`/PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=0`, `a_cargo_paciente=100000` y `origen_cobertura=SIN_COBERTURA`, sin consultar la cobertura de OS-2

#### Scenario: Sin obra social no se consulta ninguna cobertura

- **GIVEN** T1 con PACI-1 sin `obra_social_id` y una cobertura configurada para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda en 100 % particular y el puerto de cobertura no recibe ninguna consulta

#### Scenario: Línea con pieza FDI inválida se rechaza

- **GIVEN** T1 con un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea con `pieza_fdi=19`, `pieza_fdi=29`, `pieza_fdi=49`, `pieza_fdi=20`, `pieza_fdi=30` o `pieza_fdi=40`
- **THEN** el sistema responde `422`, no persiste la línea y el presupuesto sigue sin líneas

#### Scenario: Monto negativo se rechaza

- **GIVEN** T1 con un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea con `monto=-1`
- **THEN** el sistema responde `422`, no persiste la línea y el presupuesto sigue sin líneas

#### Scenario: Monto no entero se rechaza

- **GIVEN** T1 con un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea con `monto=1000.5` o con `monto="100000"`
- **THEN** el sistema responde `422`, no persiste la línea y el presupuesto sigue sin líneas

#### Scenario: Monto cero es válido y no genera deuda

- **GIVEN** T1 con PACI-1 y un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea con `monto=0` y sin cobertura
- **THEN** la línea se persiste con `cobertura_os=0` y `a_cargo_paciente=0`

#### Scenario: El invariante de la suma se rechaza en la base

- **GIVEN** una base con la migración 007 aplicada
- **WHEN** se intenta insertar una línea con `monto=100000`, `cobertura_os=60000` y `a_cargo_paciente=30000`
- **THEN** la base rechaza la fila por violar `cobertura_os + a_cargo_paciente = monto`

#### Scenario: El origen de cobertura no se recalcula al leer

- **GIVEN** una línea persistida con `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`, creada antes de que existiera una cobertura configurada para PREST-1
- **WHEN** después se configura una cobertura para PREST-1 y se consulta el presupuesto
- **THEN** la línea devuelve `origen_cobertura=SIN_COBERTURA`, `cobertura_os=0` y `validada_en_vivo=false` tal como se persistió, y el `GET` no consulta el puerto de cobertura

#### Scenario: Prestación de otro tenant no se puede presupuestar

- **GIVEN** el tenant T1 con un presupuesto en `BORRADOR` y la prestación PREST-9 del tenant T2
- **WHEN** un rol habilitado de T1 agrega una línea con `prestacion_id=PREST-9`
- **THEN** el sistema responde `404`, no persiste la línea y el presupuesto sigue sin líneas

### Requirement: Ciclo de vida de la línea de presupuesto en v1

El sistema SHALL exponer sólo el alta de líneas y SHALL NOT exponer `DELETE` ni `PATCH` de `presupuesto_lineas` en v1; las líneas SHALL agregarse únicamente con el presupuesto en `BORRADOR` y, fuera de `BORRADOR`, el alta SHALL responder `409` sin modificar las líneas existentes.

#### Scenario: Editar o borrar una línea no está expuesto en v1

- **GIVEN** T1 con un presupuesto `BORRADOR` con la línea L1
- **WHEN** se intenta `PATCH /api/presupuestos/{id}/lineas/{linea_id}` o `DELETE /api/presupuestos/{id}/lineas/{linea_id}`
- **THEN** el sistema responde `405` (o `404` si la ruta no existe) y L1 permanece intacta

#### Scenario: Agregar líneas fuera de borrador se rechaza

- **GIVEN** T1 con un presupuesto `VIGENTE` de una línea
- **WHEN** se intenta agregar otra línea
- **THEN** el sistema responde `409` y las líneas del presupuesto no cambian

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

El sistema SHALL aplicar 100 % particular cuando el paciente no tenga obra social, el puerto de cobertura no devuelva una cobertura configurada o la configuración devuelta no supere la validación de la configuración o la del resultado, dejando `cobertura_os=0`, `a_cargo_paciente=monto`, `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`.

#### Scenario: Paciente sin obra social paga el total

- **GIVEN** T1 con PACI-1 sin obra social y un presupuesto en `BORRADOR`
- **WHEN** se agrega una línea de PREST-1 con `monto=150000`
- **THEN** la línea queda con `cobertura_os=0`, `a_cargo_paciente=150000`, `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`

#### Scenario: Cobertura inexistente para la prestación cae a particular

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) pero sin cobertura configurada para OS-1/PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=150000`
- **THEN** la línea queda con `cobertura_os=0`, `a_cargo_paciente=150000` y `origen_cobertura=SIN_COBERTURA`

#### Scenario: Cobertura configurada nunca se reporta como validada en vivo

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura de OS-1 para PREST-1 configurada al 50 %
- **WHEN** se consulta el presupuesto que contiene esa línea
- **THEN** la respuesta declara `origen_cobertura=CONFIGURADA` y `validada_en_vivo=false`

#### Scenario: La etiqueta de cobertura configurada no se muestra en líneas sin cobertura

- **GIVEN** un presupuesto con una línea `SIN_COBERTURA` y otra `CONFIGURADA`
- **WHEN** se devuelve el presupuesto por la API
- **THEN** sólo la línea `CONFIGURADA` lleva la etiqueta "configurada, no validada en vivo" y la línea `SIN_COBERTURA` no la lleva

### Requirement: Cobertura por porcentaje o monto, con tope como máximo

El sistema SHALL aceptar coberturas configuradas en modo `PORCENTAJE` (0–100) o `MONTO` (centavos), SHALL recortar `cobertura_os` al `tope` cuando exista y al `monto` de la línea en todos los casos, y SHALL asignar la diferencia a `a_cargo_paciente`.

#### Scenario: Cobertura por monto fijo

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura de OS-1 en modo `MONTO` de `40000` centavos para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=40000` y `a_cargo_paciente=60000`

#### Scenario: La cobertura supera el tope

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura de OS-1 al 80 % con `tope=50000` para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=50000` y `a_cargo_paciente=50000`

#### Scenario: La cobertura no alcanza el tope

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura de OS-1 al 40 % con `tope=50000` para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=40000` y `a_cargo_paciente=60000`

#### Scenario: La cobertura mayor al monto se recorta al monto

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura de OS-1 en modo `MONTO` de `200000` centavos para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=100000` y `a_cargo_paciente=0` (nunca un saldo negativo)

### Requirement: Validación de la configuración de cobertura

El sistema SHALL validar la **configuración** devuelta por `CoberturaPort` antes de calcular: `modo ∈ {PORCENTAJE, MONTO}`, `valor` entero, `PORCENTAJE` en 0–100, `MONTO >= 0` y `tope IS NULL OR tope >= 0`. Una configuración inválida SHALL descartarse, aplicar el fallback 100 % particular, registrar auditoría `COBERTURA_INVALIDA_DESCARTADA` y responder `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`.

#### Scenario: Porcentaje fuera de 0–100 se descarta

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura de OS-1 configurada al `150 %` (o `-10 %`) para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=0`, `a_cargo_paciente=100000`, `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`

#### Scenario: Monto de cobertura negativo se descarta

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura de OS-1 en modo `MONTO` de `-50000` centavos para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=0` y `a_cargo_paciente=100000`, y la cobertura inválida no se usa

#### Scenario: Tope negativo se descarta

- **GIVEN** T1 con PACI-1 (`obra_social_id=OS-1`) y una cobertura de OS-1 al 50 % con `tope=-1` para PREST-1
- **WHEN** se agrega una línea de PREST-1 con `monto=100000`
- **THEN** la línea queda con `cobertura_os=0` y `a_cargo_paciente=100000`, y la cobertura inválida no se usa

#### Scenario: La cobertura descartada deja auditoría

- **GIVEN** T1 con una cobertura inválida para PREST-1 y un paciente con obra social
- **WHEN** se agrega una línea de PREST-1
- **THEN** se escribe una entrada `COBERTURA_INVALIDA_DESCARTADA` con `prestacion_id`, `obra_social_id` y `motivo`, sin datos personales del paciente

### Requirement: Guard del resultado del cálculo de cobertura

El sistema SHALL validar el **resultado** del cálculo antes de persistir: `cobertura_os >= 0`, `a_cargo_paciente >= 0` y `cobertura_os + a_cargo_paciente = monto`. Un resultado inconsistente SHALL descartarse —fallback 100 % particular, auditoría `COBERTURA_INVALIDA_DESCARTADA`, `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`— y SHALL NOT persistirse nunca una línea con totales inconsistentes; el CHECK de la base es la última barrera.

#### Scenario: Totales inconsistentes se descartan antes de persistir

- **GIVEN** T1 con una calculadora de cobertura inyectada como seam de test que produce `cobertura_os=60000` y `a_cargo_paciente=30000` sobre `monto=100000`
- **WHEN** se agrega la línea de PREST-1
- **THEN** el resultado se descarta, la línea se persiste con `cobertura_os=0`, `a_cargo_paciente=100000`, `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`, y nunca se guarda la combinación inconsistente

#### Scenario: El CHECK de la base rechaza una línea inconsistente

- **GIVEN** una base con la migración 007 aplicada
- **WHEN** se intenta insertar directamente una línea con `monto=100000`, `cobertura_os=60000` y `a_cargo_paciente=30000`
- **THEN** la base rechaza la fila por violar `cobertura_os + a_cargo_paciente = monto`

### Requirement: Estados y vencimiento del presupuesto

El sistema SHALL manejar los estados `BORRADOR`, `VIGENTE`, `PARCIAL`, `ACEPTADO` y `VENCIDO`; SHALL fijar `vence_en` al emitir (no al crear), rechazar con `422` una emisión con fecha pasada, reportar `VENCIDO` en el `GET` sin persistir y persistir `VENCIDO` —auditado— en el `POST /aceptar` que lo encuentra vencido, respondiendo `409`; un `PARCIAL` SHALL NOT vencer por reloj en v1 (C09-OQ-8).

#### Scenario: Emitir un presupuesto con líneas

- **GIVEN** T1 con un presupuesto `BORRADOR` que tiene una línea
- **WHEN** se emite el presupuesto
- **THEN** pasa a `estado=VIGENTE`

#### Scenario: Emitir fija el vencimiento

- **GIVEN** T1 con un presupuesto `BORRADOR` con una línea y `vence_en=NULL`
- **WHEN** se emite con `vence_en=2026-12-31T23:59:59-03:00`
- **THEN** el presupuesto queda `VIGENTE` con `vence_en=2026-12-31T23:59:59-03:00`

#### Scenario: Emitir sin líneas se rechaza

- **GIVEN** T1 con un presupuesto `BORRADOR` sin líneas
- **WHEN** se intenta emitir el presupuesto
- **THEN** el sistema responde `409` y el presupuesto permanece en `BORRADOR`

#### Scenario: Emitir con vencimiento anterior a ahora se rechaza

- **GIVEN** T1 con un presupuesto `BORRADOR` con una línea y `ahora=2026-11-10T10:00:00-03:00`
- **WHEN** se emite con `vence_en=2026-11-01T00:00:00-03:00`
- **THEN** el sistema responde `422` y el presupuesto permanece en `BORRADOR` sin `vence_en` persistido

#### Scenario: Vencimiento sin zona horaria se rechaza al emitir

- **GIVEN** T1 con un presupuesto `BORRADOR` con una línea
- **WHEN** se emite con `vence_en="2026-11-30T23:59:59"` (sin offset)
- **THEN** el sistema responde `422` y el presupuesto permanece en `BORRADOR`

#### Scenario: Editar líneas fuera de borrador se rechaza

- **GIVEN** T1 con un presupuesto en `VIGENTE`
- **WHEN** se intenta agregar o quitar una línea
- **THEN** el sistema responde `409` y las líneas del presupuesto no cambian

#### Scenario: Presupuesto vencido no admite aceptación

- **GIVEN** T1 con un presupuesto `VIGENTE` con `vence_en=2026-11-01T00:00:00-03:00` y una línea pendiente
- **WHEN** con `ahora=2026-11-10T10:00:00-03:00` se intenta aceptar la línea
- **THEN** el sistema responde `409`, persiste `estado=VENCIDO` en la misma transacción con una entrada de auditoría y no se imputa nada

#### Scenario: La lectura de un presupuesto vencido no persiste el estado

- **GIVEN** T1 con un presupuesto `VIGENTE` con `vence_en=2026-11-01T00:00:00-03:00` y `ahora=2026-11-10T10:00:00-03:00`
- **WHEN** se consulta el presupuesto dos veces por `GET`
- **THEN** ambas respuestas lo reportan `VENCIDO` y la fila de la base sigue en `VIGENTE` (la lectura no escribe ni audita)

#### Scenario: Un presupuesto parcial no vence por reloj en v1

- **GIVEN** T1 con un presupuesto `PARCIAL` con `vence_en=2026-11-01T00:00:00-03:00` y `ahora=2026-11-10T10:00:00-03:00`
- **WHEN** se consulta el presupuesto y se acepta una línea pendiente
- **THEN** el presupuesto se reporta y permanece `PARCIAL` (no pasa a `VENCIDO`), y la aceptación se registra

#### Scenario: Sin vencimiento el presupuesto no vence solo

- **GIVEN** T1 con un presupuesto `VIGENTE` y `vence_en=NULL`
- **WHEN** con `ahora=2026-12-31T10:00:00-03:00` se consulta el presupuesto
- **THEN** el estado sigue siendo `VIGENTE`

#### Scenario: No se acepta un presupuesto en borrador

- **GIVEN** T1 con un presupuesto `BORRADOR` con una línea
- **WHEN** se intenta aceptar esa línea
- **THEN** el sistema responde `409` y no se registra aceptación ni imputación

### Requirement: Aceptación parcial y total por línea

El sistema SHALL registrar la aceptación o el rechazo de cada línea; con al menos una línea aceptada y otras pendientes **o rechazadas** el presupuesto SHALL quedar `PARCIAL`; con todas las líneas aceptadas SHALL quedar `ACEPTADO`; una línea rechazada SHALL impedir `ACEPTADO` y SHALL NOT imputarse; con 0 líneas aceptadas el presupuesto SHALL conservar su estado anterior y SHALL NOT pasar nunca a `ACEPTADO`; SHALL rechazar con `409` el rechazo de una línea ya aceptada (v1 no revierte decisiones).

#### Scenario: Aceptación parcial deja el presupuesto en PARCIAL

- **GIVEN** T1 con un presupuesto `VIGENTE` de dos líneas L1 y L2
- **WHEN** se acepta L1 y se deja L2 pendiente
- **THEN** el presupuesto queda `PARCIAL` y sólo se imputa L1

#### Scenario: Aceptación total deja el presupuesto en ACEPTADO

- **GIVEN** T1 con un presupuesto `VIGENTE` de dos líneas L1 y L2, con L1 ya aceptada
- **WHEN** se acepta L2
- **THEN** el presupuesto queda `ACEPTADO` y se imputan L1 y L2, una vez cada una

#### Scenario: Aceptadas y rechazadas dejan el presupuesto en PARCIAL

- **GIVEN** T1 con un presupuesto `VIGENTE` de dos líneas L1 y L2
- **WHEN** se acepta L1 y se rechaza L2 con `acepta=false`
- **THEN** el presupuesto queda `PARCIAL` (nunca `ACEPTADO`), L1 se imputa una vez y el puerto de imputación no recibe ninguna llamada por L2

#### Scenario: Todas las líneas rechazadas conservan el estado anterior

- **GIVEN** T1 con un presupuesto `VIGENTE` de una línea pendiente
- **WHEN** se rechaza la única línea con `acepta=false`
- **THEN** el presupuesto sigue en `VIGENTE` (no existe `RECHAZADO` en el enum, C09-OQ-3), la decisión queda registrada y no se imputa nada

#### Scenario: Rechazar una línea no imputa

- **GIVEN** T1 con un presupuesto `VIGENTE` de dos líneas L1 y L2
- **WHEN** se rechaza L2 con `acepta=false`
- **THEN** la decisión de L2 queda registrada con `acepta=false`, el presupuesto sigue en `VIGENTE` y el puerto de imputación no recibe ninguna llamada por L2

#### Scenario: Rechazar una línea ya aceptada se rechaza

- **GIVEN** T1 con la línea L1 ya aceptada e imputada en un presupuesto
- **WHEN** se intenta rechazar L1 con `acepta=false`
- **THEN** el sistema responde `409`, la aceptación de L1 no cambia y no se revierte la imputación

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

#### Scenario: El medio de pago es opcional al registrar la aceptación

- **GIVEN** T1 con la línea L1 pendiente
- **WHEN** recepción registra la aceptación de L1 sin indicar `medio`
- **THEN** la aceptación se registra (`200`) con `medio=NULL`, el puerto de caja recibe `medio=NULL` y C-10 lo completa al cobrar

#### Scenario: El canal vacío se rechaza con error de validación

- **GIVEN** T1 con la línea L1 pendiente
- **WHEN** se acepta L1 con `canal=""` (payload inválido) o con el cuerpo vacío
- **THEN** el sistema responde `422` (nunca `500`), no registra aceptación y no imputa nada

### Requirement: Imputación sólo de lo aceptado, atómica e idempotente

El sistema SHALL imputar cada línea aceptada exactamente una vez por los puertos de agenda y caja; si una imputación falla SHALL NOT persistir la aceptación ni cambiar el estado. La exclusión SHALL garantizarse con `SELECT ... FOR UPDATE` sobre `presupuesto_lineas` dentro de la unidad de trabajo, no con el chequeo de la última `Aceptacion`. La imputación a agenda SHALL sólo registrar la intención y SHALL NOT crear un turno.

#### Scenario: Una línea aceptada genera una imputación de agenda y una de caja

- **GIVEN** T1 con la línea L1 de `monto=100000` y `a_cargo_paciente=60000`
- **WHEN** se acepta L1
- **THEN** el puerto de agenda recibe una llamada por L1 y el puerto de caja recibe una llamada por L1 con `monto_paciente_centavos=60000`

#### Scenario: Caja recibe los dos tramos, el actor y el medio

- **GIVEN** T1 con la línea L1 de `monto=100000`, `cobertura_os=40000` y `a_cargo_paciente=60000`, sin turno asociado
- **WHEN** la recepcionista U1 acepta L1 con `medio=EFECTIVO`
- **THEN** el puerto de caja recibe `monto_paciente_centavos=60000`, `monto_os_centavos=40000`, `actor_id=U1`, `turno_id=NULL` y `medio=EFECTIVO`, con lo que C-10 registra el ingreso del paciente y la cuenta por cobrar de la OS sin cambiar el contrato

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

#### Scenario: Dos conexiones independientes aceptan la misma línea y sólo una imputa

- **GIVEN** T1 con la línea L1 pendiente y dos conexiones independientes a PostgreSQL —dos transacciones reales, no dos llamadas del mismo proceso— que intentan aceptar L1 a la vez
- **WHEN** la primera toma `SELECT ... FOR UPDATE` sobre la fila de `presupuesto_lineas`, registra la aceptación e imputa, y la segunda revalida después del lock
- **THEN** una responde `200`, la otra responde `409` sin registrar aceptación ni llamar a ningún puerto, y los puertos reciben una única llamada por L1

#### Scenario: La imputación de agenda no crea un turno

- **GIVEN** T1 con la línea L1 pendiente y la tabla `turnos` sin cambios
- **WHEN** se acepta L1 y se imputa a agenda
- **THEN** la tabla `turnos` no cambia (misma cantidad de filas y mismos datos) porque la imputación sólo registra la intención

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

El sistema SHALL permitir crear presupuestos a `ODONTOLOGO`, `RECEPCION` y `ADMIN`, y registrar aceptación o rechazo sólo a `RECEPCION` y `ADMIN`, en nombre del paciente y con `canal=CONSULTORIO`; el `ODONTOLOGO` SHALL NOT aceptar y un rol sin permiso SHALL recibir `403`. En v1 el `PACIENTE` SHALL NOT acceder (sin login, JWT ni link público: DD-06/DD-07); su acceso es `C09-OQ-10` y no se testea.

#### Scenario: Recepción crea y registra la aceptación en nombre del paciente

- **GIVEN** T1 con un usuario RECEPCION y PACI-1
- **WHEN** recepción crea un presupuesto de PACI-1 con una línea y registra su aceptación
- **THEN** el presupuesto se crea (`201`) y la aceptación se registra (`200`) con `canal=CONSULTORIO`, sin ninguna sesión de paciente

#### Scenario: Admin registra la aceptación en nombre del paciente

- **GIVEN** T1 con un usuario ADMIN y un presupuesto `VIGENTE` de PACI-1
- **WHEN** ADMIN registra la aceptación de una línea con `canal=CONSULTORIO`
- **THEN** la aceptación se registra (`200`) con el `actor_id` de ADMIN

#### Scenario: Odontólogo crea pero no acepta

- **GIVEN** T1 con el odontólogo P1 y PACI-1
- **WHEN** P1 crea un presupuesto y luego intenta aceptar una línea
- **THEN** la creación responde `201` y la aceptación responde `403`

#### Scenario: El paciente no tiene sesión ni acceso directo en v1

- **GIVEN** T1 con PACI-1 y su presupuesto `VIGENTE`
- **WHEN** una petición se presenta con identidad de paciente (sin sesión interna) para consultar o aceptar ese presupuesto
- **THEN** el sistema responde `401` y no registra ni imputa nada; el acceso directo del paciente es `C09-OQ-10` y queda fuera de v1

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

El sistema SHALL aplicar la migración 007 creando `odontograma_hallazgos`, `presupuestos`, `presupuesto_lineas` y `aceptaciones` con `tenant_id NOT NULL`, RLS forzada fail-closed (`NULLIF(current_setting('app.tenant_id', true), '')::uuid`), CHECKs de dominio —incluidos `origen_cobertura` y `validada_en_vivo`—, UNIQUE parcial de `idempotency_key` por tenant y sólo `UPDATE` de `resuelto`, de forma reversible.

#### Scenario: Base vacía llega a head con las tablas nuevas

- **GIVEN** una base con las revisiones 001–006 aplicadas
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existen las cuatro tablas con RLS forzada y la versión vigente es 007

#### Scenario: Downgrade elimina sólo la 007

- **GIVEN** una base en la revisión 007
- **WHEN** se ejecuta `alembic downgrade 006_ficha_clinica`
- **THEN** las cuatro tablas se eliminan sin afectar turnos, catálogos, lista de espera ni ficha clínica

#### Scenario: Sin tenant la RLS no devuelve filas

- **GIVEN** la base en 007 con presupuestos de T1 y la sesión del rol de aplicación sin `app.tenant_id` fijado o fijado en cadena vacía
- **WHEN** se consulta `presupuestos` como `turnos_app`
- **THEN** la consulta devuelve cero filas (fail-closed) sin lanzar el error `42704` de parámetro no definido

#### Scenario: El contenido clínico y las aceptaciones no se editan ni borran

- **GIVEN** la base en 007 con un hallazgo HAL-1 y una aceptación ACE-1
- **WHEN** como `turnos_app` se intenta `UPDATE` de `hallazgo` o `DELETE` de HAL-1, o `UPDATE`/`DELETE` de ACE-1
- **THEN** la base rechaza las operaciones y las filas permanecen intactas

#### Scenario: El CHECK de pieza FDI se aplica en la base

- **GIVEN** la base en 007 con PACI-1
- **WHEN** se intenta insertar un hallazgo con `pieza_fdi=19` (diente inexistente), `pieza_fdi=20` (diente 0) o `pieza_fdi=49` (fuera de la grilla)
- **THEN** la base rechaza la fila por el CHECK de grilla FDI (cuadrante 1–4 × diente 1–8)

#### Scenario: El UNIQUE parcial de idempotency_key impide duplicados

- **GIVEN** la base en 007 con una línea de T1 que ya usa la key `550e8400-e29b-41d4-a716-446655440000`
- **WHEN** se intenta insertar otra línea de T1 con la misma `idempotency_key`
- **THEN** la base rechaza la segunda fila; la misma key en T2 se acepta por ser tenant-scoped

#### Scenario: Las columnas del origen de cobertura existen y están acotadas

- **GIVEN** la base en 007 aplicada
- **WHEN** se inspecciona `presupuesto_lineas` e intenta insertar `origen_cobertura='OTRA_COSA'`
- **THEN** la columna `validada_en_vivo` existe con `DEFAULT false` y el CHECK de `origen_cobertura` rechaza el valor fuera de `CONFIGURADA`/`SIN_COBERTURA`

### Requirement: UI del presupuesto con cobertura y aceptación parcial (diferida a C-09-UI)

Este requirement queda **diferido al change `C-09-UI`** por decisión del dueño (2026-11-12): C-09 v1 entrega backend, contratos, migración 007 y tests, y no toca frontend. La interfaz SHALL mostrar por línea monto, cobertura OS, a cargo y origen de cobertura —etiqueta "configurada, no validada en vivo" sólo en líneas `CONFIGURADA`—, permitir aceptar o rechazar y reflejar el estado sin recalcular cobertura en el cliente; se verifica en `C-09-UI`, no en C-09.

#### Scenario: La UI muestra el saldo a cargo por línea

- **GIVEN** un presupuesto con una línea `CONFIGURADA` de `monto=100000`, `cobertura_os=50000` y `a_cargo_paciente=50000`
- **WHEN** el usuario abre el presupuesto en `C-09-UI`
- **THEN** la UI muestra los tres importes y la etiqueta "configurada, no validada en vivo"

#### Scenario: Aceptar una línea actualiza el estado visible

- **GIVEN** un presupuesto `VIGENTE` de dos líneas abierto en la UI de `C-09-UI`
- **WHEN** el usuario acepta una línea y el backend responde `PARCIAL`
- **THEN** la UI muestra el estado `PARCIAL` y sólo la línea aceptada como imputada

#### Scenario: El error de aceptación no se muestra como éxito

- **GIVEN** una línea ya aceptada abierta en la UI de `C-09-UI`
- **WHEN** el usuario intenta aceptarla de nuevo y el backend responde `409`
- **THEN** la UI muestra el error y no marca una segunda aceptación

#### Scenario: La línea sin cobertura no muestra la etiqueta de cobertura configurada

- **GIVEN** un presupuesto con una línea `SIN_COBERTURA` en la UI de `C-09-UI`
- **WHEN** el usuario abre el presupuesto
- **THEN** la UI no muestra la etiqueta "configurada, no validada en vivo" en esa línea

### Requirement: Sin PHI en respuestas ni logs del presupuesto

El sistema SHALL NOT incluir PHI (nombre, DNI, teléfono, texto clínico) en logs ni mensajes de error; los schemas de respuesta del presupuesto SHALL usar allow-list estricta y rechazar campos extra.

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

Toda mutación de presupuesto (creación, emisión, vencimiento persistido, línea, aceptación, imputación) SHALL escribir un registro de auditoría inmutable con actor, acción, `antes`/`después`, timestamp y `tenant_id`, sin PHI.

#### Scenario: Aceptar una línea deja auditoría

- **GIVEN** T1 con una línea L1 pendiente
- **WHEN** se acepta L1
- **THEN** se escribe una entrada `ACEPTACION_REGISTRADA` con `tenant_id`, actor, `linea_id`, `acepta=true` y montos

#### Scenario: Crear y emitir un presupuesto dejan auditoría

- **GIVEN** T1 con PACI-1 y un presupuesto `BORRADOR` con una línea
- **WHEN** se crea el presupuesto y se emite
- **THEN** se escriben las entradas `PRESUPUESTO_CREADO` y `PRESUPUESTO_EMITIDO` con `tenant_id`, actor, `presupuesto_id` y estado, sin PHI

#### Scenario: El vencimiento persistido deja auditoría

- **GIVEN** T1 con un presupuesto `VIGENTE` vencido y una línea pendiente
- **WHEN** se intenta aceptar la línea y el sistema persiste `VENCIDO`
- **THEN** se escribe una entrada de auditoría del cambio de estado a `VENCIDO` con `presupuesto_id` y `vence_en`, sin PHI

#### Scenario: La auditoría del presupuesto es append-only

- **GIVEN** una entrada de auditoría de aceptación
- **WHEN** se intenta un UPDATE o DELETE sobre esa entrada
- **THEN** el sistema rechaza la operación y la entrada original permanece intacta

#### Scenario: La auditoría no expone el nombre del paciente

- **GIVEN** una mutación de presupuesto de PACI-1
- **WHEN** se consulta la entrada de auditoría
- **THEN** la entrada identifica al paciente por `paciente_id` y no incluye su nombre, DNI ni teléfono
