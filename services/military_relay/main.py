import logging
import time as time_module
import threading
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from services.military_relay import config
from services.military_relay.adsb_client import ADSBMilitaryClient
from services.military_relay.cache import bbox_cache, flight_history
from services.military_relay.military_filter import is_military, normalize_hex
from services.military_relay.models import (
    Location,
    MilitaryFlight,
    MilitaryFlightCluster,
    MilitaryFlightsResponse,
)
from services.military_relay.opensky_client import OpenskyClient

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, min_interval: float = 1.1):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time_module.time()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                time_module.sleep(self.min_interval - elapsed)
            self._last_call = time_module.time()


opensky_rate_limiter = RateLimiter(min_interval=1.1)

app = FastAPI(
    title="Military Flight Relay",
    description="ADS-B military flights relay with filtering and caching",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _background_db_update() -> None:
    """Actualiza military_hex.txt en background sin bloquear el arranque del relay."""
    try:
        from services.military_relay.update_military_db import update_military_db_if_needed
        from services.military_relay.military_filter import load_military_hex_set, _compiled_ranges

        updated = update_military_db_if_needed(config.MILITARY_HEX_FILE)
        if updated:
            load_military_hex_set.cache_clear()
            _compiled_ranges.cache_clear()
            logger.info("Cache de hex militares recargada tras actualizacion de BD")
    except Exception as exc:
        logger.error(f"Error en actualizacion de BD militar en background: {exc}")


@app.on_event("startup")
async def startup_event() -> None:
    """Lanza la actualizacion de la BD de aeronaves militares en un hilo daemon."""
    threading.Thread(
        target=_background_db_update,
        daemon=True,
        name="military-db-update",
    ).start()
    logger.info("Relay militar iniciado — actualizacion de BD lanzada en background")


@app.get("/api/military/v1/list-military-flights")
async def list_military_flights(
    neLat: float = Query(..., description="North east latitude"),
    neLon: float = Query(..., description="North east longitude"),
    swLat: float = Query(..., description="South west latitude"),
    swLon: float = Query(..., description="South west longitude"),
    operator: str | None = Query(None, description="Filter by operator"),
    aircraftType: str | None = Query(None, description="Filter by aircraft type"),
) -> MilitaryFlightsResponse:
    if neLat <= swLat or neLon <= swLon:
        raise HTTPException(
            status_code=400,
            detail="Invalid bbox: neLat must be > swLat and neLon must be > swLon",
        )

    if neLat > 90 or neLat < -90 or swLat > 90 or swLat < -90:
        raise HTTPException(status_code=400, detail="Latitude out of range (-90 to 90)")
    if neLon > 180 or neLon < -180 or swLon > 180 or swLon < -180:
        raise HTTPException(status_code=400, detail="Longitude out of range (-180 to 180)")

    cached = bbox_cache.get(neLat, neLon, swLat, swLon)
    if cached:
        if cached.isStale:
            return Response(
                content=cached.model_dump_json(),
                media_type="application/json",
                headers={"X-Stale": "true"},
            )
        return cached

    raw_flights, source_name = _fetch_from_source(neLat, neLon, swLat, swLon)

    parse_client = OpenskyClient() if config.MILITARY_SOURCE == "opensky" else ADSBMilitaryClient()

    flights: list[MilitaryFlight] = []
    for raw in raw_flights:
        if source_name == "opensky":
            raw_list = list(raw)
            hex_code = str(raw_list[0] or "") if len(raw_list) > 0 else ""
            callsign = str(raw_list[1] or "").strip() if len(raw_list) > 1 else ""
            category = raw_list[17] if len(raw_list) > 17 else None
        else:
            raw_dict = dict(raw) if isinstance(raw, dict) else {}
            hex_code = raw_dict.get("hex", "")
            callsign = raw_dict.get("call", "")
            category = None

        if not is_military(hex_code, callsign, category):
            continue

        normalized_hex = normalize_hex(hex_code)
        if normalized_hex:
            hex_code = normalized_hex

        if source_name == "opensky":
            raw_list = list(raw)
            if normalized_hex:
                raw_list[0] = normalized_hex
            flight = parse_client.parse_flight(raw_list)
        else:
            raw_dict = dict(raw) if isinstance(raw, dict) else {}
            if normalized_hex:
                raw_dict["hex"] = normalized_hex
            flight = parse_client.parse_flight(raw_dict)

        if flight:
            flights.append(flight)

    clusters = compute_clusters(flights)

    flight_dicts = [f.model_dump() for f in flights]
    flight_history.update(flight_dicts)
    trails = flight_history.get_all_trails()

    for flight in flights:
        hex_code = flight.hexCode.upper()
        if hex_code in trails:
            flight.trail = trails[hex_code]

    response = MilitaryFlightsResponse(
        flights=flights,
        clusters=clusters,
        isStale=False,
        timestamp=datetime.now(timezone.utc),
    )

    bbox_cache.set(neLat, neLon, swLat, swLon, response)

    return response


def _fetch_from_source(neLat: float, neLon: float, swLat: float, swLon: float) -> tuple[list, str]:
    try:
        if config.MILITARY_SOURCE == "opensky":
            client = OpenskyClient()
            raw = client.fetch_flights(neLat, neLon, swLat, swLon)
            if raw is None:
                raw = []
            logger.info(f"OpenSky returned {len(raw)} raw states")
            return raw, "opensky"
        else:
            client = ADSBMilitaryClient()
            raw = client.fetch_military_flights(neLat, neLon, swLat, swLon)
            if raw is None:
                raw = []
            logger.info(f"ADS-B returned {len(raw)} raw flights")
            return raw, "adsb"
    except Exception as e:
        logger.error(f"{config.MILITARY_SOURCE} fetch failed: {e}")
        fallback = bbox_cache.get_last_valid(neLat, neLon, swLat, swLon)
        if fallback:
            logger.info("Returning stale fallback")
            return [], "stale"
        raise HTTPException(status_code=503, detail=f"Source {config.MILITARY_SOURCE} unavailable: {e}")


def compute_clusters(flights: list[MilitaryFlight]) -> list[MilitaryFlightCluster]:
    if not flights:
        return []

    clusters: list[MilitaryFlightCluster] = []
    used: set[int] = set()

    for i, flight in enumerate(flights):
        if i in used:
            continue

        nearby = [flight]
        used.add(i)

        for j, other in enumerate(flights[i + 1 :], start=i + 1):
            if j in used:
                continue
            dist = haversine_distance(
                flight.location.latitude,
                flight.location.longitude,
                other.location.latitude,
                other.location.longitude,
            )
            if dist < 100:
                nearby.append(other)
                used.add(j)

        if len(nearby) >= 3:
            avg_lat = sum(f.location.latitude for f in nearby) / len(nearby)
            avg_lon = sum(f.location.longitude for f in nearby) / len(nearby)
            avg_alt = sum(f.altitude for f in nearby) // len(nearby)
            avg_spd = sum(f.speed for f in nearby) // len(nearby)

            clusters.append(
                MilitaryFlightCluster(
                    center=Location(latitude=avg_lat, longitude=avg_lon),
                    count=len(nearby),
                    avgAltitude=avg_alt,
                    avgSpeed=avg_spd,
                )
            )

    return clusters


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    R = 6371.0

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


@app.get("/health")
async def health():
    return {"status": "ok", "service": "military_relay"}


@app.get("/")
async def root():
    return {
        "message": "Military Flight Relay API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8002)
