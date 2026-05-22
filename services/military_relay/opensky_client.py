import logging
import time as time_module
import threading
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from services.military_relay import config
from services.military_relay.models import Location, MilitaryFlight

logger = logging.getLogger(__name__)

M_TO_FT = 3.28084
MS_TO_KTS = 1.94384


class OpenSkyRateLimiter:
    _lock = threading.Lock()
    _last_call = 0.0

    @classmethod
    def wait(cls) -> None:
        with cls._lock:
            now = time_module.time()
            elapsed = now - cls._last_call
            if elapsed < 1.1:
                time_module.sleep(1.1 - elapsed)
            cls._last_call = time_module.time()


_rate_limiter = OpenSkyRateLimiter()


class TokenManager:
    def __init__(self):
        self.token: Optional[str] = None
        self.expires_at: float = 0.0
        self.client_id = config.OPENSKY_CLIENT_ID
        self.client_secret = config.OPENSKY_CLIENT_SECRET

    @property
    def is_authenticated(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_token(self) -> Optional[str]:
        if not self.is_authenticated:
            return None
        if self.token and time_module.time() < self.expires_at:
            return self.token
        return self._refresh()

    def _refresh(self) -> Optional[str]:
        try:
            resp = requests.post(
                config.OPENSKY_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data["access_token"]
            expires_in = data.get("expires_in", 1800)
            self.expires_at = time_module.time() + expires_in - 30
            return self.token
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenSky token refresh failed: {e}")
            self.token = None
            self.expires_at = 0.0
            return None

    def headers(self) -> dict[str, str]:
        token = self.get_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}


class OpenskyClient:
    STATES_ICAO24 = 0
    STATES_CALLSIGN = 1
    STATES_ORIGIN_COUNTRY = 2
    STATES_TIME_POSITION = 3
    STATES_LAST_CONTACT = 4
    STATES_LONGITUDE = 5
    STATES_LATITUDE = 6
    STATES_BARO_ALTITUDE = 7
    STATES_ON_GROUND = 8
    STATES_VELOCITY = 9
    STATES_TRUE_TRACK = 10
    STATES_VERTICAL_RATE = 11
    STATES_SENSORS = 12
    STATES_GEO_ALTITUDE = 13
    STATES_SQUAWK = 14
    STATES_SPI = 15
    STATES_POSITION_SOURCE = 16
    STATES_CATEGORY = 17

    _aircraft_cache: dict[str, dict] = {}

    def __init__(self, token_manager: Optional[TokenManager] = None, session: Optional[requests.Session] = None):
        self.token_manager = token_manager or TokenManager()
        self.session = session or requests.Session()

    def fetch_flights(
        self,
        neLat: float,
        neLon: float,
        swLat: float,
        swLon: float,
    ) -> list[list[Any]]:
        _rate_limiter.wait()

        lat_min = min(swLat, neLat)
        lat_max = max(swLat, neLat)
        lon_min = min(swLon, neLon)
        lon_max = max(swLon, neLon)

        url = f"{config.OPENSKY_BASE_URL}/states/all"
        params = {
            "lamin": lat_min,
            "lamax": lat_max,
            "lomin": lon_min,
            "lomax": lon_max,
        }

        headers = self.token_manager.headers()
        logger.info(f"Fetching OpenSky states: lamin={lat_min} lamax={lat_max} lomin={lon_min} lomax={lon_max}")


        try:
            response = self.session.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 429:
                logger.warning("OpenSky rate limited (429) - returning empty results")
                return []

            if response.status_code in (401, 403):
                logger.error(
                    f"OpenSky auth error ({response.status_code}) - "
                    "configure OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET"
                )
                return []

            response.raise_for_status()
            data = response.json()
            states = data.get("states") or []
            logger.info(
                f"OpenSky /states/all -> {len(states)} estados "
                f"(bbox: lamin={lat_min} lamax={lat_max} lomin={lon_min} lomax={lon_max})"
            )
            return states
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenSky request failed: {e}")
            raise

    def fetch_aircraft_metadata(self, icao24: str) -> Optional[dict]:
        cached = self._aircraft_cache.get(icao24.lower())
        if cached is not None:
            return cached if cached else None

        url = f"{config.OPENSKY_BASE_URL}/metadata/aircraft/{icao24}"
        headers = self.token_manager.headers()

        try:
            _rate_limiter.wait()
            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self._aircraft_cache[icao24.lower()] = data
                return data
            else:
                self._aircraft_cache[icao24.lower()] = {}
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch metadata for {icao24}: {e}")
            self._aircraft_cache[icao24.lower()] = {}
            return None

    def parse_flight(self, raw: list[Any]) -> Optional[MilitaryFlight]:
        try:
            hex_code = raw[self.STATES_ICAO24] if len(raw) > self.STATES_ICAO24 else ""
            if not hex_code:
                return None

            callsign = (raw[self.STATES_CALLSIGN] or "").strip() if len(raw) > self.STATES_CALLSIGN else ""

            lat = raw[self.STATES_LATITUDE] if len(raw) > self.STATES_LATITUDE else None
            lon = raw[self.STATES_LONGITUDE] if len(raw) > self.STATES_LONGITUDE else None
            if lat is None or lon is None:
                return None

            baro_alt_m = raw[self.STATES_BARO_ALTITUDE] if len(raw) > self.STATES_BARO_ALTITUDE else None
            altitude_ft = int(baro_alt_m * M_TO_FT) if baro_alt_m is not None else 0

            velocity_ms = raw[self.STATES_VELOCITY] if len(raw) > self.STATES_VELOCITY else None
            speed_kts = int(velocity_ms * MS_TO_KTS) if velocity_ms is not None else 0

            true_track = raw[self.STATES_TRUE_TRACK] if len(raw) > self.STATES_TRUE_TRACK else None
            heading = int(true_track) if true_track is not None else 0

            last_contact = raw[self.STATES_LAST_CONTACT] if len(raw) > self.STATES_LAST_CONTACT else None
            if last_contact:
                ts = datetime.fromtimestamp(last_contact, tz=timezone.utc)
                last_seen_iso = ts.isoformat()
            else:
                last_seen_iso = datetime.now(timezone.utc).isoformat()

            origin_country = raw[self.STATES_ORIGIN_COUNTRY] if len(raw) > self.STATES_ORIGIN_COUNTRY else None
            on_ground = raw[self.STATES_ON_GROUND] if len(raw) > self.STATES_ON_GROUND else False

            category = raw[self.STATES_CATEGORY] if len(raw) > self.STATES_CATEGORY else None
            is_interesting = bool(on_ground) or (category == 7)

            aircraft_type = None
            aircraft_model = None
            registration = None
            operator_name = None
            if hex_code:
                meta = self.fetch_aircraft_metadata(hex_code)
                if meta:
                    aircraft_type = meta.get("typecode")
                    aircraft_model = meta.get("model")
                    registration = meta.get("registration")
                    operator_name = meta.get("operator")

            flight_id = f"{hex_code.upper()}:{int(datetime.fromisoformat(last_seen_iso).timestamp())}"

            return MilitaryFlight(
                id=flight_id,
                callsign=callsign or "UNKNOWN",
                hexCode=hex_code.upper(),
                location=Location(latitude=lat, longitude=lon),
                altitude=altitude_ft,
                heading=heading,
                speed=speed_kts,
                lastSeenAt=last_seen_iso,
                operatorCountry=origin_country,
                aircraftType=aircraft_type,
                aircraftModel=aircraft_model,
                registration=registration,
                operator=operator_name,
                isInteresting=is_interesting,
                source="opensky",
            )
        except Exception as e:
            logger.warning(f"Failed to parse OpenSky flight: {e}")
            return None
