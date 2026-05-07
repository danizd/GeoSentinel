# AGENTS.md — Sistema de Monitorización de Incidentes

## REGLA OBLIGATORIA
**Antes de escribir cualquier código**, leer las specs indicadas en la tabla de enrutamiento.
Si una tarea toca datos → cargar `E-MODEL`. Si toca fuente externa → cargar `E-SOURCES`.
Si hay conflicto entre spec funcional y estructural → **la estructural prevalece**.
Si falta información en las specs → señalarlo. **No inventar.**

---

## Tabla de enrutamiento: Tarea → Spec

### Specs estructurales `specs_estructurales/` — cargar siempre como contexto base

| Código | Archivo | Cuándo |
|--------|---------|--------|
| `E-ARCH` | `arquitectura.md` | Nuevos componentes, cambios en flujo de datos |
| `E-MODEL` | `modelo-datos.md` | Esquemas SQL, migraciones, modelos Pydantic |
| `E-SOURCES` | `fuentes-datos.md` | Añadir/modificar/sustituir fuentes externas |
| `E-SEC` | `seguridad.md` | Auth, secretos, exposición de API |
| `E-STD` | `estandares-codigo.md` | **Siempre** — estilo, tests, naming |
| `E-INFRA` | `infraestructura.md` | Docker, K8s, CI/CD, variables de entorno |
| `E-MON` | `monitorizacion.md` | Logging, métricas, SLAs de latencia |

### Specs funcionales `specs_funcionales/` — cargar según tarea

#### Ingesta `ingesta/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-ING-GDELT` | `ingesta/gdelt.md` | Ingestor GDELT Cloud Events v2 |
| `F-ING-ACLED` | `ingesta/acled.md` | Ingestor ACLED |
| `F-ING-FIRMS` | `ingesta/firms.md` | Ingestor FIRMS NASA |
| `F-ING-USGS` | `ingesta/usgs.md` | Ingestor USGS terremotos |
| `F-ING-ADSB` | `ingesta/adsb.md` | Ingestor ADS-B Exchange |
| `F-ING-MT` | `ingesta/marinetraffic.md` | Ingestor MarineTraffic AIS |
| `F-ING-LUM` | `ingesta/liveuamap.md` | Ingestor Liveuamap (riesgo alto) |

#### Normalización `normalizacion/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-NORM-CANON` | `normalizacion/modelo-canonico.md` | Mappers fuente → `events_canonical`, UTC |
| `F-NORM-ACTORS` | `normalizacion/actores.md` | Diccionario CAMEO↔ACLED↔interno |
| `F-NORM-SEV` | `normalizacion/escala-severidad.md` | Escala 0–10 por categoría |
| `F-NORM-CONF` | `normalizacion/modelo-confianza.md` | Confidence con clases de independencia |

#### Procesamiento `procesamiento/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-VAL` | `procesamiento/validacion-quarantine.md` | Reglas de validación, tabla quarantine |
| `F-DEDUP` | `procesamiento/deduplicacion.md` | Claves naturales por fuente |
| `F-CLUST` | `procesamiento/clustering.md` | DBSCAN espacio-temporal, métrica mixta |
| `F-LC` | `procesamiento/ciclo-vida-incidente.md` | Máquina de estados, transiciones, purga |
| `F-AOI` | `procesamiento/aoi.md` | AOI como entidad de primera clase |

#### API `api/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-API-INC` | `api/incidents.md` | `GET /v1/incidents` — filtros, paginación |
| `F-API-AOI` | `api/aoi.md` | CRUD `/v1/aoi`, suscripciones |
| `F-API-CORR` | `api/corrections.md` | `POST /v1/corrections` — human-in-the-loop |

#### UI `ui/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-UI` | `ui/dashboard.md` | Dashboard: mapa, timeline, filtros |

---

## Combinaciones de contexto para tareas complejas

| Tarea | Cargar |
|-------|--------|
| Nuevo ingestor | `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `F-ING-[X]` + `F-NORM-CANON` + `F-DEDUP` + `F-VAL` |
| Modificar modelo BD | `E-ARCH` + `E-MODEL` + `F-NORM-CANON` + spec funcional afectada |
| Clustering | `E-MODEL` + `F-CLUST` + `F-DEDUP` + `F-NORM-CONF` + `F-NORM-SEV` + `F-LC` |
| Endpoint API nuevo | `E-ARCH` + `E-SEC` + `E-STD` + `F-API-[X]` |
| Pipeline normalización | `E-MODEL` + `F-NORM-CANON` + `F-NORM-ACTORS` + `F-NORM-SEV` + `F-NORM-CONF` + `F-VAL` |
| Corrección humana | `E-SEC` + `E-MODEL` + `F-API-CORR` + `F-LC` |
| Infraestructura / CI | `E-INFRA` + `E-SEC` + `E-MON` |

---

## Decisiones de diseño (no reabrir sin revisión explícita)

| # | Decisión |
|---|----------|
| D1 | Todo timestamp en `TIMESTAMPTZ` UTC. Conversión en el mapper, nunca después. |
| D2 | `severity` Float [0.0–10.0] normalizada por categoría (ver `F-NORM-SEV`). |
| D3 | `confidence` penaliza fuentes correlacionadas: 10 `media_derived` < 2 `field_reported`. |
| D4 | DBSCAN usa métrica mixta: `w₁·(km/km_max) + w₂·(h/h_max)`. Epsilon por categoría. |
| D5 | Liveuamap = riesgo alto (sin API pública). Debe poder desactivarse sin afectar al pipeline. |
| D6 | AOIs son entidades de primera clase en BD, no filtros ad hoc. |
| D7 | Incidentes tienen máquina de estados explícita (ver `F-LC`). |
| D8 | `corrections_audit` es append-only. Nunca UPDATE ni DELETE. |
| D9 | URLs de FIRMS: nunca hardcodear región ni API key (error original: `Canada_QC/YourMapKey`). |
| D10 | URL USGS: siempre `?` antes de params (error original: `queryformat=geojson`). |
| D11 | `fatalities_total` en incidente usa `MAX`, no `SUM` (evitar doble conteo multi-fuente). |

---

## Convenciones de naming (resumen)

| Capa | Patrón |
|------|--------|
| Ingestor | `ingestors/<source>_ingestor.py` |
| Mapper | `normalizers/<source>_mapper.py` |
| Job | `jobs/<funcion>_job.py` |
| Modelo ORM | `models/<entidad>.py` |
| Schema Pydantic | `schemas/<entidad>_schema.py` |
| Test | `tests/<capa>/test_<modulo>.py` |

## Licencias (restricciones de redistribución en API propia)

| Fuente | Licencia | Restricción |
|--------|----------|-------------|
| GDELT | Dominio público | Ninguna |
| ACLED | CC BY-NC 4.0 | Solo uso no comercial |
| FIRMS | NASA libre | Atribución requerida |
| USGS | Dominio público | Ninguna |
| ADS-B Exchange | Comercial | No redistribuir raw |
| MarineTraffic | Comercial | No redistribuir raw |
| Liveuamap | Sin API pública | Riesgo legal propio |
