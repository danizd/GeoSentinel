"""Proxy hacia la API pública de CR360 (Conflict Radar 360).

El navegador no puede llamar a cr360-api.vercel.app directamente:
la API responde 500 cuando recibe un header `Origin` de navegador y no
emite `Access-Control-Allow-Origin` en el resto de peticiones (verificado).
Todo el tráfico pasa por este proxy, que además aplica caché en memoria
para respetar el rate limit upstream (X-Ratelimit-Limit: 100) y filtra
las features por `countryCode`.
"""

import os
import re
import threading
import time
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

CR360_BASE_URL = os.getenv("CR360_BASE_URL", "https://cr360-api.vercel.app").rstrip("/")
CR360_CACHE_TTL_SECONDS = float(os.getenv("CR360_CACHE_TTL_SECONDS", "10800"))
CR360_UPSTREAM_TIMEOUT_SECONDS = float(os.getenv("CR360_UPSTREAM_TIMEOUT_SECONDS", "15"))
CR360_EVENTS_MAX_HOURS = os.getenv("CR360_EVENTS_MAX_HOURS", "72")

_COUNTRY_PATTERN = re.compile(r"^[A-Z]{3}(?:,[A-Z]{3})*$")

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _parse_countries(countries: str) -> list[str]:
    """Valida el parámetro `countries` (códigos ISO-3 separados por coma)."""
    if not countries or not _COUNTRY_PATTERN.match(countries):
        raise HTTPException(
            status_code=422,
            detail="countries must be a comma-separated list of ISO-3 codes (e.g. ESP,RUS,UKR)",
        )
    return countries.split(",")


def _fetch_cached(key: str, url: str) -> Any:
    """GET con caché en memoria TTL. Devuelve el JSON crudo de la API upstream."""
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is not None and now - entry[0] < CR360_CACHE_TTL_SECONDS:
            return entry[1]

    try:
        response = requests.get(url, timeout=CR360_UPSTREAM_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"CR360 upstream error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="CR360 upstream returned invalid JSON") from exc

    with _cache_lock:
        _cache[key] = (time.monotonic(), payload)
    return payload


def _filter_by_country(payload: dict[str, Any], countries: set[str]) -> dict[str, Any]:
    """Devuelve un FeatureCollection con solo las features cuyo countryCode está en `countries`."""
    features = payload.get("features", [])
    filtered = [
        feature
        for feature in features
        if isinstance(feature.get("properties"), dict)
        and feature["properties"].get("countryCode") in countries
    ]
    return {"type": "FeatureCollection", "features": filtered}


@router.get("/cr360/events")
def list_cr360_events(countries: str = Query(...)) -> dict[str, Any]:
    """Eventos del mapa público de CR360, filtrados por países (ventana maxHours)."""
    codes = set(_parse_countries(countries))
    url = f"{CR360_BASE_URL}/api/v2/public/map/events?lang=es&maxHours={CR360_EVENTS_MAX_HOURS}"
    payload = _fetch_cached("cr360:events", url)
    return _filter_by_country(payload, codes)


@router.get("/cr360/events/{event_id}")
def get_cr360_event(event_id: int) -> dict[str, Any]:
    """Detalle completo de un evento CR360."""
    url = f"{CR360_BASE_URL}/api/v2/events/{event_id}?lang=es"
    return _fetch_cached(f"cr360:event:{event_id}", url)


@router.get("/cr360/roads")
def list_cr360_roads(countries: str = Query(...)) -> dict[str, Any]:
    """Carreteras comprometidas de CR360, filtradas por países."""
    codes = set(_parse_countries(countries))
    url = f"{CR360_BASE_URL}/api/v2/public/map/compromised-roads?lang=es"
    payload = _fetch_cached("cr360:roads", url)
    return _filter_by_country(payload, codes)


@router.get("/cr360/regions")
def list_cr360_regions(countries: str = Query(...)) -> dict[str, Any]:
    """Regiones (polígonos) de CR360, filtradas por países.

    El upstream pesa ~15 MB (10k+ polígonos mundiales); la caché lo guarda
    completo y este endpoint devuelve solo las regiones de los países pedidos.
    """
    codes = set(_parse_countries(countries))
    url = f"{CR360_BASE_URL}/api/v2/public/map/regions?lang=es"
    payload = _fetch_cached("cr360:regions", url)
    return _filter_by_country(payload, codes)
