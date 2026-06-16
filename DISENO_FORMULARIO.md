# Sistema de diseño — Formulario público de habilitación de terceros

Especificación visual del formulario público `/registro-conductor` (pasos 1 a 7),
rediseñado bajo lineamientos **Material 3** con la identidad de **Impocoma**
(naranja operativo + azul corporativo).

- **Fuente CSS:** [`static/src/css/risk_submission.css`](static/src/css/risk_submission.css)
- **Plantillas:** [`views/website_risk_submission_templates.xml`](views/website_risk_submission_templates.xml) (armazón) + `views/website_risk_submission_step_*.xml` (cuerpos)
- **Prefijo de clases del rediseño:** `risk-vr-*` (vr = *vehicle redesign*, nombre histórico del primer paso migrado).
- **Contenedor raíz:** `<main class="risk-step-page risk-vehicle-redesign-page">`

---

## 1. Filosofía

- Una sola tarjeta centrada por paso, mucho aire (gaps de 48px), jerarquía clara.
- Color de acción = **naranja** (`#f77c00`); color de marca/títulos = **azul** (`#003b73`).
- Tipografía única **Montserrat** en todo el flujo.
- Iconografía **Material Symbols Outlined**.
- Mobile-first: 1 columna por defecto, 2 columnas desde 768px.

### Fuentes externas (cargadas en el `<head>` de la plantilla)

```
Montserrat:wght@400;500;600;700
Material Symbols Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200
```

---

## 2. Paleta de colores

Los tokens viven como variables CSS en `.risk-vehicle-redesign-page` (prefijo `--vr-`).
Solo se listan los realmente usados; el bloque define el set Material 3 completo.

### Núcleo

| Token | HEX | Uso |
|---|---|---|
| `--vr-primary` | `#f77c00` | Acción: botones, barra de progreso, iconos, bordes activos |
| (hover primario) | `#d96c00` | Hover del botón primario |
| `--vr-on-primary` | `#ffffff` | Texto/icono sobre naranja |
| `--vr-secondary` | `#003b73` | Marca: títulos, etiquetas fuertes, foco de inputs |
| `--vr-on-surface` | `#121c2c` | Texto principal |
| `--vr-on-surface-variant` | `#574235` | Texto secundario, labels, ayudas |
| `--vr-outline` | `#8b7263` | Bordes acentuados |
| `--vr-outline-variant` | `#cbd5e0` | Bordes de inputs, tarjetas, separadores |

### Superficies

| Token | HEX | Uso |
|---|---|---|
| `--vr-background` | `#f5f7fa` | Fondo de página |
| `--vr-surface` | `#ffffff` | Tarjetas, inputs |
| `--vr-surface-bright` | `#f9f9ff` | Tarjetas secundarias (semi, satélite, extra, revisión) |
| `--vr-surface-variant` | `#d9e3f9` | Pista de progreso/toggle apagado, hover botón "Anterior" |
| `--vr-surface-container` | `#e7eeff` | Contenedores suaves |
| `--vr-surface-container-high` | `#dee8ff` | Hover del botón cerrar |

### Estado / acentos

| Token | HEX | Uso |
|---|---|---|
| `--vr-error` | `#ba1a1a` | Borde/acento de error, botón eliminar |
| `--vr-error-container` | `#ffdad6` | Fondo de alertas de error |
| `--vr-on-error-container` | `#93000a` | Texto de alertas de error |
| `--vr-on-error` | `#ffffff` | Texto sobre error |
| `--vr-tertiary` | `#1b6d24` | Verde "verificado"/info |
| `--vr-primary-fixed` | `#ffdcc7` | Fondo de notas destacadas (firma única) |
| `--vr-on-primary-container` | `#582800` | Texto sobre `primary-fixed` |

> **Nota — segundo namespace.** El bloque de **verificación de correo / OTP** (pasos 5 y 6)
> conserva intencionalmente las variables legacy `--risk-*` definidas en `.risk-step-page`
> (`--risk-primary: #f77c00`, `--risk-secondary: #003b73`, `--risk-fill: #f0f3ff`, etc.).
> Como los HEX coinciden con los `--vr-*`, el resultado es visualmente congruente.

---

## 3. Tipografía

Familia única: **Montserrat, sans-serif**. Escala (tamaño / interlineado / peso):

| Rol | Tamaño | Interlineado | Peso | Extras |
|---|---|---|---|---|
| Título app bar (`h1`) | 24px | 32px | 700 | 20px/28px en ≤640px |
| Título de tarjeta (`h2`) | 20px | 28px | 600 | color `--vr-secondary` |
| Encabezado de sección (`h3`) | 20px | 28px | 600 | satélite / subsección / anticipos |
| Encabezado bloque pequeño (`h3` semi, extra, copiar) | 14px | 20px | 600 | MAYÚSCULAS, `letter-spacing: 0.05em` |
| Etiqueta de campo (`label`) | 12px | 16px | 500 | MAYÚSCULAS |
| Valor de input / textarea | 16px | 24px | 400 | — |
| Placa (vehículo / remolque) | 20px | 28px | 600 | MAYÚSCULAS, color `--vr-secondary` |
| Meta de progreso | 14px | 20px | 600 | `letter-spacing: 0.05em` |
| Texto de botón | 14px | 20px | 600 | `letter-spacing: 0.05em`, MAYÚSCULAS |
| Ayuda / nota | 14px | 20px | 400–600 | color `--vr-on-surface-variant` |
| Radio / opción | 16px | 24px | 400 | — |

---

## 4. Espaciado, radios y sombras

### Radios de borde

| Elemento | Radio |
|---|---|
| Tarjeta principal | `12px` |
| Inputs, selects, textarea, botones, tarjetas secundarias | `8px` |
| Toggle, badges, botón cerrar (circular) | `9999px` (pill) |

### Sombras

| Elemento | Sombra |
|---|---|
| App bar | `0 1px 3px rgba(0,0,0,0.08)` |
| Tarjeta principal | `0 4px 20px rgba(0,0,0,0.05)` |
| Botón "Siguiente/Enviar" | `0 4px 6px rgba(0,0,0,0.12)` → hover `0 8px 14px rgba(0,0,0,0.14)` |
| Botón "Anterior" | `0 1px 3px rgba(0,0,0,0.08)` |
| Foco de input/select/textarea | `0 0 0 2px rgba(0,59,115,0.2)` (anillo azul) |

### Espaciado clave

| Contexto | Valor |
|---|---|
| Ancho máx. del contenido | `768px` (centrado) |
| Padding del `main` | `48px 16px 80px` (≥768px: laterales `64px`; ≤640px: top `32px`) |
| App bar | alto `80px`, padding `0 16px` (≥768px: `0 64px`) |
| Tarjeta principal (padding) | `24px` (≥768px: `48px`) |
| Separación entre secciones (`.risk-vr-fields`) | `48px` (≤640px: `32px`) |
| Rejilla de campos (`.risk-vr-grid`) | gap `24px` |
| Campo individual (label↔input) | gap `4px` |
| Progreso (margen inferior) | `48px` (≤640px: `32px`) |
| Acciones (margen superior) | `48px` |

---

## 5. Responsive (breakpoints)

| Breakpoint | Cambios |
|---|---|
| **Base (móvil)** | 1 columna; app bar y main con padding `16px`; tarjeta `24px`. |
| **≥ 768px** | App bar y main padding lateral `64px`; tarjeta padding `48px`; rejillas a **2 columnas** (`repeat(2, minmax(0,1fr))`); revisión a 2 columnas. |
| **≤ 640px** | Top del main `32px`; gaps de secciones `32px`; cabeceras (`semi-head`, `anticipos`, `declare-row`, `copy-owner-head`) pasan a columna; subsecciones top `32px`. |

> La especificación visual omite la barra de navegación inferior móvil (no se usa en este formulario).

---

## 6. Layout del armazón (todos los pasos)

Orden vertical dentro de `.risk-vehicle-redesign-page`:

1. **App bar** (`.risk-vr-appbar`) — sticky arriba, alto `80px`, `border-bottom: 4px solid --vr-primary`.
   - Izquierda: icono Material (color primario, 30px) + `h1` "Habilitación Terceros".
   - Derecha: botón cerrar circular (`.risk-vr-close`, 40×40, → `/`).
2. **Progreso** (`.risk-vr-progress`) — dos líneas de meta (izq. "Paso/Firma…", der. nombre del paso) + pista (`.risk-vr-progress-track`, alto `8px`) con relleno (`.risk-vr-progress-value`, ancho dinámico, bg primario, transición `500ms`).
3. **Tarjeta** (`.risk-vr-card`) dentro de un `<form>`:
   - Cabecera (`.risk-vr-card-title`): icono primario 30px + `h2` (azul), separador inferior.
   - Alerta de error (`.risk-vr-error`) si aplica.
   - Cuerpo del paso (`.risk-vr-fields`, columna con gap 48px).
4. **Acciones** (`.risk-vr-actions`): "Anterior" (si paso > 1) a la izquierda, "Siguiente/Enviar" siempre a la derecha (`margin-left:auto`).

---

## 7. Inventario de componentes

### 7.1 Campo de texto — `.risk-vr-field`
Columna con `gap: 4px`: `label` (12px MAYÚS) + `input/select/textarea`.
- Input: ancho 100%, **min-height 50px**, padding 12px, borde `1px --vr-outline-variant`, radio 8px, texto 16px.
- Foco: borde `--vr-secondary` + anillo `0 0 0 2px rgba(0,59,115,0.2)`.
- `.risk-vr-field-full`: ocupa toda la fila en rejilla (`grid-column: 1 / -1`).
- **Placa** (`#vehicle_plate`, `#semi_trailer_plate`): 20px, 600, MAYÚSCULAS, azul.

### 7.2 Rejilla — `.risk-vr-grid`
1 columna → 2 columnas en ≥768px; gap 24px.

### 7.3 Select — `.risk-vr-select-wrap`
`select` con `appearance:none`, padding derecho 44px e icono `expand_more` absoluto a la derecha.
Usado en los desplegables de **propietarios adicionales** (paso 2): tipo de documento y relación.
(El campo **"Empresa Satelital"** del paso 1 es un **input de texto libre**, no un `select`.)

### 7.4 Campo de contraseña — `.risk-vr-password`
`input` con padding derecho 48px + botón mostrar/ocultar (icono `visibility`/`visibility_off`).

### 7.5 Toggle (interruptor) — `.risk-vr-toggle`
Pista 48×24, "perilla" checkbox 24×24 con `border: 4px`.
- Apagado: pista `--vr-surface-variant`, borde `--vr-outline-variant`.
- Encendido (`:checked`): `translateX(100%)`, pista y borde `--vr-primary`.
- Acompañado de etiquetas "NO" / "SÍ" (la "SÍ" en naranja, `.risk-vr-toggle-yes`).
- Usado en: firma única (paso 5), semi/remolque (paso 1), "registrado en licencia" (paso 2).

### 7.6 Tarjeta secundaria — `.risk-vr-semi`
Bloque destacado: fondo `--vr-surface-bright`, borde `1px --vr-outline-variant`, radio 8px, padding 24px, gap 24px. Cabecera (`.risk-vr-semi-head`) con título+ayuda a la izquierda y toggle a la derecha.

### 7.7 Radios — `.risk-vr-radio-row` / `.risk-vr-radio`
Fila flexible (gap 12–24px) de opciones; cada radio 18×18 con `accent-color: --vr-primary`.
(Override necesario: el selector genérico `.risk-vr-field input` fuerza min-height 50px; `.risk-vr-radio input[type=radio]` lo restablece.)

### 7.8 Subsección con título — `.risk-vr-subsection`
Separador superior (`border-top 1px`), `padding-top: 48px` (≤640px: 32px), `h3` (20px) con icono primario. Usada para "Rastreo Satelital", "Declaraciones", "Referencias", "Firma".

### 7.9 Fila pregunta + respuesta — `.risk-vr-declare-row`
Pregunta (`p`, flex 1, min 240px) + radios; en ≤640px pasa a columna.

### 7.10 Propietarios adicionales — `.risk-vr-extra-owners`
Contenedor `surface-bright`; filas `.risk-vr-extra-owner` separadas por `border-top`; botón secundario `.risk-vr-add-owner` (contorno naranja, hover relleno); botón eliminar `.risk-vr-extra-owner-remove` (contorno rojo `--vr-error`, hover relleno).

### 7.11 Canvas de firma — `.risk-vr-signature-pad`
- `canvas`: ancho 100%, **alto 190px**, borde `1px --vr-outline-variant`, radio 8px, `touch-action:none`.
- Estado `.is-locked` (correo sin verificar): overlay `.risk-vr-signature-lock` (inset 0, fondo `rgba(249,249,255,0.78)`, icono `lock` + texto) y canvas/botón al 40% sin eventos.
- Estado `.is-disabled` (estudio vigente): pad al 45%, canvas sin eventos.
- Botón limpiar `.risk-vr-clear-signature` (contorno, icono `ink_eraser`).

### 7.12 Verificación de correo / OTP — `.risk-verify*` (estilo legacy `--risk-*`)
Tarjeta con `border-left: 4px` (naranja → verde al verificar), badge de estado (`Pendiente`/`Verificado`), pasos numerados (círculos naranjas), input OTP grande (`.risk-otp-input`, 180px, 22px, `letter-spacing: 0.5em`, tabular), botón enviar (`.risk-btn-secondary`) y verificar (`.risk-action-btn`). **Se mantiene intacto** por ser crítico y ya on-brand.

### 7.13 Tarjetas de resumen — `.risk-vr-review-card` (paso 7)
`surface-bright`, padding 24px; `h3` con icono + separador; lista `dl` en rejilla `auto 1fr` (etiqueta MAYÚS gris a la izquierda, valor a la derecha). Rejilla `.risk-vr-review-grid` 1→2 columnas.

### 7.14 Notas y alertas

| Clase | Uso | Estilo |
|---|---|---|
| `.risk-vr-error` | Error de paso | borde/fondo `error-container`, texto `on-error-container`, 600 |
| `.risk-vr-info` | Info de firma | borde `--vr-tertiary`, fondo `#e7f6e7`, texto verde |
| `.risk-vr-note` | Aviso/nota gris | 14px 600, `on-surface-variant` |
| `.risk-vr-single-note` | Nota firma única | `border-left 4px primary`, fondo `primary-fixed` |
| `.risk-vr-signature-note` | Nota legal de firmas | borde `outline-variant`, fondo `surface-bright` |
| `.risk-vr-terms-card` | Política (paso 4) | `border-left 4px primary`, fondo `surface-bright` |
| `.risk-vr-terms-accept` | Casilla de aceptación | borde, fondo `surface`, checkbox 22×22 |
| `.risk-vr-terms-warning` | Aviso cliente (paso 4) | reusa `.risk-vr-error` |

### 7.15 Botones

| Clase | Tipo | Estilo |
|---|---|---|
| `.risk-vr-next` | Primario | bg `--vr-primary`, texto blanco, min-height 56px, padding 16×32, radio 8px, sombra; hover `#d96c00`; `margin-left:auto` |
| `.risk-vr-back` | Secundario | bg `--vr-surface`, texto azul, borde `outline-variant`; hover `surface-variant` |
| `.risk-vr-add-owner`, `.risk-vr-terms-open`, `.risk-vr-clear-signature` | Contorno | borde + texto de color, hover relleno |
| `.risk-vr-extra-owner-remove` | Peligro | contorno rojo `--vr-error`, hover relleno |

---

## 8. Mapa de pasos

Definido en el dict `vr_steps` del armazón. La barra de progreso usa "de 4" para la captura
de datos (1–4) y una fase de "Firma X de 2" para las firmas (5–6).

| Paso | Icono app bar | Icono tarjeta | Meta (izq.) | Título | Progreso |
|---|---|---|---|---|---|
| 1 Vehículo | `local_shipping` | `directions_car` | Paso 1 de 4 | Información del Vehículo | 25% |
| 2 Propietario | `person` | `badge` | Paso 2 de 4 | Información del Propietario / Tenedor / Poseedor | 50% |
| 3 Conductor | `id_card` | `person` | Paso 3 de 4 | Información del Conductor | 75% |
| 4 Términos | `gavel` | `fact_check` | Paso 4 de 4 | Aceptación de Términos y Autorizaciones | 100% |
| 5 Firma propietario | `draw` | `draw` | Firma 1 de 2 | Firma del Propietario / Tenedor | 50% |
| 6 Firma conductor | `draw` | `draw` | Firma 2 de 2 | Firma del Conductor | 100% |
| 7 Revisión | `task_alt` | `fact_check` | Revisión final | Revisión de la Solicitud | 100% |

Botón de acción: **"SIGUIENTE"** (icono `arrow_forward`) en pasos 1–6, **"ENVIAR"** (icono `send`) en el paso 7.

---

## 9. Apéndice — comportamiento ligado al diseño (hooks)

Clases/IDs/atributos que el JS necesita; **no renombrar** al ajustar estilos.

| Archivo JS | Hooks |
|---|---|
| `risk_submission_vehicle.js` | `#has_semi_trailer_toggle`, `#has_semi_trailer`, `[data-semi-trailer-field]`, `.btn-toggle-password` |
| `risk_submission_owner.js` | `#same_owner_on_license(_toggle)`, `[data-registered-owner-field]`, `#extra-owners-list`, `#add-extra-owner`, `#extra-owner-template`, `[data-extra-owner-row]`, `[data-extra-owner-remove]` |
| `risk_submission_driver.js` | `#risk-owner-data` (+ `data-owner-*`), `#risk-copy-owner-to-driver`, `#risk-copy-owner-feedback` |
| `risk_submission_terms.js` | `#risk-open-terms`, `#risk-terms-modal` (`.is-open`), `#risk-close-terms`, `#risk-understand-terms`, `#risk-terms-check`, `#risk-terms-confirmed`, `#risk-terms-accept`, `#risk-terms-warning`, `#risk-submit-button` |
| `risk_submission_signatures.js` | `[data-signature-pad]`, `#{owner,driver}-signature-canvas/-input`, `[data-clear-signature]`, `input[name='*_has_valid_study']`, `#single_owner_driver_signature(_toggle)`, `[data-single-signature-note]`, `.is-locked`/`.is-disabled` |
| `risk_otp.js` | `.risk-otp-send[data-otp-sent]`, `.risk-otp-send-label`, `.risk-verify-meta[data-otp-expires]` |

---

## 10. Convenciones para mantener el sistema

- **Colores:** usar siempre tokens `--vr-*`; no incrustar HEX nuevos.
- **Tarjetas secundarias** (cualquier bloque agrupado): `--vr-surface-bright` + borde `--vr-outline-variant` + radio 8px + padding 24px.
- **Secciones nuevas dentro de un paso:** envolver en `.risk-vr-subsection` con `h3` (20px) e icono primario.
- **Radios/checkbox dentro de `.risk-vr-field`:** recordar el override de `min-height` (ver 7.7).
- **Agregar un paso al rediseño:** añadir entrada al dict `vr_steps` (icono app bar, icono tarjeta, meta, título, progreso) y el `t-call` del cuerpo en el armazón.
