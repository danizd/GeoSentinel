# F-UI-DASH — Dashboard Principal C2

> Cargar junto con: `E-ARCH-FRONT` + `F-UI-MAP` + `F-UI-TIEMPO-REAL`

## 1. Layout general

```
┌─────────────────────────────────────────────────────┐
│  DASHBOARD                                          │
│  ┌───────────────────────────────────────────────┐ │
│  │ TOPBAR → §2                                    │ │
│  │ ┌───────────────────────────────────────────┐ │ │
│  │ │ Mapa interactivo (Deck.gl sobre Mapbox)    │ │ │
│  │ │                                           │ │ │
│  │ │                                           │ │ │
│  │ └───────────────────────────────────────────┘ │ │
│  │ ┌────────────────────┬──────────────────────┐ │ │
│  │ │ PANEL LATERAL → §3  │ Panel detalle → §4   │ │ │
│  │ │ Lista incidentes    │                      │ │ │
│  │ │                     │                      │ │ │
│  │ └────────────────────┴──────────────────────┘ │ │
│  │ STATUSBAR → §5                                 │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

Layout responsive: en pantallas < 1024px el panel lateral se convierte en drawer deslizante.

## 2. Topbar

Componente: `components/panels/Topbar.tsx`

- **Logo / nombre**: `GEO SENTINEL` en JetBrains Mono
- **Filtros globales** (afectan mapa + lista simultáneamente):
  - `category`: multiselect con badges de color por categoría
  - `status`: chips `OPEN` `UPDATED` `STALE` (default: open + updated)
  - `min_severity`: slider 0–10
  - `since`: selector de ventana temporal (1h / 6h / 24h / 7d)
- **Indicador de última actualización**: `UPDATED 23s AGO` parpadeante en verde
- **Botón de refresco manual**: icono Lucide `RefreshCw`

## 3. Panel lateral — Lista de incidentes

Componente: `components/panels/IncidentList.tsx`

- Ordenado por `last_seen DESC`
- Cada item muestra:
  ```
  [BADGE_CATEGORY]  EVENT_TYPE
  admin1, country · last_seen relativo ("hace 4 min")
  SEV █████░░░░░ 5.2   CONF ███████░░░ 7.1
  SOURCES: gdelt · usgs
  ```
- Click en item → selecciona incidente → centra mapa + abre panel de detalle
- Hover → highlight del marcador en mapa
- Virtualización con `@tanstack/react-virtual` para listas > 100 items

## 4. Panel de detalle del incidente

Componente: `components/panels/IncidentDetail.tsx`

Se muestra al seleccionar un incidente, reemplaza la lista (o se superpone en mobile).

```
┌─ INCIDENT DETAIL ────────────────── [×] ─┐
│ ID: d47e34fc  STATUS: OPEN               │
│ TYPE: earthquake  CAT: disaster_natural  │
│                                          │
│ LOCATION                                 │
│ 46.8298° N  92.8746° E  (Mongolia)       │
│                                          │
│ TIMELINE                                 │
│ First seen: 2026-05-08 11:38 UTC         │
│ Last seen:  2026-05-09 04:57 UTC         │
│                                          │
│ METRICS                                  │
│ Severity max   █████████░  8.5           │
│ Confidence     ████████░░  7.2           │
│ Observations   20                        │
│                                          │
│ SOURCES                                  │
│ [SENSOR] usgs ×20                        │
│                                          │
│ [MARK FALSE POSITIVE]  [CLOSE INCIDENT]  │
└──────────────────────────────────────────┘
```

Todos los valores numéricos y coordenadas en JetBrains Mono.
Los botones de acción requieren scope `corrections:write` — ocultar si no tiene permiso.

## 5. Statusbar — Estado del sistema

Componente: `components/panels/Statusbar.tsx`

```
USGS ●verde  FIRMS ●verde  GDELT ●amarillo  ACLED ●gris
QUARANTINE: 0   INCIDENTS OPEN: 14   [JetBrains Mono]
```

- **Verde**: última ingesta < SLA definido en `E-SOURCES §3`
- **Amarillo**: última ingesta entre SLA y SLA×2
- **Rojo**: última ingesta > SLA×2 o circuit breaker abierto
- **Gris**: fuente desactivada (Liveuamap)

Datos obtenidos de `GET /v1/health/sources` (endpoint a implementar en backend).

## 6. Colores por categoría de incidente

```typescript
export const CATEGORY_COLORS = {
  conflict:         '#ef4444',  // rojo
  wildfire:         '#f97316',  // naranja
  earthquake:       '#a855f7',  // púrpura
  disaster_natural: '#06b6d4',  // cyan
  mobility:         '#38bdf8',  // azul claro
  humanitarian:     '#fbbf24',  // ámbar
  other:            '#64748b',  // gris
}
```

## 7. Colores por status de incidente

```typescript
export const STATUS_COLORS = {
  open:          '#22c55e',  // verde
  updated:       '#38bdf8',  // azul pulsante
  stale:         '#fbbf24',  // ámbar
  closed:        '#64748b',  // gris
  false_positive:'#ef4444',  // rojo tachado
}
```
