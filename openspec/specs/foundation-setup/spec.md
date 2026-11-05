# foundation-setup Specification

## Purpose
Establish the reproducible, tested and secured baseline for the whole system, so backend, frontend and infrastructure can evolve together with a verifiable CI/CD path.

## Requirements

### Requirement: Backend health endpoint is deterministic and safe

The system SHALL expose `GET /api/health` returning `200` with a JSON body that
includes `status: "UP"`, `service: "turnos-api"` and no stack trace or secret.

#### Scenario: Health returns machine-readable success
- **GIVEN** the API service is reachable
- **WHEN** the client calls `GET /api/health`
- **THEN** the response status is `200`, the payload parses as JSON, and `status` equals `UP`

#### Scenario: Unhandled errors are not leaked in health output
- **GIVEN** an internal failure occurs while serving health
- **WHEN** the client receives the response
- **THEN** the body contains no stack trace, SQL query content, or secret value

### Requirement: Environment configuration is explicit and fail-fast

The system SHALL read runtime settings from environment variables, SHALL reject
missing mandatory variables at startup with a generic error, and SHALL never log secret values.

#### Scenario: Mandatory setting is absent
- **GIVEN** `DATABASE_URL` is not set in the process environment
- **WHEN** backend settings are loaded
- **THEN** startup fails with a clear message naming the missing key `DATABASE_URL`

#### Scenario: Placeholder defaults are not treated as valid production secrets
- **GIVEN** `JWT_SECRET` contains the committed example placeholder
- **WHEN** backend settings are loaded in `production`
- **THEN** the system refuses to boot and reports that the value is not a real secret

### Requirement: Database migration baseline can be applied reproducibly

The system SHALL support `alembic upgrade head` from an empty PostgreSQL database and SHALL keep the migration chain ordered and versioned.

#### Scenario: Empty database migrates to head
- **GIVEN** a disposable PostgreSQL database is empty and reachable
- **WHEN** a migration command executes `upgrade head`
- **THEN** it completes successfully and `current` points at the latest revision

#### Scenario: Alembic chain is deterministic
- **GIVEN** the configured Alembic environment files are present
- **WHEN** the revision graph is generated
- **THEN** each revision has one predecessor and one head

### Requirement: Compose orchestrates api web db and redis with healthchecks

The system SHALL provide a `docker-compose.yml` that defines `api`, `web`, PostgreSQL 15 and Redis, SHALL wire service dependencies, and SHALL not embed plain-text production secrets in the file.

#### Scenario: Compose configuration validates
- **GIVEN** the repository checkout contains the compose file
- **WHEN** `docker compose config` is executed with the example environment
- **THEN** the command exits `0` and output includes `api`, `web`, `db`, and `redis`

#### Scenario: Services declare readiness contracts
- **GIVEN** the compose file is rendered
- **WHEN** the `api` and `web` services are inspected
- **THEN** each declares a health check or dependency wait condition plus an exposed port or internal port mapping

### Requirement: Frontend baseline builds and typechecks

The system SHALL provide a React SPA with TypeScript and Vite, SHALL compile with strict typechecking, and SHALL expose a reproducible build output.

#### Scenario: Frontend build is reproducible
- **GIVEN** dependencies are installed with the lockfile
- **WHEN** the CI job executes install, lint, test and build
- **THEN** each command exits `0` and a `dist/` directory is produced

#### Scenario: Type checking detects contract violations
- **GIVEN** a source file contains an explicit `any` outside configuration exceptions
- **WHEN** strict TypeScript checks run
- **THEN** the check fails instead of ignoring the violation

### Requirement: CI verifies backend and frontend in parallel

The system SHALL run parallel jobs for backend lint/typecheck/tests and frontend lint/typecheck/tests/build, gating pull requests on both.

#### Scenario: Pull request triggers both pipelines
- **GIVEN** a push or pull request event is emitted by the remote repository
- **WHEN** GitHub Actions reads the workflow configuration
- **THEN** independent backend and frontend jobs are scheduled on the same ref

#### Scenario: Pipeline fails when either side is red
- **GIVEN** backend tests pass but frontend typecheck fails on the same workflow run
- **WHEN** workflow status is aggregated
- **THEN** the overall run is not marked green and the branch cannot be merged

### Requirement: Shared errors never expose sensitive details

The system SHALL use structured error responses and SHALL ensure unexpected failures return a generic message while preserving correlations IDs for diagnostics.

#### Scenario: Client receives correlation id and generic message
- **GIVEN** an uncaught error reaches the API boundary
- **WHEN** the response is generated
- **THEN** the body includes a correlation id and a generic error message without PHI, SQL or stack details

#### Scenario: Structured logs are PHI-safe
- **GIVEN** a response is generated with an error path
- **WHEN** logs are inspected in CI
- **THEN** no password, token, full patient name or phone number appears in the output

### Requirement: Base tooling works locally with exact prerequisites

The system SHALL publish Python and Node prerequisites and SHALL declare all required setup steps in a single README command sequence.

#### Scenario: Fresh clone follows one documented path
- **GIVEN** a clean checkout and required runtimes installed
- **WHEN** the developer executes the documented setup commands in order
- **THEN** health checks and frontend commands can run without manual database edits
