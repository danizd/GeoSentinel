# GeoSentinel

Sistema de agregacion y monitorizacion de incidentes geoespaciales en tiempo real.
Agrega eventos de multiples fuentes (USGS, FIRMS NASA, GDELT Cloud v2, ACLED...), los normaliza
a un modelo canonico, aplica clustering espacio-temporal y los expone via API REST.

---

## Estado de implementacion

### Implementado

| Componente | Descripcion |
|------------|-------------|
| **Modelo de datos** | ORM SQLAlchemy para todas las tablas (`events_canonical`, `incidents`, `aoi`, `corrections_audit`, `events_quarantine`, `sources_metadata`) |
| **Ingestor FIRMS** | Pull polling con retry/backoff exponencial, filtro por AOI bbox, tipo 0/1 (excluye type 2/3), manejo de rate limiting 429 |
| **Ingestor USGS** | Pull polling cada 3 min, manejo de rate limiting 429, filtro `minmagnitude=4.0` |
| **Ingestor GDELT** | API GDELT Cloud v2 (gdeltcloud.com/api/v2), ventana 5 min (max 29 dias), Bearer auth, analisis de titulo para event_type, deduplicacion por `globalEventId` |
| **Ingestor ACLED** | OAuth2 Bearer token, backfill 48h, deduplicacion por `event_id`, categorias ACLED -> internal mapping |
| **Relay Militar (OpenSky)** | Microservicio FastAPI en puerto 8002. Filtra vuelos militares por categoría 7 + 53 prefijos callsign + lista hex ICAO. Rate limiting 1 req/s |
| **API Vuelos Militares** | `GET /v1/military-flights` devuelve vuelos filtrados dentro de AOIs activos. Frontend: capas Mapbox nativas (symbol SDF ✈ + circle halo) |
| **Normalizacion GDELT** | Mapper Events v2 a `EventCanonicalCreate`, CAMEO code -> category/event_type, deduplicacion por `globalEventId` |
| **Normalizacion ACLED** | Mapper JSON a `EventCanonicalCreate`, clasificacion ACLED -> internal, deduplicacion por `event_id` |
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
| **Frontend** | Dashboard React con mapa Mapbox, capas 2D/3D, panel lateral con lista de incidentes virtualizada, filtros, estado polling con TanStack Query |

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
- **Node.js 18+** (para el frontend)
- **Docker** y **Docker Compose**
- **uv** -- gestor de entorno: `pip install uv`
- Cuentas de API para las fuentes de datos:
  - **GDELT Cloud Events v2**: https://gdeltcloud.com/dashboard
  - **ACLED**: https://acleddata.com/myacled
  - **FIRMS (NASA Fire Information)**: https://firms.modaps.eosdis.nasa.gov/api/map_key/
  - **OpenSky Network** (vuelos militares): https://opensky-network.org/my-opensky/account
  - **Mapbox** (token para el frontend): https://console.mapbox.com/

---

## Puesta en marcha

### 1. Base de datos (PostgreSQL 16 + PostGIS 3.4)

```bash
docker compose up -d
```

Espera a que el healthcheck pase (`pg_isready`). La BD queda disponible en `localhost:5432`.

### 2. Entorno Python

```bash
cd backend
uv sync
```

### 3. Entorno Frontend

```bash
cd frontend
npm install
```

### 4. Variables de entorno

Crea un archivo `.env` en la raiz del proyecto (nunca commitear):

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/geosentinel
FIRMS_MAP_KEY=tu_api_key_aqui
GDELT_API_KEY=tu_gdelt_api_key
ACLED_ACCESS_TOKEN=tu_acled_access_token
ACLED_USERNAME=tu_email_registrado_en_acled
ACLED_PASSWORD=tu_password_de_acled
OPENSKY_CLIENT_ID=tu_opensky_client_id
OPENSKY_CLIENT_SECRET=tu_opensky_client_secret
MILITARY_SOURCE=opensky
MILITARY_RELAY_URL=http://localhost:8002
VITE_MAPBOX_TOKEN=tu_mapbox_token
```

> Los scripts de ingesta cargan automaticamente el `.env` desde la raiz del proyecto.

### 5. Migraciones de base de datos

```bash
cd backend
uv run alembic upgrade head
```

Esto crea todas las tablas en la BD.

### 6. Arrancar la API y el Frontend

```bash
# Terminal 1: API
cd backend
uv run uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

La API queda disponible en `http://localhost:8000`.
Documentacion interactiva (Swagger UI): `http://localhost:8000/docs`
Schema OpenAPI (ReDoc): `http://localhost:8000/redoc`
El frontend queda disponible en `http://localhost:5173`.

### 6b. Relay de vuelos militares (opcional)

Para usar la funcionalidad de vuelos militares (requiere AOIs activos):

```bash
# Terminal 3: Relay militar (OpenSky)
cd C:\Proyextos\GeoSentinel
$env:PYTHONPATH = "C:\Proyextos\GeoSentinel"
$env:MILITARY_SOURCE = "opensky"
$env:OPENSKY_CLIENT_ID = "tu_client_id"
$env:OPENSKY_CLIENT_SECRET = "tu_client_secret"
python -m services.military_relay.main
```

El relay escuchara en `http://localhost:8002` (o la URL configurada en `MILITARY_RELAY_URL`).

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

Todos los scripts de ingesta buscan el `.env` automaticamente. Ejecuta desde la raiz del proyecto:

### Ingestor USGS (terremotos >= 4.0)

Descarga y procesa eventos de las ultimas 24 horas:

```bash
cd backend
uv run python backend/scripts/run_usgs.py
```

### Ingestor FIRMS (incendios activos)

Requiere `FIRMS_MAP_KEY` configurado. Procesa hotspots del ultimo dia para los AOIs activos:

```bash
cd backend
uv run python backend/scripts/run_firms.py
```

### Ingestor GDELT (conflictos, todas las zonas)

Requiere `GDELT_API_KEY`. Descarga eventos de conflicto de las ultimas 24h por zona:

```bash
cd backend
uv run python backend/scripts/run_gdelt.py
```

### Ingestor ACLED (conflictos estructurados, batch 48h)

Requiere `ACLED_USERNAME` y `ACLED_PASSWORD` (obtiene token via OAuth2 automáticamente). Descarga las ultimas 48h:

```bash
cd backend
uv run python backend/scripts/run_acled.py
```

### Job de clustering

Agrupa los eventos en incidentes tras la ingesta:

```bash
cd backend
uv run python backend/scripts/run_clustering.py
```

### Job de ciclo de vida

Marca incidentes como `stale` y resetea `updated -> open`:

```bash
cd backend
uv run python -c "
from backend.jobs.incident_lifecycle import run_lifecycle_job, mark_stale_incidents
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('postgresql://postgres:postgres@localhost:5432/geosentinel')
Session = sessionmaker(bind=engine)

with Session() as session:
    stale = mark_stale_incidents(session)
    updated = run_lifecycle_job(session)
    print(f'Stale: {stale}, Updated: {updated}')
"
```

---

## Tests

Los tests viven en `tests/` en la raiz del proyecto. Se ejecutan desde `backend/`:

```bash
cd backend

# Ejecutar todos los tests
uv run pytest

# Con reporte de cobertura
uv run pytest --cov=backend --cov-report=term-missing

# Solo normalizacion
uv run pytest ../tests/normalizers/

# Solo clustering
uv run pytest ../tests/jobs/
```

---

## Estructura del proyecto

```
geosentinel/
├── backend/
│   ├── api/
│   │   ├── main.py              # FastAPI app, routers, CORS
│   │   ├── database.py          # Conexion SQLAlchemy (DATABASE_URL)
│   │   ├── routes/
│   │   │   ├── incidents.py     # GET /v1/incidents, GET /v1/incidents/{id}
│   │   │   ├── aoi.py           # CRUD /v1/aoi + /v1/aoi/{id}/incidents
│   │   │   ├── corrections.py   # POST /v1/corrections
│   │   │   ├── health.py        # GET /v1/health
│   │   │   ├── seed.py          # GET /v1/seed (datos de prueba)
│   │   │   └── military.py      # GET /v1/military-flights
│   │   └── schemas/             # Modelos Pydantic de respuesta API
│   ├── ingestors/
│   │   ├── firms_ingestor.py    # Pull FIRMS NASA (CSV, retry/backoff, tipo 0/1)
│   │   ├── usgs_ingestor.py     # Pull USGS GeoJSON (retry/backoff, mag>=4.0)
│   │   ├── gdelt_ingestor.py    # Pull GDELT Cloud v2 (gdeltcloud.com, Bearer)
│   │   ├── acled_ingestor.py    # Pull ACLED (OAuth2 Bearer, backfill 48h)
│   │   └── military_ingestor.py # Pull desde relay militar (OpenSky via relay)
│   ├── normalizers/
│   │   ├── firms_mapper.py      # FIRMS row -> EventCanonicalCreate
│   │   ├── usgs_mapper.py       # USGS feature -> EventCanonicalCreate
│   │   ├── gdelt_mapper.py      # GDELT Events v2 -> EventCanonicalCreate
│   │   └── acled_mapper.py      # ACLED JSON -> EventCanonicalCreate
├── services/
│   └── military_relay/          # Relay FastAPI para flights militares (OpenSky)
│       └── main.py              # Servidor en puerto 8002
│   ├── jobs/
│   │   ├── clustering_job.py    # DBSCAN espacio-temporal + metricas
│   │   ├── event_processing.py  # Upsert en events_canonical
│   │   └── incident_lifecycle.py# Maquina de estados + corrections_audit
│   ├── models/                  # ORM SQLAlchemy (tablas BD)
│   ├── schemas/                 # Pydantic internos (EventCanonicalCreate, etc.)
│   ├── scripts/                 # Scripts utilitarios (run_*, query_db, check_db)
│   ├── validation/
│   │   └── validator.py         # 6 reglas de validacion + quarantine
│   ├── alembic/                 # Migraciones de BD (herramienta: alembic)
│   └── pyproject.toml           # Dependencias gestionadas con uv
├── tests/                   # Tests pytest (en raiz del proyecto)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── map/
│   │   │   │   └── IncidentMap.tsx    # Mapa Mapbox con capas de incidentes
│   │   │   └── panels/
│   │   │       ├── IncidentList.tsx   # Lista virtualizada de incidentes
│   │   │       └── IncidentDetail.tsx # Detalle del incidente seleccionado
│   │   ├── pages/
│   │   │   └── Dashboard.tsx           # Layout principal con mapa y panel lateral
│   │   ├── stores/
│   │   │   ├── mapStore.ts            # Estado del mapa (capas, viewport)
│   │   │   └── filterStore.ts         # Filtros de incidentes
│   │   ├── types/
│   │   │   └── incident.ts            # Tipos TypeScript
│   │   └── api/
│   │       └── incidents.ts           # Llamadas a la API backend
│   ├── public/
│   └── package.json
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
| GDELT | Dominio público | Ninguna |
| ACLED | CC BY-NC 4.0 | Solo uso no comercial |
| OpenSky Network | Terms of Use | Uso no comercial permitido |
| MarineTraffic | Comercial | No redistribuir raw |
| Mapbox GL JS | Comercial | Requiere token valido - respetar limites del plan |