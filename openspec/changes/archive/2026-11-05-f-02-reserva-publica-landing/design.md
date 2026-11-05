# Design — F-02 `reserva-publica-landing`

> Estado: **propuesto, no implementado**. Este documento decide el HOW; el QUÉ
> está en `specs/reserva-publica-ui/spec.md` y el porqué en `proposal.md`.

## UI Mockups

- Decision: yes — la landing es superficie pública nueva (visual); requiere mockup antes de apply.
- Design system revision: **fundación visual F-01** (`docs/design/README.md`, archivada 2026-11-03; el repo no lleva un campo `Revision:` numérico, así que la fecha de archivado de F-01 es el ancla de revisión). Tokens y primitives vienen de `frontend/src/styles.css` (F-01), sin cambios.
- Approval: approved (2026-11-05, por el usuario)
- Mockups: `openspec/changes/f-02-reserva-publica-landing/mockups/`
- Preview: manual (sin browser/MCP de diseño autenticado en esta sesión; los HTML se abren directo y se verificarán con Playwright en el apply)
- Visual verify: manual (2026-11-05)

---

## 1. Page brief

### Contexto

- **Ruta**: `/r/:tokenTenant` (SPA pública, mobile-first). `tokenTenant` es el token opaco del consultorio que resuelve el tenant en la API (`docs/api-publica-reserva.md`).
- **Modo**: Persuade (reserva pública).
- **Audiencia**: paciente en el celular, sin login, que llegó por un link de WhatsApp del consultorio. Poca paciencia, conexión mediocre, una mano.
- **Situación de uso**: abre el link, quiere ver si hay un horario que le sirva y reservarlo sin llamar.
- **Job principal**: elegir prestación → ver huecos reales → poner nombre + teléfono + verificación → confirmar → quedarse con el token para gestionar (cancelar/reprogramar).
- **Acción de éxito**: confirmación con fecha/hora propia y un token de gestión copiable.

### Contenido y prueba

- Contenido real disponible: fechas y horarios de huecos (`inicio`/`fin`), `estado` del turno, `token_publico`, y el catálogo del tenant (`GET .../catalogo`: `prestaciones[{id, nombre, duracion_min}]`, `profesionales[{id, nombre}]`, OQ-F1 resuelta).
- Fuente de verdad: `docs/api-publica-reserva.md` y `openspec/specs/reserva-publica/spec.md` (C-06 + catálogo público de F-02).
- Qué NO se puede inventar: precios, seña, disponibilidad armada en el cliente, endpoints fuera del contrato documentado, nombres de profesionales/prestaciones que el catálogo no devuelva.
- Evidencia / assets: mockups code-first; datos de demo marcados `(TBD)` (los nombres del catálogo salen del backend, no se hardcodean en la UI).

### Estados y rangos de contenido

- **Carga**: skeleton de huecos con `aria-busy` y texto `aria-live`.
- **Vacío**: "No hay horarios disponibles" con acción de cambiar prestación o volver.
- **Error**: `404` enlace inválido (tenant inexistente/inactivo), `409` hueco tomado con hasta 3 alternativas seleccionables, `422` teléfono/campos inválidos, `403` verificación inválida o bajo anticipación, `429` demasiados intentos con `Retry-After`.
- **Éxito**: confirmación con turno propio + token.
- **Contenido largo**: lista de huecos de varios días; el encabezado de fecha queda anclado y los targets se mantienen ≥44px.

### Responsive y a11y

- 375: columna única, CTA visible sin scroll, targets ≥44px.
- 768/1440: la "ficha de turno" se ensancha; la lista de huecos se ordena como grilla de franjas horarias sin perder la marca de tiempo.
- Teclado: flujo Tab/Shift+Tab completo, Enter/Espacio, foco visible, skip link.
- Contraste AA; estados nunca solo por color; `aria-live` en carga/error/éxito; `prefers-reduced-motion`.

---

## 2. Dirección visual

La landing **no es una home de startup ni un calendario SaaS**. Es una *ficha de
turno* llevada a la web: la página entera se comporta como el papel de la agenda
del consultorio, con la regla de horarios como estructura, no como ornamento.

- **Tensión**: calma editorial (papel cálido, tinta verde) contra precisión
  clínica (líneas finas, marcas de 15 minutos, borde exacto de la anticipación).
  El paciente decide con calma; el sistema promete exactitud.
- **Composición**: asimétrica y vertical en mobile —una sola columna donde el
  **tiempo es el protagonista**— porque es el dato que organiza la decisión. La
  prestación se nombra desde el catálogo público (`GET .../catalogo`) y
  profesional/sillón aparecen como contexto discreto (nombre de profesional
  cuando el catálogo lo entrega; `sillon_id` como código neutro), nunca como
  protagonistas ni como datos inventados.
- **Foco**: el próximo hueco. Cada hueco es una franja horaria (no una card con
  sombra) con la hora en display y la duración en body; el hueco elegido se
  eleva con borde teal y foco visible. La confirmación es una ficha con el turno
  propio y el token como dato a copiar, no como decoración.
- **Tipografía**: `Bricolage Grotesque` (display, para horas y titular) +
  `Source Sans 3` (body, para el flujo). Sin labels en mayúsculas decorativas ni
  acentos en una sola palabra del titular.
- **Qué se reutiliza de `DESIGN.md`**: tokens (`--paper`, `--surface`, `--ink`,
  `--teal`, `--mint`, `--coral`, `--amber`, `--line`), primitives (`Button`,
  `Field`, `StatusBadge`, `EmptyState`, `Brand`), la regla de horarios y la
  "ficha de turno" ya presentes en `frontend/src/styles.css` (F-01).
- **Anti-goals**: cards idénticas con sombra `rgba(0,0,0,.1)`, gradientes
  decorativos, hero "big number + stats", iconos sin label, estados solo por
  color, copia genérica ("reservá en segundos").

---

## 3. Decisiones de diseño

- **D-1 — El tiempo organiza, el catálogo nombra.** La landing pide
  `GET /api/publico/{tokenTenant}/catalogo` (OQ-F1) para mostrar prestaciones por
  `nombre` + `duracion_min` y profesionales por `nombre`. Los huecos siguen
  liderando con `inicio`/`fin`; `sillon_id` se muestra como código neutro porque
  el contrato no lo nombra. No se inventan nombres ni precios.
- **D-1b — El catálogo público es un enabler backend mínimo de F-02.** Se agrega
  al dominio `reserva-publica` un `GET .../catalogo` de solo lectura, tenant
  resuelto por `{tokenTenant}`, `404` uniforme y allow-list sin PHI. Reusa
  `CatalogoPort`/`CatalogoMemoria` de C-06 (mismo patrón de adaptadores en
  memoria); el wiring SQLAlchemy real sigue siendo la deuda D9 ya declarada.
- **D-2 — Un flujo lineal de 3 pasos, no un calendario de pestañas.** Elegir
  prestación → huecos → formulario → confirmación. Menos pasos, sin carrito ni
  lock temporal (el conflicto se resuelve con `409` + alternativas, RN-GL-02).
- **D-3 — Captcha como paso anti-spam (OQ-2).** La verificación liviana es
  captcha (`PUBLIC_ANTISPAM_MODO=captcha`). La UI pide `POST .../verificacion`
  con `accion` y usa el `verificacion_id` resultante; el widget concreto
  (Turnstile/hCaptcha/proof-of-work) queda como placeholder accesible `(TBD)`
  porque el borde no lo expone (D-2 de proposal). No se acopla al proveedor.
- **D-4 — Confirmación = respuesta HTTP + token.** Sin C-13, la confirmación es
  la pantalla con el turno propio y el `token_publico` copiable, con acciones
  gestionar/cancelar/reprogramar visibles. El token se copia con botón (nada de
  selección manual frágil en móvil).
- **D-5 — Errores como parte del flujo, no como excepción.** `409` reutiliza la
  lista de huecos para mostrar las alternativas reales; `429` muestra "volvé en
  N" respetando `Retry-After`; `404` muestra "enlace inválido" sin datos de
  agenda; `403` bajo anticipación deriva a recepción con copy claro.
- **D-6 — Sin dependencias visuales nuevas.** Todo se resuelve con CSS de F-01 y
  los primitives existentes. No se agrega shadcn, icon-library ni chart lib (peso
  y mantenimiento injustificados para una landing de reserva).
- **D-7 — Datos ficticios SIEMPRE.** Mockups y tests usan "Paciente Demo" y
  teléfono ficticio formalmente válido; nunca nombres/teléfonos reales ni PHI.

## 4. Seams

La landing consume el cliente tipado `reservaPublicaClient.ts`, que mapea 1:1 con
los endpoints públicos (base `/api` vía proxy de Vite):

| Cliente | Endpoint público |
|---|---|
| `catalogo(tokenTenant)` | `GET /api/publico/{tokenTenant}/catalogo` |
| `disponibilidad(tokenTenant, { prestacion, profesional?, desde })` | `GET /api/publico/{tokenTenant}/disponibilidad` |
| `emitirVerificacion(tokenTenant, { accion })` | `POST /api/publico/{tokenTenant}/verificacion` |
| `reservar(tokenTenant, payload)` | `POST /api/publico/{tokenTenant}/reservas` |
| `consultarReserva(tokenTenant, token)` | `GET /api/publico/{tokenTenant}/reservas/{token}` |
| `cancelar(tokenTenant, token, { verificacion_id })` | `POST .../reservas/{token}/cancelacion` |
| `reprogramar(tokenTenant, token, { nuevo_inicio, verificacion_id })` | `POST .../reservas/{token}/reprogramacion` |

Tipos de respuesta (allow-list, igual que C-06): `CatalogoPublico { prestaciones: PrestacionPublica[], profesionales: ProfesionalPublico[] }`, `PrestacionPublica { id, nombre, duracion_min }`, `ProfesionalPublico { id, nombre }`, `Hueco { inicio, fin, profesional_id, sillon_id }`, `ReservaCreada { turno_id, estado, inicio, fin, origen, prestacion, sillon_id, token_publico }`, `ReservaPropia { turno_id, estado, inicio, fin, prestacion, token_publico }`, `Verificacion { verificacion_id, expira_at, canal }`, `ErrorPublico { detalle, alternativas: Hueco[] }`.

## 5. Decisión OQ-F1 (resuelta)

**Decisión: se agrega `GET /api/publico/{tokenTenant}/catalogo`** (aprobada por el
usuario el 2026-11-05). Devuelve solo lectura:

```json
{
  "prestaciones": [{ "id": "PREST-30", "nombre": "Consulta", "duracion_min": 30 }],
  "profesionales": [{ "id": "P1", "nombre": "Dra. Demo" }]
}
```

- Tenant resuelto por `{tokenTenant}`; inexistente/inactivo → `404` uniforme
  (`detalle: "recurso no encontrado"`), igual que el resto del contrato público.
- Allow-list estricta: sin `tenant_id`, sin precios, sin datos de pacientes, sin
  horarios. El catálogo no reemplaza la disponibilidad: solo permite elegir
  `prestacion` y `profesional` antes de pedir huecos.
- Implementación: método nuevo en `CatalogoPort`, adaptador `CatalogoMemoria`,
  caso de uso en `ServicioReservasPublicas` y ruta en `crear_router_publico`.
  Reusa el patrón de C-06 (adaptadores en memoria); el wiring SQLAlchemy real es
  la deuda D9 de C-06.
- La UI ya no usa prestaciones de fixture: consume `/catalogo` y, si viene vacío,
  muestra un estado vacío con salida (no inventa datos).

El contrato documentado en `docs/api-publica-reserva.md` se actualiza con el
endpoint para mantener una única fuente de verdad.

## 6. Risks / Trade-offs

- [Hueco mostrado ≠ hueco real al confirmar] → `409` + hasta 3 alternativas (D-5).
- [IDs sin nombres pueden confundir al paciente] → el catálogo público resuelve
  prestación y profesional por nombre; `sillon_id` se explica como "sillón"
  neutro (D-1).
- [Catálogo vacío o tenant sin prestaciones] → estado vacío con salida, sin
  inventar datos ni habilitar una reserva imposible.
- [Captcha sin proveedor definido] → placeholder accesible `(TBD)` y cliente
  desacoplado del proveedor (D-3).
- [Conexión mediocre en móvil] → estados de carga explícitos, sin layout shift,
  targets ≥44px, tipografía de fallback del sistema.

## 7. Migration plan

1. Mockups code-first (este change) → revisión y approval del mockup (**aprobado
   2026-11-05**).
2. Enabler backend: `GET .../catalogo` (RED→GREEN→TRIANGULATE) + contrato en
   `docs/api-publica-reserva.md`.
3. Apply frontend: cliente API + página + tests rojo-primero.
4. Verificación: `pytest`, lint/typecheck/test/build y screenshots 375/768/1440.
5. Archivar con el `[x]` pedido por el dueño.
