# Proposal

## Why

El proyecto no puede evolucionar de forma verificable sobre una base incompleta: falta el andamiaje de backend, frontend e infraestructura que permitirá CI, despliegue repetible, seguridad operativa y pruebas reales. C-01 resuelve ese vacío creando una base mínima pero completa y demostrable.

## What Changes

- Se inicializa la arquitectura desacoplada backend + frontend + infraestructura.
- Se agregan: FastAPI con `/api/health`; React + TS + Vite; Docker Compose `api`, `web`, PostgreSQL 15, Redis; Alembic; core compartido (settings, logging sin PHI, db client, excepciones y schemas).
- Se agregan baseline: `.env.example`, README, CI paralela y tests frontend/backend; todo el stack debe ser ejecutable y verificable.
- Breaking changes: ninguna sobre funcionalidades existentes del dominio; el alcance amplía y empaqueta el stack.

## Capabilities

### New Capabilities

- `foundation-setup`: cubre la base ejecutable y verificable del sistema (backend, SPA, infra y core común).

### Modified Capabilities

- Ninguna capacidad de negocio existente cambia; C-01 aporta arquitectura e infraestructura transversal.

## Impact

- Código: backend FastAPI, estructura frontend React/Vite, Docker/Compose, CI y archivos de configuración.
- API: se añade `GET /api/health`.
- Dependencias: FastAPI/SQLAlchemy/Alembic, React/Vite, toolchains de lint/test.
- Riesgos: scope creep; mitigado manteniendo C-01 en configuración, health y controles transversales.
