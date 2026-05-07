# F-DEDUP — Deduplicación por Fuente

> Cargar junto con: `E-MODEL §3`

## Regla única
Antes de insertar en `events_canonical`, verificar `UNIQUE(source, event_id_source)`.
- Si ya existe → `UPDATE ingest_time` si cambió `raw_payload`; no duplicar.
- Si no existe → INSERT.

## Claves naturales por fuente

| Fuente | Clave natural |
|--------|---------------|
| GDELT | `GLOBALEVENTID::text` |
| ACLED | `data_id::text` |
| FIRMS | `sha256(lat\|lon\|acq_date\|acq_time\|satellite)[:32]` |
| USGS | `properties.ids.split(",")[0].strip(",")` |
| ADS-B | `hex + ':' + t` |
| MarineTraffic | `mmsi + ':' + TIMESTAMP` |
| Liveuamap | `id::text` |

## Ventana de deduplicación
Para detectar actualizaciones retroactivas (especialmente ACLED), consultar registros de las últimas `DEDUP_WINDOW_DAYS=60` antes de asumir que un `event_id_source` es nuevo.
