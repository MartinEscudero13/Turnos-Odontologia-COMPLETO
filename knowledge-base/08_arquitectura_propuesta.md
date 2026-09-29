# Arquitectura Propuesta

Propuesta inicial coherente con prioridad **escalabilidad/mantenibilidad** y multi-tenancy día 1 (decisiones en `09_decisiones_y_supuestos.md`).

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| Multi-tenant, single deploy + RLS | Todas las tablas de negocio (`tenant_id` + Row-Level Security) | Aísla consultorios sin costo operativo por tenant; escala a N consultorios |
| Modular monolith (Next.js) | UI + API por dominios (agenda, clínica, caja, integraciones) | Un deploy simple hoy; extracción a servicios solo si el volumen lo pide |
| Transacción + constraint en DB | Turnos (EXCLUDE anti-solape), caja, señas | La regla crítica no depende de la UI (RN-GL-01) |
| Idempotency keys en webhooks | MP (`mp_payment_id`), WA, GCal | Reintentos externos nunca duplican efectos |
| Outbox / cola de reintentos | WA, MP-sync, GCal-sync | Degradación con gracia (RN-IN-03) |
| Append-only audit log | `auditoria` sin UPDATE/DELETE | Trazabilidad demostrable (vacío C3.3) |
| RBAC por (tenant, rol) | Middleware API + RLS | Ningún rol cruza tenants |

## Estructura de directorios

```
turnos-odontologia/
├── app/                          # Next.js App Router (rutas UI + /api/*)
│   ├── (public)/r/[token]/       # reserva online pública
│   ├── (app)/agenda|pacientes|caja|os|config/
│   └── api/...                   # Route Handlers por dominio
├── lib/
│   ├── domain/                   # agenda (slots, solapes), caja, OS, señas
│   ├── integraciones/            # whatsapp/, mercadopago/, gcal/, email/
│   ├── auth/                     # sesión, RBAC, tenant-context
│   └── audit/                    # log append-only
├── prisma/                       # schema + migraciones (tenant_id everywhere)
├── workers/                      # cron recordatorios, auto-oferta, reintentos
├── tests/                        # anti-solape, caja, seña-liberación (rojos primero)
└── knowledge-base/               # este directorio
```

## Seguridad

- Autenticación: email + password (hash argon2/bcrypt) + 2FA exigible en roles internos; sesiones cortas + refresh; link público por tokens únicos con rate-limit.
- Autorización: RBAC `(tenant_id, rol)` en middleware + RLS en PostgreSQL como segunda barrera; tests de fuga cross-tenant.
- Validación de input: schemas (zod) en borde API; teléfono E.164; FDI 11–48; montos enteros en centavos.
- Secrets management: solo variables de entorno (nunca en repo); rotación de tokens OAuth/MP/WA; PHI jamás en logs.
- Datos salud: cifrado en tránsito (TLS) y en reposo (disco gestionado); consentimiento + auditoría como base Leyes 25.326/26.529/27.706 (detalle legal: abogado, no promesa).

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL con RLS | `postgres://…` | Y |
| `AUTH_SECRET` | Firma de sesiones | `rand-64` | Y |
| `MP_ACCESS_TOKEN` / `MP_WEBHOOK_SECRET` | Cobros + firma webhooks | `APP_USR-…` | Y |
| `WA_API_TOKEN` / `WA_PHONE_ID` / `WA_BSP` | Proveedor WA declarado | `EAA…` | Y |
| `GCAL_CLIENT_ID` / `GCAL_CLIENT_SECRET` | OAuth por profesional | `….apps.googleusercontent.com` | Y |
| `APP_URL` / `RESERVA_TTL_H` / `SENA_TTL_H` | Base pública + expiraciones | `https://…`, `48`, `24` | N |
| `CANCEL_ANTICIPACION_H` | Default anticipación cancelación | `24` | N |
