# L-CORR-002: Filtrado de vuelos militares OpenSky — cadena de bugs y solución definitiva

## Problema original

La aplicación no mostraba ningún vuelo militar pese a que `map.opensky-network.org` con el filtro "U" sí los mostraba.

## Cadena de bugs identificados (en orden de descubrimiento)

### Bug 1 — URL de descarga de la BD de aeronaves incorrecta

| Campo | Valor |
|-------|-------|
| Síntoma | `military_hex.txt` nunca se actualizaba; el fichero sólo tenía 85 entradas manuales |
| Causa | `OPENSKY_DB_BASE_URL = "https://opensky-network.org/datasets/metadata"` → URL inexistente |
| Fix | `OPENSKY_DB_BASE_URL = "https://s3.opensky-network.org/data-samples/metadata"` |
| Fichero | `services/military_relay/update_military_db.py` |

### Bug 2 — Fallback de meses insuficiente (sólo 3 meses)

| Campo | Valor |
|-------|-------|
| Síntoma | Descarga fallida incluso con URL correcta; el bucket S3 sólo tiene hasta 2025-08 |
| Causa | `range(3)` intentaba 2026-05, 2026-04, 2026-03 — todos 404 |
| Fix | Ampliado a `range(24)` para alcanzar hasta 2024 hacia atrás |
| Fichero | `services/military_relay/update_military_db.py` |

### Bug 3 — Errores 401/403 de OpenSky silenciosos

| Campo | Valor |
|-------|-------|
| Síntoma | Sin flights, sin logs de error |
| Causa | Sólo se capturaba 429; errores de autenticación pasaban al `raise_for_status()` que se propagaba silenciosamente |
| Fix | Captura explícita de 401/403 con log de acción ("configure OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET") |
| Fichero | `services/military_relay/opensky_client.py` |

### Bug 4 — `altitude >= 0` rechazaba aviones en tierra con altitud negativa

| Campo | Valor |
|-------|-------|
| Síntoma | OpenSky devolvía 10 201 estados pero 0 vuelos militares parseados |
| Causa | `altitude: int = Field(..., ge=0)` en el modelo Pydantic; aviones con altitud barométrica -300 ft fallaban validación |
| Fix | Eliminado `ge=0`; altitudes negativas son válidas (aviones en tierra / errores de sensor) |
| Fichero | `services/military_relay/models.py` |

### Bug 5 — `military_hex.txt` con 85 entradas no se re-descargaba (umbral 30 días)

| Campo | Valor |
|-------|-------|
| Síntoma | El fichero tenía 7 días de antigüedad → no disparaba descarga |
| Causa | Sólo se comprobaba la edad; el fichero era un placeholder manual con 85 entradas |
| Fix | Añadido `min_entries=1000`: fuerza descarga si el fichero tiene menos de 1 000 entradas, independientemente de la edad |
| Fichero | `services/military_relay/update_military_db.py` |

### Bug 6 — `fetch_aircraft_metadata` por vuelo causaba timeout > 30 s

| Campo | Valor |
|-------|-------|
| Síntoma | Relay respondía vacío; backend cortaba la conexión a los 30 s |
| Causa | Para cada vuelo militar detectado se hacía una llamada HTTP individual al API de OpenSky (rate limiter 1,1 s + timeout 10 s). Con 20 vuelos → > 200 s de espera |
| Fix | Eliminada la llamada `fetch_aircraft_metadata` en `parse_flight`; los campos `aircraftType`, `registration`, `operator` quedan `None` (no esenciales) |
| Fichero | `services/military_relay/opensky_client.py` |

### Bug 7 — Filtro de callsigns generaba falsos positivos

| Campo | Valor |
|-------|-------|
| Síntoma | Aparecían vuelos civiles (p.ej. callsigns tipo VIPER, EAGLE, FALCON usados por charters) |
| Causa | `is_callsign_military()` matcheaba prefijos genéricos de 3-4 letras usados también por aerolíneas civiles y aviación general |
| Fix | Eliminado el check de callsign de `is_military()`. Con ~10 000 hex codes de la BD de OpenSky el callsign es redundante y genera ruido |
| Fichero | `services/military_relay/military_filter.py` |

### Bug 8 — Rangos hex ICAO estáticos capturaban aerolíneas civiles (causa principal)

| Campo | Valor |
|-------|-------|
| Síntoma | Iberia (IBE0191), Lufthansa (DLH01A), Vueling (VLG6TM) y otras civiles europeas aparecían como militares |
| Causa | `MILITARY_HEX_RANGES` usaba bloques ICAO asignados a países enteros (ej. `340000-347FFF` = España completa, no sólo Ejército del Aire; `3C4000-3C7FFF` = Alemania completa, no sólo Luftwaffe). Los bloques ICAO son de asignación nacional, no militar |
| Fix | Eliminado `is_hex_military_by_range()` de `is_military()`. La BD de OpenSky identifica correctamente las aeronaves militares sin necesidad de rangos |
| Fichero | `services/military_relay/military_filter.py` |

> **Nota**: `MILITARY_HEX_RANGES` se conserva en `config.py` por valor documental pero ya no se usa en el filtro.

### Bug 9 — Criterio `categoryDescription = "Military"` demasiado estricto → 0 resultados

| Campo | Valor |
|-------|-------|
| Síntoma | Tras intentar refinar, la BD se reconstruyó con 0 entradas |
| Causa | El campo `categoryDescription` en el CSV de OpenSky describe el **tipo físico de aeronave** (Light/Small/Heavy/Rotorcraft…), NO su afiliación militar. Nunca contiene "Military" como valor |
| Fix | Revertido: el criterio de extracción correcto es operator/owner, no categoryDescription. `categoryDescription` se mantiene como comprobación defensiva pero no produce hits |
| Fichero | `services/military_relay/update_military_db.py` |

### Bug 10 — Imagen Docker stale: `git pull` no actualiza el contenedor

| Campo | Valor |
|-------|-------|
| Síntoma | `git pull` mostraba "Already up to date" pero el contenedor ejecutaba código anterior |
| Causa | El código se copia en la imagen (`COPY services/ /app/services/`) en tiempo de build. `docker restart` no recoge cambios del host |
| Fix | Siempre usar `docker compose up -d --build military-relay` tras cambios de código |

## Filtro definitivo implementado

```python
def is_military(hex_code, callsign, category=None):
    if category == 7:               # ADS-B autoidentificación — fiable
        return True
    if is_hex_military(hex_code):   # BD OpenSky ~10 000 aeronaves
        return True
    return False
```

**Criterios eliminados permanentemente:**
- `is_hex_military_by_range()` — rangos ICAO nacionales, no militares
- `is_callsign_military()` — falsos positivos con charters y aviación general

**Criterio de extracción de `military_hex.txt`:**
```python
def _is_military_row(row):
    # categoryDescription nunca contiene "military" (es tipo físico de aeronave)
    category = row.get("categoryDescription", "").strip().lower()
    if "military" in category:   # defensivo, sin hits reales
        return True
    combined = row.get("operator","").lower() + " " + row.get("owner","").lower()
    return any(kw in combined for kw in MILITARY_OPERATOR_KEYWORDS)
```

## Resultado

~10 000 aeronaves identificadas como militares en la BD 2025-08 de OpenSky.
El filtro replica el comportamiento del filtro "U" de `map.opensky-network.org`.

## Lecciones

- **Los bloques ICAO son nacionales, no militares.** Sólo ADS-B Exchange y bases de datos especializadas (como la de OpenSky) identifican correctamente aeronaves militares por operador.
- **`categoryDescription` en OpenSky CSV describe el tipo físico** (ADS-B emitter category), no la afiliación militar. No usarlo como criterio de selección militar.
- **Con una BD de ~10 000 hex codes, los filtros secundarios (callsign, rangos) son redundantes y perjudiciales.** Añaden ruido sin añadir cobertura real.
- **Siempre reconstruir la imagen Docker** (`--build`) tras cambios de código. Un `restart` del contenedor no recoge cambios en ficheros COPY'd.
- **El endpoint `/debug`** del relay es esencial para diagnóstico: expone `hex_count`, `hex_file_age_days`, `opensky_authenticated`.

## Código relevante

- `services/military_relay/military_filter.py` — `is_military()` sin rangos ni callsigns
- `services/military_relay/update_military_db.py` — descarga BD, criterio operator/owner, fallback 24 meses, min_entries check
- `services/military_relay/models.py` — `altitude` sin constraint `ge=0`
- `services/military_relay/opensky_client.py` — logging errores HTTP, sin `fetch_aircraft_metadata`
- `services/military_relay/main.py` — endpoint `/debug`
