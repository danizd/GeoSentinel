# F-NORM-ACTORS — Normalización de Actores

> Cargar junto con: `E-MODEL` + `F-NORM-CANON`

## Problema
GDELT usa códigos CAMEO (2 letras). ACLED usa taxonomía propia estructurada.
Homologarlos a un esquema interno común es necesario para clustering correcto.

## Esquema canónico de actor
```json
{
  "role": "state_military",
  "name": "Armed Forces of Ukraine",
  "cameo_code": "MIL",
  "acled_type": "State Forces"
}
```

## Roles canónicos internos
| Rol interno | CAMEO equiv. | ACLED equiv. |
|-------------|-------------|--------------|
| `state_military` | `MIL` | State Forces |
| `nonstate_armed` | `REB` / `MIL` | Non-State Armed Group |
| `civilians` | `CVL` | Civilians |
| `police` | `COP` | State Forces / Police |
| `protesters` | `OPP` | Protesters |
| `international_org` | `IGO` | International Organization |
| `unknown` | — | — |

## Diccionario CAMEO → interno
Implementar en `normalizers/actor_mapper.py`. Fuente: `https://papalocal.com/cameo_codebook`

## Regla para actores desconocidos
Si el código no está en el diccionario → `role='unknown'`, preservar nombre original en `name`.
Nunca rechazar el evento completo por actor desconocido.
