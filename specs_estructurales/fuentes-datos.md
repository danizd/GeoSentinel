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
| ADS-B Exchange | `sensor` | Actividad aérea anómala | Medio (comercial) |
| MarineTraffic | `sensor` | Actividad naval | Medio (comercial) |
| Liveuamap | `media_derived` | Detección rápida conflictos | **Alto** (sin API pública) |
| ReliefWeb | `field_reported` | Contexto humanitario | Bajo |

---

## 2. Contratos de API por fuente

### 2.1 GDELT Cloud Events v2

- **Endpoint base**: `https://api.gdeltcloud.com/v2/`
- **Autenticación**: API key en header `X-API-Key`
- **Frecuencia de polling**: cada 5 minutos
- **Filtro recomendado**: `event_family=conflict` para reducir volumen
- **Formato de respuesta**: JSON
- **Latencia típica desde evento**: 15–30 min
- **Licencia**: Dominio público
- **Documentación**: `https://docs.gdeltcloud.com`

### 2.2 ACLED

- **Endpoint base**: `https://api.acleddata.com/acled/read`
- **Autenticación**: `?key=<API_KEY>&email=<EMAIL>` (query params)
- **Frecuencia de polling**: diaria (la fuente actualiza aprox. semanal/quincenal por región)
- **Lag real por región**: 7–28 días. Diseñar backfill para ventanas sin datos.
- **Campos clave**: `event_date`, `latitude`, `longitude`, `event_type`,
  `actor1`, `actor2`, `fatalities`, `geo_precision`, `data_id`
- **`geo_precision`**: 1=exacta, 2=ciudad/pueblo, 3=ADM2, 4=ADM1, 5=país
- **Formato**: JSON o CSV
- **Licencia**: CC BY-NC 4.0 (solo uso no comercial)
- **Documentación**: `https://acleddata.com/api-documentation/`

### 2.3 FIRMS (NASA Fire Information)

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

### 2.5 ADS-B Exchange

- **Endpoint base**: `https://adsbexchange.com/api/aircraft/v2/`
- **Autenticación**: API key en header `api-auth`
- **Frecuencia**: cada 60 segundos (posición actual)
- **Filtros**: por bounding box o por `hex` (ICAO de aeronave)
- **Campos clave**: `hex`, `flight`, `lat`, `lon`, `alt_baro`, `gs`, `track`,
  `t` (timestamp Unix), `mil` (militar: true/false)
- **Licencia**: Comercial — restricciones de redistribución
- **Uso**: Detectar actividad aérea inusual cerca de AOIs activos

### 2.6 MarineTraffic AIS API

- **Endpoint base**: `https://services.marinetraffic.com/api/`
- **Autenticación**: `?v=<version>&msgtype=json&apikey=<API_KEY>`
- **Frecuencia**: cada 5 minutos por AOI
- **Campos clave**: `MMSI`, `LAT`, `LON`, `SPEED`, `HEADING`,
  `SHIPNAME`, `SHIPTYPE`, `TIMESTAMP`
- **Licencia**: Comercial — prohibida redistribución de datos brutos
- **Uso**: Detectar actividad naval anómala (velocidad 0 en zonas de conflicto,
  agrupamiento inusual, entrada en zonas restringidas)

### 2.7 Liveuamap

- **⚠️ Estado: FUENTE DE RIESGO ALTO**
- No existe API pública documentada ni contrato de SLA.
- El repositorio referenciado (`liveuamap/liveuamap.consolecsharp.api`)
  es un cliente no oficial, no mantenido.
- **Estrategia**: implementar como fuente opcional desactivable sin afectar
  al resto del pipeline. Ver decisión D5 en `AGENTS.md`.
- **Alternativas a evaluar**: Bellingcat, NATO crisis monitors, fuentes OSINT
  con API documentada.

### 2.8 ReliefWeb API

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
| ADS-B | < 3 minutos |
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
ACLED_API_KEY=
ACLED_EMAIL=

# FIRMS
FIRMS_MAP_KEY=

# ADS-B Exchange
ADSB_API_KEY=

# MarineTraffic
MARINETRAFFIC_API_KEY=

# ReliefWeb
RELIEFWEB_APP_NAME=

# Liveuamap (opcional, desactivable)
LIVEUAMAP_ENABLED=false
LIVEUAMAP_API_KEY=
```

Ninguna clave se hardcodea en código. Gestionadas via `.env` local
y secrets de Kubernetes en producción (ver `E-INFRA`).
