# Design

## Context

The frontend currently has one `App.tsx` health card, no router, no session and no design system. C-02/C-03/C-04 provide tenant/auth/catalog APIs; C-06 is still prepared. This change establishes the visual foundation before business pages. See `proposal.md`.

## Goals / Non-Goals

**Goals:** distinctive visual language, reusable tokens/components, router, public/auth/internal shells, functional login/session, 404, accessibility and visual QA.

**Non-Goals:** agenda, patient CRUD UI, public booking, cash, reports, Ficha/odontogram, production persistent auth storage.

## Decisions

**D1 — Two surfaces, two densities.**
Public/patient surfaces are editorial and mobile-first; internal surfaces are operational, dense and keyboard-friendly. Both share one token set and brand.

**D2 — A clinical, precise visual world instead of generic SaaS.**
Palette: deep ink green, warm paper, clinical teal, mint, amber and coral. Type: `Bricolage Grotesque` for display and `Source Sans 3` for body, with one clear scale. Structure references appointment slots and time rulers rather than generic cards.

**D3 — React Router with in-memory session.**
Use `react-router-dom` 6.30.1. `AuthProvider` keeps access/refresh tokens in memory; refresh persistence is a later security decision. `RequireSession` redirects to `/login`. No token is written to localStorage in this change.

**D4 — Small component layer, no UI framework.**
Build accessible primitives (`Button`, `Field`, `Surface`, `StatusBadge`, `EmptyState`, shells) with typed props. Avoid shadcn until a page needs a complex primitive; this keeps visual control and dependency weight low.

**D5 — Login calls the real C-03 endpoint.**
`/api/auth/login` with `tenant_slug`, email and password. Error messages are generic and never include token/password. Success navigates to `/app`.

**D6 — Figma MCP primary, Stitch optional, code-first fallback.**
Figma remote MCP is documented as `https://mcp.figma.com/mcp` and uses OAuth. Stitch MCP is documented as optional because its URL/credentials come from the Stitch setup. The `visual-turnos` skill treats both as optional inputs; the repo must remain buildable without them.

**D7 — Visual QA is executable.**
Run build/typecheck/lint/tests; use Playwright screenshots at 375/768/1440 when the browser is available; verify focus, contrast, reduced motion and no horizontal overflow.

## Risks / Trade-offs

- In-memory session disappears on reload → acceptable for foundation; persistent refresh storage requires an explicit security decision.
- Login depends on a seeded user → document demo credential creation separately; no user is hardcoded.
- Figma write-to-canvas may require a paid seat → use read/design-context; code-first fallback.
- Two typefaces add a network dependency → provide system fallbacks and avoid layout shift.

## Migration plan

1. Add tokens, components and router.
2. Implement home, login, protected shell, 404 and session.
3. Add skill and design MCP docs.
4. Run build/tests and capture screenshots.
5. Archive after review.
