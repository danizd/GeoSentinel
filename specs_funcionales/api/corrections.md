# F-API-CORR — API de Correcciones (Human-in-the-Loop)

> Cargar junto con: `E-SEC` + `E-MODEL` + `F-LC`

## Endpoint
`POST /v1/corrections`

## Auth requerida
Scope `corrections:write`

## Body

```json
{
  "incident_id": "uuid",
  "correction_type": "false_positive",
  "reason": "Texto libre obligatorio",
  "new_category": null,
  "new_coordinates": null
}
```

## Tipos de corrección (`correction_type`)

| Tipo | Efecto en incidente |
|------|---------------------|
| `false_positive` | `status → false_positive` |
| `reclassify` | Cambia `category` y/o `event_type` |
| `relocate` | Actualiza `canonical_point` |
| `merge` | Fusiona dos incidentes (requiere `target_incident_id`) |
| `close` | `status → closed` |

## Invariantes (ver D8)
- Toda corrección crea registro inmutable en `corrections_audit` con `before_state` y `after_state`
- `corrections_audit` es append-only: **nunca UPDATE ni DELETE**
- Respuesta incluye el estado actualizado del incidente
