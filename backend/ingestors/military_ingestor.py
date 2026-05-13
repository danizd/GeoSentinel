import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from sqlalchemy import text
from sqlalchemy.orm import Session
from urllib3.util.retry import Retry

from backend.jobs.event_processing import process_and_upsert_event
from backend.schemas.events import Actor, CategoryEnum, EventCanonicalCreate
from backend.validation.validator import validate_event, insert_quarantine

logger = logging.getLogger(__name__)

RELAY_BASE_URL = os.getenv("MILITARY_RELAY_URL", "http://localhost:8000")
POLL_INTERVAL_SECONDS = 60

DEFAULT_BACKOFF_BASE = 2
DEFAULT_BACKOFF_MAX = 60
DEFAULT_MAX_RETRIES = 5

MILITARY_CALLSIGN_PREFIXES_FULL = [
    "RCH", "REACH", "MOOSE", "EVAC", "DUSTOFF",
    "VIPER", "RAPTOR", "SENTRY", "AWACS", "COBRA", "PYTHON",
    "NAVY", "USAF", "USN", "USMC", "NATO", "RAF",
    "IAF", "VKS", "PLAAF",
]

ANOMALY_RADIUS_KM = 50
CLUSTER_MIN_COUNT = 3
CLUSTER_RADIUS_KM = 100


class MilitaryIngestor:
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        relay_url: str = RELAY_BASE_URL,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: int = DEFAULT_BACKOFF_BASE,
        backoff_max: int = DEFAULT_BACKOFF_MAX,
    ):
        self.session = session or self._create_session(max_retries)
        self.relay_url = relay_url
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

    def _create_session(self, max_retries: int) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _calculate_backoff(self, attempt: int) -> int:
        backoff = self.backoff_base**attempt
        return min(backoff, self.backoff_max)

    def get_active_aois(self, db_session: Session) -> list[dict[str, Any]]:
        result = db_session.execute(
            text("""
                SELECT aoi_id, name, ST_XMax(geometry) as max_lon, ST_YMax(geometry) as max_lat,
                       ST_XMin(geometry) as min_lon, ST_YMin(geometry) as min_lat
                FROM aoi
                WHERE is_active = true
            """)
        )
        aois = []
        for row in result:
            aois.append({
                "aoi_id": str(row[0]),
                "name": row[1],
                "max_lon": float(row[2]),
                "max_lat": float(row[3]),
                "min_lon": float(row[4]),
                "min_lat": float(row[5]),
            })
        return aois

    def fetch_from_relay(
        self,
        neLat: float,
        neLon: float,
        swLat: float,
        swLon: float,
    ) -> dict[str, Any]:
        url = f"{self.relay_url}/api/military/v1/list-military-flights"
        params = {
            "neLat": neLat,
            "neLon": neLon,
            "swLat": swLat,
            "swLon": swLon,
        }

        logger.info(f"Fetching from relay: {url} with params {params}")

        attempt = 0
        last_exc: Exception | None = None

        while attempt < self.max_retries:
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                is_stale = response.headers.get("X-Stale", "false").lower() == "true"
                if is_stale:
                    logger.warning("Relay returned stale data")
                    data["_is_stale"] = True
                else:
                    data["_is_stale"] = False

                return data
            except requests.exceptions.Timeout as e:
                last_exc = e
                attempt += 1
                if attempt >= self.max_retries:
                    logger.error("Relay request timeout (max retries reached)")
                    raise
                wait_time = self._calculate_backoff(attempt)
                logger.warning(f"Relay timeout, retrying in {wait_time}s (attempt {attempt})")
                time.sleep(wait_time)
            except requests.exceptions.HTTPError as e:
                last_exc = e
                attempt += 1
                if attempt >= self.max_retries:
                    logger.error(f"Relay HTTP error (max retries reached): {e}")
                    raise
                wait_time = self._calculate_backoff(attempt)
                logger.warning(f"Relay HTTP error, retrying in {wait_time}s (attempt {attempt})")
                time.sleep(wait_time)
            except requests.exceptions.RequestException as e:
                logger.error(f"Relay request failed: {e}")
                raise

        if last_exc is not None:
            raise last_exc
        return {"flights": [], "clusters": []}

    def military_event_id(self, hex_code: str, last_seen_at: str) -> str:
        ts = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        ts_60 = int(ts.timestamp() // 60) * 60
        return f"{hex_code.upper()}:{ts_60}"

    def check_incident_proximity(self, db_session: Session, lat: float, lon: float) -> bool:
        result = db_session.execute(
            text("""
                SELECT COUNT(*)
                FROM incidents
                WHERE status = 'active'
                  AND category = 'conflict'
                  AND ST_DWithin(
                    location_point::geography,
                    ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography,
                    :radius_meters
                  )
            """),
            {"lon": lon, "lat": lat, "radius_meters": ANOMALY_RADIUS_KM * 1000}
        )
        count = result.scalar()
        return count > 0

    def check_cluster(self, flights: list[dict], lat: float, lon: float) -> bool:
        count = 0
        for f in flights:
            f_lat = f.get("location", {}).get("latitude", 0)
            f_lon = f.get("location", {}).get("longitude", 0)
            dist = self._haversine_distance(lat, lon, f_lat, f_lon)
            if dist < CLUSTER_RADIUS_KM:
                count += 1
        return count >= CLUSTER_MIN_COUNT

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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

    def map_to_canonical(self, flight: dict[str, Any], is_stale: bool = False) -> EventCanonicalCreate:
        hex_code = flight.get("hexCode", "")
        callsign = flight.get("callsign", "UNKNOWN")
        last_seen = flight.get("lastSeenAt", datetime.now(timezone.utc).isoformat())

        event_id = self.military_event_id(hex_code, last_seen)

        location = flight.get("location", {})
        lat = location.get("latitude", 0.0)
        lon = location.get("longitude", 0.0)

        source_refs = ["military_relay"]
        if is_stale:
            source_refs.append("stale_cache")

        source_refs.append(f"altitude:{flight.get('altitude', 0)}ft")
        source_refs.append(f"speed:{flight.get('speed', 0)}kts")
        if flight.get("operator"):
            source_refs.append(f"operator:{flight.get('operator')}")
        if flight.get("aircraftType"):
            source_refs.append(f"aircraft:{flight.get('aircraftType')}")

        actors = [
            Actor(
                role="military_aircraft",
                name=callsign,
                cameo_code=None,
            )
        ]

        confidence = flight.get("confidence")
        if confidence is None:
            confidence = 8.0

        severity = 3.0

        is_interesting = flight.get("isInteresting", False)
        if is_interesting:
            severity = max(severity, 6.0)

        return EventCanonicalCreate(
            event_id_source=event_id,
            source="military",
            event_time=datetime.fromisoformat(last_seen.replace("Z", "+00:00")),
            event_type="military_flight",
            category=CategoryEnum.MOBILITY,
            latitude=lat,
            longitude=lon,
            location_accuracy_km=1.0,
            operatorCountry=flight.get("operatorCountry"),
            actors=actors,
            severity=severity,
            confidence=confidence,
            source_refs=source_refs,
        )

    def run(self, db_session: Session, process_callback=None) -> dict[str, Any]:
        aois = self.get_active_aois(db_session)
        logger.info(f"Found {len(aois)} active AOIs")

        if not aois:
            logger.warning("No active AOIs found, skipping military flight ingestion")
            return {"processed": 0, "quarantined": 0, "duplicates": 0, "total_fetched": 0}

        callback = process_callback or process_and_upsert_event

        all_flights: list[dict[str, Any]] = []
        seen_event_ids: set[str] = set()

        processed = 0
        quarantined = 0
        duplicates = 0
        total_fetched = 0

        for aoi in aois:
            try:
                response = self.fetch_from_relay(
                    neLat=aoi["max_lat"],
                    neLon=aoi["max_lon"],
                    swLat=aoi["min_lat"],
                    swLon=aoi["min_lon"],
                )

                is_stale = response.get("_is_stale", False)
                flights = response.get("flights", [])
                total_fetched += len(flights)

                for flight in flights:
                    event_id = self.military_event_id(
                        flight.get("hexCode", ""),
                        flight.get("lastSeenAt", "")
                    )

                    if event_id in seen_event_ids:
                        duplicates += 1
                        continue
                    seen_event_ids.add(event_id)

                    all_flights.append(flight)

                logger.info(f"AOI {aoi['name']}: fetched {len(flights)} flights, is_stale={is_stale}")

            except Exception as e:
                logger.error(f"Error fetching from relay for AOI {aoi['name']}: {e}")
                continue

        for flight in all_flights:
            try:
                is_stale = False

                event_id = self.military_event_id(
                    flight.get("hexCode", ""),
                    flight.get("lastSeenAt", "")
                )

                location = flight.get("location", {})
                lat = location.get("latitude", 0.0)
                lon = location.get("longitude", 0.0)

                near_incident = self.check_incident_proximity(db_session, lat, lon)
                is_interesting = flight.get("isInteresting", False)
                is_cluster = self.check_cluster(all_flights, lat, lon)

                if near_incident or is_interesting or is_cluster:
                    logger.info(f"Anomaly detected for flight {event_id}: near_incident={near_incident}, interesting={is_interesting}, cluster={is_cluster}")

                event = self.map_to_canonical(flight, is_stale)

                if near_incident:
                    event.severity = max(event.severity, 7.0)
                if is_interesting:
                    event.severity = max(event.severity, 6.0)
                if is_cluster:
                    event.severity = max(event.severity, 5.0)

                validation = validate_event(event)

                if not validation.is_valid:
                    insert_quarantine(
                        session=db_session,
                        source="military",
                        raw_payload=flight,
                        rejection_code=validation.rejection_code,
                        rejection_detail=validation.rejection_detail,
                    )
                    quarantined += 1
                    continue

                result = callback(db_session, event)
                if result.get("duplicate"):
                    duplicates += 1
                else:
                    processed += 1

            except Exception as e:
                logger.error(f"Error processing flight: {e}")
                quarantined += 1

        return {
            "processed": processed,
            "quarantined": quarantined,
            "duplicates": duplicates,
            "total_fetched": total_fetched,
        }


def run_polling():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
    Session = sessionmaker(bind=engine)

    ingestor = MilitaryIngestor()

    while True:
        session = Session()
        try:
            result = ingestor.run(session)
            logger.info(f"Military poll result: {result}")
        except Exception as e:
            logger.error(f"Military polling failed: {e}")
        finally:
            session.close()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_polling()