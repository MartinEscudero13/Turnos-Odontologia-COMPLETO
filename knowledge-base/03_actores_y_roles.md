# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|---|---|---|
| Paciente | Persona que reserva y recibe atención (datos FICTICIOS en ejemplos: "María Gómez", DNI 99.999.999) | Link público responsive 24/7 (sin login en v1: nombre + teléfono por turno) + WhatsApp; firma consentimiento en móvil |
| Odontólogo | Profesional que atiende dentro de un tenant | Web autenticada: su agenda, fichas de sus pacientes, odontograma, evolución |
| Recepción | Gestión operativa del tenant | Web autenticada: agenda completa, caja, señas, OS, lista de espera, recordatorios |
| Admin (tenant) | Dueño/administrador del consultorio | Todo lo de recepción + catálogos, usuarios del tenant, cierres, reportes, exportación |
| Superadmin plataforma | Operador del SaaS (no ve PHI salvo soporte auditado) | Altas de tenants, planes, monitoreo; sin acceso a clínica salvo intervención auditada |

> Alcance multi-tenant: Paciente/Odontólogo/Recepción/Admin pertenecen a **un tenant**; ningún rol cruza tenants. RBAC se evalúa siempre con `(tenant_id, rol)`.

## RBAC — Matriz de permisos

| Recurso | Paciente (link público) | Odontólogo | Recepción | Admin tenant |
|---|---|---|---|---|
| Disponibilidad / reserva online | R (crear/cancelar **sus** turnos) | R | CRUD | CRUD |
| Agenda del tenant | — (solo sus turnos) | R total, W solo propios | CRUD | CRUD |
| Sobreturno explícito | — | Crear (propio, auditado) | Crear (auditado) | Crear (auditado) |
| Pacientes / ficha / odontograma / evolución | R propio | CRUD (pacientes que atiende) | R + crear ficha base | CRUD |
| Presupuesto (crear/aceptar) | Aceptar parcial/total | Crear | Crear, registrar aceptación | Crear, anular |
| Caja / señas / cierre | Pagar seña (link MP) | R | CRUD movimientos, cierre | CRUD + anular con motivo |
| Obras sociales / liquidación | — | R | CRUD | CRUD |
| Catálogos (prestaciones, sillones, horarios) | — | R | R | CRUD |
| Usuarios del tenant / roles | — | — | — | CRUD |
| Auditoría / exportación 1-clic | — | R propia | R | R + exportar |
| Config tenant (seña, anticipación, recordatorios) | — | — | R | CRUD |

## Rutas públicas (sin autenticación)

- `/r/[tokenTenant]` — landing de reserva del consultorio (slots, reservar, cancelar/reprogramar con token de turno).
- `/pagar/[tokenSena]` — pago de seña vía Mercado Pago.
- `/api/disponibilidad`, `/api/reservas/publicas` (rate-limited + captcha/OTP liviano anti-spam).
- `/api/webhooks/*` (firmados: MP, WhatsApp, Google).
- Login (`/login`) y recupero de acceso.
