# F-API-INC — API de Incidentes

> Cargar junto con: `E-ARCH` + `E-SEC` + `E-STD`

## Endpoint principal
`GET /v1/incidents`

## Parámetros de query

| Param | Tipo | Descripción |
|-------|------|-------------|
| `bbox` | `float,float,float,float` | `lon_min,lat_min,lon_max,lat_max` |
| `category` | `string` | `conflict,wildfire,earthquake,...` |
| `status` | `string` | `open,updated,stale,closed` (default: `open,updated`) |
| `since` | `datetime` ISO8601 | Filtro por `last_seen` |
| `min_severity` | `float` [0–10] | Umbral mínimo |
| `min_confidence` | `float` [0–10] | Umbral mínimo |
| `sources` | `string[]` | Filtrar por fuentes (`gdelt,acled,...`) |
| `include_fp` | `bool` | Incluir `false_positive` (default: false) |
| `page` | `int` | Paginación (default: 1) |
| `limit` | `int` | Máx 100 (default: 20) |
| `aoi_id` | `uuid` | Filtrar por AOI |

## Respuesta
```json
{
  "total": 42,
  "page": 1,
  "incidents": [
    {
      "incident_id": "uuid",
      "status": "open",
      "category": "conflict",
      "event_type": "conflict_battle",
      "canonical_point": {"lon": 36.8, "lat": 47.1},
      "first_seen": "2025-01-10T14:23:00Z",
      "last_seen": "2025-01-15T09:11:00Z",
      "severity_max": 7.5,
      "confidence": 6.2,
      "fatalities_total": 45,
      "sources": ["gdelt", "acled"],
      "observation_count": 12
    }
  ]
}
```

## Restricciones de datos (ver `E-SEC` y `AGENTS.md §7`)
- No exponer `hex` ADS-B ni `MMSI` de MarineTraffic en campos visibles
- Datos ACLED: solo en contextos no comerciales
