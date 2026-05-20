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

## 9. Visualización en frontend — implementación detallada

Ver `F-UI-MAP`. Esta sección documenta la solución final y los problemas
que llevaron a ella.

---

### 9.1 Historial de intentos fallidos

El camino hasta la solución actual pasó por múltiples iteraciones.
Cada una falló por una razón específica. Se documentan aquí para evitar
repetirlas.

#### Intento 1: IconLayer de DeckGL con PNG externo
```
DeckGL > MapboxOverlay > IconLayer(iconAtlas: '/avion.png')
```
- **Síntoma**: el icono nunca se renderizaba.
- **Causa**: `MapboxOverlay` comparte el contexto WebGL de Mapbox GL JS.
  `IconLayer` intenta crear una textura desde una URL externa, pero la
  carga asíncrona de la imagen no se completa antes del primer frame.
  DeckGL no lanza error, simplemente no pinta.
- **Conclusión**: `IconLayer` + textura desde URL es incompatible con
  `MapboxOverlay`.

#### Intento 2: IconLayer con SVG data URL inline (`encodeURIComponent`)
```
IconLayer(iconAtlas: 'data:image/svg+xml,...')
```
- **Síntoma**: igual que el intento 1. Sin errores, sin renderizado.
- **Causa**: aunque el data URL se resuelve sincrónicamente, la
  decodificación del SVG a textura WebGL falla en el contexto prestado
  de Mapbox.
- **Conclusión**: el formato de imagen (PNG/SVG/data URL) no es el
  problema; el problema es el contexto WebGL.

#### Intento 3: IconLayer con `<canvas>` HTML generado en módulo
```
const atlas = buildAirplaneAtlas()  // canvas.toDataURL()
IconLayer(iconAtlas: atlas)
```
- **Síntoma**: renderizado intermitente. A veces visible, a veces no.
- **Causa**: el canvas se crea una vez al cargar el módulo. Cuando
  `setProps({ layers })` actualiza las capas en el overlay, la textura
  ya está resuelta pero el contexto WebGL de Mapbox la descarta en
  ciertos frames.
- **Conclusión**: inconsistente. No apto para producción.

#### Intento 4: DeckGL como raíz (sin MapboxOverlay)
```
DeckGL(controller=true) > Map(react-map-gl)
```
- **Síntoma**: los iconos se renderizan pero **no se anclan al globo 3D**.
  En 3D, los puntos flotan en el espacio.
- **Causa**: DeckGL usa proyección Web Mercator plana; Mapbox en modo
  globo usa proyección esférica. Las coordenadas no coinciden cuando hay
  `pitch > 0` o `projection: 'globe'`.
- **Conclusión**: DeckGL no soporta globo 3D de Mapbox. Forzar 2D
  Mercator resuelve el anclaje pero **pierde el globo 3D**, que es
  un requisito de la aplicación.

#### Intento 5: Marcadores HTML DOM (`<Marker>` con ✈ Unicode)
```
<Marker longitude={...} latitude={...}>
  <div style={{ transform: `rotate(${heading}deg)` }}>✈</div>
</Marker>
```
- **Síntoma**: los marcadores no se anclan correctamente. Flotan al
  mover el mapa.
- **Causa**: `react-map-gl` v7 + proyección globo no sincroniza bien
  la posición de `Marker` en el viewport.
- **Conclusión**: viola D12 de AGENTS.md. Descartado.

---

### 9.2 Solución final: Mapbox SDF con iconos SVG cargados vía loadImage

#### Arquitectura

```
Map (react-map-gl, dueño del canvas)
  └── Source (GeoJSON de flights)
        ├── Layer circle (halo oscuro)
        ├── Layer circle (halo claro)
        └── Layer symbol (SDF SVG, rotado, coloreado)
```

No se usa DeckGL para las capas militares. Todo es nativo de Mapbox GL JS.

#### ¿Por qué funciona?

1. **Iconos SVG nativos**: los iconos se cargan con `map.loadImage()`
   desde archivos SVG en `public/icons/`. Mapbox los rasteriza internamente
   a la resolución del dispositivo, sin depender de la fuente del sistema.
2. **SDF (Signed Distance Field)**: `map.addImage('airplane-icon', img, { sdf: true })`.
   El modo SDF permite que Mapbox coloree dinámicamente el icono con
   `icon-color` y lo escale sin pérdida de calidad.
3. **`icon-rotation-alignment: 'map'`**: el icono rota respecto al norte
   geográfico, no respecto a la pantalla. Esto es esencial para que el
   rumbo del avión se muestre correctamente en el globo 3D.
4. **Renderizado nativo**: al ser capas de Mapbox (no de DeckGL), el
   globo 3D, el pitch y el bearing funcionan sin problemas.
5. **Sin dependencia del SO**: los SVG son idénticos en Windows, macOS
   y Linux. No hay variabilidad de glifos como con caracteres Unicode
   (`✈`, `⛵`, `⛨`).

#### Registro de iconos (detalle de implementación)

Los iconos SVG se cargan en el evento `onLoad` del mapa con
`map.loadImage()`:

```typescript
// IncidentMap.tsx — handleMapLoad
const handleMapLoad = useCallback((e: any) => {
  const map = e.target

  const icons = [
    { url: '/icons/airplane.svg', id: 'airplane-icon' },
    { url: '/icons/ship.svg', id: 'ship-icon' },
    { url: '/icons/shield.svg', id: 'shield-icon' },
  ]

  icons.forEach(({ url, id }) => {
    if (map.hasImage(id)) return
    map.loadImage(url, (err: any, img: any) => {
      if (err) {
        console.error(`Error loading icon ${id}:`, err)
        return
      }
      if (!map.hasImage(id)) {
        map.addImage(id, img, { sdf: true })
      }
    })
  })
}, [])
```

**Iconos disponibles** (`frontend/public/icons/`):

| Archivo | Icono | ViewBox | Relleno |
|---------|-------|---------|---------|
| `airplane.svg` | Silueta de avión militar (vista superior, nariz al norte) | 24×24 | `#FFFFFF` |
| `ship.svg` | Silueta de buque (vista superior) | 24×24 | `#FFFFFF` |
| `shield.svg` | Escudo militar | 24×24 | `#FBBF24` |

**Requisitos de los SVG**: sin atributos `width`/`height` fijos (Mapbox
escala con `icon-size`), sin `stroke` (no funciona bien con SDF), sin
gradientes ni filtros, `<path>` con `fill` sólido centrado en el viewBox.
Para aviones, la nariz apunta hacia arriba (0° = norte) y Mapbox rota
en sentido horario.

**Por qué `onLoad` y no `useEffect` con `useMap()`**:
- `useMap()` dentro de un componente hijo puede devolver `null` si el
  mapa aún no está montado.
- `onLoad` se dispara exactamente cuando el mapa está listo para aceptar
  imágenes. Es el momento canónico para `addImage()`.

**Por qué `map.loadImage()` y no canvas+Unicode** (ver F-CORR-001):
Los caracteres Unicode dependen de la fuente del sistema operativo y no
fueron diseñados como iconos de mapa. Los SVG producen siluetas
predecibles, nítidas y escalables sin depender del SO. Además, el
código es más simple: 1 llamada a `loadImage` frente a 5 pasos
(canvas → fillText → toDataURL → new Image → addImage).

#### Contraste: sistema de doble halo

El icono por sí solo no tiene suficiente contraste contra fondos
variables (satélite oscuro, calles claras, nubes). Se usa un sistema de
**doble halo** mediante dos capas `circle` debajo del icono:

```
Capa halo-dark (circle, #000, 14px, 35% opacity)
  └── Capa halo-light (circle, #FFF, 10px, 30% opacity)
        └── Capa symbol (SDF SVG, color país, 95% opacity)
```

```json
// Capa 1: halo exterior oscuro — contraste sobre zonas claras (nubes, desierto)
{
  "id": "military-flights-halo-dark",
  "type": "circle",
  "paint": {
    "circle-radius": 14,
    "circle-color": "#000000",
    "circle-opacity": 0.35
  }
}

// Capa 2: halo interior blanco — contraste sobre zonas oscuras (satélite, mar)
{
  "id": "military-flights-halo-light",
  "type": "circle",
  "paint": {
    "circle-radius": 10,
    "circle-color": "#FFFFFF",
    "circle-opacity": 0.3
  }
}

// Capa 3: icono del avión
{
  "id": "military-flights-symbol",
  "type": "symbol",
  "layout": {
    "icon-image": "airplane-icon",
    "icon-size": 0.35,
    "icon-allow-overlap": true,
    "icon-ignore-placement": true,
    "icon-rotate": ["get", "heading"],
    "icon-rotation-alignment": "map"
  },
  "paint": {
    "icon-color": ["get", "color"],
    "icon-opacity": 0.95
  }
}
```

**Por qué dos halos**: un solo halo blanco es invisible sobre fondo
claro (desierto, nubes). Un solo halo negro es invisible sobre fondo
oscuro (satélite, mar). La combinación de ambos garantiza contraste
en cualquier terreno.

#### Datos: GeoJSON generado desde la API

Los flights se convierten a GeoJSON en un `useMemo`:

```typescript
const geojson = useMemo(() => ({
  type: 'FeatureCollection' as const,
  features: flights.map(f => ({
    type: 'Feature' as const,
    properties: {
      id: f.id,
      callsign: f.callsign,
      heading: f.heading,
      color: getMilitaryColor(f.operatorCountry),
    },
    geometry: {
      type: 'Point' as const,
      coordinates: [f.location.longitude, f.location.latitude],
    },
  })),
}), [flights])
```

Las propiedades `heading` y `color` se usan como data-driven properties
en las capas Mapbox (`["get", "heading"]`, `["get", "color"]`).

#### Selección de vuelo y popup

El click se captura con el evento `onClick` del componente `Map` de
react-map-gl, filtrando por `interactiveLayerIds`:

```typescript
<Map
  onClick={handleFlightClick}
  interactiveLayerIds={['military-flights-symbol']}
  ...
>
```

```typescript
const handleFlightClick = (e: any) => {
  const features = e.features || []
  for (const feature of features) {
    if (feature.layer?.id === 'military-flights-symbol'
        || feature.source === 'military-flights-src') {
      const props = feature.properties
      if (props?.id) {
        const flight = flights.find(f => f.id === props.id)
        if (flight) {
          setSelectedFlight(flight)
          return
        }
      }
    }
  }
  setSelectedFlight(null)  // click fuera = deseleccionar
}
```

El popup es un panel **fijo** (no un Marker) posicionado con
`absolute bottom-4 right-4` para que no se mueva con el mapa:

```typescript
{selectedFlight && (
  <div className="absolute bottom-4 right-4 ...">
    <div>Callsign: {selectedFlight.callsign}</div>
    <div>Hex: {selectedFlight.hexCode}</div>
    <div>Alt: {selectedFlight.altitude} ft</div>
    <div>Spd: {selectedFlight.speed} kts</div>
    <div>Hdg: {selectedFlight.heading}°</div>
    <div>Country: {selectedFlight.operatorCountry}</div>
    {selectedFlight.aircraftType && <div>Type: {selectedFlight.aircraftType}</div>}
    {selectedFlight.aircraftModel && <div>Model: {selectedFlight.aircraftModel}</div>}
    {selectedFlight.registration && <div>Reg: {selectedFlight.registration}</div>}
  </div>
)}
```

#### Mapa de colores por país

```typescript
function getMilitaryColor(country?: string | null): string {
  const mapping: Record<string, string> = {
    'United States': '#3B82F6',   // blue
    'United Kingdom': '#06B6D4',   // cyan
    'Russia':         '#EF4444',   // red
    'China':          '#EAB308',   // yellow
    'France':         '#A855F7',   // purple
    'Luxembourg':     '#84CC16',   // lime
  }
  if (!country) return '#FFFFFF'
  return mapping[country] || '#FBBF24'  // default: orange
}
```

---

### 9.3 Lecciones aprendidas

| Problema | Causa raíz | Solución |
|----------|-----------|----------|
| IconLayer no renderiza | MapboxOverlay = contexto WebGL ajeno | Renderizado nativo Mapbox |
| Icono flota en globo 3D | DeckGL no soporta proyección globo | Capas nativas Mapbox con `icon-rotation-alignment: map` |
| SDF no se carga a tiempo | `useMap()` retorna null antes de mount | `onLoad` del Map como punto de registro |
| Sin contraste en satélite | Fondo variable (claro/oscuro) | Doble halo (oscuro + blanco) |
| Popup se mueve con el mapa | `Marker` sigue coordenadas geográficas | Panel fijo con `absolute` positioning |