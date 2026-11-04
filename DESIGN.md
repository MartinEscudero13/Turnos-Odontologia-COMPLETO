# Design

> Visual authority for Turnos-Odontologia. This is a working system, not a moodboard.
> PRODUCT.md is the product truth; this file owns the visual world.

## World

**La agenda como instrumento de precisión.** La interfaz toma la lógica de una ficha de turno y una regla de horarios: líneas finas, marcas de tiempo, papel cálido, tinta verde profunda y un acento clínico. No es un dashboard genérico de tarjetas flotantes ni una landing de startup.

### Personality

- Clínica, no fría.
- Precisa, no rígida.
- Humana, sin infantilizar.
- Con textura de papel y señalética de consultorio, sin nostalgia vintage.

## Palette

| Token | Hex | Uso |
|---|---|---|
| `--paper` | `#F4F1E9` | Fondo público y papel |
| `--surface` | `#FFFDF7` | Superficies elevadas |
| `--ink` | `#17231E` | Texto principal |
| `--ink-soft` | `#4E5E56` | Texto secundario |
| `--line` | `#D6D1C4` | Líneas, divisores, inputs |
| `--teal` | `#0C6B5A` | Acción principal, foco, éxito |
| `--teal-deep` | `#07493E` | Hover y fondos de marca |
| `--mint` | `#D7E9DF` | Superficie de confirmación |
| `--amber` | `#C98A2E` | Pendiente, atención |
| `--coral` | `#BF5140` | Error, cancelación |
| `--white` | `#FFFFFF` | Contraste puntual |

No usar pares genéricos tipo crema + terracota ni negro + verde ácido. La combinación anterior nace del instrumental odontológico, el papel de ficha y la señalética de consultorio.

## Typography

- **Display:** `Bricolage Grotesque` (600/700), tracking negativo leve.
- **Body/UI:** `Source Sans 3` (400/500/600), buena legibilidad en tablas y formularios.
- Fallback: `Georgia` para display y `system-ui` para body.
- Escala: `--step--1: .78rem`, `--step-0: 1rem`, `--step-1: 1.25rem`, `--step-2: 1.6rem`, `--step-3: clamp(2rem, 5vw, 3.6rem)`.
- Línea de lectura ≤ 72 caracteres. Nada de labels en mayúsculas decorativas ni acentos en una sola palabra del titular.

## Layout

- **Público:** máximo 1180px; hero asimétrico; una “ficha de turno” como objeto estructural; CTA visible sin scroll en mobile.
- **Login:** dos columnas en desktop (contexto + formulario); una columna en mobile; el formulario no parece una tarjeta SaaS genérica.
- **Interno:** rail de 248px + topbar; contenido de alta densidad; sidebar colapsable en tablet.
- **Grid:** 12 columnas, gutters 16/24/32px, radios 2px/10px/999px.
- **Textura:** líneas de horario repetidas y marcas de 15 minutos como estructura, no como ornamento.

## Components

### Button
Variantes `primary`, `secondary`, `quiet`, `danger`. Altura mínima 44px. Foco de 3px con offset. Nunca usar sólo color para comunicar estado.

### Field
Label persistente, hint opcional, error asociado con `aria-describedby`. Input de 48px en mobile. El error se muestra debajo y con icono/texto.

### Surface
Papel con borde de 1px, sin sombras grandes. La elevación se reserva para diálogos y la ficha de turno.

### StatusBadge
`success` (mint/teal), `pending` (amber), `danger` (coral), `neutral` (line). Incluye texto, no sólo color.

### EmptyState
Título, explicación y una acción. Para el shell interno: “Todavía no hay una página de agenda en esta fundación” con CTA a volver al inicio.

### PageHeader
Título, contexto y acciones. En interno, una línea de tenant/rol visible sin ruido.

## Page recipes

### `/`
Hero con promesa concreta, ficha de turno con hora y profesional, tres capacidades verificables y CTA a `/login`. Estado de API al pie del hero, no como tarjeta protagonista.

### `/login`
Columna editorial con “Tu agenda empieza con una credencial” y tres hechos del producto; formulario con tenant, email, password, loading, error y link de regreso. Sin registro ni login de paciente en v1.

### `/app`
Rail interno con Agenda/Pacientes/Catálogos/Caja/Reportes como destinos futuros (deshabilitados con `aria-disabled`), tenant visible, logout y empty state de fundación.

### 404
“Ese turno no existe” con retorno a `/`; composición sobre la grilla de horarios. Sin humor excesivo.

## Motion

- Entrada de página: un único fade/translate de 240ms.
- Interacciones: 120ms ease-out.
- Sin hover en todas las tarjetas.
- `prefers-reduced-motion: reduce` desactiva transforms y duraciones.

## Anti-patterns

- Cards idénticas con sombra `rgba(0,0,0,.1)`.
- Hero de “big number + gradient + stats” sin relación con el producto.
- Gradientes decorativos sin función.
- Iconos sin label en acciones críticas.
- Tablas apretadas sin jerarquía o acciones escondidas.
- Colores de estado sin texto/icono.
- Copia genérica: “potenciá tu gestión”, “solución integral”, “revolucioná tu consultorio”.

## Accessibility

- Focus visible en todo control.
- Contraste AA mínimo.
- `aria-live` para health/login/errores.
- Skip link en shells.
- Teclado: Tab/Shift+Tab, Enter/Espacio, Escape en diálogos.
- Nunca usar `placeholder` como único label.

## Design MCP

- **Figma MCP** (primario si hay archivo): `https://mcp.figma.com/mcp`, OAuth; leer frames/variables y convertir contexto a tokens/componentes. Escribir al canvas puede requerir seat Full y está en beta.
- **Stitch MCP** (opcional): setup project-specific; sirve para generar/explorar pantallas, no para leer un design system existente.
- **Code-first**: si no hay MCP autenticado, la skill `visual-turnos` implementa desde este documento y verifica con screenshots. No bloquear el change.
