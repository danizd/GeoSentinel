# F-AOI — Areas of Interest (AOI)

> Cargar junto con: `E-MODEL` + `E-SEC`

## AOI como entidad de primera clase (Decisión D6)
Las AOIs no son filtros ad hoc. Son entidades persistidas en BD que controlan:
- El bbox de polling de FIRMS, ADS-B, MarineTraffic
- Los filtros de alertas para operadores
- Las queries de `/incidents` por defecto

## Esquema (ver DDL completo en `E-MODEL §2.5`)
- `geometry`: polígono WGS84 arbitrario
- `categories`: filtro por categoría (`NULL` = todas)
- `min_severity`: umbral mínimo para alertas

## API CRUD
- `POST /v1/aoi` — crear AOI
- `GET /v1/aoi/{id}` — obtener AOI
- `PUT /v1/aoi/{id}` — actualizar
- `DELETE /v1/aoi/{id}` — desactivar (`is_active=false`, nunca DELETE físico)
- `GET /v1/aoi/{id}/incidents` — incidentes dentro del AOI

## Efecto en ingestores
Al modificar un AOI activo, los ingestores que usan bbox dinámico (FIRMS, ADS-B, MT)
deben recargar la configuración en el próximo ciclo de polling.
