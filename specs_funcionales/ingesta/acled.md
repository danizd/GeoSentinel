# F-ING-ACLED — Ingestor ACLED

> Cargar junto con: `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `F-NORM-CANON` + `F-DEDUP` + `F-VAL`

## Contrato
- **Endpoint**: `https://api.acleddata.com/acled/read` — parámetros en `E-SOURCES §2.2`
- **Patrón**: Pull batch diario → topic `raw.acled`
- **⚠️ Lag real**: 7–28 días por región. Implementar backfill para detectar actualizaciones retroactivas.
- **Auth**: `?key=ACLED_API_KEY&email=ACLED_EMAIL`
- **Licencia**: CC BY-NC 4.0 — solo uso no comercial

## Deduplicación
Clave: `event_id_source = data_id::text`
ACLED puede actualizar registros existentes (corregir `fatalities`) → hacer UPDATE, no inserción duplicada.

## Mapeo → `events_canonical`

| Campo ACLED | Campo canónico | Notas |
|-------------|----------------|-------|
| `event_date` | `event_time` | `YYYY-MM-DD` → `00:00:00 UTC` |
| `latitude/longitude` | `location_point` | EPSG:4326 directo |
| `event_type` | `event_type` | Ver `F-NORM-CANON §2` |
| `fatalities` | `fatalities` | `-1` = desconocido → permitido, no rechazar |
| `geo_precision` | `location_accuracy_km` | 1→0.1 · 2→5 · 3→25 · 4→100 · 5→500 |
| `actor1/actor2` | `actors` | Ver `F-NORM-ACTORS` |
| `admin1/admin2` | `admin1/admin2` | |
| `country` | `country_iso2` | Convertir a ISO 3166-1 alpha-2 |

`source_independence_class = 'field_reported'` — factor confianza: ×1.5
