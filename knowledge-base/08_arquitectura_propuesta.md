# Arquitectura Propuesta

Propuesta inicial coherente con prioridad **escalabilidad/mantenibilidad** y multi-tenancy día 1 (decisiones en `09_decisiones_y_supuestos.md`).

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| Multi-tenant, single deploy + RLS | Todas las tablas de negocio (`tenant_id` + Row-Level Security) | Aísla consultorios sin costo operativo por tenant; escala a N consultorios |
| API FastAPI por dominios + SPA desacoplada | Backend `app/routers` por dominio (agenda, clínica, caja, integraciones); frontend React consume `/api` | Un compose simple hoy (api/web/db/redis); extracción a servicios solo si el volumen lo pide |
| ORM SQLAlchemy + migraciones Alembic | Modelos con `tenant_id` everywhere, revisiones versionadas | Integridad y migraciones trazables sin SQL crudo en código de negocio |
| Transacción + constraint en DB | Turnos (EXCLUDE anti-solape), caja, señas | La regla crítica no depende de la UI (RN-GL-01) |
| Idempotency keys en webhooks | MP (`mp_payment_id`), WA, GCal | Reintentos externos nunca duplican efectos |
| Outbox / colas Redis | WA, MP-sync, GCal-sync (workers con backoff) | Degradación con gracia (RN-IN-03) |
| Append-only audit log | `auditoria` sin UPDATE/DELETE | Trazabilidad demostrable (vacío C3.3) |
| RBAC por (tenant, rol) | Dependencias FastAPI + RLS | Ningún rol cruza tenants |
| Auth JWT + refresh + 2FA | Access corto + refresh rotado; 2FA exigible en roles internos | Sesiones sin estado, revocables, aptas para API desacoplada |

## Estructura de directorios

```
turnos-odontologia/
├── backend/                        # API FastAPI (Python)
│   ├── app/
│   │   ├── routers/                # un router por dominio (/api/turnos, /api/caja, ...)
│   │   ├── models/                 # modelos SQLAlchemy (tenant_id everywhere)
│   │   ├── schemas/                # schemas Pydantic (borde API)
│   │   ├── core/                   # settings, db client, auth JWT, RBAC, audit
│   │   └── workers/                # cron recordatorios, auto-oferta, reintentos (colas Redis)
│   └── alembic/                    # revisiones de migración versionadas
├── frontend/                       # SPA React + TypeScript + Vite
│   └── src/                        # routes (incl. pública /r/:token), agenda, caja, ...
├── docker-compose.yml              # api + web + db (PostgreSQL) + redis
├── tests/                          # anti-solape, caja, seña-liberación (rojos primero)
└── knowledge-base/                 # este directorio
```

## Seguridad

- Autenticación: email + password (hash argon2/bcrypt) + 2FA exigible en roles internos; JWT access corto + refresh rotado; link público por tokens únicos con rate-limit.
- Autorización: RBAC `(tenant_id, rol)` en dependencias FastAPI + RLS en PostgreSQL como segunda barrera; tests de fuga cross-tenant.
- Validación de input: schemas Pydantic v2 en borde API; teléfono E.164; FDI 11–48; montos enteros en centavos.
- Secrets management: solo variables de entorno (nunca en repo); rotación de tokens OAuth/MP/WA; PHI jamás en logs.
- Datos salud: cifrado en tránsito (TLS) y en reposo (disco gestionado); consentimiento + auditoría como base Leyes 25.326/26.529/27.706 (detalle legal: abogado, no promesa).

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL con RLS | `postgres://…` | Y |
| `REDIS_URL` | Colas Redis (workers) | `redis://…` | Y |
| `JWT_SECRET` (+ `JWT_ALGORITHM`/`JWT_EXPIRES_MIN`) | Firma de access/refresh | `rand-64` | Y |
| `MP_ACCESS_TOKEN` / `MP_WEBHOOK_SECRET` | Cobros + firma webhooks | `APP_USR-…` | Y |
| `WA_API_TOKEN` / `WA_PHONE_ID` / `WA_BSP` | Proveedor WA declarado | `EAA…` | Y |
| `GCAL_CLIENT_ID` / `GCAL_CLIENT_SECRET` | OAuth por profesional | `….apps.googleusercontent.com` | Y |
| `APP_URL` / `RESERVA_TTL_H` / `SENA_TTL_H` | Base pública + expiraciones | `https://…`, `48`, `24` | N |
| `CANCEL_ANTICIPACION_H` | Default anticipación cancelación | `24` | N |
