# Visión y Objetivos

## Propósito del sistema

**Unir, en un único SaaS multi-tenant argentino, los tres mundos que ningún competidor une bien: clínica odontológica profunda + obras sociales/ARCA + WhatsApp/Mercado Pago.**

Los consultorios odontológicos chicos y medianos coordinan turnos por WhatsApp y teléfono: sufren dobles reservas, confirmaciones manuales que consumen horas de recepción y ausentismo por olvidos o cancelaciones de último momento que dejan sillones vacíos. Los sistemas relevados (18 + 3 turneros, ver `docs/discovery/informe-discovery.md`) cubren partes —Dentalink la clínica, DentalTec las obras sociales, DentalSoft/FLAP la operación con Mercado Pago— pero ninguno encadena turno → cobertura → caja → liquidación con evidencia y precio ARS transparente. Este sistema nace para cerrar ese hueco desde el día 1 como SaaS multi-tenant (varios consultorios aislados).

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|---|---|---|
| Paciente | Reservar/cancelar/reprogramar online 24/7 sin llamar | Recibir recordatorios por WhatsApp; ver su presupuesto y saldo |
| Odontólogo | Ver su agenda del día y atender con la ficha clínica a mano | Registrar odontograma FDI y evolución en minutos; cobrar lo pactado |
| Recepción | Gestionar agenda completa, caja, señas y obras sociales sin fricción | Reasignar huecos liberados vía lista de espera; cerrar caja diaria |
| Admin del consultorio (tenant) | Operar su consultorio aislado con roles, auditoría y reportes | Configurar prestaciones, OS, señas y horarios; exportar sus datos en 1 clic |

## Alcance v1.0 (MVP)

- Agenda multi-profesional y por sillón/box con duraciones variables, bloqueos/feriados y anti-solapamiento real (sobreturno como excepción explícita y auditada).
- Reserva online 24/7 por link (confirmar/cancelar/reprogramar sin llamar) + lista de espera con auto-oferta de huecos liberados.
- Recordatorios y confirmación por WhatsApp (proveedor declarado) + email fallback, con estados visibles.
- Ficha clínica + odontograma FDI con historial → presupuesto por pieza con aceptación parcial → imputación a agenda y caja.
- Caja diaria multi-medio + señas por Mercado Pago con liberación automática + cierre diario + comisiones + reportes base.
- Cobertura de obras sociales configurable (3–5 OS iniciales, "configurada" no "validada en vivo") + liquidación simple presentable.
- Sincronización bidireccional con Google Calendar por profesional.
- Base legal mínima: RBAC, auditoría, consentimiento firmado, exportación en 1 clic, respaldo declarado (Leyes 25.326, 26.529, 27.706).
- Multi-tenancy desde el día 1: cada consultorio (tenant) opera aislado.

## Fuera de alcance (v1.0)

- Facturación electrónica nativa ARCA con CUIT (roadmap post-v1, ver `10_preguntas_abiertas.md`).
- Validación de cobertura de obra social en tiempo real vía SOAP/WS (fase 2 con 1–2 OS piloto).
- Periodontograma completo, módulos ortodoncia/estética, PACS/DICOM e imágenes avanzadas.
- IA diagnóstica o por voz, app móvil nativa (portal web responsive alcanza), marketplace propio, marca blanca.
- Campañas de marketing y recuperación comercial (sí hay recall sanitario, ver `06_funcionalidades.md`).
- Multi-sucursal avanzada e inventarios con lotes.

## Métricas de éxito

- Ausentismo (no-show) del tenant baja ≥ 30% a 90 días de usar recordatorios WA (vara vendor: −40% DentalSoft).
- 0 (cero) solapamientos no explícitos por mes y tenant (todo solape es sobreturno auditado).
- ≥ 60% de las reservas del tenant creadas por el link online (no por teléfono) a 90 días.
- Hueco cancelado reasignado vía lista de espera en < 2 h en horario hábil.
- Cierre de caja diario cuadrado (diferencia = 0) en ≥ 98% de los días operativos.
