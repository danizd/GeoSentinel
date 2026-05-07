# GeoSentinel

Sistema de agregacion y monitorizacion de incidentes geoespaciales en tiempo real.
Agrega eventos de multiples fuentes (FIRMS NASA, USGS, GDELT, ACLED...), los normaliza
a un modelo canonico, aplica clustering espacio-temporal y los expone via API REST.

---

## Estado de implementacion

### Implementado

| Componente | Descripcion |
|------------|-------------|
| **Modelo de datos** | ORM SQLAlchemy para todas las tablas (`events_canonical`, `incidents`, `aoi`, `corrections_audit`, `events_quarantine`, `sources_metadata`) |
| **Ingestor FIRMS** | Pull polling con retry/backoff exponencial, filtro por AOI bbox, manejo de rate limiting 429 |
| **Ingestor USGS** | Pull polling cada 3 min, manejo de rate limiting 429, filtro `minmagnitude=4.0` |
| **Normalizacion FIRMS** | Mapper CSV a `EventCanonicalCreate`, severidad por FRP (MW), deduplicacion SHA-256 |
| **Normalizacion USGS** | Mapper GeoJSON a `EventCanonicalCreate`, severidad por magnitud Richter, deduplicacion por `properties.ids` |
| **Validacion / Quarantine** | 6 reglas de rechazo (`INVALID_COORDS`, `NULL_COORDS`, `FUTURE_DATE`, `NULL_EVENT_TYPE`, `NEGATIVE_FATALITIES`, `SCHEMA_ERROR`), insercion en `events_quarantine` |
| **Deduplicacion** | Upsert por `(source, event_id_source)` con actualizacion de `ingest_time` |
| **Clustering** | DBSCAN espacio-temporal con metrica mixta normalizada, parametros por categoria, `canonical_point` como centroide ponderado por `confidence` |
| **Ciclo de vida del incidente** | Maquina de estados completa (`open -> updated -> stale -> closed / false_positive`), transiciones validas/invalidas, auditoria |
| **API Incidents** | `GET /v1/incidents` con filtros: `bbox`, `category`, `status`, `since`, `min_severity`, `min_confidence`, `sources`, `aoi_id`, `include_fp` + paginacion |
| **API AOI** | CRUD completo `/v1/aoi`, geometria real desde PostGIS, filtro espacial `ST_Intersects` en `/incidents` |
| **API Corrections** | `POST /v1/corrections` con tipos `false_positive`, `close`, `reclassify`, `relocate`, `merge`; auditoria append-only |
| **Confianza** | Calculo ponderado por clase de independencia de fuente con penalizacion por ventana de 6h para `media_derived` |

### Pendiente / Gaps conocidos

| Componente | Estado |
|------------|--------|
| **JWT / Autenticacion** | No implementado -- endpoints publicos actualmente |
| **Rate limiting API** | No implementado |
| **Metricas Prometheus** | No implementado |
| **Circuit breaker** | No implementado |
| **Bus de eventos Kafka/Redis** | MVP directo -- ingestores llaman al pipeline sincronamente |
| **Job de purga/archivado** | No implementado -- tabla `incidents_archive` no creada |
| **`canonical_point` como GEOMETRY** | Almacenado como WKT `String` -- pendiente migracion a `GEOMETRY(POINT,4326)` |

---

## Requisitos previos

- **Python 3.12+** (gestionado con `uv`)
- **Docker** y **Docker Compose**
- **uv** -- gestor de entorno: `pip install uv`
- API key de NASA FIRMS: https://firms.modaps.eosdis.nasa.gov/api/map_key/

---

## Puesta en marcha

### 1. Base de datos (PostgreSQL 16 + PostGIS 3.4)

```bash
docker compose up -d
```

Espera a que el healthcheck pase (`pg_isready`). La BD queda disponible en `localhost:5432`.

### 2. Entorno Python

```bash
uv sync
```

### 3. Variables de entorno

Crea un archivo `.env` en la raiz del proyecto (nunca commitear):

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/geosentinel
FIRMS_MAP_KEY=tu_api_key_aqui
GDELT_API_KEY=tu_gdelt_api_key
ACLED_API_KEY=tu_acled_api_key
ACLED_EMAIL=tu_email_registrado_en_acled
```

Carga el `.env` antes de ejecutar cualquier comando:

```bash
# Linux / macOS
export $(cat .env | xargs)
```

```powershell
# Windows PowerShell
Get-Content .env | ForEach-Object { $k,$v = $_ -split '=',2; [System.Environment]::SetEnvironmentVariable($k,$v) }
```

### 4. Migraciones de base de datos

```bash
uv run alembic upgrade head
```

Esto crea todas las tablas en la BD.

### 5. Arrancar la API

```bash
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

La API queda disponible en `http://localhost:8000`.
Documentacion interactiva (Swagger UI): `http://localhost:8000/docs`
Schema OpenAPI (ReDoc): `http://localhost:8000/redoc`

---

## Seed de datos de prueba

Para insertar las fuentes de datos y 3 incidentes de ejemplo (conflicto, terremoto, incendio):

```bash
curl http://localhost:8000/v1/seed
```

---

## Endpoints principales

### Health

```bash
# Estado del servicio
curl http://localhost:8000/v1/health

# Estado de la BD
curl http://localhost:8000/v1/health/db
```

### Incidentes

```bash
# Listar incidentes activos (open + updated)
curl "http://localhost:8000/v1/incidents"

# Filtrar por categoria
curl "http://localhost:8000/v1/incidents?category=wildfire"

# Filtrar por bounding box (lon_min,lat_min,lon_max,lat_max)
curl "http://localhost:8000/v1/incidents?bbox=-10.0,35.0,5.0,45.0"

# Filtrar por severidad minima y multiples fuentes
curl "http://localhost:8000/v1/incidents?min_severity=6.0&sources=firms,usgs"

# Incluir false_positives con paginacion
curl "http://localhost:8000/v1/incidents?include_fp=true&page=2&limit=50"

# Incidentes desde una fecha (status abiertos, actualizados y stale)
curl "http://localhost:8000/v1/incidents?since=2025-01-10T00:00:00Z&status=open,updated,stale"

# Detalle de un incidente por ID
curl "http://localhost:8000/v1/incidents/{incident_id}"
```

### AOI (Areas of Interest)

```bash
# Crear un AOI -- Espana peninsular
curl -X POST http://localhost:8000/v1/aoi \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Espana Peninsular",
    "description": "Monitorizacion de la Peninsula Iberica",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[
        [-9.5, 35.9], [4.3, 35.9], [4.3, 43.8], [-9.5, 43.8], [-9.5, 35.9]
      ]]
    },
    "categories": ["conflict", "wildfire"],
    "min_severity": 3.0
  }'

# Listar todos los AOIs activos
curl http://localhost:8000/v1/aoi

# Obtener AOI por ID
curl http://localhost:8000/v1/aoi/{aoi_id}

# Incidentes dentro de un AOI (filtro espacial ST_Intersects)
curl "http://localhost:8000/v1/aoi/{aoi_id}/incidents"

# Actualizar AOI
curl -X PUT http://localhost:8000/v1/aoi/{aoi_id} \
  -H "Content-Type: application/json" \
  -d '{"min_severity": 5.0, "is_active": true}'

# Desactivar AOI (soft delete -- nunca DELETE fisico)
curl -X DELETE http://localhost:8000/v1/aoi/{aoi_id}
```

### Correcciones (Human-in-the-Loop)

```bash
# Marcar incidente como falso positivo
curl -X POST http://localhost:8000/v1/corrections \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "{incident_id}",
    "correction_type": "false_positive",
    "reason": "Evento duplicado de fuente no verificada"
  }'

# Cerrar un incidente manualmente
curl -X POST http://localhost:8000/v1/corrections \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "{incident_id}",
    "correction_type": "close",
    "reason": "Incidente confirmado como finalizado"
  }'

# Reclasificar categoria de un incidente
curl -X POST http://localhost:8000/v1/corrections \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "{incident_id}",
    "correction_type": "reclassify",
    "reason": "Clasificacion incorrecta por fuente mediatica",
    "new_category": "wildfire",
    "new_event_type": "wildfire_hotspot"
  }'
```

---

## Obtencion de datos reales

### Ingestor USGS (terremotos >= 4.0)

Descarga y procesa eventos de las ultimas 24 horas:

```bash
uv run python -c "
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ingestors.usgs_ingestor import USGSIngestor

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/geosentinel'))
Session = sessionmaker(bind=engine)

with Session() as session:
    ingestor = USGSIngestor()
    result = ingestor.poll(session)
    print(result)
"
```

### Ingestor FIRMS (incendios activos)

Requiere `FIRMS_MAP_KEY` configurado. Procesa hotspots del ultimo dia para un bbox:

```bash
uv run python -c "
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ingestors.firms_ingestor import FIRMSIngestor

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/geosentinel'))
Session = sessionmaker(bind=engine)

with Session() as session:
    ingestor = FIRMSIngestor()
    result = ingestor.poll(session, bbox=(-10.0, 35.0, 5.0, 45.0), days=1)
    print(result)
"
```

### Ingestor GDELT (conflictos, cada 5 min)

Requiere `GDELT_API_KEY`. Descarga eventos de conflicto de los ultimos 5 minutos:

```bash
uv run python -c "
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ingestors.gdelt_ingestor import GDELTIngestor

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/geosentinel'))
Session = sessionmaker(bind=engine)

with Session() as session:
    ingestor = GDELTIngestor()
    result = ingestor.run(session)
    print(result)
"
```

### Ingestor ACLED (conflictos estructurados, batch diario)

Requiere `ACLED_API_KEY` y `ACLED_EMAIL`. Descarga las ultimas 48h (incluye actualizaciones retroactivas).
Para backfill de una fecha concreta usar `since_date`:

```bash
uv run python -c "
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ingestors.acled_ingestor import ACLEDIngestor

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/geosentinel'))
Session = sessionmaker(bind=engine)

with Session() as session:
    ingestor = ACLEDIngestor()
    # Backfill desde una fecha especifica
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    result = ingestor.run(session, since_date=since)
    print(result)
"
```

### Job de clustering

Agrupa los eventos en incidentes tras la ingesta:

```bash
uv run python -c "
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from jobs.clustering_job import run_clustering_job

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/geosentinel'))
Session = sessionmaker(bind=engine)

with Session() as session:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    result = run_clustering_job(session, last_run_time=since)
    print(result)
"
```

### Job de ciclo de vida

Marca incidentes como `stale` y resetea `updated -> open`:

```bash
uv run python -c "
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from jobs.incident_lifecycle import run_lifecycle_job, mark_stale_incidents

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/geosentinel'))
Session = sessionmaker(bind=engine)

with Session() as session:
    stale = mark_stale_incidents(session)
    updated = run_lifecycle_job(session)
    print(f'Stale: {stale}, Updated: {updated}')
"
```

---

## Tests

```bash
# Ejecutar todos los tests
uv run pytest

# Con reporte de cobertura
uv run pytest --cov=. --cov-report=term-missing

# Solo normalizacion
uv run pytest tests/normalizers/

# Solo clustering
uv run pytest tests/jobs/
```

---

## Estructura del proyecto

```
geosentinel/
├── api/
│   ├── main.py              # FastAPI app, routers, CORS
│   ├── database.py          # Conexion SQLAlchemy (DATABASE_URL)
│   ├── routes/
│   │   ├── incidents.py     # GET /v1/incidents, GET /v1/incidents/{id}
│   │   ├── aoi.py           # CRUD /v1/aoi + /v1/aoi/{id}/incidents
│   │   ├── corrections.py   # POST /v1/corrections
│   │   ├── health.py        # GET /v1/health
│   │   └── seed.py          # GET /v1/seed (datos de prueba)
│   └── schemas/             # Modelos Pydantic de respuesta API
├── ingestors/
│   ├── firms_ingestor.py    # Pull FIRMS NASA (CSV, retry/backoff)
│   └── usgs_ingestor.py     # Pull USGS GeoJSON (retry/backoff)
├── normalizers/
│   ├── firms_mapper.py      # FIRMS row -> EventCanonicalCreate
│   └── usgs_mapper.py       # USGS feature -> EventCanonicalCreate
├── jobs/
│   ├── clustering_job.py    # DBSCAN espacio-temporal + metricas
│   ├── event_processing.py  # Upsert en events_canonical
│   └── incident_lifecycle.py# Maquina de estados + corrections_audit
├── models/                  # ORM SQLAlchemy (tablas BD)
├── schemas/                 # Pydantic internos (EventCanonicalCreate, etc.)
├── validation/
│   └── validator.py         # 6 reglas de validacion + quarantine
├── alembic/                 # Migraciones de BD (herramienta: alembic)
├── tests/                   # Tests pytest
├── specs_estructurales/     # E-ARCH, E-MODEL, E-SEC, E-STD, E-MON...
├── specs_funcionales/       # F-ING-*, F-NORM-*, F-CLUST, F-LC, F-API-*
├── docker-compose.yml       # PostgreSQL 16 + PostGIS 3.4
└── pyproject.toml           # Dependencias gestionadas con uv
```

---

## Licencias de datos

| Fuente | Licencia | Restriccion |
|--------|----------|-------------|
| FIRMS NASA | NASA libre | Atribucion requerida |
| USGS | Dominio publico | Ninguna |
| GDELT | Dominio publico | Ninguna |
| ACLED | CC BY-NC 4.0 | Solo uso no comercial |
| ADS-B Exchange | Comercial | No redistribuir raw |
| MarineTraffic | Comercial | No redistribuir raw |