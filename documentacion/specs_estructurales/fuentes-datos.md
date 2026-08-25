# E-SOURCES — Inventario de Fuentes de Datos

> **Spec estructural / transversal** — Obligatoria al añadir, modificar
> o sustituir cualquier fuente externa. Contiene los contratos de API
> corregidos y validados.

---

## 1. Clasificación de fuentes

| Fuente | Clase | Rol en el sistema | Riesgo |
|--------|-------|-------------------|--------|
| GDELT Cloud Events v2 | `media_derived` | Detección rápida de conflictos | Bajo |
| ACLED | `field_reported` | Confirmación estructurada | Bajo |
| FIRMS (NASA) | `sensor` | Detección de incendios | Bajo |
| USGS | `sensor` | Terremotos tiempo real | Bajo |
| OpenSky Network | `sensor` | Vuelos militares | Bajo |
| AISStream | `sensor` | Buques AIS tiempo real | Medio (comercial) |
| MarineTraffic | `sensor` | Actividad naval enriquecida | Medio (comercial) |
| Liveuamap | `media_derived` | Detección rápida conflictos | **Alto** (sin API pública) |
| ReliefWeb | `field_reported` | Contexto humanitario | Bajo |
| CR360 (Conflict Radar 360) | `media_derived` | Radar de conflictos OSINT (página `/radar`, **fuera del pipeline canónico**) | Medio (licencia no verificada, rate limit) |

---

## 2. Contratos de API por fuente

### 2.1 GDELT Cloud Events v2 (https://gdeltcloud.com/dashboard)

##### Resumen
GDELT Cloud v2 es la interfaz recomendada para nuevos desarrollos sobre productos generados de GDELT Cloud, incluyendo Events, Stories, summaries, descubrimiento de entidades y geografía administrativa.[1] La documentación oficial la presenta como una superficie simplificada y orientada a producto, distinta de la API clásica de GDELT Project, y especifica autenticación mediante API key enviada como Bearer token.[1]
https://gdeltcloud.com/dashboard

##### Base y autenticación
La API usa autenticación por cabecera `Authorization: Bearer gdelt_sk_...`.[1] La documentación oficial indica que v2 reutiliza el mismo formato de API key que v1, pero recomienda v2 para nuevos dashboards, flujos de monitorización y búsquedas ad hoc.[1]
Permite 100 llamadas al mes a la API y se resetea el dia 1 de cada mes

###### Ejemplo de cabecera
```http
Authorization: Bearer gdelt_sk_...
```

###### Dominio base
Los ejemplos documentados usan el dominio `https://gdeltcloud.com/api/v2/`.[1]

##### Diseño funcional
La API v2 se centra en objetos generados y normalizados, no en campos crudos de GDELT clásico.[1] La documentación indica expresamente que v2 se enfoca en Events estructurados, Stories agrupadas, métricas generadas, descubrimiento de entidades y enlaces entre entidades, Stories y Events.[1]

También aclara que v2 **no expone** campos legacy o knobs de ajuste como `scope`, `detail`, `geo_scope`, `event_readiness`, `cluster_certainty`, `language`, `quad_class` o `raw total_events`.[1]

##### Endpoints principales
| Endpoint | Descripción |
|---|---|
| `GET /api/v2/events` | Lista Events estructurados.[1] |
| `GET /api/v2/events/{event_id}` | Devuelve un Event concreto.[1] |
| `GET /api/v2/events/summary` | Resumen agregado de Events por bucket.[1] |
| `GET /api/v2/stories` | Lista Stories agrupadas.[1] |
| `GET /api/v2/stories/{story_id}` | Devuelve una Story concreta.[1] |
| `GET /api/v2/stories/{story_id}/articles` | Lista completa de artículos de una Story.[1] |
| `GET /api/v2/stories/summary` | Resumen agregado de Stories.[1] |
| `GET /api/v2/entities` | Lista entidades descubiertas.[1] |
| `GET /api/v2/entities/{entity_id}` | Perfil y enlaces de una entidad.[1] |
| `GET /api/v2/geo/admin1` | Descubre valores válidos de `admin1` por país.[1] |

##### Convenciones de geografía
La documentación recomienda usar nombres de país en inglés natural, como `France`, `United States` o `South Korea`.[1] El backend acepta también ISO-3 y aliases legacy FIPS por compatibilidad, pero normaliza la salida del país a nombre inglés plano.[1]

Los filtros `region` y `continent` se expanden internamente a listas ISO-3.[1] En Events, los filtros geográficos hacen match tanto por localización del evento como por países de origen de actores; en Stories ocurre algo equivalente a través de Events enlazados.[1]

`admin1` es opcional y filtra solo la localización del evento o story, no el origen de actores.[1] Cuando un match geográfico amplio se produce por origen del actor y no por localización primaria, la API lo refleja en `geo_context.actor_origin_countries`.[1]

##### Estructuras de respuesta
Los endpoints de lista devuelven un sobre con `success`, `data` y `pagination`.[1] Los endpoints de detalle devuelven un único objeto en `data`, y los endpoints summary devuelven `group_by` junto con buckets agregados en `data`.[1]

###### Envelope de lista
```json
{
  "success": true,
  "data": [],
  "pagination": {
    "limit": 25,
    "cursor": null,
    "next_cursor": "25"
  }
}
```

###### Error estándar
```json
{
  "success": false,
  "error": "Invalid continent. Use one of: Africa, Asia, Europe, North America, South America, Oceania",
  "code": "INVALID_CONTINENT"
}
```
La documentación publica este formato de error estándar.[1]

##### Events
Los Events son uno de los dos objetos principales de v2 y pueden pertenecer a las familias `conflict` o `cameoplus`.[1] El Event card documentado incluye identificador estable, geografía normalizada, actores, métricas, fatalities, referencias a stories y entidades, y top articles como evidencia resumida.[1]

###### Filtros comunes de `GET /api/v2/events`
| Parámetro | Descripción |
|---|---|
| `date_start`, `date_end` | Rango de fechas en `YYYY-MM-DD`.[1] |
| `country`, `region`, `continent`, `admin1` | Filtros geográficos.[1] |
| `event_family` | `conflict` o `cameoplus`.[1] |
| `category`, `subcategory` | Clasificación del evento; `category` acepta uno o varios valores separados por coma.[1] |
| `domain` | Uno de `POLITICAL`, `ECONOMIC`, `CORPORATE`, `TECHNOLOGY`, `INFRASTRUCTURE`, `HEALTH`, `INFORMATION`, `ENVIRONMENT`, `CRIME`.[1] |
| `has_fatalities` | `true` o `false`.[1] |
| `search` | Búsqueda semántica o libre en endpoints de lista.[1] |
| `sort` | `significance` o `recent`.[1] |
| `limit`, `cursor` | Paginación.[1] |

###### Ejemplo de consulta
```bash
curl "https://gdeltcloud.com/api/v2/events?country=France&category=Protests&date_start=2026-04-01&date_end=2026-04-17&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Campos principales de un Event
| Campo | Descripción |
|---|---|
| `id` | Identificador estable v2 del Event.[1] |
| `url`, `primary_story_url` | URL pública GDELT Cloud utilizable como cita si el Event tiene Story enlazada.[1] |
| `family` | `conflict` o `cameoplus`.[1] |
| `title`, `summary` | Título y resumen generados.[1] |
| `event_date` | Fecha del evento.[1] |
| `category`, `subcategory`, `domain`, `event_code` | Taxonomía y código asociado.[1] |
| `geo` | Localización principal del Event.[1] |
| `geo_context` | Explica matches geográficos amplios, incluido actor origin.[1] |
| `actors` | Actores con nombre, país normalizado y rol.[1] |
| `metrics` | Significance, Goldstein, magnitud, confianza y otras métricas según familia.[1] |
| `has_fatalities`, `fatalities` | Indicador y cuenta de fatalidades.[1] |
| `story_refs` | Referencias a Stories enlazadas.[1] |
| `entity_refs` | Entidades enlazadas con tipo y, cuando exista, Wikipedia URL.[1] |
| `top_articles` | Top 3 artículos inline.[1] |

###### Event Summary
`GET /api/v2/events/summary` acepta `group_by=date|country|region|continent|category|subcategory`.[1] La documentación indica que los summary buckets incluyen recuentos simples y estadísticas agregadas de significance, Goldstein, CAMEO+, confidence, article evidence y fatality counts o rates.[1]

Importante: los endpoints summary **no aceptan `search`**.[1] La recomendación oficial es usar primero el endpoint de lista para recuperación semántica y después el summary con filtros estructurados.[1]

###### Ejemplo de Event Summary
```bash
curl "https://gdeltcloud.com/api/v2/events/summary?region=Middle%20East&event_family=conflict&has_fatalities=true&group_by=country&date_start=2026-04-01&date_end=2026-04-17" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

##### Stories
Las Stories representan clusters narrativos y devuelven top articles como vista resumida de evidencia.[1] La story card incluye geografía principal inferida desde Events enlazados, métricas agregadas, linked events, entity refs y flags de fatalidades.[1]

###### Filtros comunes de `GET /api/v2/stories`
| Parámetro | Descripción |
|---|---|
| `date_start`, `date_end` | Rango de fechas.[1] |
| `country`, `region`, `continent`, `admin1` | Filtros geográficos.[1] |
| `category`, `event_category`, `subcategory`, `domain` | Filtros temáticos y por eventos enlazados.[1] |
| `has_events`, `has_fatalities` | Filtros booleanos.[1] |
| `article_count_min`, `article_count_max` | Volumen mínimo o máximo de artículos.[1] |
| `search` | Recuperación semántica en listas.[1] |
| `sort` | `significance` o `recent`.[1] |
| `limit`, `cursor` | Paginación.[1] |

###### Ejemplo de consulta
```bash
curl "https://gdeltcloud.com/api/v2/stories?continent=Asia&search=new%20data%20center%20projects&article_count_min=2&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Story Articles
Los endpoints de lista y detalle solo devuelven los top 3 artículos inline.[1] Para obtener el conjunto completo de fuentes, la documentación indica usar `GET /api/v2/stories/{story_id}/articles`, que además soporta paginación por `cursor`.[1]

###### Story Summary
`GET /api/v2/stories/summary` usa el mismo patrón general que Events summary, con `group_by=date|country|region|continent|category|subcategory`.[1] Los buckets incluyen story counts, linked event counts, article volume, recency y agregados de métricas derivadas de Events enlazados.[1]

También aquí, los endpoints summary **no aceptan `search`**.[1]

##### Entities
La API publica `GET /api/v2/entities` y `GET /api/v2/entities/{entity_id}` para descubrimiento y perfilado de entidades.[1] Las entity cards incluyen `id`, `url`, `name`, `type`, `wikipedia_url` y métricas como `article_count`, `mention_count`, `story_count`, `event_count` y `avg_salience`.[1]

Los perfiles de entidad añaden `story_refs` y `event_refs` enlazados.[1] La documentación aclara que esta primera iteración v2 está centrada en descubrimiento limpio y linking, mientras que un rediseño más profundo de entidades queda diferido.[1]

##### Admin1 discovery
Para descubrir valores válidos de `admin1`, la documentación recomienda consultar un país cada vez mediante `GET /api/v2/geo/admin1?country=...`.[1] La respuesta incluye `success`, `country`, la lista `admin1` y el `source`.[1]

###### Ejemplo
```bash
curl "https://gdeltcloud.com/api/v2/geo/admin1?country=France" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

##### Ranking y significance
El orden por defecto es `sort=significance`.[1] La documentación explica que Event significance combina Goldstein severity, magnitud CAMEO+, systemic importance, propagation potential, market sensitivity, fatalities, article evidence y confidence con pesos definidos.[1]

La fórmula publicada es: Goldstein severity 25%, CAMEO+ magnitude 20%, systemic importance 15%, propagation potential 10%, market sensitivity 10%, fatalities 10%, article evidence 5% y confidence 5%.[1] También especifica que `goldstein_scale` se expone públicamente, está presente para todos los Conflict Events, para los CAMEO+ políticos y puede ser `null` en dominios no políticos donde no sea significativo.[1]

En Stories, significance combina linked Event significance, article count capado y recency.[1] Cuando la prioridad es frescura en lugar de importancia, la documentación recomienda `sort=recent`.[1]

##### Buenas prácticas oficiales
La guía recomienda usar Events cuando se necesitan incidentes estructurados, actores, categorías, fatalities o métricas event-level.[1] Recomienda usar Stories cuando interesa una narrativa agrupada con evidencia periodística superior.[1]

También recomienda usar summaries para dashboards y trend charts, con drill-down posterior a Events o Stories usando los mismos filtros.[1] Para monitorización en vivo, aconseja consultar el último día poblado o una ventana móvil de 7 a 30 días usando `date_start` y `date_end` explícitos.[1]

La documentación añade que `search` debe reservarse para recuperación semántica en endpoints de lista, porque v2 embebe el texto de consulta, aplica filtros estructurados como candidate set y rankea por similitud coseno con embeddings almacenados.[1] Esto refuerza que summaries son analíticos, mientras que listas son de retrieval.[1]

##### Ejemplos de uso
###### Monitorización por país
```bash
curl "https://gdeltcloud.com/api/v2/events?country=United%20States&date_start=2026-04-11&date_end=2026-04-17&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Infraestructura
```bash
curl "https://gdeltcloud.com/api/v2/events?event_family=cameoplus&domain=INFRASTRUCTURE&country=United%20States&date_start=2026-04-11&date_end=2026-04-17&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Búsqueda semántica de eventos
```bash
curl "https://gdeltcloud.com/api/v2/events?search=attacks%20on%20energy%20infrastructure&date_start=2026-04-11&date_end=2026-04-17&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Protestas recientes
```bash
curl "https://gdeltcloud.com/api/v2/events?category=Protests,CRIME&country=India&date_start=2026-04-17&date_end=2026-04-17&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Trend diario
```bash
curl "https://gdeltcloud.com/api/v2/events/summary?category=Protests,CRIME&country=India&group_by=date&date_start=2026-04-11&date_end=2026-04-17" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Stories sobre data centers en Asia
```bash
curl "https://gdeltcloud.com/api/v2/stories?continent=Asia&search=new%20data%20center%20projects&article_count_min=1&date_start=2026-04-11&date_end=2026-04-17&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Fatal conflict monitoring
```bash
curl "https://gdeltcloud.com/api/v2/events?event_family=conflict&has_fatalities=true&country=Lebanon&date_start=2026-04-11&date_end=2026-04-17&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

###### Drilldown por admin1
```bash
curl "https://gdeltcloud.com/api/v2/geo/admin1?country=United%20States" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

```bash
curl "https://gdeltcloud.com/api/v2/events?country=United%20States&admin1=District%20of%20Columbia&date_start=2026-04-11&date_end=2026-04-17&sort=significance" \
 -H "Authorization: Bearer $GDELT_CLOUD_API_KEY"
```

##### JSON técnico resumido
```json
{
  "api": "GDELT Cloud",
  "version": "v2",
  "base_url": "https://gdeltcloud.com/api/v2",
  "authentication": {
    "type": "Bearer API key",
    "header": "Authorization: Bearer gdelt_sk_...",
    "required": true
  },
  "resources": [
    "events",
    "events/{event_id}",
    "events/summary",
    "stories",
    "stories/{story_id}",
    "stories/{story_id}/articles",
    "stories/summary",
    "entities",
    "entities/{entity_id}",
    "geo/admin1"
  ],
  "event_filters": [
    "date_start",
    "date_end",
    "country",
    "region",
    "continent",
    "admin1",
    "event_family",
    "category",
    "subcategory",
    "domain",
    "has_fatalities",
    "search",
    "sort",
    "limit",
    "cursor"
  ],
  "story_filters": [
    "date_start",
    "date_end",
    "country",
    "region",
    "continent",
    "admin1",
    "category",
    "event_category",
    "subcategory",
    "domain",
    "has_events",
    "has_fatalities",
    "article_count_min",
    "article_count_max",
    "search",
    "sort",
    "limit",
    "cursor"
  ],
  "summary_group_by": [
    "date",
    "country",
    "region",
    "continent",
    "category",
    "subcategory"
  ],
  "notes": [
    "Summary endpoints do not accept search.",
    "Use plain English geography names in docs and apps.",
    "Use geo/admin1 to discover valid admin1 values."
  ]
}
```

##### Referencia oficial
La referencia principal utilizada en esta guía es la documentación oficial de GDELT Cloud v2.[1]






### 2.2 ACLED (https://acleddata.com/myacled)


#### Resumen
La API de ACLED permite consultar eventos de conflicto mediante un endpoint REST autenticado con token Bearer obtenido a través de OAuth2 con *password grant*.[1] La documentación oficial relevante se concentra en la guía general de API, la página específica del endpoint ACLED y la explicación de los elementos comunes de la API.[1][2][3]

#### Endpoint base
El endpoint operativo para consultar datos ACLED es `https://acleddata.com/api/acled/read`.[1] La documentación del endpoint también presenta la base `https://acleddata.com/api/` y el recurso `acled`, que en la práctica se utiliza a través de la ruta anterior.[1]

##### Ejemplo de consulta
```text
https://acleddata.com/api/acled/read?_format=csv&country=Georgia|Armenia|Azerbaijan&year=2021
```
Ejemplos de este tipo aparecen en la documentación oficial del endpoint.[1]

#### Autenticación
La autenticación se realiza mediante OAuth2 usando el flujo **Resource Owner Password Credentials** (`grant_type=password`).[1] El token se solicita en `https://acleddata.com/oauth/token` enviando los parámetros `grant_type=password`, `client_id=acled`, `username=<email>` y `password=<password>` como `application/x-www-form-urlencoded`.[1]

##### Solicitud de token
```bash
curl -X POST 'https://acleddata.com/oauth/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=password' \
  --data-urlencode 'client_id=acled' \
  --data-urlencode 'username=TU_EMAIL' \
  --data-urlencode 'password=TU_PASSWORD'
```
La respuesta devuelve un token de acceso utilizable en las llamadas posteriores al endpoint ACLED.[1]

##### Uso del token
Las consultas al endpoint deben incluir la cabecera `Authorization: Bearer <ACCESS_TOKEN>`.[1] La documentación oficial muestra este patrón en los ejemplos de acceso autenticado.[1]

```bash
curl -X GET 'https://acleddata.com/api/acled/read?_format=json&limit=10' \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

#### Formatos de respuesta
La API soporta formatos de salida `json`, `csv` y `xml` mediante extensiones o el parámetro `_format`.[2] La documentación revisada no confirma de forma clara `txt` como formato estándar en la sección de elementos comunes, por lo que no conviene asumirlo sin validación adicional.[2]

##### Selección del formato
```text
?_format=json
?_format=csv
?_format=xml
```
La documentación oficial utiliza `_format` en los ejemplos, por lo que ese es el mecanismo más seguro para fijar el formato de respuesta.[1][2]

#### Estructura de la respuesta JSON
Cuando se solicita JSON, la respuesta incluye metadatos de envoltura además del array principal de datos.[1] Entre los campos documentados están `status`, `success`, `last_update`, `count`, `messages`, `data`, `filename` y `data_query_restrictions`.[1]

##### Esquema general
```json
{
  "status": 200,
  "success": true,
  "last_update": "...",
  "count": ...,
  "messages": [],
  "data": [...],
  "filename": "...",
  "data_query_restrictions": {...}
}
```
Este esquema resume la estructura que la documentación muestra para respuestas JSON del endpoint ACLED.[1]

#### Parámetros y filtros habituales
La API admite filtros sobre dimensiones como país, año, actores, tipos de evento, fechas y localización administrativa.[1] También documenta operadores y convenciones para paginación, tamaño de fichero y composición de consultas.[1][2]

##### Ejemplos frecuentes
- `country=Ukraine`
- `year=2025`
- `event_type=Battles`
- `limit=500`
- `page=2`
- `event_date=2025-01-01|2025-01-31`

Estos ejemplos son representativos de los filtros descritos en la documentación oficial y de su sintaxis general basada en parámetros de query string.[1][2]

#### Campos clave devueltos
La tabla oficial de columnas devueltas incluye identificadores, fechas, ubicación, taxonomía del evento, actores, impacto y metadatos de trazabilidad.[1]

| Categoría | Campos relevantes |
|---|---|
| Identificación | `event_id_cnty`[1] |
| Fecha | `event_date`, `year`, `time_precision`[1] |
| Ubicación | `region`, `country`, `admin1`, `admin2`, `admin3`, `location`, `latitude`, `longitude`, `geo_precision`[1] |
| Clasificación | `disorder_type`, `event_type`, `sub_event_type`[1] |
| Actores | `actor1`, `assoc_actor_1`, `inter1`, `actor2`, `assoc_actor_2`, `inter2`, `interaction`, `civilian_targeting`[1] |
| Impacto | `fatalities`, `tags`[1] |
| Metadatos | `iso`, `source`, `source_scale`, `notes`, `timestamp`[1] |
| Población | `population_*` cuando se solicita población ampliada[ cite:1] |

#### Precisión geográfica
`geo_precision` está documentado como un código numérico entre 1 y 3 que indica el nivel de certeza de la localización.[1] No se ha verificado en la documentación oficial revisada un rango de 1 a 5 para este campo.[1]

#### Frecuencia de actualización y polling
La documentación revisada no fija una frecuencia oficial de polling para clientes externos.[1][2] Tampoco se encontró en esas páginas una tabla oficial de *lag* por región o una promesa documental de actualización semanal, quincenal o por rangos de días.[1][2]

#### Restricciones de uso
El uso de los datos de ACLED está sujeto a términos específicos y restricciones de licencia publicadas por la organización.[4][5][6] La documentación de uso y acceso indica que el uso comercial requiere revisión específica y no debe asumirse como permitido por defecto.[4][5][6]


#### Recomendaciones de implementación
- Solicitar el token con `application/x-www-form-urlencoded`.[1]
- Enviar siempre `Authorization: Bearer <token>` en cada consulta.[1]
- Fijar el formato con `_format=json`, `_format=csv` o `_format=xml`.[1][2]
- No asumir permiso comercial sin revisión legal de los términos de ACLED.[4][5][6]
- Validar paginación, límites y restricciones de consulta antes de automatizar ingestas masivas.[1][2]

### 2.3 FIRMS (NASA Fire Information) (https://firms.modaps.eosdis.nasa.gov/api/map_key/)

- **Endpoint API**: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/<PRODUCT>/<AREA_COORDS>/<DAYS>/`
  - `MAP_KEY`: clave personal del usuario (no hardcodear)
  - `PRODUCT`: `VIIRS_SNPP_NRT`, `MODIS_NRT`, etc.
  - `AREA_COORDS`: `lon_min,lat_min,lon_max,lat_max` del AOI (no hardcodear región)
  - `DAYS`: 1–10
- **⚠️ Error anterior corregido**: la URL de ejemplo `Canada_QC/YourMapKey`
  era un placeholder incorrecto. Usar siempre AOI dinámico y MAP_KEY de entorno.
- **Frecuencia**: cada 1–3 horas (NRT tiene lag ~3 h)
- **Campos clave**: `latitude`, `longitude`, `acq_date`, `acq_time`,
  `satellite`, `instrument`, `frp`, `confidence`, `type`
- **`frp`** (Fire Radiative Power): en MW, proxy de intensidad del incendio
- **Precisión espacial**: 375 m (VIIRS) / 1 km (MODIS)
- **Licencia**: NASA, uso libre con atribución
- **Documentación**: `https://firms.modaps.eosdis.nasa.gov/api/`

### 2.4 USGS Earthquake Hazards

- **⚠️ URL corregida** (error detectado en documento original):
  ```
  # INCORRECTO (faltaba '?'):
  https://earthquake.usgs.gov/fdsnws/event/1/queryformat=geojson

  # CORRECTO:
  https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson
  ```
- **Parámetros clave**: `starttime`, `endtime`, `minmagnitude`, `maxdepth`,
  `minlatitude`, `minlongitude`, `maxlatitude`, `maxlongitude`
- **Frecuencia de polling**: cada 3 minutos (feed near-real-time)
- **Campos clave**: `id`, `properties.time` (epoch ms), `properties.mag`,
  `properties.place`, `geometry.coordinates` [lon, lat, depth]
- **Licencia**: Dominio público (U.S. government)
- **Documentación**: `https://earthquake.usgs.gov/fdsnws/event/1/`

### 2.5-MIL Military Flights (OpenSky Network)

- **Fuente primaria**: OpenSky Network — `https://opensky-network.org`
- **Cuenta**: `https://opensky-network.org/my-opensky/account`
- **Endpoint interno**: `GET /api/military/v1/list-military-flights`
  — servicio relay propio que consume OpenSky y normaliza antes de exponer al frontend
- **Parámetros**: `neLat`, `neLon`, `swLat`, `swLon`, `operator?`, `aircraftType?`
- **Patrón**: Pull polling cada 60 seg por bbox de AOIs activos
- **⚠️ No consultar sin bbox** — sin coordenadas devuelve respuesta vacía
- **Filtro de militaridad** (ver `F-ING-MIL`):
  - **Categoría 7** (`category == 7` en API de OpenSky) — captura todos los vuelos militares nativamente
  - **Callsign** — 53 prefijos militares conocidos (FAF, GAF, AME, PLF, CFC, SVF, DAF, etc.)
  - **Hex ICAO** — lista en `data/military_hex.txt` (85 entradas, ampliable sin redespliegue)
  - Cualquiera de los tres criterios activa el filtro
- **Frecuencia de datos OpenSky**: cada 5 segundos (estado)
- **Cache**: por bbox + ventana temporal de 60 seg para reducir
  presión sobre OpenSky
- **Fallback**: si la fuente en vivo falla, servir última lectura válida
  (stale) sin dejar la interfaz vacía
- **Autenticación**: Basic Auth con `OPENSKY_CLIENT_ID` y `OPENSKY_CLIENT_SECRET`
  (cuenta gratuita de OpenSky, limitada a 1 req/segundo)
- **Licencia**: OpenSky Network Terms of Use — uso no comercial permitido
- **Restricciones**: `hexCode` individual no se expone en API pública (ver `E-SEC`)
- **`source_independence_class`**: `sensor` — factor confianza: ×2.0
- **SLA latencia**: < 3 minutos (datos de OpenSky tienen lag ~5 seg)
- **Renderizado frontend**: capas nativas Mapbox (symbol + circle), iconos SVG cargados con `map.loadImage()`, registrados como SDF para coloreado dinámico por país, doble halo (oscuro + blanco) para contraste, sin dependencia de DeckGL

### 2.6 Ingestor AISStream (Buques AIS en Tiempo Real)

- **Fuente primaria**: AISStream.io — `https://aisstream.io`
- **Cuenta**: `https://aisstream.io/dashboard`
- **Arquitectura**: WebSocket, sin polling HTTP
  - Relay interno (`ais-relay`) mantiene conexión WS persistente con AISStream
  - El relay normaliza, escribe snapshot en Redis y detecta dark-ships
  - El ingestor consume `/api/ais/snapshot` y `/api/ais/events?since=T`
  - `AISSTREAM_API_KEY` nunca sale del relay
- **Endpoint del relay**:
  - `GET /api/ais/snapshot` — estado actual de todos los buques
  - `GET /api/ais/events?since=TIMESTAMP` — deltas incrementales
  - `GET /api/military/v1/list-military-vessels?bbox=...` — buques militares por AOI
  - `GET /health/ais` — estado WS upstream + age del snapshot
- **Patrón**: WebSocket persistente + snapshot Redis + polling de deltas cada 5s
- **Latencia**: tiempo real (sub-segundo desde emisión AIS)
- **Dark-ship detection**: si `now - lastAisUpdate > DARK_SHIP_THRESHOLD_MIN` (20 min, configurable) → `isDark=true`
- **Cache / fallback**: snapshot en Redis con TTL; si upstream cae → servir stale con `X-Stale: true`
- **Circuit breaker**: 5 fallos consecutivos → stale indefinido + métrica `ais_upstream_connected=0`
- **Enriquecimiento opcional**: USNI (United States Naval Institute) via API externa
- **Campos clave**: `mmsi`, `lat`, `lon`, `sog`, `cog`, `heading`, `navigationalStatus`, `vesselType`, `flag`, `isDark`
- **Autenticación**: `AISSTREAM_API_KEY` (API key de aisstream.io)
- **Licencia**: AISStream.io Terms of Service — uso comercial requiere plan de pago
- **Restricciones**: `mmsi` individual nunca en API pública (ver `E-SEC`); solo datos agregados por AOI
- **Relación con MarineTraffic**: fuentes complementarias. AISStream tiene menor latencia (WS vs polling 5 min) y detección nativa de dark-ships. MarineTraffic tiene datos enriquecidos. En deduplicación cross-fuente, AISStream tiene prioridad.
- **`source_independence_class`**: `sensor` — factor confianza: ×2.0
- **SLA latencia**: < 5 segundos (emisión AIS → relay → snapshot Redis)
- **Renderizado frontend**: capas nativas Mapbox (symbol SDF + circle doble halo), icono SVG de buque cargado con `map.loadImage()`, coloreado dinámico por bandera, trail de posiciones como capa `line`, sin dependencia de DeckGL
- **Métricas obligatorias**: `ais_upstream_connected`, `ais_inbound_per_sec`, `ais_snapshot_age_ms`, `ais_dark_ships_total`

**Variables de entorno requeridas**:
```dotenv
# Relay
AISSTREAM_API_KEY=
AIS_RELAY_URL=http://localhost:8003
AIS_SNAPSHOT_INTERVAL_MS=3000
DARK_SHIP_THRESHOLD_MIN=20

# Ingestor
AIS_POLL_EVENTS_MS=5000
```

### 2.7 MarineTraffic AIS API (complementaria)

- **Endpoint base**: `https://services.marinetraffic.com/api/`
- **Autenticación**: `?v=<version>&msgtype=json&apikey=<API_KEY>`
- **Frecuencia**: cada 5 minutos por AOI
- **Campos clave**: `MMSI`, `LAT`, `LON`, `SPEED`, `HEADING`,
  `SHIPNAME`, `SHIPTYPE`, `TIMESTAMP`
- **Licencia**: Comercial — prohibida redistribución de datos brutos
- **Uso**: Complemento de AISStream para datos enriquecidos. En deduplicación cross-fuente, AISStream tiene prioridad por menor latencia.
- **Nota**: No implementado en esta versión. Ver `F-ING-MT`.

### 2.8 Liveuamap

- **⚠️ Estado: FUENTE DE RIESGO ALTO**
- No existe API pública documentada ni contrato de SLA.
- El repositorio referenciado (`liveuamap/liveuamap.consolecsharp.api`)
  es un cliente no oficial, no mantenido.
- **Estrategia**: implementar como fuente opcional desactivable sin afectar
  al resto del pipeline. Ver decisión D5 en `AGENTS.md`.
- **Alternativas a evaluar**: Bellingcat, NATO crisis monitors, fuentes OSINT
  con API documentada.

### 2.10 CR360 — Conflict Radar 360 (radar de eventos y carreteras)

- **Sitio**: `https://www.conflictradar360.com/`
- **Base API**: `https://cr360-api.vercel.app/api/v2`
- **⚠️ CORS (verificado)**: la API **no puede llamarse desde el navegador**.
  - Con header `Origin` de navegador responde `500`.
  - Sin `Origin` responde `200` pero sin `Access-Control-Allow-Origin`.
  - El preflight `OPTIONS` devuelve `500`.
  - **Todo el tráfico debe pasar por el proxy propio** `GET /v1/cr360/*` (ver `F-UI-*` radar).
- **Endpoints**:
  - `GET /public/map/events?lang=es&maxHours=72` — FeatureCollection mundial de eventos (puntos). Sin filtro server-side por país (parámetro `countryCode` ignorado, verificado) → filtrar en el proxy.
  - `GET /events/{id}?lang=es` — detalle completo de un evento (media, enlaces, fuerza, confianza). Público, sin auth.
  - `GET /public/map/compromised-roads?lang=es` — FeatureCollection de carreteras comprometidas (LineString). `maxHours` no tiene efecto (dataset estático).
  - `GET /public/map/regions?lang=es` — FeatureCollection mundial de **regiones** (polígonos `Polygon`/`MultiPolygon`): **~10.600 features / ~15 MB** (verificado). Sin filtro server-side ni ventana temporal. España ~209 regiones, Ucrania ~101, **Rusia 0** (ago 2026). Misma caché en memoria (15 MB) + filtrado por `countryCode` en el proxy.
- **Filtrado por país**: `countryCode` ISO-3 en `properties` (ESP/RUS/UKR...). El proxy recibe `?countries=ESP,RUS,UKR` y valida formato `^[A-Z]{3}(,[A-Z]{3})*$`.
- **Rate limit upstream**: `X-Ratelimit-Limit: 100` (verificado). El proxy cachea en memoria (TTL por defecto 3 h) para no quemarlo con los detalles por click.
- **Media (CDN verificado)**: `publicId` tipo `cr360/g4jxr6vvgmd8ozh4xvbb` → `https://res.cloudinary.com/dmmlghevj/image/upload/f_auto,q_auto/<publicId>` (Cloudinary). Los iconos (`cr360/icons/<id>`) usan el mismo patrón.
- **Frecuencia**: la página `/radar` hace polling cada 3 h (configurable `VITE_POLL_CR360_MS`); el proxy reutiliza su caché para no llamar upstream más de 1 vez por TTL.
- **Licencia**: **no documentada / no verificada**. Uso bajo responsabilidad del operador; requiere atribución prudente.
- **Fuera del pipeline canónico**: CR360 alimenta la página `/radar` directamente (no pasa por `events_canonical`, dedup, clustering ni quarantine).

### 2.11 Natural Earth — fronteras estáticas (dominio público)

- **Origen**: Natural Earth 1:10m admin-0 countries (`ne_10m_admin_0_countries.geojson`), dominio público.
- **Uso**: remarcar los límites nacionales en el radar (p. ej. frontera de Ucrania). No es una API en vivo: es un asset estático.
- **Asset**: `frontend/public/geojson/ukraine-border.geojson` — feature extraída (MultiPolygon, incluye Crimea), ~58 KB, servida por Vite en `/geojson/ukraine-border.geojson`.
- **Actualización**: manual; re-extraer de Natural Earth si cambia la frontera.
- **Licencia**: dominio público (Natural Earth). Atribución recomendada.

### 2.9 ReliefWeb API

- **Endpoint base**: `https://api.reliefweb.int/v1/`
- **Autenticación**: `?appname=<your-app-name>` (requerido pero libre)
- **Recursos principales**: `/reports`, `/disasters`, `/jobs`
- **Uso**: Enriquecimiento humanitario de incidentes existentes (no detección)
- **Frecuencia**: diaria / bajo demanda
- **Licencia**: CC BY 3.0 IGO










---

## 3. SLAs de latencia objetivo

| Fuente | Latencia máxima aceptable (evento → `/incidents`) |
|--------|--------------------------------------------------|
| USGS | < 5 minutos |
| GDELT | < 20 minutos |
| OpenSky (militar) | < 3 minutos |
| AISStream | < 5 segundos |
| FIRMS | < 3 horas |
| MarineTraffic | < 10 minutos |
| Liveuamap | < 20 minutos (si activo) |
| ACLED | < 24 horas desde publicación semanal |
| ReliefWeb | < 24 horas (enriquecimiento, no detección) |

> Los SLAs se monitorean mediante métricas en `E-MON`.

---

## 4. Variables de entorno requeridas por fuente

```dotenv
# GDELT
GDELT_API_KEY=

# ACLED
ACLED_USERNAME=
ACLED_PASSWORD=
ACLED_ACCESS_TOKEN=

# FIRMS
FIRMS_MAP_KEY=

# ADS-B Exchange
ADSB_API_KEY=

# OpenSky Network (vuelos militares)
OPENSKY_CLIENT_ID=
OPENSKY_CLIENT_SECRET=

# MarineTraffic
MARINETRAFFIC_API_KEY=

# ReliefWeb
RELIEFWEB_APP_NAME=

# Liveuamap (opcional, desactivable)
LIVEUAMAP_ENABLED=false
LIVEUAMAP_API_KEY=

# CR360 (Conflict Radar 360) — proxy de la página /radar
CR360_BASE_URL=https://cr360-api.vercel.app
CR360_CACHE_TTL_SECONDS=10800
CR360_UPSTREAM_TIMEOUT_SECONDS=15
CR360_EVENTS_MAX_HOURS=72

# Configuración del relay militar
MILITARY_SOURCE=opensky
MILITARY_RELAY_URL=http://localhost:8002
```

Ninguna clave se hardcodea en código. Gestionadas via `.env` local
y secrets de Kubernetes en producción (ver `E-INFRA`).
