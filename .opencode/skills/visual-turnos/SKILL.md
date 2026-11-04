---
name: visual-turnos
description: Diseña, rediseña y audita las superficies visuales de Turnos-Odontologia (reserva pública, login, agenda, pacientes, caja, reportes) con una dirección propia del dominio odontológico, accesibilidad AA y verificación con screenshots. Usala cuando el pedido sea "rediseñá esta página", "armá el sistema visual", "revisá el diseño", "hacé que no parezca plantilla", "adaptá a mobile" o "auditá esta UI". Puede usar Figma MCP o Stitch MCP como fuente de diseño; si no hay MCP, trabaja code-first.
---

# Visual Turnos

Skill de proyecto para el frente visual de Turnos-Odontologia. Se apoya en los principios de
`impeccable` (proceso, craft, auditoría y live review) y `frontend-design` (dirección propia,
tipografía, anti-defaults). **No copia ni reemplaza esas skills**: agrega el contexto del
producto, las reglas de accesibilidad y los gates verificables de este repo.

## Antes de tocar UI

1. Leé [`PRODUCT.md`](../../../PRODUCT.md) y [`DESIGN.md`](../../../DESIGN.md).
2. Leé [`AGENTS.md`](../../../AGENTS.md) y la KB del flujo afectado.
3. Revisá el estado real de la page y sus APIs. No inventes módulos, estados ni datos.
4. Si existe Figma MCP autenticado, pedí el link del frame o variables. Si no existe,
   continuá code-first y dejalo declarado en el reporte.

## Entradas obligatorias

- Ruta/página y modo: **Persuade** (reserva pública), **Operate** (panel) o **Read** (ayuda).
- Audiencia y contexto de uso (paciente móvil, recepción desktop, etc.).
- Job principal y acción de éxito.
- Estados: carga, vacío, error, permiso, éxito, contenido largo.
- Fuente visual: Figma node/link, Stitch screen, o `code-first`.
- Restricciones: backend disponible, copy real, datos ficticios, breakpoints.

Si falta una entrada que cambia el resultado, preguntá una vez y esperá. No completes el
brief con valores de dominio inventados.

## Flujo

### 1. Page brief

Escribí un brief corto:

1. Quién llega y en qué estado.
2. Qué debe entender o hacer.
3. Qué prueba real sostiene la página.
4. Dirección visual: tensión/composición/foco, no una lista de colores.
5. Qué queda fuera y qué no debe cambiar.
6. Estados y rangos de contenido.
7. Restricciones de a11y, responsive y performance.

### 2. Dirección visual

- La página debe pertenecer al mundo de `DESIGN.md`: papel, tinta verde, grilla de horarios,
  precisión clínica.
- No usar defaults genéricos: cards idénticas, gradientes decorativos, hero “big number + stats”,
  eyebrows en todas las secciones, iconos sin label.
- Máximo 2 familias tipográficas. La tipografía y la estructura deben hacer trabajo real.
- El paciente móvil manda en la reserva; la recepción manda en la densidad de agenda.

### 3. MCP de diseño

**Figma (primario si hay archivo)**

- Endpoint remoto: `https://mcp.figma.com/mcp`; autenticación OAuth.
- Usalo para leer frames, variables, componentes y contexto de diseño.
- Escribir al canvas puede requerir asiento Full y está en beta; no es requisito para implementar.
- Pedí links de selección, no captures informales, y no subas PHI.

**Stitch (opcional)**

- Requiere el setup project-specific de Stitch y sus credenciales; la URL no es fija.
- Útil para generar o explorar pantallas nuevas; no lo uses para “leer” un design system que no existe.

**Fallback**

- Sin MCP autenticado, implementá desde `DESIGN.md` y verificá con screenshots.
- Registrá `MCP usado: figma | stitch | ninguno` en el cierre.

### 4. Implementación

- Reutilizá tokens y primitives existentes antes de crear otros.
- Tipado estricto; nada de `any` en props/eventos.
- Labels persistentes, foco visible, `aria-live` para estados y targets ≥44px.
- No agregar dependencias visuales sin justificar peso y mantenimiento.
- Mantené el copy en español rioplatense y sin jerga técnica en la superficie pública.
- No inventar datos de pacientes, testimonios, precios ni métricas.

### 5. Auditoría

Antes de entregar:

- Build, lint, typecheck y tests del frontend.
- 375 / 768 / 1440 px, sin overflow horizontal.
- Teclado: recorrido completo, foco visible, Enter/Espacio/Escape.
- `prefers-reduced-motion`.
- Contraste AA y estados no comunicados sólo por color.
- Screenshots de `/`, `/login`, `/app` y 404 si la page lo requiere.
- Revisar que no haya PHI, tokens ni secretos en screenshots o logs.

Comandos:

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

## Salida que tenés que devolver

- Brief confirmado.
- Archivos tocados y tokens/componentes reutilizados.
- Evidencia visual (rutas de screenshots o resultado de la herramienta de browser).
- Hallazgos de a11y/responsive con severidad.
- `MCP usado` y cualquier limitación.
- Qué NO se implementó y por qué.

## Prohibiciones

- No copies código, copy ni paletas de otro producto.
- No uses Figma/Stitch como excusa para no poder construir.
- No cambies contratos de backend ni agregues estados que la API no tenga.
- No uses imágenes de pacientes reales ni datos sensibles en Figma, Stitch o screenshots.
- No declares una página “lista” sin build/tests y revisión visual.
