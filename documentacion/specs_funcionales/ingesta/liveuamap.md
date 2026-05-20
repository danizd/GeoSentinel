# F-ING-LUM — Ingestor Liveuamap

> ⚠️ **FUENTE DE RIESGO ALTO** — Decisión D5 en `AGENTS.md`

## Estado actual
- Sin API pública documentada ni SLA garantizado.
- **Desactivado por defecto**: `LIVEUAMAP_ENABLED=false`
- El fallo de este ingestor nunca debe propagar errores al pipeline principal.

## Implementación obligatoria
```python
if not settings.LIVEUAMAP_ENABLED:
    logger.info("Liveuamap disabled — skipping")
    return
```

## Alternativas si no está disponible
GDELT actúa como sustituto parcial para detección de conflictos.
Evaluar: Crisis Group API, Bellingcat feeds OSINT con API documentada.

## Si se habilita
- Polling cada 5 min → topic `raw.liveuamap`
- Deduplicación por campo `id` nativo
- `source_independence_class = 'media_derived'` — factor confianza: ×0.5
