# E-MON — Monitorización, Métricas y SLAs

> **Spec estructural / transversal**

## 1. Métricas obligatorias por ingestor

Cada ingestor debe emitir (Prometheus labels: `source=<nombre>`):

| Métrica | Tipo | Descripción |
|---------|------|-------------|
| `ingestor_poll_total` | Counter | Polls realizados |
| `ingestor_events_fetched_total` | Counter | Eventos recibidos |
| `ingestor_errors_total` | Counter | Errores (label: `error_type`) |
| `ingestor_latency_seconds` | Histogram | Tiempo de llamada API |
| `ingestor_circuit_open` | Gauge | 1 si circuit breaker abierto |

## 2. Métricas del pipeline

| Métrica | Alerta si… |
|---------|-----------|
| `events_quarantine_unresolved` | > 100 en los últimos 30 min |
| `clustering_job_duration_seconds` | p95 > 60 s |
| `incidents_open_total` | Caída > 80% en 10 min (posible fallo pipeline) |
| `source_last_event_age_seconds` | > SLA de la fuente × 2 |

## 3. Logging estructurado

Todos los logs en JSON con campos mínimos:

```json
{
  "timestamp": "2025-01-15T10:23:45Z",
  "level": "ERROR",
  "source": "firms",
  "component": "ingestor",
  "event": "api_call_failed",
  "attempt": 3,
  "error_type": "ConnectionTimeout",
  "detail": "..."
}
```

## 4. SLAs de latencia (referencia de E-SOURCES)

Ver tabla completa en `specs/structural/data-sources.md §3`.
El dashboard de monitorización debe mostrar el lag real vs SLA por fuente.
