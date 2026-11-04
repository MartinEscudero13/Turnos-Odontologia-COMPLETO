# visual-foundation Specification

## Purpose
Provide a distinctive, accessible and testable visual foundation for the public and internal Turnos-Odontologia surfaces.

## Requirements

### Requirement: Public home communicates the product and current system health

The system SHALL render a public home with a clear CTA to login, the product promise and a health indicator that reflects `/api/health` without exposing patient data.

#### Scenario: Home loads with healthy API
- **DADO** que el frontend abre `/`
- **CUANDO** `/api/health` responde `UP`
- **ENTONCES** la página muestra el nombre del producto, un CTA de ingreso y el estado `API operativa`

#### Scenario: Home handles unavailable API
- **DADO** que el frontend abre `/`
- **CUANDO** `/api/health` falla
- **ENTONCES** la página muestra un estado de API no disponible sin romper el layout ni exponer errores internos

### Requirement: Login is functional and accessible

The system SHALL provide a login form with tenant, email and password fields, visible labels, a loading state and an actionable error message. Successful login SHALL create an in-memory session and navigate to `/app`; logout SHALL clear it.

#### Scenario: Valid login creates a session
- **DADO** un usuario con credenciales válidas
- **CUANDO** envía el formulario de `/login`
- **ENTONCES** se guarda la sesión en memoria y se navega a `/app`

#### Scenario: Invalid login stays on the form
- **DADO** credenciales inválidas
- **CUANDO** se envía el formulario
- **ENTONCES** se muestra un mensaje de error asociado al formulario y no se navega

#### Scenario: Form is keyboard accessible
- **DADO** un usuario que navega con teclado
- **CUANDO** recorre la página `/login`
- **ENTONCES** todos los controles tienen label, foco visible y un orden lógico

### Requirement: Internal shell is protected and ready for pages

The system SHALL render `/app` only with an active in-memory session; without it, SHALL redirect to `/login`. The shell SHALL include tenant context, navigation placeholders and logout.

#### Scenario: Unauthenticated user is redirected
- **DADO** que no hay sesión activa
- **CUANDO** se abre `/app`
- **ENTONCES** el router redirige a `/login`

#### Scenario: Authenticated user sees internal shell
- **DADO** una sesión activa
- **CUANDO** se abre `/app`
- **ENTONCES** se muestra el shell interno con navegación y una página de inicio operativa vacía

### Requirement: Unknown routes are recoverable

The system SHALL render a 404 page for unknown routes with a link back to `/` and a clear message.

#### Scenario: Unknown route shows 404
- **DADO** una URL inexistente
- **CUANDO** se navega a ella
- **ENTONCES** se muestra la página 404 y se puede volver al inicio

### Requirement: Visual system is consistent and responsive

The system SHALL use shared tokens and components with responsive layouts at mobile, tablet and desktop widths, visible focus, reduced-motion support and no horizontal overflow.

#### Scenario: Mobile layout remains usable
- **DADO** un viewport de 375px
- **CUANDO** se abre `/`, `/login` o `/app`
- **ENTONCES** el contenido no desborda horizontalmente y los CTAs son alcanzables

#### Scenario: Motion respects the user preference
- **DADO** `prefers-reduced-motion: reduce`
- **CUANDO** se renderiza una entrada animada
- **ENTONCES** la animación se desactiva o se reduce a un cambio instantáneo

### Requirement: Page briefs and design MCP are documented

The system SHALL include a project skill for visual work and documentation for Figma/Stitch MCP setup, with a code-first fallback when no design MCP is available.

#### Scenario: Visual skill is discoverable
- **DADO** un agente que abre el repo
- **CUANDO** consulta las instrucciones y el registry
- **ENTONCES** encuentra `visual-turnos` y sus quality gates

#### Scenario: Figma MCP is optional
- **DADO** un entorno sin Figma MCP autenticado
- **CUANDO** un agente sigue la skill visual
- **ENTONCES** puede trabajar code-first sin bloquearse y registra que no usó MCP
