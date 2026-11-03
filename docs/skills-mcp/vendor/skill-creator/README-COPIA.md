# Copia versionada de `skill-creator`

Esta carpeta es una copia de la skill creadora que usamos, guardada dentro del repositorio porque la
instalamos **fuera** de él (en el directorio global del agente). No es código nuestro y no se modifica:
sirve como referencia y respaldo de la versión exacta con la que generamos nuestra skill.

## Procedencia

| Dato | Valor |
|---|---|
| Skill | `skill-creator` |
| Repositorio de origen | https://github.com/anthropics/skills (carpeta `skills/skill-creator`) |
| Licencia | Apache-2.0 (ver `LICENSE.txt`) |
| Copiada el | 29/10/2026 |
| Instalación local de origen | `C:\Users\ramir\.config\opencode\skills\skill-creator\` |
| SHA-256 de `SKILL.md` | `E030E7685E26283B4A76F5202AA3AE8516FB41DDE799BE5AE8EA6393EC009FE9` |

## Instalación reproducible

Con el CLI de skills:

```bash
npx skills add https://github.com/anthropics/skills --skill skill-creator
```

Instalación manual (equivalente): copiar esta carpeta a la ubicación de skills del agente. opencode busca
skills en:

- proyecto: `.opencode/skills/<name>/SKILL.md`
- global: `~/.config/opencode/skills/<name>/SKILL.md`

En Windows la ruta global equivale a `C:\Users\<usuario>\.config\opencode\skills\`.

## Requisitos

- Node.js (para el CLI `npx skills`) o copia manual de la carpeta.
- Python 3 + `pyyaml` si se quiere correr `scripts/quick_validate.py`.
  ```bash
  python -m pip install --user pyyaml
  ```

## Comprobación

```bash
python scripts/quick_validate.py <ruta-a-la-skill-a-validar>
```

Salida esperada: `Skill is valid!`. También se puede verificar que el agente la lista entre las skills
disponibles y que responde al invocarla por nombre.
