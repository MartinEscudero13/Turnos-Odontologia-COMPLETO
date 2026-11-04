# Proposal

## Why

El frontend actual sólo renderiza el estado de `/api/health` en una tarjeta. No existe un sistema visual, router, shell público/interno ni una página de login real. Antes de construir agenda, pacientes o reserva pública, necesitamos una base visual coherente, accesible y verificable.

## What Changes

- Crear `PRODUCT.md` y `DESIGN.md` como fuentes de verdad de producto y diseño.
- Incorporar un design system de tokens y componentes reutilizables.
- Agregar React Router y los shells público, autenticación e interno.
- Implementar `/` (home + estado del sistema), `/login` (contra `/api/auth/login`), `/app` (shell interno protegido) y `*` (404).
- Crear la skill de proyecto `visual-turnos`, basada en `impeccable` y `frontend-design`, con soporte para Figma MCP y Stitch MCP.
- Documentar la configuración de MCP de diseño sin secretos.
- Agregar tests de rutas, login, estados y accesibilidad básica.
- **Fuera de alcance**: agenda, pacientes, reserva pública, caja y reportes; se implementarán como changes por página.

## Capabilities

### New Capabilities

- `visual-foundation`: shells, sistema visual, rutas base, login y estados accesibles.

### Modified Capabilities

- Ninguna capacidad de negocio cambia; se reemplaza el shell visual de la fundación.

## Impact

- `frontend/src/` (router, layouts, componentes, páginas, estilos), `frontend/package.json`.
- `PRODUCT.md`, `DESIGN.md`, `.opencode/skills/visual-turnos/`, `.atl/skill-registry.md`, `AGENTS.md`, `CLAUDE.md`.
- `docs/design/` con MCP Figma/Stitch.
- Tests frontend y screenshots de aceptación.
