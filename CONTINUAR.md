# CONTINUAR — Lautaro

> Esta es la entrada corta para la IA de Lautaro. No es un manual de instalación.

## Prompt para pegar en OpenCode

```text
Leé completo CONTINUAR.md, AGENTS.md, AUTHORS.md y docs/equipo/guia-lautaro.md.

No modifiques nada todavía.
Resumime:
1) qué está terminado,
2) qué falta para C-06,
3) el plan TDD de las 50 tareas,
4) qué preguntas abiertas bloquean la implementación.

Después esperá mi confirmación antes de tocar archivos.
```

## Estado

- C-01 a C-04, C-05 y F-01: **terminados y archivados**.
- TP2 skill + MCP: **terminado y pusheado**.
- **C-06 `reserva-online-publica`: siguiente trabajo, 0/50 tareas.**
- Video del TP2: **no hace falta ahora**; queda para cuando se pida.

## Lo único que necesita hacer Lautaro

1. Tener el repo actualizado.
   - Si ya lo clonó y está en `master`, no hace falta nada.
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

## Antes de implementar C-06

- Cargar `revisor-escenarios-turnos` y auditar `openspec/changes/c-06-reserva-online-publica`.
- Cargar `visual-turnos` para cualquier pantalla nueva.
- Leer `PRODUCT.md`, `DESIGN.md` y `docs/design/README.md`.
- No tocar C-01 a C-04 ni la fundación visual sin hablarlo con Martin.

## Guía extendida

[`docs/equipo/guia-lautaro.md`](docs/equipo/guia-lautaro.md) tiene el detalle de entorno, MCP, comandos y solución de problemas. **No hace falta leerla entera antes de empezar**; usala cuando algo no funcione.
