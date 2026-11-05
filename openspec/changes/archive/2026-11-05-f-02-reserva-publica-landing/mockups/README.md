# Mockups — F-02 `reserva-publica-landing`

> Code-first (sin Figma/Stitch MCP autenticado). Fuente visual: `DESIGN.md` +
> `docs/design/README.md` (F-01). **Approval: approved (2026-11-05, por el usuario).**

## Cómo abrirlos

Abrir cada `.html` directo en el navegador (no necesita build). Importan
`tokens.css` y `mockups.css`, que están en esta carpeta.

- Mobile: inspeccionar a **390px** (o 375px).
- Desktop: **1440px**.

## Pantallas

| Archivo | Pantalla | Breakpoints |
|---|---|---|
| `01-elegir-prestacion.html` | Elegir prestación → ver huecos (franjas horarias) | 390 / 1440 |
| `02-formulario-reserva.html` | Formulario: nombre + teléfono + captcha (TBD) | 390 / 1440 |
| `03-confirmacion.html` | Confirmación con token + acciones gestionar/cancelar/reprogramar | 390 / 1440 |
| `04-errores.html` | Errores: 404 (enlace inválido), 409 (con 3 alternativas), 429 (muchos intentos) | 390 / 1440 |

## Tokens y componentes reutilizados de F-01

- **Tokens** (`tokens.css`): copia exacta del bloque `:root` de
  `frontend/src/styles.css` (F-01): `--paper`, `--surface`, `--ink`, `--ink-soft`,
  `--line`, `--teal`, `--teal-deep`, `--mint`, `--amber`, `--coral`, `--white`,
  radios, tipografía (`Bricolage Grotesque` + `Source Sans 3`) y escala.
- **Primitives** (`mockups.css`): `brand`/`brand-mark`/`brand-name`, `button`
  (primary/secondary/quiet/danger/small/full), `field`, `status-badge`
  (success/pending/danger/neutral), `eyebrow`, `muted`, `skip-link`, foco
  visible y `prefers-reduced-motion` — mismos nombres de clase y valores que F-01.
- **Nuevo (propio de esta landing, no de F-01)**: `.ficha` (ficha de turno),
  `.ruler` (regla de horarios como textura), `.slot`/`.slots` (franja horaria),
  `.prest-list`/`.prest-option` (selector de prestación), `.captcha` (placeholder),
  `.token-card`, `.chosen`, `.error-state`.

## Placeholders `(TBD)`

- **Prestaciones** ("Consulta", "Limpieza"): la API pública no lista el catálogo
  (OQ-F1 / deuda D-1). Son datos de demo marcados `demo (TBD)`.
- **Captcha**: OQ-2 resolvió `captcha`, pero el proveedor no está definido; el
  widget es un placeholder accesible `captcha (TBD)`.
- **Profesional/sillón**: la API devuelve IDs, no nombres; se muestran como
  "Profesional disponible" y "Sillón N" neutros.

## Datos ficticios

Nada de PHI ni datos reales. El turno de ejemplo es "Consulta · lunes 06.10 a las
09:00". El teléfono del placeholder es `+54 9 11 0000 0000` (ficticio, válido en
forma E.164).

## Approval

- **Approval: pending.** Los mockups quedan sujetos a revisión explícita del dueño
  antes del apply (design-mockups gate).
