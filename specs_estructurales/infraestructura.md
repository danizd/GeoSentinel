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

## 3. Docker Compose (entorno dev)

```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: geosentinel
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: geosentinel
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DB_URL=postgresql+asyncpg://geosentinel:${DB_PASSWORD}@postgres:5432/geosentinel
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
      - VITE_MAPBOX_TOKEN=${MAPBOX_TOKEN}
    depends_on:
      - api

volumes:
  pgdata:
```

## 4. Variables de entorno globales

```dotenv
INCIDENT_WINDOW_DAYS=30          # ventana deslizante activa
INCIDENT_STALE_HOURS=72          # horas sin actividad → status=stale
CLUSTERING_INTERVAL_SECONDS=300  # frecuencia del job de clustering
DB_URL=postgresql+asyncpg://...
KAFKA_BOOTSTRAP_SERVERS=...
```
