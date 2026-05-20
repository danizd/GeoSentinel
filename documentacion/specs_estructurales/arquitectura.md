# E-ARCH — Arquitectura del Sistema

> **Spec estructural / transversal** — Leer siempre que se añadan componentes,
> se modifique el flujo de datos o se integren nuevas fuentes.

---

## 1. Visión general

Sistema de agregación y nowcasting de incidentes en tiempo real.
Arquitectura de capas desacopladas comunicadas mediante bus de eventos.

```
┌─────────────────────────────────────────────────────────────┐
│  FUENTES EXTERNAS                                           │
│  GDELT · ACLED · FIRMS · USGS · ADS-B · MarineTraffic · …  │
└────────────────────────┬────────────────────────────────────┘
                         │ pull / webhook
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA 1 — INGESTA                                           │
│  ingestors/<source>_ingestor.py                             │
│  · Retry + backoff exponencial                              │
│  · Circuit breaker por fuente                               │
│  · Emit → bus de eventos (Kafka topic: raw_events)          │
└────────────────────────┬────────────────────────────────────┘
                         │ Kafka / Redis Streams
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA 2 — VALIDACIÓN Y QUARANTINE                           │
│  jobs/validation_job.py                                     │
│  · Reglas de validación por fuente                          │
│  · Coords imposibles, fechas futuras, campos nulos críticos │
│  · OK → topic: validated_events                             │
│  · KO → tabla: events_quarantine (con motivo)               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA 3 — NORMALIZACIÓN                                     │
│  normalizers/<source>_mapper.py                             │
│  · Mapeo a events_canonical                                 │
│  · Normalización UTC obligatoria aquí                       │
│  · Asignación severity inicial y source_independence_class  │
│  · Deduplicación por clave natural de fuente                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA 4 — CLUSTERING E INCIDENTES                           │
│  jobs/clustering_job.py  ·  jobs/incident_lifecycle_job.py  │
│  · DBSCAN espacio-temporal (ver F-CLUST)                    │
│  · Máquina de estados del incidente (ver F-LC)              │
│  · Actualización de severidad y confidence agregados        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  BASE DE DATOS  — PostgreSQL 16 + PostGIS 3.4               │
│  raw_events_* · events_quarantine · events_canonical        │
│  incidents · geometries · aoi · corrections_audit           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA 5 — API                                               │
│  FastAPI  ·  /incidents  /aoi  /corrections  /health        │
│  Autenticación JWT · Rate limiting · Versionado /v1/        │
└─────────────────────────────────────────────────────────────┘
```

## 2. Principios de diseño

- **Tolerancia a fallos por fuente**: el fallo de un ingestor no debe
  propagar errores al resto del pipeline. Cada ingestor es independiente.
- **Desacoplamiento ingesta/procesamiento**: el bus de eventos (Kafka/Redis)
  actúa como buffer. El procesamiento puede ir más lento que la ingesta
  sin perder datos.
- **Estado en base de datos, no en memoria**: ningún componente guarda
  estado local que no esté persistido. Los jobs son re-ejecutables (idempotentes).
- **Ventana deslizante**: el sistema mantiene activos los últimos N días
  (configurable por `INCIDENT_WINDOW_DAYS`). El histórico se archiva.

## 3. Decisiones tecnológicas

| Componente | Tecnología | Alternativa MVP |
|------------|-----------|-----------------|
| Bus de eventos | Apache Kafka | Redis Streams |
| Base de datos | PostgreSQL 16 + PostGIS 3.4 | — (no negociable) |
| API framework | FastAPI 0.111+ | — |
| Runtime | Python 3.12 | — |
| Contenedores | Docker + Kubernetes | Docker Compose (dev) |
| Scheduler | Airflow 2.x | APScheduler (MVP) |

## 4. Flujo de datos por tipo de fuente

| Fuente | Patrón | Frecuencia | Topic Kafka |
|--------|--------|-----------|-------------|
| GDELT | Pull polling | Cada 5 min | `raw.gdelt` |
| USGS | Pull polling | Cada 3 min | `raw.usgs` |
| FIRMS | Pull polling | Cada 1 h | `raw.firms` |
| ACLED | Pull batch | Diaria | `raw.acled` |
| ADS-B | Pull polling | Cada 1 min | `raw.adsb` |
| MarineTraffic | Pull polling | Cada 5 min | `raw.marinetraffic` |
| Liveuamap | Pull polling (riesgo alto) | Cada 5 min | `raw.liveuamap` |
