# F-ING-ADSB — Ingestor ADS-B Exchange

> Cargar junto con: `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `E-SEC` + `F-NORM-CANON` + `F-DEDUP`

## Contrato
- **Endpoint**: `https://adsbexchange.com/api/aircraft/v2/` — ver `E-SOURCES §2.5`
- **Patrón**: Pull polling cada 60 seg, bbox por AOIs activos → topic `raw.adsb`
- **Auth**: header `api-auth` ← `ADSB_API_KEY`
- **Licencia comercial**: No redistribuir identificadores de aeronaves individuales (ver `E-SEC`)

## Deduplicación
Clave: `hex + ':' + t` (ICAO + timestamp Unix)

## Lógica de detección — solo crear evento si:
- Aeronave con `mil=true` en radio < 50 km de incidente activo
- Cambio de altitud > 5000 ft/min
- Velocidad 0 sobre territorio en conflicto activo > 10 min

## Restricción de exposición
El campo `hex` (ICAO individual) no se expone en `/incidents` público. Solo datos agregados.

`source_independence_class = 'sensor'` — factor confianza: ×2.0
