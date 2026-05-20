# F-VAL — Validación y Quarantine

> Cargar junto con: `E-MODEL` + `F-NORM-CANON`

## Posición en el pipeline
Capa entre ingesta y normalización. Todo evento pasa por aquí antes de llegar a `events_canonical`.

## Reglas de validación (rechazo → `events_quarantine`)

| Código | Condición |
|--------|-----------|
| `INVALID_COORDS` | `lat < -90 OR lat > 90 OR lon < -180 OR lon > 180` |
| `NULL_COORDS` | `lat IS NULL OR lon IS NULL` |
| `FUTURE_DATE` | `event_time > now() + interval '1 hour'` |
| `NULL_EVENT_TYPE` | `event_type IS NULL OR event_type = ''` |
| `NEGATIVE_FATALITIES` | `fatalities < -1` (`-1` = desconocido en ACLED, permitido) |
| `SCHEMA_ERROR` | Fallo de parsing del payload fuente |

## Registro en quarantine
```sql
INSERT INTO events_quarantine (source, raw_payload, rejection_code, rejection_detail)
VALUES (...);
```

## Resolución de quarantine
Un operador o job automático puede:
1. Corregir el payload manualmente
2. Marcar `resolved=TRUE` y reencolar al topic de ingesta correspondiente
3. Descartar definitivamente (marcar `resolved=TRUE` sin reencolar)

## Métricas obligatorias
- `events_quarantine_unresolved` → alerta si > 100 en 30 min (ver `E-MON`)
