# F-ING-USGS — Ingestor USGS Terremotos

> Cargar junto con: `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `F-NORM-CANON` + `F-DEDUP` + `F-VAL`

## Contrato
- **URL correcta** (D10 — error original corregido):
  ```
  https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=...&minmagnitude=4.0
  ```
- **Patrón**: Pull polling cada 3 min → topic `raw.usgs`
- **Filtro**: `minmagnitude=4.0` para reducir ruido de microsismicidad

## Deduplicación
```python
event_id_source = properties["ids"].split(",")[0].strip(",")
```

## Mapeo → `events_canonical`

| Campo USGS | Campo canónico | Notas |
|------------|----------------|-------|
| `properties.time` | `event_time` | Epoch ms → `datetime.fromtimestamp(ms/1000, tz=UTC)` |
| `geometry.coordinates[0]` | `lon` | |
| `geometry.coordinates[1]` | `lat` | |
| `geometry.coordinates[2]` | `source_refs` | Profundidad en km |
| `properties.mag` | `severity` | Normalizar con `F-NORM-SEV §earthquake` |
| `properties.type` | `event_type` | Ver `F-NORM-CANON §2` |
| `properties.place` | `source_refs` | Descripción textual de ubicación |

`source_independence_class = 'sensor'` — factor confianza: ×2.0
