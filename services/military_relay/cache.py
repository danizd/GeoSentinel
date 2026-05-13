import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional

from services.military_relay import config
from services.military_relay.models import MilitaryFlightsResponse

logger = logging.getLogger(__name__)

MAX_TRAIL_LENGTH = 5


@dataclass
class CacheEntry:
    response: MilitaryFlightsResponse
    timestamp: float


class BBoxCache:
    def __init__(self, ttl_seconds: int = config.CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, CacheEntry] = {}

    def _bbox_key(self, neLat: float, neLon: float, swLat: float, swLon: float) -> str:
        bbox_str = f"{neLat},{neLon},{swLat},{swLon}"
        return hashlib.md5(bbox_str.encode()).hexdigest()

    def get(
        self,
        neLat: float,
        neLon: float,
        swLat: float,
        swLon: float,
    ) -> Optional[MilitaryFlightsResponse]:
        key = self._bbox_key(neLat, neLon, swLat, swLon)
        entry = self._cache.get(key)

        if entry is None:
            return None

        age = time.time() - entry.timestamp

        if age <= self.ttl_seconds:
            logger.debug(f"Cache hit (fresh): {key}, age={age:.1f}s")
            return entry.response

        if age <= self.ttl_seconds * 2:
            logger.debug(f"Cache hit (stale): {key}, age={age:.1f}s")
            stale_response = MilitaryFlightsResponse(
                flights=entry.response.flights,
                clusters=entry.response.clusters,
                isStale=True,
                timestamp=entry.response.timestamp,
            )
            return stale_response

        logger.debug(f"Cache expired: {key}, age={age:.1f}s")
        del self._cache[key]
        return None

    def set(
        self,
        neLat: float,
        neLon: float,
        swLat: float,
        swLon: float,
        response: MilitaryFlightsResponse,
    ) -> None:
        key = self._bbox_key(neLat, neLon, swLat, swLon)
        self._cache[key] = CacheEntry(
            response=response,
            timestamp=time.time(),
        )
        logger.debug(f"Cache set: {key}")

    def get_last_valid(
        self,
        neLat: float,
        neLon: float,
        swLat: float,
        swLon: float,
    ) -> Optional[MilitaryFlightsResponse]:
        key = self._bbox_key(neLat, neLon, swLat, swLon)
        entry = self._cache.get(key)

        if entry is None:
            return None

        stale_response = MilitaryFlightsResponse(
            flights=entry.response.flights,
            clusters=entry.response.clusters,
            isStale=True,
            timestamp=entry.response.timestamp,
        )
        logger.info(f"Returning stale fallback for bbox key: {key}")
        return stale_response


bbox_cache = BBoxCache()


class FlightTrail:
    def __init__(self, hex_code: str):
        self.hex_code = hex_code.upper()
        self.positions: list[dict] = []

    def add_position(self, lat: float, lon: float, timestamp: str, altitude: int, heading: int, speed: int) -> None:
        self.positions.append({
            "location": {"latitude": lat, "longitude": lon},
            "timestamp": timestamp,
            "altitude": altitude,
            "heading": heading,
            "speed": speed,
        })
        if len(self.positions) > MAX_TRAIL_LENGTH:
            self.positions = self.positions[-MAX_TRAIL_LENGTH:]

    def to_path(self) -> list[list[float]]:
        return [[p["location"]["longitude"], p["location"]["latitude"]] for p in self.positions]


class FlightHistoryBuffer:
    def __init__(self, max_age_seconds: int = 300):
        self.max_age_seconds = max_age_seconds
        self._trails: dict[str, FlightTrail] = {}
        self._last_update: dict[str, float] = {}

    def _hex_key(self, hex_code: str) -> str:
        return hex_code.upper().replace("-", "").replace(" ", "")

    def update(self, flights: list[dict]) -> None:
        current_time = time.time()
        active_hexes = set()

        for flight in flights:
            hex_code = flight.get("hexCode", "")
            if not hex_code:
                continue

            key = self._hex_key(hex_code)
            active_hexes.add(key)

            location = flight.get("location", {})
            lat = location.get("latitude")
            lon = location.get("longitude")
            if lat is None or lon is None:
                continue

            if key not in self._trails:
                self._trails[key] = FlightTrail(hex_code)

            self._trails[key].add_position(
                lat=lat,
                lon=lon,
                timestamp=flight.get("lastSeenAt", ""),
                altitude=flight.get("altitude", 0),
                heading=flight.get("heading", 0),
                speed=flight.get("speed", 0),
            )
            self._last_update[key] = current_time

        for key in list(self._trails.keys()):
            if key not in active_hexes:
                age = current_time - self._last_update.get(key, 0)
                if age > self.max_age_seconds:
                    del self._trails[key]
                    if key in self._last_update:
                        del self._last_update[key]

    def get_trail(self, hex_code: str) -> list[list[float]]:
        key = self._hex_key(hex_code)
        trail = self._trails.get(key)
        if trail:
            return trail.to_path()
        return []

    def get_all_trails(self) -> dict[str, list[list[float]]]:
        return {hex_code: trail.to_path() for hex_code, trail in self._trails.items() if len(trail.positions) > 1}


flight_history = FlightHistoryBuffer()