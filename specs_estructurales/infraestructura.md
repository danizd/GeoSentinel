# E-INFRA — Infraestructura

> **Spec estructural / transversal**

## 1. Entornos

| Entorno | Stack | Notas |
|---------|-------|-------|
| `dev` | Docker Compose | PostgreSQL + Redis Streams + FastAPI |
| `staging` | Kubernetes (1 nodo) | Kafka single-broker |
| `prod` | Kubernetes (HA) | Kafka cluster, PostgreSQL RDS o CloudNative PG |

## 2. Retry y circuit breaker (valores de referencia)

```python
RETRY_MAX_ATTEMPTS = 5
RETRY_BACKOFF_BASE_SECONDS = 2   # espera = base^attempt + jitter
RETRY_MAX_WAIT_SECONDS = 120
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5   # fallos consecutivos para abrir
CIRCUIT_BREAKER_RECOVERY_SECONDS = 300  # tiempo hasta half-open
```

## 3. Variables de entorno globales

```dotenv
INCIDENT_WINDOW_DAYS=30          # ventana deslizante activa
INCIDENT_STALE_HOURS=72          # horas sin actividad → status=stale
CLUSTERING_INTERVAL_SECONDS=300  # frecuencia del job de clustering
DB_URL=postgresql+asyncpg://...
KAFKA_BOOTSTRAP_SERVERS=...
```
