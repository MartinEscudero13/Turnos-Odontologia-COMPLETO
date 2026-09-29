# Descripción General

## Stack tecnológico

Stack **propuesto por esta KB** (decisión documentada en `09_decisiones_y_supuestos.md` DD-01; prioriza escalabilidad/mantenibilidad multi-tenant):

| Capa | Tecnologías | Versión mínima |
|---|---|---|
| Frontend + Backend web | Next.js (TypeScript, App Router, API Routes / Route Handlers) | Next.js 14+, Node 20 LTS |
| Base de datos | PostgreSQL con aislamiento por tenant (`tenant_id` + Row-Level Security) | PostgreSQL 15+ |
| ORM / migraciones | Prisma (o Drizzle) con migraciones versionadas | Prisma 5+ |
| Auth / sesión | Auth.js (NextAuth) o equivalente, JWT + refresh, 2FA para roles internos | — |
| Pagos | SDK/API Mercado Pago (Checkout Pro / link de pago + webhooks) | API v1 vigente |
| Mensajería | WhatsApp Business API oficial (proveedor/BSP a definir) + email fallback (SMTP) | Cloud API vigente |
| Calendario | Google Calendar API v3 (OAuth2 por profesional, sync bidireccional) | v3 |
| Deploy | Contenedores (Docker) + PostgreSQL gestionado con backup diario | — |
| Observabilidad | Logs estructurados + auditoría en DB + alertas de webhooks caídos | — |

> Alternativa descartada y por qué: ver DD-01 (monolito instalable/local-first) y DD-02 (documental/schemaless sin integridad transaccional).

## Arquitectura general

SaaS multi-tenant con **un solo deploy y aislamiento lógico por `tenant_id`** en todas las tablas de negocio, reforzado con Row-Level Security en PostgreSQL. Cada consultorio es un tenant: tiene sus profesionales, sillones, prestaciones, OS, caja y pacientes, invisibles para otros tenants.

```
Paciente (móvil) ── link público ──┐
Recepción/Odontólogo (web) ────────┼──► Next.js (UI + API) ──► PostgreSQL (RLS por tenant_id)
                                   │         ├──► WhatsApp Cloud API (recordatorios)
                                   │         ├──► Mercado Pago (señas + webhooks)
                                   │         └──► Google Calendar (OAuth por profesional)
```

Decisiones de alto nivel: (1) monorepo Next.js para arrancar con un solo deploy y partir a servicios solo si el volumen lo exige (prioridad: mantenibilidad); (2) toda escritura de negocio (turno/cobro/seña) en transacción con constraint anti-solapamiento en DB, no solo en UI; (3) webhooks idempotentes para MP y WA; (4) nada de PHI en logs ni en mensajes.

## Integraciones externas

| Servicio | Propósito | Tipo |
|---|---|---|
| WhatsApp Business Cloud API | Recordatorios, confirmación, auto-oferta de lista de espera | REST + webhooks entrantes |
| Mercado Pago | Señas online atadas a reserva, cobros | REST (Checkout/link) + webhooks |
| Google Calendar | Sync bidireccional de agenda por profesional | REST OAuth2 + push notifications |
| Email (SMTP) | Fallback de avisos y comprobantes | SMTP |
| ARCA / OS en tiempo real | — | Post-v1 (ver `11_integraciones.md`) |

## API REST (principales, agrupadas por recurso)

- `/api/tenants/*` — alta/configuración del consultorio (solo admin tenant + superadmin plataforma).
- `/api/profesionales`, `/api/sillones`, `/api/prestaciones` — catálogos del tenant.
- `/api/turnos` — CRUD + `POST /turnos/:id/sobreturno` (explícito) + `POST /turnos/:id/cancelar|reprogramar`.
- `/api/disponibilidad?profesional=&prestacion=&desde=` — slots reales (público, por token de link).
- `/api/reservas/publicas` — reserva online sin login (nombre + teléfono + validación anti-spam).
- `/api/lista-espera` — alta y auto-oferta de huecos.
- `/api/pacientes`, `/api/fichas`, `/api/odontograma`, `/api/presupuestos/:id/aceptar`.
- `/api/caja/movimientos`, `/api/caja/cierre`, `/api/senas` (+ `/api/webhooks/mercadopago`).
- `/api/obras-sociales`, `/api/liquidaciones`.
- `/api/recordatorios` + `/api/webhooks/whatsapp`; `/api/calendar/oauth|webhook`.
- `/api/auditoria`, `/api/exportacion` (1 clic), `/api/consentimientos`.
