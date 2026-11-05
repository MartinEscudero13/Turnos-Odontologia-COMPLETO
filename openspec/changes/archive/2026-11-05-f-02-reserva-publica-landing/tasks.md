# Tasks — F-02 `reserva-publica-landing`

> Estado: **propuesto, no implementado**. TDD rojo-primero: cada tarea nombra el
> test exacto que la verifica y el archivo destino. Comandos:
> backend `py -m pytest tests/ -q`; frontend `cd frontend && npm test` (Vitest,
> setup en `src/test/setup.ts`), `npm run typecheck`, `npm run lint`, `npm run
> build`. Los tests se suman a los de F-01 (`App.test.tsx`) y C-06 sin tocarlos.
> Datos ficticios SIEMPRE: "Paciente Demo", teléfono `+54 9 11 0000 0000`. Nunca
> PHI ni tokens en logs (CA-G7). Las prestaciones/profesionales salen de
> `GET .../catalogo` (OQ-F1 resuelta), no de un fixture hardcodeado en la UI.

## 0. Enabler backend — catálogo público (OQ-F1)

- [x] 0.1 RED: crear `tests/test_catalogo_publico.py::test_catalogo_tenant_devuelve_solo_sus_prestaciones_y_profesionales` — dos tenants sembrados en `CatalogoMemoria`; `GET /api/publico/T1/catalogo` ⇒ `200` con solo prestaciones/profesionales de T1 (`id`, `nombre`, `duracion_min`). GREEN: agregar `prestaciones_activas(tenant_id)` y `profesionales_activos(tenant_id)` a `CatalogoPort`/`CatalogoMemoria` (`backend/app/reservas/puertos.py`), `catalogo()` en `ServicioReservasPublicas` (`backend/app/reservas/servicio.py`) y la ruta en `crear_router_publico` (`backend/app/routers/reservas_publicas.py`) con schemas allow-list en `backend/app/schemas/reserva.py`.
- [x] 0.2 RED: `test_catalogo_publico.py::test_catalogo_no_expone_phi_ni_claves_internas` — las claves son exactamente `id`/`nombre`/`duracion_min` y `id`/`nombre`; no aparece `tenant_id`, `precio_base`, `paciente_id` ni horarios. GREEN: modelos `PrestacionPublicaOut`, `ProfesionalPublicoOut`, `CatalogoPublicoOut` (extra=`forbid` no aplica a salida; sí allow-list explícita).
- [x] 0.3 RED: `test_catalogo_publico.py::test_catalogo_token_tenant_inexistente_404` — `GET /api/publico/NO-EXISTE/catalogo` ⇒ `404` con `{"detalle","alternativas":[]}`. GREEN: reusar `_resolver_tenant`/`NoEncontrado` (no capturar distinto).
- [x] 0.4 TRIANGULATE: `test_catalogo_publico.py::test_catalogo_tenant_sin_datos_devuelve_listas_vacias` — tenant activo sin siembra ⇒ `{"prestaciones": [], "profesionales": []}`. Actualizar `docs/api-publica-reserva.md` con la fila del endpoint.

## 1. Cliente de API pública (tipado, allow-list)

- [x] 1.1 Crear `frontend/src/reservaPublicaClient.ts` con los tipos
  `PrestacionPublica`, `ProfesionalPublico`, `CatalogoPublico`, `Hueco`,
  `ReservaCreada`, `ReservaPropia`, `Verificacion`, `ErrorPublico` y las
  funciones `catalogo`, `disponibilidad`, `emitirVerificacion`, `reservar`,
  `consultarReserva`, `cancelar`, `reprogramar`, todas contra
  `/api/publico/{tokenTenant}/...` con `fetch` inyectable (mismo patrón que
  `authClient.ts`). Verifica
  `src/reservaPublicaClient.test.ts::test_catalogo_mapea_allowlist` (RED: módulo
  ausente; GREEN: mapea solo `id`/`nombre`/`duracion_min` y `id`/`nombre`, y
  descarta claves extra).
- [x] 1.1b Verifica
  `src/reservaPublicaClient.test.ts::test_disponibilidad_mapea_huecos_del_allowlist`
  (mapea solo `inicio`, `fin`, `profesional_id`, `sillon_id`).
- [x] 1.2 Mapear errores a `ApiResult` con `status` y `detalle`/`alternativas`
  sin exponer trazas. Verifica
  `src/reservaPublicaClient.test.ts::test_reservar_mapea_409_con_alternativas`
  (`409` ⇒ `{ ok:false, status:409, alternativas:[{inicio,fin}] }`).
- [x] 1.3 Garantizar que el cliente **no** loguea tokens, nombre ni teléfono.
  Verifica
  `src/reservaPublicaClient.test.ts::test_cliente_no_loguea_token_ni_phi`.

## 2. Página de reserva `/r/:tokenTenant`

- [x] 2.1 Agregar la ruta `/r/:tokenTenant` bajo `PublicLayout` en
  `frontend/src/App.tsx` y el componente `frontend/src/pages/ReservaPage.tsx`.
  Verifica `src/App.test.tsx::test_ruta_r_tokenTenant_renderiza_reserva` (render
  con `MemoryRouter initialEntries=['/r/T1']`).
- [x] 2.2 Paso "elegir prestación": al montar, llamar `catalogo(tokenTenant)` y
  renderizar un selector accesible (radio/lista) con `nombre` + `duracion_min`
  por prestación y el nombre del profesional cuando corresponda. Si el catálogo
  viene vacío ⇒ estado vacío con salida; `404` ⇒ enlace inválido. Verifica
  `src/pages/ReservaPage.test.tsx::test_muestra_prestaciones_del_catalogo` y
  `src/pages/ReservaPage.test.tsx::test_catalogo_vacio_muestra_salida` (labels
  visibles, targets ≥44px, sin jerga técnica, sin datos inventados).
- [x] 2.3 Paso "ver huecos": al elegir prestación, llamar
  `disponibilidad` y renderizar franjas horarias con `inicio`/`fin` legibles.
  Verifica
  `src/pages/ReservaPage.test.tsx::test_renderiza_huecos_como_franjas_horarias`
  (dos huecos ⇒ dos botones con horas `09:00`/`10:00` y duración).
- [x] 2.4 Estado vacío: lista vacía ⇒ `EmptyState` reutilizado con acción de
  cambiar prestación. Verifica
  `src/pages/ReservaPage.test.tsx::test_sin_huecos_muestra_estado_vacio`.
- [x] 2.5 Estado de carga: `aria-busy`/`aria-live` y sin reserva habilitada
  durante el fetch. Verifica
  `src/pages/ReservaPage.test.tsx::test_carga_anunciada_sin_reserva`.

## 3. Formulario de reserva (nombre + teléfono + verificación)

- [x] 3.1 Formulario con `Field` de nombre y teléfono (autocomplete, inputMode
  `tel`), resumen del hueco elegido y botón de reserva. Verifica
  `src/pages/ReservaPage.test.tsx::test_formulario_con_labels_persistentes`.
- [x] 3.2 Paso anti-spam (captcha, OQ-2): llamar `emitirVerificacion({accion})` y
  usar su `verificacion_id`; el widget es placeholder accesible `(TBD)`.
  Verifica
  `src/pages/ReservaPage.test.tsx::test_emite_verificacion_y_usa_verificacion_id`
  (`POST .../verificacion` con `accion=reservar`).
- [x] 3.3 Reserva feliz: `POST .../reservas` con payload strict ⇒ navega a
  confirmación con `token_publico`. Verifica
  `src/pages/ReservaPage.test.tsx::test_reserva_exitosa_navega_a_confirmacion`.
- [x] 3.4 Teléfono inválido: `422` ⇒ error asociado al campo, sin navegar ni
  token. Verifica
  `src/pages/ReservaPage.test.tsx::test_telefono_invalido_muestra_error_422`.
- [x] 3.5 Verificación inválida/vencida: `403` ⇒ error y reintento del paso, sin
  turno. Verifica
  `src/pages/ReservaPage.test.tsx::test_verificacion_invalida_muestra_error_403`.
- [x] 3.6 Hueco tomado: `409` ⇒ renderiza las alternativas (hasta 3) como huecos
  seleccionables. Verifica
  `src/pages/ReservaPage.test.tsx::test_409_muestra_alternativas_seleccionables`.
- [x] 3.7 Anti-spam: `429` ⇒ mensaje con `Retry-After`, sin reintento automático.
  Verifica `src/pages/ReservaPage.test.tsx::test_429_muestra_reintento_respetando_retry_after`.

## 4. Gestión "mi turno" por token

- [x] 4.1 Pantalla de confirmación/gestión `frontend/src/pages/GestionTurnoPage.tsx`
  (o sección) que consulta `GET .../reservas/{token}` y muestra el turno propio +
  acciones. Verifica
  `src/pages/GestionTurnoPage.test.tsx::test_consulta_turno_propio_por_token`.
- [x] 4.2 Cancelar con anticipación ⇒ `200` ⇒ estado `CANCELADO` visible y token
  inactivo. Verifica
  `src/pages/GestionTurnoPage.test.tsx::test_cancelar_con_anticipacion_muestra_cancelado`.
- [x] 4.3 Reprogramar con anticipación ⇒ `200` ⇒ turno nuevo en pantalla con el
  mismo token. Verifica
  `src/pages/GestionTurnoPage.test.tsx::test_reprogramar_con_anticipacion_muestra_nuevo_horario`.
- [x] 4.4 Bajo el umbral ⇒ `403` ⇒ derivación a recepción, sin mutar el horario
  mostrado. Verifica
  `src/pages/GestionTurnoPage.test.tsx::test_bajo_umbral_deriva_a_recepcion`.
- [x] 4.5 Token de gestión copiable (botón con `navigator.clipboard` mockeado) y
  nunca en el DOM de forma de selección manual frágil. Verifica
  `src/pages/GestionTurnoPage.test.tsx::test_token_copiable_por_boton`.

## 5. Estados de enlace y privacidad

- [x] 5.1 `404` de `tokenTenant` ⇒ "enlace inválido" sin datos. Verifica
  `src/pages/ReservaPage.test.tsx::test_token_tenant_inexistente_404`.
- [x] 5.2 Privacidad: las franjas y la confirmación nunca muestran
  nombre/teléfono de terceros. Verifica
  `src/pages/ReservaPage.test.tsx::test_no_muestra_nombres_de_terceros` y
  `src/pages/GestionTurnoPage.test.tsx::test_confirmacion_solo_turno_propio`.

## 6. Accesibilidad y responsive

- [x] 6.1 Estilos de la landing en `frontend/src/styles.css` (sección
  `reserva-publica`): franjas horarias ≥44px, foco visible, `prefers-reduced-motion`,
  sin overflow en 375px. Verifica
  `src/pages/ReservaPage.test.tsx::test_targets_accesibles_y_labels` (rol/labels).
- [x] 6.2 `aria-live` en carga/error/éxito y estados no comunicados solo por
  color (texto + ícono). Verifica
  `src/pages/ReservaPage.test.tsx::test_estados_asincronos_anunciados`.

## 7. Verificación y cierre

- [x] 7.1 `py -m pytest tests/ -q` (backend), `npm run lint`, `npm run typecheck`,
  `npm test` y `npm run build` (frontend) en verde; los tests de F-01 y C-06
  intactos (CA-G9).
- [x] 7.2 Screenshots de `/r/:tokenTenant` (375/768/1440) con Playwright
  (`scripts/visual-screenshots.mjs` o MCP) y verificación de foco/contraste.
- [x] 7.3 `openspec validate f-02-reserva-publica-landing --strict` limpio y
  marcar `[x]` el change en `CHANGES.md` (sección transversal).
  - Validación `--strict`: **limpia** (2026-11-05). Pendiente: alta del change en
    `CHANGES.md` §Cambios transversales (no existía entrada F-02 al implementar).
