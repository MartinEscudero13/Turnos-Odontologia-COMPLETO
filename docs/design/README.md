# Diseño visual — Turnos-Odontologia

Esta carpeta documenta la fundación visual y las integraciones de diseño.

- Fuente de producto: [`PRODUCT.md`](../../PRODUCT.md)
- Fuente visual: [`DESIGN.md`](../../DESIGN.md)
- Skill del proyecto: [`.opencode/skills/visual-turnos/SKILL.md`](../../.opencode/skills/visual-turnos/SKILL.md)
- Brief reutilizable: [`page-brief-template.md`](page-brief-template.md)

## MCP de diseño

### Figma MCP (primario si hay archivo)

Figma ofrece un servidor remoto oficial:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "figma": {
      "type": "remote",
      "url": "https://mcp.figma.com/mcp",
      "enabled": true
    }
  }
}
```

Pasos:

1. Copiar el bloque de [`figma-mcp.example.json`](figma-mcp.example.json) al `opencode.json` del proyecto o al global.
2. Reiniciar el cliente y autenticar la cuenta de Figma cuando lo pida.
3. Verificar con `opencode mcp list`.
4. Compartir con el agente el link de selección del frame (`Copy link to selection`), no una captura.
5. Usar Figma para leer frames, variables, componentes y contexto de diseño. Escribir al canvas puede requerir un asiento Full y está en beta; no es requisito para implementar.

**No commitear** tokens, cookies, capturas con PHI ni configuraciones vivas de la cuenta. El repo sólo versiona el ejemplo.

### Stitch MCP (opcional)

Stitch es una herramienta de Google Labs para generar/explorar pantallas. Su MCP no tiene una URL pública fija: la URL y credenciales salen del flujo de setup de Stitch.

- Config de ejemplo: [`stitch-mcp.example.json`](stitch-mcp.example.json), reemplazando el placeholder.
- Skills oficiales: [`google-labs-code/stitch-skills`](https://github.com/google-labs-code/stitch-skills).
- Usarlo para generar pantallas o explorar variantes, no para “leer” un design system inexistente.
- Si no está configurado, la skill sigue en modo **code-first**.

## Fallback code-first

La fundación visual no depende de un MCP. `visual-turnos` puede implementar y auditar desde `DESIGN.md`, con screenshots y tests. En el cierre hay que declarar:

```text
MCP usado: figma | stitch | ninguno
```

## Quality gate

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Y revisión visual en 375 / 768 / 1440, foco, teclado, contraste AA, `prefers-reduced-motion` y sin overflow horizontal.
