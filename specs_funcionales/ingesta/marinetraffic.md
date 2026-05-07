# F-ING-MT — Ingestor MarineTraffic AIS

> Cargar junto con: `E-ARCH` + `E-SOURCES` + `E-STD` + `E-MON` + `E-SEC` + `F-NORM-CANON` + `F-DEDUP`

## Contrato
- **Endpoint base**: `https://services.marinetraffic.com/api/` — ver `E-SOURCES §2.6`
- **Patrón**: Pull polling cada 5 min por AOI activo → topic `raw.marinetraffic`
- **Auth**: `?apikey=MARINETRAFFIC_API_KEY`
- **Licencia comercial**: Prohibida redistribución de datos de buques individuales (ver `E-SEC`)

## Deduplicación
Clave: `mmsi + ':' + TIMESTAMP` (Unix)

## Lógica de detección — solo crear evento si:
- Buque detenido (velocidad 0) en zona de conflicto activa > 30 min
- Agrupamiento anómalo: ≥ 5 buques en radio < 5 km fuera de puerto
- Entrada en zona de exclusión marítima activa

## Restricción de exposición
`MMSI` individual no se expone en `/incidents` público.

`source_independence_class = 'sensor'` — factor confianza: ×2.0
