# AGENTS.md — Sistema de Monitorización de Incidentes

## REGLA OBLIGATORIA
**Antes de escribir cualquier código**, leer las specs indicadas en la tabla de enrutamiento.
Si una tarea toca datos → cargar `E-MODEL`. Si toca fuente externa → cargar `E-SOURCES`.
Si toca cualquier componente frontend → cargar `E-ARCH-FRONT`.
Si hay conflicto entre spec funcional y estructural → **la estructural prevalece**.
Si falta información en las specs → señalarlo. **No inventar.**

---

## Tabla de enrutamiento: Tarea → Spec

### Specs estructurales `documentacion/specs_estructurales/` — cargar siempre como contexto base

| Código | Archivo | Cuándo |
|--------|---------|--------|
| `E-ARCH` | `documentacion/specs_estructurales/arquitectura.md` | Nuevos componentes backend, cambios en flujo de datos |
| `E-ARCH-FRONT` | `documentacion/specs_estructurales/arquitectura-frontend.md` | **Siempre en tareas frontend** |
| `E-MODEL` | `documentacion/specs_estructurales/modelo-datos.md` | Esquemas SQL, migraciones, modelos Pydantic |
| `E-SOURCES` | `documentacion/specs_estructurales/fuentes-datos.md` | Añadir/modificar/sustituir fuentes externas |
| `E-SEC` | `documentacion/specs_estructurales/seguridad.md` | Auth, secretos, exposición de API |
| `E-STD` | `documentacion/specs_estructurales/estandares-codigo.md` | **Siempre** — estilo, tests, naming |
| `E-INFRA` | `documentacion/specs_estructurales/infraestructura.md` | Docker, K8s, CI/CD, variables de entorno |
| `E-MON` | `documentacion/specs_estructurales/monitorizacion.md` | Lotablagging, métricas, SLAs de latencia |

### Specs funcionales `documentacion/specs_funcionales/` — cargar según tarea

#### Ingesta `ingesta/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-ING-GDELT` | `documentacion/specs_funcionales/ingesta/gdelt.md` | Ingestor GDELT Cloud Events v2 |
| `F-ING-ACLED` | `documentacion/specs_funcionales/ingesta/acled.md` | Ingestor ACLED |
| `F-ING-FIRMS` | `documentacion/specs_funcionales/ingesta/firms.md` | Ingestor FIRMS NASA |
| `F-ING-USGS` | `documentacion/specs_funcionales/ingesta/usgs.md` | Ingestor USGS terremotos |
| `F-ING-MIL` | `documentacion/specs_funcionales/ingesta/military-flights.md` | Ingestor Vuelos Militares (OpenSky via relay) |
| `F-ING-AIS` | `documentacion/specs_funcionales/ingesta/aisstream.md` | Ingestor Buques AISStream (WebSocket) |
| `F-ING-MT` | `documentacion/specs_funcionales/ingesta/marinetraffic.md` | Ingestor MarineTraffic AIS |
| `F-ING-LUM` | `documentacion/specs_funcionales/ingesta/liveuamap.md` | Ingestor Liveuamap (riesgo alto) |

#### Normalización `normalizacion/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-NORM-CANON` | `documentacion/specs_funcionales/normalizacion/modelo-canonico.md` | Mappers fuente → `events_canonical`, UTC |
| `F-NORM-ACTORS` | `documentacion/specs_funcionales/normalizacion/actores.md` | Diccionario CAMEO↔ACLED↔interno |
| `F-NORM-SEV` | `documentacion/specs_funcionales/normalizacion/escala-severidad.md` | Escala 0–10 por categoría |
| `F-NORM-CONF` | `documentacion/specs_funcionales/normalizacion/modelo-confianza.md` | Confidence con clases de independencia |

#### Procesamiento `procesamiento/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-VAL` | `documentacion/specs_funcionales/procesamiento/validacion-quarantine.md` | Reglas de validación, tabla quarantine |
| `F-DEDUP` | `documentacion/specs_funcionales/procesamiento/deduplicacion.md` | Claves naturales por fuente |
| `F-CLUST` | `documentacion/specs_funcionales/procesamiento/clustering.md` | DBSCAN espacio-temporal, métrica mixta |
| `F-LC` | `documentacion/specs_funcionales/procesamiento/ciclo-vida-incidente.md` | Máquina de estados, transiciones, purga |
| `F-AOI` | `documentacion/specs_funcionales/procesamiento/aoi.md` | AOI como entidad de primera clase |

#### API `api/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-API-INC` | `documentacion/specs_funcionales/api/incidents.md` | `GET /v1/incidents` — filtros, paginación |
| `F-API-AOI` | `documentacion/specs_funcionales/api/aoi.md` | CRUD `/v1/aoi`, suscripciones |
| `F-API-CORR` | `documentacion/specs_funcionales/api/corrections.md` | `POST /v1/corrections` — human-in-the-loop |

#### UI `ui/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-UI-DASH` | `documentacion/specs_funcionales/ui/dashboard.md` | Layout principal C2, panels, statusbar |
| `F-UI-MAP` | `documentacion/specs_funcionales/ui/mapa-incidentes.md` | Mapbox GL JS + Deck.gl, capas, interacciones |
| `F-UI-TIEMPO-REAL` | `documentacion/specs_funcionales/ui/tiempo-real.md` | Polling TanStack Query, estados de carga |
| `F-UI-AUTH` | `documentacion/specs_funcionales/ui/autenticacion-ui.md` | Login, authStore, protección de rutas |
| `F-UI-CORR` | `documentacion/specs_funcionales/ui/correcciones-ui.md` | UI correcciones humanas, confirmaciones |
| `F-UI-AOI` | `documentacion/specs_funcionales/ui/aoi-ui.md` | Gestión de AOI, dibujo en mapa |
| `F-UI-REFRESH` | `documentacion/specs_funcionales/ui/refresh-controls.md` | Botones de actualización manual de datos |

#### Correcciones `correcciones/`
| Código | Archivo | Tarea |
|--------|---------|-------|
| `F-CORR-001` | `documentacion/specs_funcionales/correcciones/iconos-svg-mapbox.md` | Sustituir iconos Unicode por SVG en capas de vuelos y buques |
---

## Combinaciones de contexto para tareas complejas

### Backend
| Tarea | Cargar |
|-------|--------|
| Nuevo ingestor | `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `F-ING-[X]` + `F-NORM-CANON` + `F-DEDUP` + `F-VAL` |
| Modificar modelo BD | `E-ARCH` + `E-MODEL` + `F-NORM-CANON` + spec funcional afectada |
| Clustering | `E-MODEL` + `F-CLUST` + `F-DEDUP` + `F-NORM-CONF` + `F-NORM-SEV` + `F-LC` |
| Endpoint API nuevo | `E-ARCH` + `E-SEC` + `E-STD` + `F-API-[X]` |
| Pipeline normalización | `E-MODEL` + `F-NORM-CANON` + `F-NORM-ACTORS` + `F-NORM-SEV` + `F-NORM-CONF` + `F-VAL` |
| Corrección humana | `E-SEC` + `E-MODEL` + `F-API-CORR` + `F-LC` |
| Infraestructura / CI | `E-INFRA` + `E-SEC` + `E-MON` |

### Frontend
| Tarea | Cargar |
|-------|--------|
| Cualquier componente frontend | `E-ARCH-FRONT` + spec funcional correspondiente |
| Mapa / capas Deck.gl | `E-ARCH-FRONT` + `F-UI-MAP` + `F-UI-DASH` |
| Polling / datos en tiempo real | `E-ARCH-FRONT` + `F-UI-TIEMPO-REAL` + `F-UI-DASH` |
| Autenticación y rutas protegidas | `E-ARCH-FRONT` + `F-UI-AUTH` + `E-SEC` |
| Panel de correcciones | `E-ARCH-FRONT` + `F-UI-CORR` + `F-UI-AUTH` + `F-API-CORR` |
| Gestión de AOI en UI | `E-ARCH-FRONT` + `F-UI-AOI` + `F-API-AOI` + `F-UI-MAP` |
| Setup inicial del proyecto | `E-ARCH-FRONT` + `E-STD` |
| Botones de refresh | `E-ARCH` + `E-ARCH-FRONT` + `E-SEC` + `F-UI-REFRESH` + `F-UI-AUTH` |
| Puntos de incidentes se ven a través del globo 3D (antípodas) | `documentacion/lecciones_aprendidas/L-CORR-001-antipodas-globo-3d.md` |
---

## Decisiones de diseño (no reabrir sin revisión explícita)

### Backend
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
| D9 | URLs de FIRMS: nunca hardcodear región ni API key. |
| D10 | URL USGS: siempre `?` antes de params. |
| D11 | `fatalities_total` usa MAX, no SUM (evitar doble conteo multi-fuente). |

### Frontend
| # | Decisión |
|---|----------|
| D12 | Deck.gl gestiona todas las capas de datos sobre Mapbox. Nunca marcadores DOM en el canvas. |
| D13 | Lucide React es el único set de iconos. No mezclar con Heroicons. |
| D14 | Zustand para estado UI. TanStack Query para datos del servidor. No mezclar responsabilidades. |
| D15 | Framer Motion solo en: pulso de hotspots, fade de panel de detalle, badges de estado. |
| D16 | Polling cada 30s para incidentes. No WebSockets en esta versión. |
| D17 | Lista de incidentes virtualizada con `@tanstack/react-virtual` si > 100 items. |
| D18 | `VITE_MAPBOX_TOKEN` nunca hardcodeada. Siempre desde variables de entorno. |
| D19 | Token JWT en localStorage (v1). Evaluar httpOnly cookies en versión futura. |

---

## Convenciones de naming

### Backend
| Capa | Patrón |
|------|--------|
| Ingestor | `ingestors/<source>_ingestor.py` |
| Mapper | `normalizers/<source>_mapper.py` |
| Job | `jobs/<funcion>_job.py` |
| Modelo ORM | `models/<entidad>.py` |
| Schema Pydantic | `schemas/<entidad>_schema.py` |
| Test | `tests/<capa>/test_<modulo>.py` |

### Frontend
| Capa | Patrón |
|------|--------|
| Componente React | `PascalCase.tsx` |
| Hook personalizado | `use<Nombre>.ts` |
| Store Zustand | `<nombre>Store.ts` |
| Función API | `api/<recurso>.ts` |
| Tipos globales | `types/<entidad>.ts` |
| Test | `<Componente>.test.tsx` |

---

## Licencias (restricciones en API propia y frontend)

| Fuente | Licencia | Restricción |
|--------|----------|-------------|
| GDELT | Dominio público | Ninguna |
| ACLED | CC BY-NC 4.0 | Solo uso no comercial |
| FIRMS | NASA libre | Atribución requerida |
| USGS | Dominio público | Ninguna |
| ADS-B Exchange | Comercial | No redistribuir raw ni exponer `hex` individual |
| MarineTraffic | Comercial | No redistribuir raw ni exponer `MMSI` individual |
| Liveuamap | Sin API pública | Riesgo legal propio |
| Mapbox GL JS | Comercial | Requiere token válido — respetar límites de plan |
