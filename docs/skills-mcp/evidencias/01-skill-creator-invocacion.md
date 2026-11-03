# Evidencia 01 — La skill creadora en acción: `quick_validate.py`

**Fecha**: 2026-11-03 · **Repo**: Turnos-Odontologia

## Qué se hizo

La skill del proyecto (`.opencode/skills/revisor-escenarios-turnos/`) se creó **adaptando** el procedimiento de
la skill propia del proyecto hermano (mismo dominio, distinto esquema de RN). La adaptación necesitó pasar por el
validador oficial que trae `vendor/skill-creator`, versionado en este repo para que la validación sea reproducible.

## Ejecución

```bash
cd docs/skills-mcp/vendor/skill-creator
py scripts\quick_validate.py "..\..\..\.opencode\skills\revisor-escenarios-turnos"
```

**Antes**:

```text
Description cannot contain angle brackets (< or >)
```

El `description` del frontmatter llevaba `<...>` (p. ej. `opsx:propose <change>`). La regla del validador prohíbe
ángulos en el description para no romper la lista de comandos del cliente.

**Después**: el frontmatter se reescribió sin ningún `<` / `>`, conservando todos los triggers:

```text
Skill is valid!
```

## Qué prueba

- La skill versionada en el repo supera la validación estructural de la skill creadora (frontmatter YAML válido,
  `name`, `description` sin ángulos).
- El vendor del creador quedó en el repo para auditar el criterio exacto aplicado, en vez de tomarlo como caja negra.

## Antes y después

| Aspecto | Antes | Después |
|---|---|---|
| Validación `quick_validate.py` | ❌ `Description cannot contain angle brackets` | ✅ `Skill is valid!` |
| Frontmatter | ángulos en `description` | ninguno |
| Triggers conservados | — | sí |

## Limitaciones

`quick_validate.py` es un validador mínimo (estructura, frontmatter). No valida la semántica del procedimiento ni el
vocabulario RN; eso se comprueba con la evidencia 04, no aquí.
