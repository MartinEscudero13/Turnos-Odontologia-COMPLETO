# auth-access Specification

## Purpose
Provide secure login, session rotation, two-factor authentication, role-based authorization and audit trails for internal users.

## Requirements

### Requirement: Credential login

The system SHALL authenticate an active user with normalized email and Argon2 password hash inside its tenant, and SHALL return an access JWT and a refresh token. Invalid credentials SHALL return the same generic `401` response.

#### Scenario: Valid credentials return tokens
- **DADO** un tenant activo y un usuario activo con email `admin@demo.test` y contraseña válida
- **CUANDO** se envía `POST /api/auth/login` con tenant, email y contraseña correctos
- **ENTONCES** la respuesta `200` incluye `access_token`, `refresh_token` y `token_type=bearer`

#### Scenario: Wrong password is generic
- **DADO** el mismo usuario activo
- **CUANDO** se envía una contraseña incorrecta
- **ENTONCES** la respuesta es `401` con el mismo mensaje que un email inexistente y no emite tokens

#### Scenario: Inactive tenant or user cannot login
- **DADO** un tenant inactivo o un usuario inactivo
- **CUANDO** se intenta autenticar
- **ENTONCES** la respuesta es `403` sin tokens

### Requirement: Refresh rotation and logout

The system SHALL store only a hash of the refresh token, SHALL rotate it on every refresh, and SHALL revoke the used token. Logout SHALL revoke the presented refresh token.

#### Scenario: Refresh rotates and invalidates the old token
- **DADO** una sesión con refresh token válido
- **CUANDO** se llama `POST /api/auth/refresh`
- **ENTONCES** se emite un refresh nuevo, el anterior queda revocado y reutilizarlo devuelve `401`

#### Scenario: Logout revokes the session
- **DADO** una sesión con refresh token válido
- **CUANDO** se llama `POST /api/auth/logout` con ese token
- **ENTONCES** el token queda revocado y un refresh posterior devuelve `401`

### Requirement: Access token contract

The system SHALL sign access tokens with `JWT_SECRET`, SHALL include `sub`, `tenant_id`, `role`, `type=access` and expiry, and SHALL reject expired or tampered tokens with `401`.

#### Scenario: Valid token authenticates
- **DADO** un access token vigente de un usuario activo
- **CUANDO** se llama `GET /api/auth/me` con `Authorization: Bearer`
- **ENTONCES** la respuesta `200` devuelve id, email, rol y tenant sin password_hash

#### Scenario: Expired or tampered token is rejected
- **DADO** un token vencido o con firma alterada
- **CUANDO** se usa en un endpoint protegido
- **ENTONCES** la respuesta es `401`

### Requirement: Two-factor authentication for internal roles

The system SHALL require a valid TOTP code at login when `two_factor=true`; missing or invalid codes SHALL NOT issue tokens.

#### Scenario: Valid TOTP completes login
- **DADO** un usuario interno con `two_factor=true` y secreto TOTP configurado
- **CUANDO** envía email, password y el código TOTP vigente
- **ENTONCES** la respuesta `200` emite access y refresh token

#### Scenario: Missing or invalid TOTP blocks login
- **DADO** el mismo usuario con 2FA habilitado
- **CUANDO** omite el código o envía uno inválido
- **ENTONCES** la respuesta es `401` sin tokens y sin revelar el secreto

### Requirement: Role-based authorization and tenant isolation

The system SHALL expose a dependency that requires an authenticated user with one of the allowed roles; a user of another tenant SHALL NOT operate on resources of the current tenant.

#### Scenario: Allowed role passes
- **DADO** un usuario `ADMIN` autenticado
- **CUANDO** accede a una ruta que requiere `ADMIN`
- **ENTONCES** la respuesta es `200`

#### Scenario: Insufficient role is forbidden
- **DADO** un usuario `RECEPCION` autenticado
- **CUANDO** accede a una ruta que requiere `ADMIN`
- **ENTONCES** la respuesta es `403` sin ejecutar la operación

#### Scenario: Token of another tenant cannot cross
- **DADO** un token de T1 y una ruta que opera sobre T2
- **CUANDO** se intenta la operación
- **ENTONCES** la respuesta es `403`/`404` uniforme y no modifica T2

### Requirement: Login rate limit

The system SHALL limit login attempts to `5` per `60` seconds per `(IP, email)` and SHALL respond `429` with `Retry-After` after the limit, without emitting tokens.

#### Scenario: Sixth attempt is rate-limited
- **DADO** cinco intentos de login fallidos en la ventana
- **CUANDO** se intenta el sexto
- **ENTONCES** la respuesta es `429` y no se emiten tokens

### Requirement: Access audit trail

The system SHALL record append-only audit entries for successful login, refresh, logout and rejected access, with tenant, actor, action and timestamp, and SHALL NOT include passwords, tokens, PHI or TOTP secrets.

#### Scenario: Successful login is audited
- **DADO** un login válido
- **CUANDO** la autenticación finaliza
- **ENTONCES** existe una entrada `LOGIN` con actor y tenant, sin email completo ni tokens

#### Scenario: Rejected access is audited without PHI
- **DADO** un intento de acceso con rol insuficiente
- **CUANDO** la API responde `403`
- **ENTONCES** la auditoría registra el rechazo sin password, token ni datos clínicos
