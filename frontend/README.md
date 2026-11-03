# Frontend — Turnos-Odontologia

SPA React + TypeScript + Vite. In this foundation slice it renders the public health status of the API and establishes strict tooling for future feature work.

## Prerequisites

- Node.js 20+ (verified with Node 24)
- npm 10+

## Setup

```bash
npm ci
npm run dev
```

The SPA reads `VITE_API_BASE_URL`; during local development, `/api` is proxied to `http://localhost:8000`.

## Verification

```bash
npm run lint
npm run typecheck
npm test
npm run build
```
