# Evidencia visual — fundación

Capturas generadas con Playwright y API mockeada (health `UP` + login exitoso), sin backend ni datos reales.

| Página | 375 | 768 | 1440 |
|---|---|---|---|
| Home | `home-375.png` | `home-768.png` | `home-1440.png` |
| Login | `login-375.png` | `login-768.png` | `login-1440.png` |
| Panel | `app-375.png` | `app-768.png` | `app-1440.png` |
| 404 | `404-375.png` | `404-768.png` | `404-1440.png` |

## Cómo regenerar

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 4173
# en otra terminal
cd frontend
npm run visual:screenshots
```

El script `frontend/scripts/visual-screenshots.mjs` verifica overflow horizontal en cada breakpoint y falla si una página lo tiene.

## Resultado de auditoría

- **Home**: Lighthouse 1.00 accesibilidad / 1.00 best practices / 1.00 SEO.
- **Login**: Lighthouse 1.00 / 1.00 / 1.00.
- **404**: Lighthouse 1.00 / 1.00 / 1.00.
- **Panel**: revisado por captura visual; requiere sesión mockeada para Lighthouse.
- **MCP de diseño usado**: ninguno; flujo code-first. Figma/Stitch quedan documentados y opcionales.

## Límites

- No se corrieron E2E contra el backend real en esta pasada; login fue mockeado para capturas.
- No se probó con lector de pantalla físico; sí estructura de labels, foco y criterios axe/Lighthouse.
