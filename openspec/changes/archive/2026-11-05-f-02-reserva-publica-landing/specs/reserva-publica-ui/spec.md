# reserva-publica-ui Specification

## Purpose

Proveer la superficie pública mobile-first `/r/:tokenTenant` que consume el
contrato de C-06 (`docs/api-publica-reserva.md`) sin login: ver disponibilidad
real, reservar con nombre + teléfono y verificación anti-spam, y gestionar el
turno propio con el token. Toda lectura/escritura pasa por la API pública; la UI
no arma disponibilidad en el cliente, no inventa endpoints ni estados y nunca
muestra nombre/teléfono de terceros.

> Los escenarios son verificables contra el cliente de API mockeado con `fetch`
> (React Testing Library + Vitest). Cada respuesta respeta las formas de
> respuesta y los códigos del contrato (allow-list). La lista de prestaciones y
> los nombres de profesional provienen del catálogo público
> (`GET /api/publico/{tokenTenant}/catalogo`, OQ-F1 resuelta): la página no asume
> ni inventa datos cuando el catálogo viene vacío.

## ADDED Requirements

### Requirement: Catálogo público para elegir prestación

El sistema SHALL pedir `GET /api/publico/{tokenTenant}/catalogo` al abrir la
landing y renderizar las prestaciones con su `nombre` y `duracion_min` y los
profesionales con su `nombre`. SHALL NOT inventar prestaciones ni nombres cuando
la respuesta viene vacía, y SHALL NOT mostrar datos de pacientes, precios ni
claves internas del tenant.

#### Scenario: Catálogo cargado permite elegir prestación

- **GIVEN** el paciente abre `/r/T1` y `GET .../catalogo` responde `200` con dos
  prestaciones (`Consulta`, 30 min; `Limpieza`, 45 min) y un profesional
  (`Dra. Demo`)
- **WHEN** se renderiza el paso de elección
- **THEN** se muestran ambas prestaciones con su nombre y duración, el
  profesional aparece por su nombre y cada opción es un control accesible de al
  menos 44px

#### Scenario: Catálogo vacío no inventa datos

- **GIVEN** el paciente abre `/r/T1` y `GET .../catalogo` responde `200` con
  listas vacías
- **WHEN** se renderiza el paso de elección
- **THEN** se muestra un estado vacío ("el consultorio todavía no publicó
  prestaciones") con salida clara y no se habilita ninguna reserva

#### Scenario: tokenTenant inexistente en el catálogo

- **GIVEN** el paciente abre `/r/NO-EXISTE` y `GET .../catalogo` responde `404`
- **WHEN** se renderiza la página
- **THEN** se muestra "este enlace no corresponde a un consultorio activo" sin
  listas de prestaciones ni datos de turnos

### Requirement: La landing muestra disponibilidad real como franjas horarias

El sistema SHALL pedir
`GET /api/publico/{tokenTenant}/disponibilidad?prestacion=&desde=` y renderizar
cada hueco como una franja horaria accesible que muestra `inicio`/`fin` legibles.
SHALL NOT armar una grilla en el cliente ni mostrar nombres de profesional o
sillón que el catálogo/contrato no entregue (profesional puede venir por nombre
desde `/catalogo`; `sillon_id` es un código opaco).

#### Scenario: Huecos renderizados como franjas horarias

- **GIVEN** el paciente abre `/r/T1`, elige una prestación del catálogo y
  `GET .../disponibilidad` responde `200` con dos huecos
  (`2026-10-06T09:00:00-03:00`–`09:30:00-03:00` y
  `2026-10-06T10:00:00-03:00`–`10:30:00-03:00`)
- **WHEN** se renderiza la lista
- **THEN** se muestran dos franjas con las horas `09:00` y `10:00` y su duración,
  cada una es un botón alcanzable de al menos 44px y ninguna expone nombre ni
  teléfono de paciente

#### Scenario: Sin huecos muestra estado vacío con salida

- **GIVEN** el paciente abre `/r/T1` y `GET .../disponibilidad` responde `200`
  con lista vacía
- **WHEN** se renderiza el resultado
- **THEN** se muestra un estado vacío con mensaje claro ("No hay horarios
  disponibles") y una acción para cambiar de prestación o volver a intentar

#### Scenario: Carga anunciada sin habilitar reserva

- **GIVEN** el paciente abre `/r/T1` y `GET .../disponibilidad` está en curso
- **WHEN** se observa la página durante la carga
- **THEN** la región de huecos anuncia carga (`aria-busy` / texto en `aria-live`)
  y no hay ninguna acción de reserva habilitada

### Requirement: Reservar sin login con identificación liviana y verificación

El sistema SHALL recoger nombre y teléfono (E.164), obtener una verificación
single-use vía `POST /api/publico/{tokenTenant}/verificacion` con `accion`, y
crear la reserva con `POST /api/publico/{tokenTenant}/reservas` enviando
`prestacion`, `profesional`, `inicio`, `nombre`, `telefono` y `verificacion_id`
(payload strict). El éxito navega a la confirmación con `token_publico`.

#### Scenario: Reserva exitosa navega a confirmación con token

- **GIVEN** el paciente seleccionó el hueco de `2026-10-06T09:00:00-03:00`,
  completa nombre "Paciente Demo" y teléfono `+54 9 11 0000 0000`, y la
  verificación responde `201` con `verificacion_id=VER-1`
- **WHEN** envía el formulario y `POST .../reservas` responde `201` con
  `estado=PENDIENTE` y `token_publico` no vacío
- **THEN** se navega a la confirmación, se muestra la fecha/hora del turno propio
  y el token de gestión está disponible para copiar

#### Scenario: Teléfono inválido no crea nada

- **GIVEN** el paciente completa un teléfono que no normaliza a E.164
  (p. ej. `no-es-un-telefono`) y una verificación válida
- **WHEN** `POST .../reservas` responde `422`
- **THEN** se muestra un mensaje de error asociado al campo teléfono, no se
  navega y no se muestra ningún token

#### Scenario: Verificación inválida o vencida responde 403 sin turno

- **GIVEN** el paciente completa nombre/teléfono válidos pero la verificación
  usada está vencida o ya fue consumida
- **WHEN** `POST .../reservas` responde `403`
- **THEN** se muestra un mensaje de error accesible y se permite reintentar el
  paso de verificación, sin mostrar ningún turno creado

#### Scenario: Hueco tomado entre pasos responde 409 con alternativas

- **GIVEN** el paciente confirmó un hueco que dejó de estar libre antes de enviar
- **WHEN** `POST .../reservas` responde `409` con `detalle` y hasta 3
  alternativas (`inicio`/`fin`)
- **THEN** la UI muestra las alternativas como huecos seleccionables, no crea
  ningún turno y permite elegir una alternativa para reintentar

### Requirement: Anti-spam y límite de intentos visibles

El sistema SHALL reflejar el límite de intentos del contrato sin reintentos
automáticos: ante `429` SHALL mostrar un mensaje claro y respetar el
`Retry-After`.

#### Scenario: 429 con Retry-After

- **GIVEN** el paciente (o un bot) supera el límite de intentos sobre el tenant
- **WHEN** la API responde `429` con `Retry-After`
- **THEN** se muestra un mensaje de "muchos intentos, volvé en N" y no se
  reintenta automáticamente ni se muestra disponibilidad nueva

### Requirement: Gestionar el turno propio con token

Con el `token_publico` el paciente SHALL poder consultar su turno
(`GET .../reservas/{token}`) y cancelar o reprogramar con verificación y
anticipación mínima; bajo el umbral la acción pública SHALL responder `403` y la
UI SHALL derivar a recepción sin mutar el turno mostrado.

#### Scenario: Consulta del turno propio

- **GIVEN** un turno `PENDIENTE` con `token_publico=TOK-B`
- **WHEN** se pide `GET .../reservas/TOK-B` y responde `200` con `estado`,
  `inicio`, `fin` y `prestacion`
- **THEN** se muestra el turno propio con su fecha/hora y las acciones
  cancelar/reprogramar

#### Scenario: Cancelar con anticipación suficiente

- **GIVEN** un turno `PENDIENTE` que inicia en más de `CANCEL_ANTICIPACION_H` y
  una verificación válida para cancelar
- **WHEN** el paciente cancela y `POST .../cancelacion` responde `200`
- **THEN** se muestra el turno en estado `CANCELADO` y el token deja de gestionar

#### Scenario: Reprogramar con anticipación suficiente

- **GIVEN** un turno `PENDIENTE` con anticipación suficiente y un hueco nuevo
  libre
- **WHEN** el paciente reprograma y `POST .../reprogramacion` responde `200`
- **THEN** se muestra el turno nuevo en su horario y el mismo token sigue
  gestionando

#### Scenario: Bajo el umbral deriva a recepción sin mutar

- **GIVEN** un turno que inicia en menos de `CANCEL_ANTICIPACION_H`
- **WHEN** el paciente intenta cancelar o reprogramar y la API responde `403`
- **THEN** se muestra un mensaje de derivación a recepción ("gestioná este turno
  en el consultorio"), el horario mostrado no cambia y no se ofrece cancelar ni
  reprogramar de nuevo sin aviso

### Requirement: Enlace inválido con salida clara

El sistema SHALL tratar un `tokenTenant` inexistente o inactivo como enlace
inválido, sin exponer datos de agenda.

#### Scenario: tokenTenant inexistente responde 404

- **GIVEN** el paciente abre `/r/NO-EXISTE` y cualquier endpoint público
  responde `404`
- **WHEN** se renderiza la página
- **THEN** se muestra "este enlace no corresponde a un consultorio activo" sin
  lista de huecos ni datos de turnos

### Requirement: Privacidad en la superficie pública

La UI SHALL mostrar solo el turno propio y los huecos; SHALL NOT renderizar
nombre, teléfono ni dato clínico de otros pacientes, y SHALL NOT loguear tokens ni
PHI.

#### Scenario: Los huecos no exponen pacientes

- **GIVEN** `GET .../disponibilidad` responde `200` con huecos de varios
  profesionales
- **WHEN** se renderiza la lista
- **THEN** ninguna franja muestra `paciente_id`, nombre, teléfono ni dato clínico

#### Scenario: La confirmación muestra solo el turno propio

- **GIVEN** una reserva creada con `token_publico` y otro turno activo de otro
  paciente en el mismo tenant
- **WHEN** se muestra la confirmación
- **THEN** las únicas claves visibles son las del turno propio (fecha/hora,
  `estado`, `prestacion`, `sillon_id`, `token_publico`) y no aparece el nombre ni
  el teléfono del otro paciente

#### Scenario: Sin tokens ni PHI en logs del cliente

- **GIVEN** una reserva pública exitosa
- **WHEN** se inspecciona el flujo del cliente
- **THEN** el cliente no escribe `token_publico`, nombre ni teléfono en consola o
  logs

### Requirement: Accesibilidad y responsive

El sistema SHALL mantener labels persistentes, foco visible, `aria-live` para
estados asíncronos, targets de al menos 44px, contraste AA, estados no
comunicados solo por color, soporte de `prefers-reduced-motion` y ausencia de
overflow horizontal en móvil.

#### Scenario: Navegación por teclado y foco visible

- **GIVEN** un paciente que navega con teclado por `/r/T1`
- **WHEN** recorre el flujo completo
- **THEN** todos los controles tienen label accesible, el foco es visible y el
  orden es lógico (incluido el botón de copiar token y las alternativas del 409)

#### Scenario: Estados asíncronos anunciados

- **GIVEN** una acción de reserva en curso o un error devuelto
- **WHEN** el estado cambia
- **THEN** el cambio se anuncia con `aria-live` (carga, error, éxito) y no se
  comunica solo con color

#### Scenario: Sin overflow en móvil y sin animación con reduced motion

- **GIVEN** un viewport de 375px y `prefers-reduced-motion: reduce`
- **WHEN** se abre `/r/T1` y la confirmación
- **THEN** no hay overflow horizontal, los CTAs son alcanzables y las animaciones
  de entrada se desactivan
