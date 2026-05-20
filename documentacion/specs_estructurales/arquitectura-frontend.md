# E-ARCH-FRONT — Arquitectura Frontend

> **Spec estructural / transversal** — Obligatoria en cualquier tarea de frontend.

## 1. Stack tecnológico (no negociable)

| Capa | Tecnología | Versión mínima |
|------|-----------|----------------|
| Framework | React + TypeScript | 18.x / 5.x |
| Build | Vite | 5.x |
| Routing | React Router | v6 |
| Mapa base | Mapbox GL JS | 3.x |
| Capas de datos | Deck.gl | 9.x |
| Estado global | Zustand | 4.x |
| Datos / polling | TanStack Query (React Query) | 5.x |
| Estilos | Tailwind CSS | 3.x |
| Iconos | Lucide React | latest ← único, no mezclar con Heroicons |
| Animaciones | Framer Motion | 11.x (uso moderado) |
| Tipografía | JetBrains Mono | via Google Fonts o self-hosted |
| Tests | Vitest + React Testing Library | latest |
| Mapa wrapper | react-map-gl | 7.x |
| Dibujo geo | @mapbox/mapbox-gl-draw | 1.x |
| Virtualización | @tanstack/react-virtual | 3.x |
| Fechas | date-fns | 3.x |

## 2. Estructura de directorios

```
src/
├── api/              # Clientes de API y hooks de TanStack Query
│   ├── incidents.ts
│   ├── aoi.ts
│   └── corrections.ts
├── components/       # Componentes reutilizables
│   ├── map/          # Componentes Mapbox + Deck.gl
│   ├── panels/       # Paneles laterales, widgets
│   └── ui/           # Primitivos (Badge, Button, Tooltip...)
├── stores/           # Stores Zustand
│   ├── mapStore.ts   # Viewport, capas activas, selección
│   ├── filterStore.ts # Filtros activos de incidentes
│   └── authStore.ts  # Token JWT, usuario
├── hooks/            # Hooks personalizados
├── pages/            # Vistas de React Router
├── types/            # Tipos TypeScript globales
│   ├── incident.ts
│   ├── aoi.ts
│   └── api.ts
└── utils/            # Helpers puros (formateo, colores, coordenadas)
```

## 3. Estética C2 táctico

### Paleta de colores (CSS variables en `tailwind.config.ts`)
```
--color-bg-base:        #0a0e1a   /* fondo principal */
--color-bg-panel:       #0f1525   /* paneles */
--color-bg-glass:       rgba(15,21,37,0.75)  /* glassmorphism */
--color-border-glow:    rgba(56,189,248,0.3) /* bordes luminosos */
--color-accent-blue:    #38bdf8   /* acento primario */
--color-accent-amber:   #fbbf24   /* alertas medias */
--color-accent-red:     #ef4444   /* alertas críticas */
--color-accent-green:   #22c55e   /* estado OK */
--color-text-primary:   #e2e8f0
--color-text-secondary: #64748b
```

### Glassmorphism — clase Tailwind base
```css
.panel-glass {
  background: var(--color-bg-glass);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border-glow);
  border-radius: 8px;
}
```

### Tipografía
- **JetBrains Mono** para: coordenadas, timestamps, IDs, métricas numéricas, feed de eventos
- **Sistema sans-serif** (Inter o Tailwind default) para: etiquetas, títulos de panel, navegación

## 4. Estilo Mapbox — tema oscuro táctico
```typescript
const MAP_STYLE = 'mapbox://styles/mapbox/satellite-streets-v12'
// Alternativa self-hosted oscuro: 'mapbox://styles/mapbox/dark-v11'
```
Variable de entorno: `VITE_MAPBOX_TOKEN` (nunca hardcodeada)

## 5. Arquitectura de datos en tiempo real

**Patrón: polling con TanStack Query** (no WebSocket en esta versión)

```typescript
// Intervalo de refresco por recurso
const POLL_INCIDENTS   = 30_000   // 30 segundos
const POLL_STATS       = 60_000   // 1 minuto
const POLL_SOURCES     = 120_000  // 2 minutos (latencia fuentes)
```

Cuando el usuario cambia filtros → invalidar query → refetch inmediato.

## 6. Gestión de estado — responsabilidades Zustand vs TanStack Query

| Qué | Dónde |
|-----|-------|
| Datos del servidor (incidentes, AOI) | TanStack Query |
| Viewport del mapa (center, zoom) | Zustand `mapStore` |
| Filtros activos (category, severity...) | Zustand `filterStore` |
| Incidente seleccionado | Zustand `mapStore` |
| Token JWT | Zustand `authStore` (+ localStorage) |
| Estado de modales / paneles | useState local |

## 7. Variables de entorno

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_MAPBOX_TOKEN=
VITE_POLL_INCIDENTS_MS=30000
```

## 8. Reglas de animación (Framer Motion)

**Permitido:**
- Pulso en hotspots activos (`open`, `updated`)
- Fade-in de panel de detalle al seleccionar incidente
- Transición de badges de estado

**Prohibido:**
- Page transitions elaboradas
- Animaciones en la tabla/lista de incidentes (degrada rendimiento con 100+ items)
- Cualquier animación que bloquee interacción con el mapa

## 9. Rendimiento — reglas obligatorias

- Deck.gl ScatterplotLayer para > 1000 puntos (nunca SVG/DOM para esto)
- Lista de incidentes: virtualización con `@tanstack/react-virtual` si > 100 items
- Imágenes y tiles: lazy loading
- Bundle: code splitting por ruta con `React.lazy`

## 10. Despliegue

### Dockerfile multi-stage

```dockerfile
# Stage 1: build
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### nginx.conf con fallback SPA

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Variables de entorno en producción

```dotenv
VITE_API_BASE_URL=https://api.geosentinel.example.com
VITE_MAPBOX_TOKEN=pk.xxx
```
