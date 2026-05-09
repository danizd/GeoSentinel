# F-ING-GDELT — Ingestor GDELT Cloud v2

> Cargar junto con: `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `F-NORM-CANON` + `F-DEDUP` + `F-VAL`

## Contrato

- **Base URL**: `https://gdeltcloud.com/api/v2`
- **Autenticación**: `Authorization: Bearer gdelt_sk_...`
- **Patrón**: Pull polling cada 5 min → `events_canonical`
- **Límite**: 100 calls/mes (resetea día 1 de cada mes)

## Zonas de conflicto monitorizadas

| País | Región |
|------|--------|
| Ukraine | Europa del Este |
| Israel, Palestine, Gaza | Oriente Medio |
| Syria, Yemen | Oriente Medio |
| Sudan | África |
| Mali, Burkina Faso, Niger | Sahel |
| Colombia | Latinoamérica |
| Myanmar | Sudeste Asiático |

## Filtros aplicados

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `event_family` | `conflict` | Solo eventos de conflicto |
| `has_fatalities` | `true` | Solo eventos con víctimas |
| `sort` | `recent` | Orden por fecha |
| `limit` | 100 | Máx registros por request |

## Deduplicación

Clave: `event_id_source = event.id` (identificador estable v2)

## Mapeo → `events_canonical`

| Campo GDELT Cloud | Campo canónico | Notas |
|-------------------|----------------|-------|
| `id` | `event_id_source` | Identificador v2 |
| `event_date` | `event_time` | `YYYY-MM-DD` → UTC |
| `geo.lat/lon` | `location_point` | WGS84 |
| `category` | `event_type` | Ver mapeo categorías |
| `metrics.goldstein_scale` | `severity` | Normalizar -10..+10 → 1..10 |
| `fatalities` | `fatalities` | Si `has_fatalities=true` |
| `url` | `source_url` | URL GDELT Cloud |
| `actors` | `actors` | Normalizados del JSON |

## Mapeo de categorías

| GDELT category/subcategory | event_type interno |
|---------------------------|-------------------|
| Battles | `conflict_battle` |
| Explosions | `conflict_explosion` |
| Protests | `social_protest` |
| Riots | `social_riot` |
| Civilian Violence | `conflict_atrocity` |
| Terrorism | `conflict_terror` |
| Criminal Violence | `conflict_criminal` |

## Notas importantes

- **No** usa campos legacy GDELT (CAMEO codes, SQLDATE, etc.)
- **Sí** usa campos v2: `geo`, `metrics`, `actors`, `stories`, `entities`
- Confidence basada en `goldstein_scale`: `min(10, abs(goldstein) + 5)`
- `has_fatalities=true` filtra eventos significativos

`source_independence_class = 'media_derived'` — factor confianza: ×0.5
