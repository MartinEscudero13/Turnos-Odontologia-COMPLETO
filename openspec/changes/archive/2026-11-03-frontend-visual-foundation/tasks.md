# Tasks — `frontend-visual-foundation`

## 1. Design truth

- [x] 1.1 Crear `PRODUCT.md` con usuarios, propósito, contexto operativo y restricciones reales; verificar que no invente métricas ni testimonios.
- [x] 1.2 Crear `DESIGN.md` con dirección visual, tokens, tipografía, componentes, layouts y anti-patrones; verificar que cubra público e interno.

## 2. Sistema visual

- [x] 2.1 Definir tokens CSS y reset accesible; verificar contraste/foco y `prefers-reduced-motion`.
- [x] 2.2 Crear primitives tipadas (`Button`, `Field`, `Surface`, `StatusBadge`, `EmptyState`, `PageHeader`); verificar con tests de render.
- [x] 2.3 Crear shells público, auth e interno responsive; verificar 375/768/1440 sin overflow horizontal.

## 3. Router y sesión

- [x] 3.1 Agregar `react-router-dom` y rutas `/`, `/login`, `/app`, `*`; verificar que el build y los tests de navegación pasen.
- [x] 3.2 Implementar `AuthProvider` en memoria, login real contra `/api/auth/login` y `RequireSession`; verificar éxito, error, logout y redirect.
- [x] 3.3 Implementar 404 recuperable y estados de API health; verificar con tests de páginas.

## 4. Skill y MCP

- [x] 4.1 Crear `.opencode/skills/visual-turnos/SKILL.md` basada en `impeccable` y `frontend-design`, con quality gates y fallback code-first.
- [x] 4.2 Registrar la skill en `.atl/skill-registry.md` y en `AGENTS.md`/`CLAUDE.md` (idénticos); verificar hashes.
- [x] 4.3 Documentar Figma MCP (`https://mcp.figma.com/mcp`) y Stitch MCP opcional en `docs/design/` con ejemplo sin secretos.

## 5. Verificación y cierre

- [x] 5.1 Actualizar tests de frontend, correr `npm run lint`, `npm run typecheck`, `npm test` y `npm run build`.
- [x] 5.2 Capturar screenshots de `/`, `/login`, `/app` y 404 en 375/768/1440; guardar evidencia en `docs/design/`.
- [x] 5.3 Ejecutar `openspec validate frontend-visual-foundation --strict`, archivar el change y actualizar README/CHANGES.
