# F-CLUST — Clustering Espacio-Temporal de Incidentes

> **Spec funcional** — Cargar junto con `E-MODEL`, `F-NORM-SEV`, `F-NORM-CONF`
> y `F-LC` para implementar o modificar el job de clustering.

---

## 1. Problema

Agrupar eventos de múltiples fuentes que describen el mismo hecho físico
en un único incidente canónico, evitando tanto la fragmentación (mismo
evento = múltiples incidentes) como la sobremezcla (eventos distintos = uno).

---

## 2. Algoritmo base: DBSCAN con métrica mixta normalizada

### 2.1 Métrica de distancia

**⚠️ Decisión de diseño D4 de AGENTS.md**: mezclar km y horas sin
normalizar produce un epsilon arbitrario. La métrica combinada es:

```
d(e1, e2) = w_space · (haversine_km(e1, e2) / KM_MAX)
           + w_time  · (|e1.event_time - e2.event_time| / HOURS_MAX)
```

Donde los valores de referencia por categoría son:

| Categoría | `KM_MAX` | `HOURS_MAX` | `w_space` | `w_time` | `epsilon` |
|-----------|---------|------------|---------|---------|---------|
| `conflict` | 50 km | 48 h | 0.6 | 0.4 | 0.15 |
| `wildfire` | 20 km | 24 h | 0.7 | 0.3 | 0.20 |
| `earthquake` | 100 km | 2 h | 0.5 | 0.5 | 0.10 |
| `disaster_natural` | 75 km | 72 h | 0.5 | 0.5 | 0.15 |
| `mobility` | 30 km | 6 h | 0.8 | 0.2 | 0.12 |

> Los valores son punto de partida calibrable. Documentar cambios aquí.

### 2.2 Restricción adicional: misma categoría

Eventos de categorías distintas **nunca** se agrupan en el mismo incidente,
independientemente de la proximidad espacio-temporal.

### 2.3 `min_samples` para DBSCAN

```python
MIN_SAMPLES_BY_CLASS = {
    'sensor': 1,          # un hotspot FIRMS ya es incidente
    'field_reported': 1,
    'media_derived': 2,   # requiere al menos 2 fuentes media-derived
}
```

Si el cluster tiene solo fuentes `media_derived`, `min_samples=2`.

---

## 3. Flujo del job de clustering

```python
# Pseudocódigo — implementar en jobs/clustering_job.py

def run_clustering_job():
    # 1. Obtener eventos nuevos no asignados (event_canonical sin incident_id)
    new_events = fetch_unassigned_events(since=last_run_time)

    # 2. Por categoría (procesar por separado)
    for category in CATEGORIES:
        cat_events = [e for e in new_events if e.category == category]
        if not cat_events:
            continue

        # 3. Obtener incidentes activos de esta categoría como "semillas"
        active_incidents = fetch_active_incidents(category=category)

        # 4. Intentar asignar cada evento a incidente existente
        for event in cat_events:
            best_incident = find_closest_incident(
                event, active_incidents,
                km_max=KM_MAX[category],
                hours_max=HOURS_MAX[category],
                epsilon=EPSILON[category]
            )
            if best_incident:
                assign_event_to_incident(event, best_incident)
                # → dispara transición a 'updated' en F-LC
            else:
                # 5. Si no encaja en ninguno, crear incidente nuevo
                create_new_incident(event)
```

---

## 4. Geometría canónica del incidente

- **`canonical_point`**: centroide ponderado por `confidence` de los eventos del cluster
- **`canonical_geometry`**: convex hull si hay ≥ 3 puntos distintos, else buffer de 5 km

```python
def compute_canonical_point(events: list[Event]) -> Point:
    # Centroide ponderado por confidence
    total_weight = sum(e.confidence for e in events)
    lat = sum(e.lat * e.confidence for e in events) / total_weight
    lon = sum(e.lon * e.confidence for e in events) / total_weight
    return Point(lon, lat)
```

---

## 5. Métricas agregadas del incidente tras clustering

| Campo en `incidents` | Cálculo |
|----------------------|---------|
| `severity_max` | `max(events.severity)` |
| `severity_latest` | `severity` del evento más reciente |
| `confidence` | Ver `F-NORM-CONF` §3 (ponderado por independencia) |
| `fatalities_total` | `max(events.fatalities)` (no suma; evitar doble conteo) |
| `source_count` | `len(set(events.source))` |
| `observation_count` | `len(events)` |

> ⚠️ `fatalities_total` usa `MAX`, no `SUM`, para evitar contar
> las mismas víctimas múltiples veces cuando distintas fuentes reportan
> el mismo evento con el mismo número de muertos.
