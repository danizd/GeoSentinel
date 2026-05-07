# E-MODEL — Modelo de Datos Canónico

> **Spec estructural / transversal** — Obligatoria en cualquier tarea que
> toque esquemas SQL, migraciones, modelos Pydantic o lógica de clustering.

---

## 1. Principios del modelo

- Toda fecha/hora: `TIMESTAMPTZ` (UTC). Sin excepciones.
- Toda geometría: `GEOMETRY(POINT, 4326)` o `GEOMETRY(GEOMETRY, 4326)` (WGS84).
- Los campos `severity` y `confidence` son `FLOAT` en rango `[0.0, 10.0]`.
- Las claves primarias de eventos fuente son compuestas: `(source, event_id_source)`.

---

## 2. DDL principal

### 2.1 `sources_metadata`

```sql
CREATE TABLE sources_metadata (
    source              TEXT PRIMARY KEY,          -- 'gdelt','acled','firms','usgs','adsb','mt','liveuamap'
    display_name        TEXT NOT NULL,
    independence_class  TEXT NOT NULL              -- 'sensor','field_reported','media_derived'
                        CHECK (independence_class IN ('sensor','field_reported','media_derived')),
    typical_latency_min INT,                       -- minutos desde evento hasta disponibilidad
    update_frequency    TEXT,                      -- '5min','1h','daily','weekly_regional'
    coverage_notes      TEXT,
    license             TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT now()
);
```

### 2.2 `events_quarantine`

```sql
CREATE TABLE events_quarantine (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    raw_payload     JSONB NOT NULL,
    ingest_time     TIMESTAMPTZ DEFAULT now(),
    rejection_code  TEXT NOT NULL,               -- 'INVALID_COORDS','FUTURE_DATE','NULL_REQUIRED','SCHEMA_ERROR'
    rejection_detail TEXT,
    resolved        BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX ON events_quarantine (source, ingest_time);
CREATE INDEX ON events_quarantine (resolved) WHERE resolved = FALSE;
```

### 2.3 `events_canonical`

```sql
CREATE TABLE events_canonical (
    -- Identidad
    id                  BIGSERIAL PRIMARY KEY,
    event_id_source     TEXT NOT NULL,
    source              TEXT NOT NULL REFERENCES sources_metadata(source),
    UNIQUE (source, event_id_source),

    -- Temporalidad (siempre UTC)
    event_time          TIMESTAMPTZ NOT NULL,
    ingest_time         TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Clasificación
    event_type          TEXT NOT NULL,           -- 'conflict_battle','airstrike','wildfire_hotspot','earthquake',...
    category            TEXT NOT NULL            -- 'conflict','disaster_natural','wildfire','mobility','humanitarian'
                        CHECK (category IN ('conflict','disaster_natural','wildfire','mobility','humanitarian','other')),

    -- Geografía
    location_point      GEOMETRY(POINT, 4326) NOT NULL,
    location_accuracy_km FLOAT,                 -- radio de incertidumbre en km
    admin1              TEXT,
    admin2              TEXT,
    country_iso2        TEXT,

    -- Geometría extendida (polígonos, áreas)
    geometry            GEOMETRY(GEOMETRY, 4326),
    geometry_type       TEXT CHECK (geometry_type IN ('POINT','POLYGON','MULTIPOLYGON')),

    -- Actores
    actors              JSONB,                   -- [{role:'state_military', name:'...', cameo_code:'...'}]

    -- Métricas
    fatalities          INT,
    severity            FLOAT CHECK (severity BETWEEN 0 AND 10),
    confidence          FLOAT CHECK (confidence BETWEEN 0 AND 10),

    -- Fuente
    source_url          TEXT,
    source_refs         TEXT[],
    raw_event_id        BIGINT,                  -- FK opcional a raw_events_* por source

    -- Flags
    is_confirmed        BOOLEAN DEFAULT FALSE,
    is_rumor            BOOLEAN DEFAULT FALSE
);

-- Índices críticos para clustering y queries de bounding box
CREATE INDEX ON events_canonical USING GIST (location_point);
CREATE INDEX ON events_canonical (event_time, category);
CREATE INDEX ON events_canonical (source, event_time);
CREATE INDEX ON events_canonical (category, is_confirmed);
```

### 2.4 `incidents`

```sql
CREATE TYPE incident_status AS ENUM ('open','updated','stale','closed','false_positive');

CREATE TABLE incidents (
    -- Identidad
    incident_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Temporalidad
    first_seen          TIMESTAMPTZ NOT NULL,
    last_seen           TIMESTAMPTZ NOT NULL,
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Clasificación
    event_type          TEXT NOT NULL,
    category            TEXT NOT NULL,
    country_iso2        TEXT,
    admin1              TEXT,

    -- Estado (máquina de estados — ver F-LC)
    status              incident_status NOT NULL DEFAULT 'open',
    status_changed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Geometría canónica
    canonical_point     GEOMETRY(POINT, 4326) NOT NULL,
    canonical_geometry  GEOMETRY(GEOMETRY, 4326),

    -- Métricas agregadas
    severity_max        FLOAT CHECK (severity_max BETWEEN 0 AND 10),
    severity_latest     FLOAT CHECK (severity_latest BETWEEN 0 AND 10),
    confidence          FLOAT CHECK (confidence BETWEEN 0 AND 10),
    fatalities_total    INT DEFAULT 0,
    source_count        INT DEFAULT 0,
    observation_count   INT DEFAULT 0,

    -- Fuentes que lo soportan
    sources             TEXT[],                  -- ['gdelt','firms','acled']
    linked_event_ids    BIGINT[]                 -- IDs de events_canonical
);

CREATE INDEX ON incidents USING GIST (canonical_point);
CREATE INDEX ON incidents (status, last_seen);
CREATE INDEX ON incidents (category, status);
CREATE INDEX ON incidents (last_seen) WHERE status IN ('open','updated');
```

### 2.5 `aoi` (Areas of Interest)

```sql
CREATE TABLE aoi (
    aoi_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT,
    geometry        GEOMETRY(GEOMETRY, 4326) NOT NULL,
    categories      TEXT[],                      -- filtro por categoría; NULL = todas
    min_severity    FLOAT DEFAULT 0.0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON aoi USING GIST (geometry);
CREATE INDEX ON aoi (is_active) WHERE is_active = TRUE;
```

### 2.6 `corrections_audit`

```sql
CREATE TABLE corrections_audit (
    correction_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents(incident_id),
    corrected_by    TEXT NOT NULL,               -- user_id o 'system'
    correction_type TEXT NOT NULL                -- 'false_positive','reclassify','relocate','merge','close'
                    CHECK (correction_type IN ('false_positive','reclassify','relocate','merge','close')),
    before_state    JSONB NOT NULL,
    after_state     JSONB NOT NULL,
    reason          TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- Tabla APPEND-ONLY: nunca UPDATE ni DELETE
```

---

## 3. Tabla de claves naturales de deduplicación por fuente

| Fuente | Clave natural |
|--------|---------------|
| GDELT | `(source='gdelt', event_id_source=GLOBALEVENTID::text)` |
| ACLED | `(source='acled', event_id_source=data_id::text)` |
| FIRMS | `(source='firms', event_id_source=sha256(lat\|\|lon\|\|acq_date\|\|acq_time\|\|satellite))` |
| USGS | `(source='usgs', event_id_source=properties.ids split por coma, primero)` |
| ADS-B | `(source='adsb', event_id_source=hex + ':' + timestamp_unix)` |
| MarineTraffic | `(source='marinetraffic', event_id_source=mmsi + ':' + timestamp_unix)` |
| Liveuamap | `(source='liveuamap', event_id_source=id::text)` |

---

## 4. Clases de independencia de fuente

Usadas en el cálculo de `confidence` (ver `F-NORM-CONF`):

| Clase | Valor en confidence | Ejemplos |
|-------|--------------------|---------  |
| `sensor` | Alto (×2.0) | FIRMS, USGS, ADS-B, MarineTraffic |
| `field_reported` | Medio-alto (×1.5) | ACLED, ReliefWeb, ACAPS |
| `media_derived` | Bajo (×0.5) | GDELT, Liveuamap |

> Dos fuentes `media_derived` sobre el mismo hecho probablemente
> extraen del mismo artículo de prensa. No son independientes.
