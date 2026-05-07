# F-NORM-CANON — Modelo Canónico y Normalización UTC

> **Spec funcional** — Obligatoria para todos los mappers.

## 1. Regla UTC (Decisión D1 de AGENTS.md)

**Toda fecha se normaliza a UTC en el mapper, nunca después.**

| Fuente | Campo original | Formato | Conversión requerida |
|--------|---------------|---------|----------------------|
| ACLED | `event_date` | `YYYY-MM-DD` (sin hora) | Asignar `00:00:00 UTC`. Añadir nota en `source_refs` |
| GDELT | `SQLDATE` | `YYYYMMDD` | Ídem, `00:00:00 UTC` |
| FIRMS | `acq_date` + `acq_time` | `YYYY-MM-DD` + `HHMM` | Combinar como UTC directo |
| USGS | `properties.time` | Epoch ms | `datetime.fromtimestamp(ms/1000, tz=UTC)` |
| ADS-B | `t` | Epoch Unix (s) | `datetime.fromtimestamp(t, tz=UTC)` |
| MarineTraffic | `TIMESTAMP` | ISO 8601 con offset | Convertir a UTC |

## 2. Mapeo de `event_type` por fuente

### ACLED → interno
```python
ACLED_TYPE_MAP = {
    "Battles": "conflict_battle",
    "Explosions/Remote violence": "conflict_explosion",
    "Violence against civilians": "conflict_civilian_violence",
    "Protests": "social_protest",
    "Riots": "social_riot",
    "Strategic developments": "conflict_strategic",
}
```

### USGS → interno
```python
USGS_TYPE_MAP = {
    "earthquake": "earthquake",
    "explosion": "explosion_seismic",
    "quarry blast": "quarry_blast",
}
```

### FIRMS → interno
Todos los hotspots: `event_type = "wildfire_hotspot"`, `category = "wildfire"`

## 3. Contrato de salida del mapper

Todo mapper debe devolver un objeto compatible con el schema Pydantic
`EventCanonicalCreate` (definido en `schemas/event_schema.py`):

```python
class EventCanonicalCreate(BaseModel):
    event_id_source: str
    source: str
    event_time: datetime       # SIEMPRE timezone-aware UTC
    ingest_time: datetime      # SIEMPRE timezone-aware UTC
    event_type: str
    category: str
    latitude: float
    longitude: float
    location_accuracy_km: float | None = None
    country_iso2: str | None = None
    admin1: str | None = None
    actors: list[dict] | None = None
    fatalities: int | None = None
    severity: float | None = None
    confidence: float | None = None
    source_url: str | None = None
    source_refs: list[str] | None = None
    is_rumor: bool = False
```
