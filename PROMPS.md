# PROMPS.md — Guía de implementación progresiva

Nunca todo de golpe. Con proyectos de esta complejidad, hacerlo de una sola vez garantiza código inconsistente, errores que se propagan entre capas y contexto demasiado grande para que la IA lo maneje bien.

La estrategia óptima es **vertical y en capas**, implementando un slice completo funcional antes de pasar al siguiente. Aquí está la secuencia:

---

## Fase 0 — Cimientos (hacer tú, no la IA)

Antes de escribir una línea de código generado, debes tener esto manualmente:

```
git init
uv init / pyproject.toml
docker-compose.yml  (postgres+postgis, kafka o redis, fastapi)
.env.example
alembic init
```

Esto no se delega porque es la base sobre la que todo lo demás se apoya. Si la IA monta el scaffolding inicial sin que tú lo revises, introduce decisiones difíciles de deshacer.

---

## Fase 1 — Base de datos y modelo canónico

**Un solo prompt, una sola tarea:**
> "Lee E-MODEL y E-STD. Genera las migraciones Alembic para todas las tablas del modelo canónico: `sources_metadata`, `events_quarantine`, `events_canonical`, `incidents`, `aoi`, `corrections_audit`. Incluye todos los índices geoespaciales."

**Validas tú:**
- Ejecutar `alembic upgrade head` en local
- Verificar con `\d events_canonical` en psql que los índices GIST existen
- Insertar una fila de prueba manual

**Por qué parar aquí:** si el modelo está mal, todo lo que construyas encima heredará el error.

---

## Fase 2 — Capa de validación y schema Pydantic

**Un prompt:**
> "Lee E-MODEL, F-VAL y E-STD. Implementa: (1) el schema Pydantic `EventCanonicalCreate`, (2) la función de validación que rechaza eventos inválidos con los códigos de `F-VAL`, (3) la función que inserta en `events_quarantine`. Incluye tests de todos los casos de rechazo."

**Validas tú:** ejecutar `pytest tests/` — todos los tests de validación en verde.

---

## Fase 3 — Primer ingestor + mapper (USGS, el más simple)

USGS es la fuente más limpia: sensor, API pública, sin licencia restrictiva, sin lag.

**Prompt:**
> "Lee E-ARCH, E-SOURCES, F-ING-USGS, F-NORM-CANON y F-DEDUP. Implementa el ingestor USGS completo: polling cada 3 min, retry con backoff, normalización UTC, deduplicación por clave natural, validación y escritura en `events_canonical`. Incluye tests para timeout, 429, coordenadas inválidas y fecha futura."

**Validas tú:**
- Correr el ingestor 10 minutos en local con datos reales
- Consultar `SELECT count(*) FROM events_canonical WHERE source='usgs'`
- Revisar que `event_time` tiene timezone UTC

**Por qué USGS primero:** si el patrón ingestor→mapper→validación→BD funciona con la fuente más simple, es el molde para todas las demás.

---

## Fase 4 — Replicar el patrón: FIRMS y GDELT

Con el patrón validado, añadir las otras dos fuentes del MVP:

**Dos prompts separados** (uno por fuente):
> "Usando el mismo patrón del ingestor USGS ya implementado, lee F-ING-FIRMS y F-NORM-CANON. Implementa el ingestor FIRMS con clave sintética SHA256, bbox dinámico por AOI, y los campos específicos de FIRMS."

**Validas tú:** mismo checklist que Fase 3.

---

## Fase 5 — Job de clustering

Este es el componente más delicado. Hacerlo antes de tener datos reales de varias fuentes es un error.

**Prerequisito:** tener al menos 48h de datos de USGS + FIRMS + GDELT en BD.

**Prompt:**
> "Lee E-MODEL, F-CLUST, F-NORM-CONF, F-NORM-SEV y F-LC. Implementa el job de clustering con la métrica mixta normalizada definida en F-CLUST §2.1. Usa los valores de epsilon por categoría de la tabla. Implementa también la lógica de creación/actualización de incidentes y las transiciones de estado definidas en F-LC."

**Validas tú (crítico):**
- Ejecutar el job manualmente con `--dry-run`
- Revisar en BD que incidentes de distinto `category` nunca se fusionan
- Verificar que `fatalities_total` usa MAX, no SUM
- Comprobar transiciones de estado con datos sintéticos

---

## Fase 6 — API básica

**Un prompt:**
> "Lee E-ARCH, E-SEC, F-API-INC y E-STD. Implementa el endpoint `GET /v1/incidents` con todos los filtros definidos en la spec, autenticación JWT con scope `incidents:read`, rate limiting y paginación. Incluye tests de auth fallida, bbox inválido y paginación."

**Validas tú:** probar con curl/Postman contra datos reales de tu BD local.

---

## Fase 7 — Fuentes secundarias y correcciones

Con el sistema funcionando end-to-end, añadir en prompts separados:
- ACLED (backfill incluido)
- Endpoint `/corrections`
- Sistema de AOI completo
- ADS-B / MarineTraffic (si tienes acceso)

---

## Reglas de oro para cada prompt

Tres cosas que debes hacer siempre antes de pasar a la siguiente fase:

**1. Tests en verde.** No avanzar si hay tests rojos. La IA del siguiente prompt asumirá que lo anterior funciona.

**2. Revisar el código generado.** Especialmente: manejo de errores, que no haya API keys hardcodeadas, que los timestamps sean siempre UTC.

**3. Commit limpio.** Un commit por fase. Si algo falla más adelante, puedes volver a un estado conocido.

---

## Lo que nunca debes hacer en un solo prompt

- Ingestor + mapper + clustering + API juntos
- Pedir "implementa todo el sistema"
- Pedir código sin haber validado la fase anterior

El motivo es técnico: la ventana de contexto de la IA se llena, las specs relevantes no caben todas, y el modelo empieza a "inventar" detalles que no están en las specs. Los prompts pequeños y enfocados producen código más fiel a lo que has diseñado.

---

## Estado actual del proyecto

### Implementado ✅

| Componente | Detalles |
|------------|-----------|
| **Modelo de datos** | Tablas: `events_canonical`, `incidents`, `aoi`, `corrections_audit`, `events_quarantine`, `sources_metadata`. Índices GIST en geometrías. |
| **Ingestor USGS** | Polling cada 3 min, retry/backoff, `minmagnitude=4.0`, deduplicación por `properties.ids` |
| **Ingestor FIRMS** | Polling con retry/backoff, bbox dinámico por AOI, tipo 0/1 (excluye type 2/3), deduplicación SHA-256 |
| **Ingestor GDELT** | API GDELT Cloud v2 (gdeltcloud.com/api/v2), ventana 5 min (max 29 días), Bearer auth, análisis de título para event_type, deduplicación por `globalEventId` |
| **Ingestor ACLED** | OAuth2 Bearer token, backfill 48h, deduplicación por `event_id` |
| **Normalización** | Mappers para USGS, FIRMS, GDELT, ACLED → `EventCanonicalCreate` |
| **Validación** | 6 reglas de rechazo, quarantine con código de error |
| **Deduplicación** | Upsert por `(source, event_id_source)` |
| **Clustering** | DBSCAN espacio-temporal, métrica mixta normalizada, epsilon por categoría, `canonical_point` como centroide ponderado |
| **Ciclo de vida** | Máquina de estados: `open -> updated -> stale -> closed / false_positive`, auditoría append-only |
| **API Incidents** | Filtros completos: bbox, category, status, since, min_severity, min_confidence, sources, aoi_id, include_fp + paginación |
| **API AOI** | CRUD completo, geometría real desde PostGIS, filtro espacial `ST_Intersects` |
| **API Corrections** | Tipos: false_positive, close, reclassify, relocate, merge |
| **Confianza** | Clases de independencia, penalización 6h para `media_derived` |

### Pendiente ❌

| Componente | Prioridad | Notas |
|------------|----------|-------|
| **JWT / Autenticación** | Media | Endpoints públicos actualmente |
| **Rate limiting API** | Media | No implementado |
| **Métricas Prometheus** | Baja | Para producción |
| **Circuit breaker** | Baja | Para resiliencia |
| **Bus de eventos (Kafka/Redis)** | Media | MVP usa llamadas síncronas |
| **Job de purga/archivado** | Baja | Tabla `incidents_archive` no creada |
| **`canonical_point` como GEOMETRY** | Media | Actualmente WKT String |
| **Ingestor ACLED** | Alta | Cuenta temporalmente bloqueada por intentos fallidos, reintentar |
| **Tests pytest** | Alta | Cobertura baja |

### Scripts disponibles

```
scripts/
├── run_acled.py           # Ingestor ACLED (OAuth2, espera desbloqueo de cuenta)
├── run_clustering.py     # Job de clustering
├── run_firms.py           # Ingestor FIRMS
├── run_gdelt.py           # Ingestor GDELT Cloud v2
├── run_seed.py            # Datos de prueba
├── run_usgs.py            # Ingestor USGS
├── check_db.py            # Verificar conexión BD
├── create_conflict_aois.py# Crear AOIs de conflicto
└── query_db.py            # Consultas rápidas de diagnóstico
```

### Base de datos actual

- **23 eventos** (20 USGS, 3 GDELT)
- **21 incidentes** (17 disasters_natural, 3 conflict, 1 false_positive)
- **6 AOIs** de conflicto pre-creados

### Decisiones de diseño aplicadas

- D1: Timestamps en `TIMESTAMPTZ` UTC
- D2: Severity Float 0.0–10.0 por categoría
- D3: Confidence penaliza fuentes correlacionadas
- D4: DBSCAN métrica mixta normalizada
- D5: Liveuamap desactivable sin afectar pipeline
- D6: AOIs como entidad de primera clase
- D7: Máquina de estados explícita
- D8: `corrections_audit` append-only
- D9: FIRMS URLs sin hardcodear región/key
- D10: USGS URLs con `?` antes de params
- D11: `fatalities_total` usa MAX, no SUM

### Próximos pasos recomendados

1. **Probar ACLED** cuando se desbloquee la cuenta (credenciales correctas en `.env`, endpoint migrado a `acleddata.com/api/acled/read`)
2. **Añadir tests pytest** para ingestores y normalizadores
3. **Implementar JWT auth** para la API
4. **Crear job de purga** para incidentes archivados
5. **Migrar `canonical_point`** a `GEOMETRY(POINT,4326)`

---

## Lo que nunca debes hacer en un solo prompt

- Ingestor + mapper + clustering + API juntos
- Pedir "implementa todo el sistema"
- Pedir código sin haber validado la fase anterior

El motivo es técnico: la ventana de contexto de la IA se llena, las specs relevantes no caben todas, y el modelo empieza a "inventar" detalles que no están en las specs. Los prompts pequeños y enfocados producen código más fiel a lo que has diseñado.