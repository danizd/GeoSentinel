# F-ING-MIL — Ingestor Vuelos Militares

> Cargar junto con: `E-ARCH` + `E-SOURCES §2.5` + `E-SOURCES §2.5-MIL`
> + `E-SEC` + `F-NORM-CANON` + `F-DEDUP`

## 1. Arquitectura

Este ingestor NO consulta OpenSky Network ni ADS-B Exchange directamente.
Consume el relay interno `/api/military/v1/list-military-flights`
que ya devuelve datos filtrados y normalizados desde OpenSky.

```
OpenSky Network
       ↓
   relay/militar       ← filtrado callsign + hex, cache por bbox
       ↓
   ingestor (este)     ← normalización al modelo canónico
       ↓
   events_canonical
```

El relay es un microservicio separado (FastAPI). Su implementación: ver §5.
La configuración del relay se realiza mediante variables de entorno:
- `MILITARY_SOURCE=opensky` — fuente de datos
- `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET` — credenciales
- `MILITARY_RELAY_URL` — URL donde corre el relay (default: `http://localhost:8002`)

Cuenta de OpenSky: `https://opensky-network.org/my-opensky/account`

## 2. Filtro de militaridad (implementado en el relay)

### Regla base
Conservar el vuelo si se cumple **cualquiera** de:
- **Categoría 7 de OpenSky** (`category == 7`) — marcador nativo de vuelo militar
- callsign coincide con patrón militar conocido
- hex ICAO pertenece a lista militar conocida

El filtro por categoría 7 captura todos los vuelos que OpenSky clasifica como militares, sin depender de patrones de callsign. Los patrones de callsign y la lista de hex son complementos.

### Patrones de callsign

**Prefijos largos** (match directo):
```python
MILITARY_CALLSIGN_PREFIXES_FULL = [
    # USA / NATO
    "RCH", "REACH", "MOOSE", "EVAC", "DUSTOFF",
    "VIPER", "RAPTOR", "SENTRY", "AWACS", "COBRA", "PYTHON",
    "NAVY", "USAF", "USN", "USMC", "NATO", "RAF",
    # Países europeos
    "FAF", "GAF", "AME", "ITAF", "PLF", "TUAF", "RFR",
    "SVF", "NAF", "BAF", "HAF", "ROF", "HUAF", "DAF",
    # Commonwealth / otros
    "CFC", "RCAF", "ASF", "IAF", "VKS", "PLAAF",
    # Tácticos / ejercicios
    "BLUE", "RED", "GOLD",
    "LION", "MACE", "SABER", "STORM", "THNDR",
    "DEMON", "HAWK", "EAGLE", "FALCON", "HORNET",
    "RAVEN", "DRAGON", "PHANTOM", "TIGER", "WOLF",
    "SPAR", "HKY", "CNV", "VV",
]
```

**Prefijos cortos** (solo si van seguidos de dígitos):
```python
MILITARY_CALLSIGN_PREFIXES_SHORT = [
    "AE", "RF", "TF", "PAT", "SAM",
    "OPS", "CTF", "IRG", "TAF",
]
# Regex: ^(AE|RF|TF|PAT|SAM|OPS|CTF|IRG|TAF)\d+
```

### Hex ICAO militar
- Mantener lista conocida en `data/military_hex.txt` (una entrada por línea)
- Normalizar siempre a **MAYÚSCULAS** antes de comparar y antes de cachear
- La lista debe ser actualizable sin redespliegue (fichero externo, no hardcoded)

## 3. Modelo canónico de vuelo militar

Forma estable que devuelve el relay al ingestor:

```typescript
interface MilitaryFlight {
  // Obligatorios
  id:            string        // hex + ':' + timestamp_unix
  callsign:      string
  hexCode:       string        // siempre MAYÚSCULAS
  location: {
    latitude:    number
    longitude:   number
  }
  altitude:      number        // pies
  heading:       number        // grados 0-360
  speed:         number        // nudos
  lastSeenAt:    string        // ISO 8601 UTC

  // Opcionales
  aircraftType?:    string
  operator?:        string
  operatorCountry?: string
  registration?:    string
  aircraftModel?:   string
  origin?:          string
  destination?:     string
  isInteresting?:   boolean
  confidence?:      number
}
```

## 4. Mapeo → `events_canonical`

| Campo MilitaryFlight | Campo canónico | Notas |
|----------------------|----------------|-------|
| `hexCode + ':' + lastSeenAt` | `event_id_source` | Clave de deduplicación |
| `lastSeenAt` | `event_time` | Ya en UTC ISO 8601 |
| `location.latitude/longitude` | `location_point` | WGS84 |
| `callsign` | `actors[0].name` | `role: 'military_aircraft'` |
| `operatorCountry` | `country_iso2` | Si disponible |
| `altitude` + `speed` | `source_refs` | Guardar como JSON string |
| — | `event_type` | `'military_flight'` |
| — | `category` | `'mobility'` |
| `confidence` (del relay) | `confidence` | Normalizar a escala 0–10 |

`source_independence_class = 'sensor'` — factor confianza: ×2.0

## 5. Implementación del relay

El relay es un microservicio ligero (FastAPI) que:

1. Recibe bbox del ingestor: `neLat, neLon, swLat, swLon`
2. Consulta OpenSky Network API con esas coordenadas (autenticación Basic Auth)
3. Aplica filtro callsign + hex ICAO (§2)
4. Normaliza la respuesta al modelo de §3
5. Cachea resultado por `hash(bbox)` durante 60 segundos
6. Devuelve `{ flights: MilitaryFlight[], clusters: MilitaryFlightCluster[] }`

**Variables de entorno requeridas**:
```dotenv
MILITARY_SOURCE=opensky
OPENSKY_CLIENT_ID=geosentinel
OPENSKY_CLIENT_SECRET=tu_secret_aqui
MILITARY_RELAY_URL=http://localhost:8002
```

**Límite de rate**: OpenSky gratuito permite 1 req/segundo.
El relay debe respetar este límite; si se supera, esperar y reintentar.

**Cache de fallback**: si OpenSky falla, devolver última
respuesta válida para ese bbox con header `X-Stale: true`.
El ingestor debe registrar `source_refs: ['stale_cache']` en ese caso.

**Inicio del relay**:
```bash
cd C:\Proyextos\GeoSentinel
$env:PYTHONPATH = "C:\Proyextos\GeoSentinel"
python -m services.military_relay.main
```

El relay escuchará en el puerto definido por `MILITARY_RELAY_URL` (default 8002).

## 6. Deduplicación

Clave natural: `hexCode.toUpperCase() + ':' + timestamp_unix_60s`

El sufijo `_60s` redondea el timestamp al minuto más cercano,
evitando duplicados por llamadas consecutivas del mismo vuelo:

```python
def military_event_id(hex_code: str, last_seen_at: str) -> str:
    ts = datetime.fromisoformat(last_seen_at)
    ts_60 = int(ts.timestamp() // 60) * 60
    return f"{hex_code.upper()}:{ts_60}"
```

## 7. Lógica de detección de anomalías

Solo escalar a incidente (o enriquecer incidente existente) si:

- Vuelo en radio < 50 km de incidente activo con `category='conflict'`
- `isInteresting = true` según el relay
- Altitud 0 sobre territorio en conflicto activo > 10 min
  (posible aeronave derribada o aterrizaje de emergencia)
- Agrupamiento: ≥ 3 aeronaves militares en radio < 100 km

Vuelos que no cumplen ninguna condición → registrar en
`events_canonical` pero NO generar incidente nuevo automáticamente.

## 8. Restricciones de exposición (ver `E-SEC`)

- `hexCode` individual **nunca** en respuestas de `/v1/incidents` público
- `callsign` puede exponerse de forma agregada
- Datos de origen/destino solo en contextos con scope `incidents:read`
  y solo si `operatorCountry` no es aliado sensible (decisión operacional)

## 9. Visualización en frontend

Ver `F-UI-MAP`. Las capas específicas para vuelos militares son:

### Arquitectura de renderizado

El frontend **NO usa DeckGL** para las capas de vuelos militares. Usa capas **nativas de Mapbox GL JS** (symbol + circle layers) porque:
- `IconLayer` de DeckGL es incompatible con `MapboxOverlay` (no comparte texturas en el contexto WebGL de Mapbox)
- La arquitectura DeckGL-como-raíz obliga a renunciar al globo 3D
- Las capas nativas de Mapbox soportan globo 3D, SDF, rotación por propiedad y colorización dinámica sin depender de texturas WebGL externas

### Registro del icono

El icono del avión (✈ Unicode) se registra como imagen SDF en el evento `onLoad` del mapa:
1. Se renderiza el carácter ✈ en un `<canvas>` de 48×48px con `fillText`
2. El canvas se convierte a `Image` vía `canvas.toDataURL()`
3. La imagen se añade al estilo del mapa con `map.addImage('airplane-icon', img, { sdf: true })`

### Capas Mapbox (en orden z)

| Capa | Tipo | Propósito |
|------|------|-----------|
| `military-flights-halo-dark` | `circle` | Halo exterior oscuro (14px, opacity 0.35) — contraste sobre zonas claras |
| `military-flights-halo-light` | `circle` | Halo interior blanco (10px, opacity 0.3) — contraste sobre zonas oscuras |
| `military-flights-symbol` | `symbol` | Icono ✈ SDF, rotado por `heading`, coloreado por `operatorCountry`, `icon-rotation-alignment: map` |
| `military-trails-line` | `line` | Trails de vuelo (GeoJSON LineString), color por país, opacity 0.5 |

### Selección y popup

- Click sobre el icono → `onClick` del Map filtra features de `military-flights-symbol`
- Al seleccionar un vuelo → panel fijo `absolute bottom-4 right-4` con info completa
- El panel muestra: callsign, hex, altitud, velocidad, rumbo, país, tipo, operador, lat/lon
- Click fuera o botón × cierra el panel

### Mapa de colores por país

```typescript
const COUNTRY_COLORS: Record<string, string> = {
  'United States': '#3B82F6',  // blue
  'United Kingdom': '#06B6D4',  // cyan
  'Russia': '#EF4444',          // red
  'China': '#EAB308',           // yellow
  'France': '#A855F7',          // purple
  'Luxembourg': '#84CC16',      // lime
   default: '#FBBF24',          // orange
}
```

La capa de vuelos militares se activa desde el control
`[TRACKS]` en `LayerControls` (`F-UI-MAP §5`).