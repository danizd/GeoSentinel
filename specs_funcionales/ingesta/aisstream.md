# F-ING-AIS — Ingestor AISStream (Buques AIS en Tiempo Real)

> Cargar junto con: `E-ARCH` + `E-SOURCES §2.6` + `E-SOURCES §2.6-AIS`
> + `E-SEC` + `F-NORM-CANON` + `F-DEDUP` + `E-INFRA`

---

## 1. Arquitectura

AISStream usa WebSocket, no polling HTTP. Requiere un relay persistente
que mantenga la conexión upstream y sirva snapshots al ingestor.

```
AISStream (WebSocket upstream)
      ↓  AISSTREAM_API_KEY
  ais-relay/               ← servicio separado, mantiene WS abierto
      ├── normaliza mensajes AIS al modelo §3
      ├── escribe snapshot en Redis cada AIS_SNAPSHOT_INTERVAL_MS
      ├── detecta dark-ship events
      └── publica deltas vía /api/ais/events
            ↓
  ingestor/aisstream_ingestor.py
      ├── consume /api/ais/snapshot (carga inicial)
      ├── consume /api/ais/events?since=TIMESTAMP (deltas)
      ├── normaliza al modelo canónico (§4)
      ├── aplica lógica de anomalías (§7)
      └── escribe en events_canonical + topic raw.aisstream
```

El relay es un microservicio separado (Python o Node).
El ingestor consume el relay, no AISStream directamente.
La `AISSTREAM_API_KEY` **nunca sale del relay**.

---

## 2. Endpoints del relay (surface API)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/ws/aisstream` | WS | Proxy WebSocket — reenvía frames AIS a clientes autorizados |
| `/api/ais/snapshot` | GET | Estado actual de todos los buques (array normalizado) |
| `/api/ais/events` | GET | Deltas incrementales desde `?since=TIMESTAMP` |
| `/api/military/v1/list-military-vessels` | GET | Buques militares filtrados por bbox |
| `/health/ais` | GET | Estado del relay: upstream conectado, age del snapshot |

El ingestor usa principalmente `/api/ais/snapshot` en el arranque
y `/api/ais/events` para actualizaciones incrementales.

---

## 3. Modelo normalizado de buque (relay → ingestor)

```typescript
interface AISVessel {
  // Obligatorios
  id:                 string        // MMSI como string
  mmsi:               string        // siempre string, nunca int
  lat:                number
  lon:                number
  sog:                number        // speed over ground en nudos
  cog:                number        // course over ground en grados
  heading:            number        // heading real en grados (0-360)
  navigationalStatus: string        // 'underway','anchored','moored','aground',...
  lastAisUpdate:      string        // ISO 8601 UTC
  source:             'aisstream' | 'stale_cache'

  // Opcionales
  name?:              string
  callsign?:          string
  vesselType?:        string        // 'warship','tanker','cargo','passenger',...
  flag?:              string        // ISO2 del país de bandera
  imo?:               string
  destination?:       string
  isDark?:            boolean       // true si perdió señal AIS
  darkSince?:         string        // ISO 8601 UTC — cuándo dejó de transmitir
  usniSource?:        boolean       // enriquecido con USNI
  usniDeploymentStatus?: string     // 'deployment','exercise','transit','unknown'
  dimensions?: {
    length: number
    width:  number
  }
}
```

```typescript
interface AISCluster {
  vesselCount:  number
  centroidLat:  number
  centroidLon:  number
  activityType: 'deployment' | 'exercise' | 'transit' | 'unknown'
}
```

---

## 4. Mapeo → `events_canonical`

| Campo AISVessel | Campo canónico | Notas |
|-----------------|----------------|-------|
| `mmsi + ':' + lastAisUpdate_60s` | `event_id_source` | Ver deduplicación §6 |
| `lastAisUpdate` | `event_time` | Ya en UTC |
| `lat / lon` | `location_point` | WGS84 |
| `flag` | `country_iso2` | ISO2 del país de bandera |
| `name` + `callsign` | `actors[0]` | `role: 'vessel'`, `name: callsign ?? name` |
| `sog` + `heading` | `source_refs` | JSON string con datos de movimiento |
| `isDark` | `is_rumor` | `true` si dark-ship (señal perdida) |
| — | `event_type` | `'vessel_position'` o `'vessel_dark'` si `isDark=true` |
| — | `category` | `'mobility'` |
| `usniDeploymentStatus` | `source_refs` | Añadir como campo adicional |

`source_independence_class = 'sensor'` — factor confianza: ×2.0

> **⚠️ MMSI individual nunca en API pública** — ver `E-SEC` y D11 adaptado.
> Solo exponer datos agregados por zona en `/v1/incidents`.

---

## 5. Relación con MarineTraffic (F-ING-MT)

AISStream y MarineTraffic son **fuentes complementarias, no excluyentes**:

| Criterio | AISStream | MarineTraffic |
|----------|-----------|---------------|
| Latencia | Tiempo real (WS) | ~5 min (polling) |
| Coste | Menor | Mayor |
| Cobertura | Global AIS raw | Global AIS + enriquecido |
| Dark-ship | Detección nativa | No nativa |
| Enriquecimiento | Via USNI opcional | Integrado |

**Deduplicación cross-fuente**: si un buque aparece en ambas fuentes
en la misma ventana temporal, el registro de AISStream tiene prioridad
por menor latencia. Usar MMSI como clave de deduplicación cross-fuente.

---

## 6. Deduplicación

Clave natural por posición: `MMSI + ':' + timestamp_unix_60s`

```python
def ais_event_id(mmsi: str, last_ais_update: str) -> str:
    ts = datetime.fromisoformat(last_ais_update.replace('Z', '+00:00'))
    ts_60 = int(ts.timestamp() // 60) * 60
    return f"{mmsi}:{ts_60}"
```

Dark-ship events tienen clave distinta: `MMSI + ':dark:' + dark_since_60s`
para que coexistan con los eventos de posición normales.

---

## 7. Lógica de anomalías — cuándo escalar a incidente

Solo crear o enriquecer incidente si se cumple alguna condición:

| Condición | Tipo de evento generado |
|-----------|------------------------|
| `isDark=true` en zona de conflicto activa (AOI con `category='conflict'`) | `vessel_dark` — posible supresión AIS intencional |
| `isDark=true` durante > 30 min en cualquier zona | `vessel_dark` — pérdida de señal prolongada |
| `sog=0` (buque detenido) en zona de conflicto > 30 min | `vessel_stopped_conflict` |
| Agrupamiento: ≥ 5 buques en radio < 10 km fuera de puerto | `vessel_cluster_anomaly` |
| `usniDeploymentStatus='deployment'` en AOI activo | enriquecer incidente existente |
| Buque entra en zona de exclusión marítima activa (bbox AOI marcado como exclusion) | `vessel_exclusion_zone` |

Buques en tránsito normal → registrar en `events_canonical`
pero **NO generar incidente nuevo automáticamente**.

---

## 8. Dark-ship detection (en el relay)

El relay es responsable de detectar y marcar `isDark`:

```
Para cada buque en snapshot:
  si (now - lastAisUpdate) > DARK_SHIP_THRESHOLD_MIN → isDark = true, darkSince = lastAisUpdate
  si buque reaparece tras estar dark → isDark = false, generar evento 'vessel_reappeared'
```

Variable de entorno: `DARK_SHIP_THRESHOLD_MIN=20` (configurable)

---

## 9. Cache y resiliencia del relay

- Snapshot en Redis con TTL = `AIS_SNAPSHOT_INTERVAL_MS * 3`
- Si upstream AISStream falla → servir último snapshot válido
  con header `X-Stale: true` y campo `source: 'stale_cache'`
- El ingestor registra `source_refs: ['stale_cache']` cuando recibe datos stale
- Reconexión al upstream con backoff exponencial + jitter (ver `E-INFRA §2`)
- Circuit breaker: si upstream falla > 5 veces consecutivas,
  servir stale indefinidamente y emitir métrica `ais_upstream_connected=0`

---

## 10. Métricas obligatorias del relay (ver `E-MON`)

| Métrica | Tipo | Alerta si |
|---------|------|-----------|
| `ais_upstream_connected` | Gauge | = 0 durante > 2 min |
| `ais_inbound_per_sec` | Counter | = 0 durante > 5 min |
| `ais_snapshot_age_ms` | Gauge | > `AIS_SNAPSHOT_INTERVAL_MS * 3` |
| `ais_dark_ships_total` | Gauge | Subida brusca > 50% en 10 min |
| `ais_drops_per_sec` | Counter | > 100/s sostenido |

---

## 11. Variables de entorno

```dotenv
# Relay
AISSTREAM_API_KEY=               # nunca exponer al cliente
AIS_SNAPSHOT_INTERVAL_MS=3000    # cadencia de escritura en Redis
DARK_SHIP_THRESHOLD_MIN=20       # minutos sin señal para marcar isDark
AIS_UPSTREAM_QUEUE_HIGH_WATER=   # watermark alto de cola upstream
AIS_UPSTREAM_QUEUE_LOW_WATER=    # watermark bajo de cola upstream

# Ingestor
AIS_RELAY_BASE_URL=http://ais-relay:8001
AIS_POLL_EVENTS_MS=5000          # frecuencia de /api/ais/events
```

---

## 12. Visualización en frontend (ver `F-UI-MAP`)

Tres capas Deck.gl para buques:

**ScatterplotLayer** `'vessels-layer'`
Buques activos como círculos coloreados por `usniDeploymentStatus` o `vesselType`:

| Estado / Tipo | Color |
|---------------|-------|
| `deployment` | Rojo `[239,68,68]` |
| `exercise` | Naranja `[249,115,22]` |
| `transit` | Amarillo `[234,179,8]` |
| `unknown` / resto | Gris `[100,116,139]` |
| `isDark=true` | Púrpura pulsante `[168,85,247]` |

**PathLayer** `'vessels-trails-layer'`
Últimas N posiciones por MMSI como trail de movimiento.
El relay debe mantener un buffer histórico de posiciones por buque.

**ScatterplotLayer** `'vessels-dark-layer'`
Capa separada solo para dark-ships (`isDark=true`).
Radio mayor, color púrpura, animación de pulso via Framer Motion
en componente DOM superpuesto (no en canvas).

La capa de buques se activa desde el control `[VESSELS]`
en `LayerControls` (`F-UI-MAP §5`) — añadir este botón.

---

## 13. Tests obligatorios

| Test | Descripción |
|------|-------------|
| Snapshot inicial | El ingestor carga correctamente `/api/ais/snapshot` al arrancar |
| Delta incremental | `/api/ais/events?since=T` devuelve solo cambios posteriores a T |
| Dark-ship detection | Buque sin señal > threshold → `isDark=true` en snapshot |
| Deduplicación | Mismo MMSI en llamadas consecutivas no genera duplicado |
| Stale fallback | Relay caído → ingestor recibe `source='stale_cache'` sin error |
| Anomalía dark en conflicto | Buque dark en AOI de conflicto → genera incidente |
| Cross-fuente MMSI | Mismo buque en AISStream y MarineTraffic → un solo evento canónico |
| MMSI no expuesto | `/v1/incidents` no incluye campo `mmsi` en respuesta pública |