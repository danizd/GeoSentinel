# F-API-AOI — API de Areas of Interest

> Cargar junto con: `E-ARCH` + `E-SEC` + `E-STD` + `F-AOI`

## Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| `POST` | `/v1/aoi` | Crear AOI. Body: `{name, geometry GeoJSON, categories[], min_severity}` |
| `GET` | `/v1/aoi` | Listar AOIs activos del usuario |
| `GET` | `/v1/aoi/{id}` | Obtener AOI por ID |
| `PUT` | `/v1/aoi/{id}` | Actualizar AOI |
| `DELETE` | `/v1/aoi/{id}` | Desactivar (`is_active=false`) — nunca DELETE físico |
| `GET` | `/v1/aoi/{id}/incidents` | Incidentes dentro del AOI (usa parámetros de `F-API-INC`) |

## Auth requerida
Scope `aoi:manage` — ver `E-SEC §1`

## Validaciones
- `geometry` debe ser GeoJSON válido (`Polygon` o `MultiPolygon`)
- Área máxima: 5.000.000 km² (evitar AOIs globales)
- `min_severity` en rango [0.0, 10.0]
