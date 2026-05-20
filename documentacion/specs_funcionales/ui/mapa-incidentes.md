# F-UI-MAP — Mapa de Incidentes (Mapbox GL JS + Deck.gl)

> Cargar junto con: `E-ARCH-FRONT` + `F-UI-DASH` + `F-UI-TIEMPO-REAL`

## 1. Inicialización

```typescript
// components/map/IncidentMap.tsx
import Map from 'react-map-gl'

const MAP_STYLE = 'mapbox://styles/mapbox/satellite-streets-v12'
const INITIAL_VIEW = { longitude: 20, latitude: 20, zoom: 2.5, pitch: 0, bearing: 0 }
```

Mapbox maneja el mapa base y todas las capas de datos (incidentes, vuelos,
buques, AOI). **Nunca añadir marcadores DOM encima del canvas**.
Vuelos y buques usan capas nativas Mapbox (symbol SDF + doble halo).
Incidentes y heatmap usan Deck.gl vía MapboxOverlay si es necesario.

## 2. Capas Deck.gl

### Capa 1 — Incidentes (ScatterplotLayer)

```typescript
new ScatterplotLayer({
  id: 'incidents-layer',
  data: incidents,
  getPosition: d => [d.canonical_point.lon, d.canonical_point.lat],
  getRadius: d => Math.max(20000, d.severity_max * 15000), // radio en metros
  getFillColor: d => hexToRgb(CATEGORY_COLORS[d.category]),
  getLineColor: d => d.status === 'updated' ? [56, 189, 248, 255] : [255,255,255,80],
  lineWidthMinPixels: 1,
  stroked: true,
  pickable: true,
  onClick: ({ object }) => selectIncident(object),
  updateTriggers: { getFillColor: [filters], getRadius: [incidents] }
})
```

### Capa 2 — Pulso en incidentes activos (animación)

```typescript
// Solo para status 'open' y 'updated'
// Implementar con AnimatedArcLayer o ScatterplotLayer con tiempo animado
// Usar requestAnimationFrame — NO Framer Motion para capas Deck.gl
new ScatterplotLayer({
  id: 'incidents-pulse',
  data: activeIncidents,
  getRadius: d => pulseRadius(d, animationTime), // radio pulsante
  getFillColor: d => [...hexToRgb(CATEGORY_COLORS[d.category]), pulseOpacity(animationTime)],
  pickable: false, // la capa de pulso no intercepta clicks
})
```

### Capa 3 — Heatmap de densidad (HeatmapLayer)

Activable desde topbar. Útil para ver zonas de alta actividad global.

```typescript
new HeatmapLayer({
  id: 'incidents-heat',
  data: incidents,
  getPosition: d => [d.canonical_point.lon, d.canonical_point.lat],
  getWeight: d => d.severity_max,
  radiusPixels: 60,
  intensity: 1,
  threshold: 0.05,
  visible: heatmapEnabled,
})
```

### Capa 4 — AOI (PolygonLayer)

```typescript
new PolygonLayer({
  id: 'aoi-layer',
  data: aois,
  getPolygon: d => d.geometry.coordinates,
  getFillColor: [56, 189, 248, 20],   // azul muy transparente
  getLineColor: [56, 189, 248, 180],  // borde azul
  lineWidthMinPixels: 1,
  pickable: true,
})
```

## 3. Interacciones

| Acción | Comportamiento |
|--------|---------------|
| Click en marcador | Seleccionar incidente → abrir panel detalle |
| Click en mapa vacío | Deseleccionar incidente |
| Hover en marcador | Tooltip con: tipo, severidad, última actualización |
| Doble click en mapa | Zoom in |
| Scroll | Zoom in/out |
| Click derecho en mapa | Menú contextual: "Crear AOI aquí" |

## 4. Tooltip de incidente (hover)

```
┌────────────────────────────┐
│ ● EARTHQUAKE               │
│ Mongolia · ADM1            │
│ SEV 8.5  CONF 7.2          │
│ Last seen: hace 4 min      │
│ Sources: usgs (×20)        │
└────────────────────────────┘
```
Fondo glassmorphism. JetBrains Mono. Sin bordes duros.

## 5. Controles de capa (HUD overlay)

Componente: `components/map/LayerControls.tsx`
Posición: esquina superior derecha del mapa.

```
[SCATTER]  [HEAT]  [AOI]  [TRACKS]
```
Botones tipo toggle con estética militar. `TRACKS` desactivado hasta implementar ADS-B/MT.

## 6. Miniatura de coordenadas (HUD overlay)

Posición: esquina inferior izquierda.

```
46.8298° N  92.8746° E   ZOOM 4.2
```
En JetBrains Mono. Actualiza en tiempo real con mousemove sobre el mapa.

## 7. Sincronización mapa ↔ filtros

Cuando el usuario aplica filtros en el topbar:
1. `filterStore` actualiza los filtros activos
2. TanStack Query refetch con los nuevos parámetros
3. Deck.gl recibe nuevos datos y re-renderiza las capas
4. El viewport del mapa **no se resetea** (el usuario no pierde su zoom/posición)

Cuando el usuario selecciona un incidente desde la lista:
1. `mapStore.selectedIncident` se actualiza
2. El mapa anima (`flyTo`) hacia `canonical_point` del incidente
3. Zoom target: 6 (suficiente para ver contexto regional)
