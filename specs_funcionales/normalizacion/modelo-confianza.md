# F-NORM-CONF — Modelo de Confianza

> **Spec funcional** — Cargar junto con `E-MODEL` y `F-NORM-SEV`.

## 1. Principio fundamental

**Decisión D3 de AGENTS.md**: las fuentes con el mismo origen mediático
son correlacionadas, no independientes. El modelo penaliza redundancia.

## 2. Clases de independencia

| Clase | Factor base | Lógica |
|-------|-------------|--------|
| `sensor` | `2.0` | Dato físico directo (satélite, sismógrafo, AIS/ADS-B) |
| `field_reported` | `1.5` | Reportado en campo por organización especializada |
| `media_derived` | `0.5` | Extraído de medios por NLP; alta tasa de duplicación |

## 3. Algoritmo de cálculo

```python
def compute_confidence(events: list[Event]) -> float:
    """
    Confidence 0–10 para un grupo de eventos del mismo incidente.
    Penaliza fuentes correlacionadas (media_derived del mismo ciclo de noticias).
    """
    score = 0.0
    seen_media_cycle = set()  # para detectar noticias del mismo ciclo

    for event in events:
        factor = INDEPENDENCE_FACTORS[event.source_independence_class]

        if event.source_independence_class == 'media_derived':
            # Solo contar una vez por ventana de 6h de noticias
            cycle_key = f"{event.source}:{event.event_time // timedelta(hours=6)}"
            if cycle_key in seen_media_cycle:
                factor *= 0.1  # penalización fuerte por redundancia
            seen_media_cycle.add(cycle_key)

        score += factor

    # Normalizar a 0–10 con techo
    return min(score * 10 / MAX_EXPECTED_SCORE, 10.0)

MAX_EXPECTED_SCORE = 8.0  # calibrar según datos reales
```
