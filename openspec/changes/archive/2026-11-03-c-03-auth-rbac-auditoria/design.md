# Design

## Context

C-02 provides `tenants`, `usuarios`, `auditoria`, RLS and the `turnos_app` role. C-03 adds the missing session/auth layer. See `proposal.md`.

## Goals / Non-Goals

**Goals:** Argon2 login, JWT access, rotated refresh tokens, TOTP for internal users, RBAC dependency and access audit.

**Non-Goals:** Password recovery, user administration UI, OAuth, Redis-backed distributed rate limiting (in-process for C-03; can move later), migration of all C-05 routes to JWT.

## Decisions

**D1 — Argon2id password hashing.**
Use `argon2-cffi` with default parameters; never compare plaintext. Alternative bcrypt rejected for new code because Argon2 is the modern default and the KB allows either.

**D2 — Short access JWT + opaque refresh token.**
JWT `HS256` with `JWT_SECRET`, `sub`, `tenant_id`, `role`, `type=access`; refresh token is random, stored only as SHA-256 hash with expiry/revocation. Rotate on every refresh; old token revoked. This allows logout and replay detection without storing the raw refresh secret.

**D3 — TOTP for `two_factor=true`, encrypted at rest.**
Use `pyotp`, store the secret encrypted with a Fernet key derived from `JWT_SECRET`; never return it. If 2FA is enabled and the secret is absent, login fails closed.

**D4 — RBAC dependency with tenant context.**
`get_current_user` decodes JWT, validates `type=access`, then loads the user within the token tenant. A `require_roles(*roles)` dependency returns `403` for insufficient roles. The RLS context is set on every session before user/audit queries in PostgreSQL, so a forged/cross-tenant token does not expose another tenant.

**D5 — In-process login rate limiter for C-03.**
`(IP, email)` fixed 60-second window, 5 attempts, `429 + Retry-After`. It is deterministic and testable; Redis-backed distributed limiting belongs to a later operations change.

**D6 — Migration 004 after C-05's 003.**
C-02 owns 001; C-04 still owns the 002 placeholder; C-05 owns 003. C-03 adds refresh tokens and `two_factor_secret` in 004. This keeps the archived C-05 migration intact and avoids a second migration with the same revision.

## Risks / Trade-offs

- In-process rate limit is per worker → document; move to Redis when workers scale.
- JWT logout relies on revoking refresh tokens; access tokens remain valid until short expiry. This matches DD-07.
- TOTP secret encryption uses `JWT_SECRET`; rotate both together.
- No C-05 route migration to JWT yet; C-05 tests remain on the provisional actor dependency. C-03 exposes the real dependency for C-06 onward.

## Migration plan

1. Add model/column and migration 004.
2. Implement auth service, rate limiter, audit helper and router.
3. Add API/unit tests plus optional PostgreSQL RLS auth test.
4. Validate OpenSpec and archive.
