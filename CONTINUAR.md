# CONTINUAR — Lautaro

> Esta es la entrada corta para la IA de Lautaro. No es un manual de instalación.

## Prompt para pegar en OpenCode

```text
Leé completo CONTINUAR.md, AGENTS.md, AUTHORS.md y docs/equipo/guia-lautaro.md.

No modifiques nada todavía.
Resumime:
1) qué está terminado hasta C-16,
2) qué queda para la entrega (video y validación real de Twilio),
3) qué deudas de integración están declaradas y en qué orden conviene cerrarlas,
4) qué preguntas abiertas bloquean la implementación.

Después esperá mi confirmación antes de tocar archivos.
```

## Estado (2026-11-16)

- C-01 a C-17 y F-01 a F-06: **terminados, verificados y archivados** (23 changes).
- **C-13 WhatsApp cerrado con Twilio Sandbox y Meta Cloud API**: recordatorios, webhook firmado, SI/NO y recall. **C-17** agregó el adaptador oficial de Meta.
- **C-16 cierre operativo**: transiciones de agenda, acciones de caja y presupuesto, toggles de OS/usuarios, desconexión de calendario, KPI de ocupación y herramientas de superadmin/respaldo.
- **Demo online**: <https://turnos.zoriontech.me> · Swagger <https://api-turnos.zoriontech.me/docs>.
- **Frontend interno completo**: `/app` con agenda, pacientes, clínica, caja, señas, WhatsApp, obras sociales, calendario y configuración.
- **API demo**: C-05 a C-17 montados en `create_app` sobre adaptadores en memoria.
- **Login demo**: tenant `demo` · `admin@demo.test` con la password definida en `DEMO_PASSWORD` (Compose corre migraciones + seed).
- TP2 skill + MCP: **terminado y pusheado**.
- Backend: **837 passed + 53 skipped** en local · **890 passed + 0 skipped** con `C02_DATABASE_URL`.
- Frontend: **41 tests, lint, typecheck y build** en verde.
- Migraciones **001 a 012** aplicadas y reversibles contra PostgreSQL real.
- **Pendiente**: video de entrega y validación real de Twilio (la cuenta trial está bloqueada por un incidente de Twilio).

## Deudas declaradas (leer antes de proponer nada)

1. Los routers de C-05 a C-17 ya están montados sobre adaptadores en memoria:
   reserva, lista de espera, ficha, odontograma, presupuesto, caja, señas, WhatsApp, obras sociales,
   calendario y administración. El estado se pierde al reiniciar; la aceptación de presupuesto sí
   imputa a caja (cobro pendiente si no hay medio).
2. La UI interna cubre C-05 a C-17; la edición avanzada de entidades queda fuera.
3. La cobertura de OS es configurada, no validada en vivo (PO-04) y usa `prestaciones.precio_base`; los aranceles por OS (PO-08) son fase 2.
4. Google Calendar usa un adaptador fake y `oauth_ref` ficticio; los bloqueos externos se consultan pero C-06 todavía no los lee para disponibilidad.
5. WhatsApp usa Twilio Sandbox; producción requiere número propio y plantillas aprobadas. El fallback email es un log hasta configurar SMTP.
6. Superadmin y respaldo van por CLI (`tools/superadmin.py`, `tools/backup.py`); no hay cron en el stack ni rol HTTP cross-tenant.
7. La ocupación usa la capacidad semanal declarada; sin horarios cargados devuelve `0.0`.
8. El ERD de `knowledge-base/04_modelo_de_datos.md` no incluye las tablas 007 a 012.

Detalle completo en [`README.md` § Límites declarados del alcance](README.md#límites-declarados-del-alcance).

## Lo único que necesita hacer Lautaro

1. Tener el repo actualizado.
   - Si ya lo clonó y está en `master`:
     ```bash
     git pull --ff-only
     ```
   - Si el clone es viejo o tiene conflictos:
     ```bash
     git fetch origin
     git reset --hard origin/master
     ```
   - Si nunca lo clonó:
     ```bash
     git clone https://github.com/MartinEscudero13/Turnos-Odontologia-COMPLETO.git
     cd Turnos-Odontologia-COMPLETO
     ```
2. Abrir OpenCode dentro de esa carpeta.
3. Pegar el prompt de arriba.

## Git: solo cuando vaya a commitear

No hace falta configurar Git para leer, diseñar o implementar. Solo antes de crear commits:

```bash
git config --local user.name "Lautaro Naranjo"
git config --local user.email "228012306+lauty-naranjo@users.noreply.github.com"
```

## Antes de implementar el próximo change

- Cargar `revisor-escenarios-turnos` y auditar la spec antes de escribir código. Es obligatoria para
  cualquier change que toque agenda, turnos, anticipación, pagos, caja, obras sociales o lista de espera.
- Cargar `visual-turnos` para cualquier pantalla nueva.
- Leer `PRODUCT.md`, `DESIGN.md` y `docs/design/README.md`.
- Correr la suite completa con PostgreSQL antes de archivar: `skipped == 0` es condición de cierre.
- No tocar la fundación (C-01 a C-04) ni la fundación visual (F-01) sin hablarlo con Martin.

## Guía extendida

[`docs/equipo/guia-lautaro.md`](docs/equipo/guia-lautaro.md) tiene el detalle de entorno, MCP, comandos y solución de problemas. **No hace falta leerla entera antes de empezar**; usala cuando algo no funcione.
