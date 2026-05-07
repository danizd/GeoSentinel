# F-UI — Dashboard de Incidentes

> Cargar junto con: `F-API-INC` + `F-API-AOI` + `E-SEC`

## Vista principal
Panel dividido en dos áreas: mapa interactivo (70%) + lista de incidentes (30%).

## Componentes obligatorios

### Mapa
- Capa base: OpenStreetMap o Mapbox
- Marcadores por incidente con color por `category` y tamaño por `severity_max`
- Clustering visual para zonas densas
- Click en marcador → panel lateral con detalle del incidente

### Lista de incidentes
- Ordenada por `last_seen DESC`
- Filtros: `category`, `status`, `min_severity`, `sources`
- Búsqueda por texto en `admin1`, `country_iso2`
- Paginación: 20 items por página

### Panel de detalle del incidente
- Campos: `incident_id`, `status`, `category`, `event_type`, `first_seen`, `last_seen`
- Severidad y confianza como indicadores visuales (barras 0–10)
- Lista de fuentes con badge por `source_independence_class`
- Timeline de observaciones (`linked_event_ids`)
- Botones de corrección (requiere scope `corrections:write`)
- Enlace "detectado por X hace Y · confirmado por Z"

### Indicadores de estado del sistema
- Latencia actual vs SLA por fuente (verde/amarillo/rojo)
- Contador de eventos en quarantine sin resolver

## Estado de incidente — código de color
| Status | Color |
|--------|-------|
| `open` | Verde |
| `updated` | Azul |
| `stale` | Amarillo |
| `closed` | Gris |
| `false_positive` | Rojo tachado |
