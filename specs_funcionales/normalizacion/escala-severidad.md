# F-NORM-SEV — Escala de Severidad Canónica

> Severidad: Float [0.0 – 10.0], normalizada por categoría.
> **Decisión D2 de AGENTS.md**: comparar severidades entre categorías
> distintas requiere escala común.

## Tablas de normalización por categoría

### Conflicto armado (fuente: ACLED `fatalities`, GDELT `goldstein_scale`)
| Víctimas fatales | Severidad |
|-----------------|-----------|
| 0 | 1.0 |
| 1–5 | 3.0 |
| 6–25 | 5.0 |
| 26–100 | 7.0 |
| 101–500 | 8.5 |
| > 500 | 10.0 |

### Terremoto (fuente: USGS `mag`)
| Magnitud Richter | Severidad |
|-----------------|-----------|
| < 4.0 | 1.0 |
| 4.0–5.0 | 3.5 |
| 5.0–6.0 | 5.5 |
| 6.0–7.0 | 7.5 |
| > 7.0 | 10.0 |

### Incendio (fuente: FIRMS `frp` en MW)
| FRP (MW) | Severidad |
|---------|-----------|
| < 50 | 2.0 |
| 50–200 | 4.0 |
| 200–1000 | 6.5 |
| > 1000 | 9.0 |

---

# F-DEDUP — Deduplicación

> Cargar junto con `E-MODEL §3` (tabla de claves naturales).

## Regla única

Antes de insertar en `events_canonical`, verificar `(source, event_id_source)`.
Si ya existe → UPDATE de `ingest_time` y `raw_payload` si cambió; no duplicar.

### FIRMS: generación de clave sintética

```python
import hashlib

def firms_event_id(row: dict) -> str:
    key = f"{row['latitude']}|{row['longitude']}|{row['acq_date']}|{row['acq_time']}|{row['satellite']}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]
```

---

# F-VAL — Validación y Quarantine

> Capa obligatoria entre ingesta y normalización.

## Reglas de validación

| Código | Condición de rechazo |
|--------|---------------------|
| `INVALID_COORDS` | `lat < -90 OR lat > 90 OR lon < -180 OR lon > 180` |
| `NULL_COORDS` | `lat IS NULL OR lon IS NULL` |
| `FUTURE_DATE` | `event_time > now() + 1h` |
| `NULL_EVENT_TYPE` | `event_type IS NULL OR event_type = ''` |
| `NEGATIVE_FATALITIES` | `fatalities < -1` (`-1` es código ACLED para "desconocido", permitido) |
| `SCHEMA_ERROR` | Fallo de parsing del payload de la fuente |

Eventos rechazados → `events_quarantine` con `rejection_code` y `raw_payload`.
Un operador o job automático puede resolverlos y reencolarlos.
