# Proposal — F-02 `reserva-publica-landing`

## Why

C-06 (`reserva-online-publica`, archivado 2026-11-05) dejó listo y verificado el
contrato público: disponibilidad server-side, reserva sin login con token por
turno, cancelar/reprogramar con anticipación y anti-spam. Lo que falta es la
superficie donde el paciente usa ese contrato: la landing `/r/:tokenTenant`.

Hoy `frontend/` tiene la fundación visual de F-01 (tokens, primitives, shells,
home, login, 404) pero ninguna página de reserva. Sin esta landing el paciente
sigue dependiendo de WhatsApp/teléfono y el motor de C-06 queda sin canal de uso
real (`knowledge-base/06_funcionalidades.md` §US-010; `07_flujos_principales.md`
§Flujo 1; `docs/api-publica-reserva.md`).

Este change es **frontend (React + TypeScript + Vite) más un enabler backend
mínimo**: construye la página mobile-first que consume la API pública de C-06 y
agrega `GET /api/publico/{tokenTenant}/catalogo` (solo lectura) para que el
paciente pueda elegir la prestación. No modifica disponibilidad, reserva,
anticipación, anti-spam ni alternativas de C-06.

## What Changes

- Nueva ruta pública `/r/:tokenTenant` (mobile-first) con el flujo completo:
  elegir prestación → ver huecos reales → nombre + teléfono + verificación
  anti-spam (captcha, OQ-2) → confirmación con token de gestión.
- **Enabler backend**: `GET /api/publico/{tokenTenant}/catalogo` (OQ-F1) con las
  prestaciones (`id`, `nombre`, `duracion_min`) y profesionales (`id`, `nombre`)
  del tenant resuelto por `{tokenTenant}`; `404` uniforme, allow-list sin PHI.
  Reusa `CatalogoPort`/`CatalogoMemoria` de C-06.
- Pantalla de gestión "mi turno" desde el token: consultar, cancelar y reprogramar
  con anticipación mínima (`CANCEL_ANTICIPACION_H`, default 24 h).
- Cliente de API pública tipado (`reservaPublicaClient.ts`) que consume
  exclusivamente los 7 endpoints documentados en `docs/api-publica-reserva.md`
  (allow-list, sin inventar estados).
- Estados completos y accesibles: carga, vacío, error (404 / 403 / 409 con
  alternativas / 422 / 429 con `Retry-After`), éxito y contenido largo.
- Tests con React Testing Library + Vitest (setup existente de F-01:
  `src/test/setup.ts`, `App.test.tsx`), rojo-primero.
- Mockups HTML/CSS code-first (sin Figma/Stitch MCP autenticado) en
  `openspec/changes/f-02-reserva-publica-landing/mockups/`.

## Capabilities

### New Capabilities

- `reserva-publica-ui`: landing pública de reserva sin login, consumo del contrato
  de C-06, gestión por token y estados accesibles/verificables.

### Modified Capabilities

- `reserva-publica` (C-06): se **agrega** un requirement de catálogo público de
  solo lectura. No cambia ningún requirement existente de disponibilidad,
  reserva, gestión, anti-spam ni privacidad.
- `visual-foundation` (F-01): se **consume** la fundación visual (tokens y
  primitives) sin alterar sus requirements. El router agrega una ruta pública más
  bajo el mismo `PublicLayout`, sin tocar home/login/404 existentes.

## Actores

| Actor | Interacción en F-02 |
|---|---|
| Paciente | Abre `/r/:tokenTenant` desde el celular, sin login: elige prestación, ve huecos reales, reserva con nombre + teléfono, gestiona su turno con el token |
| Recepción / Admin | No cambia su flujo; recibe las derivaciones por debajo del umbral de anticipación |
| Sistema | Sirve la SPA; la API pública de C-06 ya resuelve disponibilidad, anti-spam, anticipación y privacidad |

## US cubiertas

| US | Criterios cubiertos acá | Criterios diferidos |
|---|---|---|
| US-010 — Reserva por link sin llamar | CA-1 (slots servidor-side) y CA-2 (nombre + teléfono) **en superficie** | CA-3 confirmación por WA/email → C-13 (acá la confirmación es la respuesta HTTP con token) |
| US-011 — Cancelar / reprogramar con anticipación | CA-1 anticipación configurable (default 24 h) y CA-2 derivación a recepción **en superficie** | — |

## Dependencias

- **C-06 `reserva-online-publica`** (archivado): es el contrato de API que consume
  la landing. F-02 **no reimplementa** disponibilidad, anticipación, anti-spam ni
  alternativas; lee `docs/api-publica-reserva.md` y
  `openspec/specs/reserva-publica/spec.md` como fuente de verdad.
- **F-01 `frontend-visual-foundation`** (archivado): tokens CSS, primitives
  (`Button`, `Field`, `Brand`, `StatusBadge`, `EmptyState`, `PageHeader`), shells
  (`PublicLayout`) y el setup de tests. Se reutilizan sin modificarlos.

## Deuda declarada (explícita, no oculta)

| # | Deuda | Estado real | Mitigación en F-02 |
|---|---|---|---|
| D-1 | **~~No hay endpoint público para listar prestaciones ni nombres legibles de profesional/sillón~~ → resuelta (OQ-F1)** | `disponibilidad` y `reservas` siguen devolviendo IDs (`profesional_id`, `sillon_id`, `prestacion`); se agrega `GET .../catalogo` con `nombre` de prestación y profesional | La landing consume `/catalogo` para elegir prestación y mostrar el nombre del profesional. `sillon_id` se mantiene como código neutro (el contrato no lo nombra). El endpoint es solo lectura, tenant-scoped y sin PHI |
| D-2 | **Proveedor de captcha sin definir** | OQ-2 quedó en `captcha`, pero `VerificadorPort` abstrae el proveedor (Turnstile/hCaptcha/proof-of-work); el borde no expone el challenge | La UI muestra el paso anti-spam como placeholder accesible `(TBD)`; el cliente sólo pide `POST .../verificacion` y envía `verificacion_id`, sin acoplarse al proveedor |
| D-3 | **Confirmación por WA/email no existe** (C-13) | Sin envío de mensajes | La confirmación es la respuesta HTTP con `token_publico` mostrada en pantalla |
| D-4 | **Seña no existe** (C-11) | La reserva queda `PENDIENTE` | La landing no muestra precios ni seña; estado `PENDIENTE` se muestra tal cual |

## Criterios de aceptación globales

- [ ] CA-G1 `/r/:tokenTenant` renderiza el flujo completo sin login y sin datos ajenos: catálogo → elegir prestación → huecos → formulario → confirmación con token.
- [ ] CA-G1b `GET .../catalogo` devuelve solo prestaciones (`id`, `nombre`, `duracion_min`) y profesionales (`id`, `nombre`) del tenant; `404` uniforme para `tokenTenant` inexistente/inactivo; sin PHI ni claves internas.
- [ ] CA-G2 La disponibilidad mostrada proviene de `GET .../disponibilidad` y se muestra como franjas horarias; el vacío y la carga tienen salida clara.
- [ ] CA-G3 Reservar envía `POST .../reservas` con el payload strict de C-06 y navega a confirmación con `token_publico`; `409` muestra las alternativas reales (hasta 3) sin crear turno.
- [ ] CA-G4 `403`/`422`/`429` muestran mensaje accesible alineado al código; `429` respeta `Retry-After` sin reintentos automáticos.
- [ ] CA-G5 Gestión por token: consultar/cancelar/reprogramar con anticipación; bajo el umbral muestra derivación a recepción sin mutar.
- [ ] CA-G6 `404` de `tokenTenant` inexistente muestra "enlace inválido" sin datos de agenda.
- [ ] CA-G7 Privacidad: la UI nunca muestra nombre/teléfono de terceros; solo IDs, estados, horarios del turno propio y nombres del catálogo público.
- [ ] CA-G8 Accesibilidad AA: labels persistentes, foco visible, `aria-live` en estados asíncronos, targets ≥44px, contraste, sin estados comunicados solo por color, `prefers-reduced-motion`, sin overflow en 375/1440.
- [ ] CA-G9 Regresión backend y frontend: `py -m pytest tests/ -q`, `npm run lint`, `npm run typecheck`, `npm test` y `npm run build` en verde; los tests de F-01 y C-06 intactos.
- [ ] CA-G10 `openspec validate f-02-reserva-publica-landing --strict` sin errores ni warnings.
