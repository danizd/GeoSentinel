# F-ING-FIRMS — Ingestor FIRMS NASA

> Cargar junto con: `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `F-NORM-CANON` + `F-DEDUP` + `F-VAL`

## Contrato
- **URL dinámica** (D9 — nunca hardcodear región ni API key):
  `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/{PRODUCT}/{lon_min,lat_min,lon_max,lat_max}/{DAYS}/`
- `PRODUCT`: `VIIRS_SNPP_NRT` (375m) o `MODIS_NRT` (1km) — según resolución requerida
- **Patrón**: Pull cada 1–3 horas, bbox dinámico por AOI activo → topic `raw.firms`

## Deduplicación (clave sintética)
```python
sha256(f"{lat}|{lon}|{acq_date}|{acq_time}|{satellite}")[:32]
```

## Mapeo → `events_canonical`

| Campo FIRMS | Campo canónico | Notas |
|-------------|----------------|-------|
| `latitude/longitude` | `location_point` | WGS84 |
| `acq_date` + `acq_time` | `event_time` | `YYYYMMDD` + `HHMM` → UTC |
| `frp` | `severity` | Normalizar con `F-NORM-SEV §wildfire` |
| `satellite` | `source_refs` | Incluir satélite en refs |
| `type` | `event_type` | 0=wildfire_hotspot · 1=volcano · 2=other · 3=offshore |

- `category = 'wildfire'` para type=0
- `location_accuracy_km`: VIIRS=0.375, MODIS=1.0
- Filtrar: solo procesar registros con `confidence IN ('nominal','high')`

`source_independence_class = 'sensor'` — factor confianza: ×2.0
