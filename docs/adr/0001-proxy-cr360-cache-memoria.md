# ADR-0001: Proxy CR360 con caché en memoria (TTL)

- **Estado**: Aceptado
- **Fecha**: 2026-08-25
- **Contexto**: [CR360 (Conflict Radar 360)](../documentacion/specs_estructurales/fuentes-datos.md#210-cr360--conflict-radar-360-radar-de-eventos-y-carreteras)

## Contexto

La página `/radar` consume la API pública de CR360 (`cr360-api.vercel.app`). Verificaciones hechas sobre la API real:

1. **El navegador no puede llamarla directamente**: con un header `Origin` de navegador responde `500`; sin `Origin` responde `200` pero sin `Access-Control-Allow-Origin`; el preflight `OPTIONS` devuelve `500`.
2. **Rate limit**: `X-Ratelimit-Limit: 100` (por ventana) — un cliente que pida el listado cada 3 h más un detalle por cada click agotaría el cupo.
3. **Payloads grandes**: el listado de eventos trae ~510 features (72 h); el de regiones **~10.600 features / ~15 MB**.
4. No hay filtro server-side por país: el proxy debe filtrar por `countryCode`.

## Decisión

Añadir un proxy en FastAPI (`GET /v1/cr360/events`, `/v1/cr360/events/{id}`, `/v1/cr360/roads`, `/v1/cr360/regions`) que:

- Cacha el JSON upstream **en memoria** (dict + lock, TTL por defecto 3 h) para que CR360 reciba como mucho 1 llamada por recurso y ventana.
- Filtra server-side por `countries` (param validado `^[A-Z]{3}(,[A-Z]{3})*$`, ISO-3), devolviendo solo las features del país.
- Para regiones, cachea el upstream completo (~15 MB) y filtra por petición, compartiendo una sola llamada entre distintos conjuntos de países.

Alternativas descartadas:

- **Sin caché**: cada refresh del frontend y cada detalle por click consumiría el rate limit de 100.
- **Caché en Redis/BD**: infraestructura y complejidad adicionales para un dato que tolera estar desactualizado 3 h; el resto del sistema ya no usa Redis en esta versión.
- **Filtrar y cachear por país**: duplicaría la llamada upstream de 15 MB por cada combinación de países.

## Consecuencias

**Positivas**

- El frontend solo recibe los datos filtrados (~218 eventos, ~138 carreteras, ~310 regiones para ESP/RUS/UKR) pese al payload mundial.
- Protege el rate limit de CR360; TTL y URL base configurables por entorno.
- Sin dependencias nuevas ni servicios extra.

**Negativas / a vigilar**

- La caché es **estado en memoria** (se pierde al reiniciar y no escala horizontalmente), en tensión con el principio E-ARCH de "estado en BD". Es aceptable por ser una caché efímera con TTL, no fuente de verdad, y estar fuera del pipeline canónico.
- Pico de memoria de ~15 MB por el payload de regiones.
- El primer request tras un reinicio (o tras expirar el TTL) tarda ~2-4 s en descargar y parsear el upstream de regiones.

**Revisar si**: el sistema escala a múltiples réplicas o el upstream endurece el rate limit → mover la caché a Redis (o a un almacén compartido) sin cambiar el contrato del proxy.
