# Decisiones de skills — Turnos-Odontologia

*Fase `find-skill` (Etapa 5 del TP): el agente solo recomendó; la decisión de instalar fue mía (Martin Escudero). Una línea de justificación por skill, como pide la consigna.*

| # | Skill | Decisión | Justificación |
|---|---|---|---|
| 1 | `vercel-react-best-practices` | Instalar | Guía de performance React (fetching, bundle) para la SPA de reserva 24/7 y la agenda. |
| 2 | `frontend-design` | Instalar | Diseño mobile-first distintivo: el paciente reserva desde el celular, no puede parecer una planilla. |
| 3 | `web-design-guidelines` | Instalar | Auditoría de accesibilidad/UX de reserva y agenda con formato file:line. |
| 4 | `supabase-postgres-best-practices` | Instalar | Nuestro mayor riesgo técnico: RLS multi-tenant e integridad anti-solape en PostgreSQL. |
| 5 | `prisma-postgres` | Instalar (luego no aplicable) | Se instaló con el stack inicial (Next.js+Prisma); tras el cambio obligatorio a FastAPI+SQLAlchemy quedó marcada NO APLICABLE en AGENTS.md. No se desinstaló para no romper el registry. |
| 6 | `shadcn` | Instalar | Componentes accesibles para agenda del día, odontograma FDI y caja multi-medio. |
| 7 | `systematic-debugging` | Instalar | Metodología root-cause-first para dobles reservas, huecos falsos y fallos de recordatorios. |
| 8 | `diagnosing-bugs` | Instalar | Loop de diagnóstico para regresiones de cancelación/reprogramación y lista de espera. |
