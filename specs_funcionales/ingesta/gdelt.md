# F-ING-GDELT — Ingestor GDELT Cloud Events v2

> Cargar junto con: `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `F-NORM-CANON` + `F-DEDUP` + `F-VAL`

## Contrato
- **Endpoint**: `https://api.gdeltcloud.com/v2/` — parámetros completos en `E-SOURCES §2.1`
- **Patrón**: Pull polling cada 5 min → topic Kafka `raw.gdelt`
- **Filtro recomendado**: `event_family=conflict`
- **Auth**: header `X-API-Key` ← `GDELT_API_KEY`

## Deduplicación
Clave: `event_id_source = GLOBALEVENTID::text`

## Mapeo → `events_canonical`

| Campo GDELT | Campo canónico | Notas |
|-------------|----------------|-------|
| `SQLDATE` | `event_time` | `YYYYMMDD` → `YYYY-MM-DD 00:00:00 UTC` |
| `ActionGeo_Lat/Long` | `location_point` | WGS84 |
| `EventCode` CAMEO | `event_type` | Ver `F-NORM-ACTORS` |
| `GoldsteinScale` | `severity` | Normalizar con `F-NORM-SEV` |
| `SOURCEURL` | `source_url` | |

`source_independence_class = 'media_derived'` — factor confianza: ×0.5

## Tests obligatorios
Timeout · HTTP 429 (respetar `Retry-After`) · JSON malformado · coordenadas nulas
