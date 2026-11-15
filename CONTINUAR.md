# CONTINUAR — Lautaro

> Esta es la entrada corta para la IA de Lautaro. No es un manual de instalación.

## Prompt para pegar en OpenCode

```text
Leé completo CONTINUAR.md, AGENTS.md, AUTHORS.md y docs/equipo/guia-lautaro.md.

No modifiques nada todavía.
Resumime:
1) qué está terminado hasta C-11,
2) qué falta para el próximo change (C-12 obras sociales),
3) qué deudas de integración están declaradas y en qué orden conviene cerrarlas,
4) qué preguntas abiertas bloquean la implementación.

Después esperá mi confirmación antes de tocar archivos.
```

## Estado (2026-11-15)

- C-01 a C-12, C-14, C-15 (parcial) y F-01 a F-05: **terminados, verificados y archivados** (19 changes).
- **API demo**: C-05 a C-15 montados en `create_app` sobre adaptadores en memoria.
- TP2 skill + MCP: **terminado y pusheado**.
- Backend: **787 passed + 51 skipped** en local · **838 passed + 0 skipped** con `C02_DATABASE_URL`.
- Migraciones **001 a 011** aplicadas y reversibles contra PostgreSQL real.
- **Único pendiente del roadmap**: C-13 `whatsapp-recordatorios`, bloqueado por PO-03 (no hay proveedor/BSP definido).
- C-15 se cerró en alcance parcial: admin, configuración, exportación y KPIs; WhatsApp, superadmin, respaldo automático y ocupación quedan declarados.
- Video del TP2: **no hace falta ahora**; queda para cuando se pida.

## Deudas declaradas (leer antes de proponer nada)

1. Los routers de C-05 a C-12 y C-14 ya están montados sobre adaptadores en memoria:
   reserva, lista de espera, ficha, odontograma, presupuesto, caja, señas, obras sociales y calendario. El
   estado se pierde al reiniciar y las aceptaciones de presupuesto no escriben en caja.
2. La UI de C-09, C-10, C-11, C-12, C-14 y C-15 está diferida a `C-09-UI`, `C-10-UI`, `C-11-UI`, `C-12-UI`, `C-14-UI` y `C-15-UI`; esos changes no existen todavía.
3. La cobertura de OS es configurada, no validada en vivo (PO-04) y usa `prestaciones.precio_base`; los aranceles por OS (PO-08) son fase 2.
4. Google Calendar usa un adaptador fake y `oauth_ref` ficticio; los bloqueos externos se consultan pero C-06 todavía no los lee para disponibilidad.
5. C-15 es parcial: sin superadmin cross-tenant, sin job de respaldo y sin KPI de ocupación (requiere capacidad por horarios).
6. El ERD de `knowledge-base/04_modelo_de_datos.md` no incluye las tablas 007 a 011.

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
