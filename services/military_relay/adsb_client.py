import logging
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from services.military_relay import config
from services.military_relay.models import Location, MilitaryFlight

logger = logging.getLogger(__name__)


class ADSBMilitaryClient:
    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.api_key = api_key or config.ADSB_API_KEY
        self.auth_header = config.ADSB_AUTH_HEADER
        self.session = session or requests.Session()
        self.base_url = config.ADSB_BASE_URL

    def _build_url(
        self,
        neLat: float,
        neLon: float,
        swLat: float,
        swLon: float,
    ) -> str:
        latMin = min(swLat, neLat)
        latMax = max(swLat, neLat)
        lonMin = min(swLon, neLon)
        lonMax = max(swLon, neLon)
        if self.base_url.endswith("/aircraft"):
            return f"{self.base_url}?latMin={latMin}&latMax={latMax}&lngMin={lonMin}&lngMax={lonMax}"
        return f"{self.base_url}/lat/{latMin}/lon/{lonMin}/dist/200/"

    def fetch_military_flights(
        self,
        neLat: float,
        neLon: float,
        swLat: float,
        swLon: float,
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            raise ValueError("ADSB_API_KEY not configured")

        url = self._build_url(neLat, neLon, swLat, swLon)
        headers = {self.auth_header: self.api_key}

        logger.info(f"Fetching ADS-B flights: {url}")

        try:
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data.get("ac", [])
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"ADS-B request failed: {e}")
            raise

    def parse_flight(self, raw: dict[str, Any]) -> Optional[MilitaryFlight]:
        try:
            hex_code = raw.get("hex", "")
            if not hex_code:
                return None

            callsign = raw.get("call", "").strip()

            lat = raw.get("lat")
            lon = raw.get("lon")
            if lat is None or lon is None:
                return None

            altitude = raw.get("alt", 0) or 0
            heading = raw.get("trk", 0) or 0
            speed = raw.get("gs", 0) or 0

            last_seen = raw.get("t")
            if last_seen:
                try:
                    ts = datetime.fromtimestamp(last_seen, tz=timezone.utc)
                    last_seen_iso = ts.isoformat()
                except (ValueError, OSError):
                    last_seen_iso = datetime.now(timezone.utc).isoformat()
            else:
                last_seen_iso = datetime.now(timezone.utc).isoformat()

            flight_id = f"{hex_code.upper()}:{int(datetime.fromisoformat(last_seen_iso).timestamp())}"

            return MilitaryFlight(
                id=flight_id,
                callsign=callsign or "UNKNOWN",
                hexCode=hex_code.upper(),
                location=Location(latitude=lat, longitude=lon),
                altitude=altitude,
                heading=heading,
                speed=speed,
                lastSeenAt=last_seen_iso,
                aircraftType=raw.get("type"),
                operator=raw.get("op"),
                operatorCountry=raw.get("cou"),
                registration=raw.get("reg"),
                aircraftModel=raw.get("ttyp"),
                origin=raw.get("From"),
                destination=raw.get("to"),
                isInteresting=raw.get("interesting", False),
            )
        except Exception as e:
            logger.warning(f"Failed to parse flight: {e}")
            return None