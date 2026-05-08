import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobs.event_processing import process_and_upsert_event
from normalizers.usgs_mapper import normalize_usgs_event
from schemas.events import EventCanonicalCreate
from validation.validator import validate_event, insert_quarantine

logger = logging.getLogger(__name__)

USGS_BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
POLL_INTERVAL_SECONDS = 180
MIN_MAGNITUDE = 4.0

DEFAULT_BACKOFF_BASE = 2
DEFAULT_BACKOFF_MAX = 60
DEFAULT_MAX_RETRIES = 5


class USGSIngestor:
    def __init__(
        self,
        session: requests.Session | None = None,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        min_magnitude: float = MIN_MAGNITUDE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: int = DEFAULT_BACKOFF_BASE,
        backoff_max: int = DEFAULT_BACKOFF_MAX,
    ):
        self.session = session or self._create_session(max_retries)
        self.poll_interval = poll_interval
        self.min_magnitude = min_magnitude
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

    def _build_url(self, starttime: datetime, endtime: datetime) -> str:
        fmt = "%Y-%m-%dT%H:%M:%S"
        return (
            f"{USGS_BASE_URL}?format=geojson"
            f"&starttime={starttime.strftime(fmt)}"
            f"&endtime={endtime.strftime(fmt)}"
            f"&minmagnitude={self.min_magnitude}"
        )

    def fetch_earthquakes(
        self,
        starttime: datetime,
        endtime: datetime,
    ) -> list[dict[str, Any]]:
        url = self._build_url(starttime, endtime)
        logger.info(f"Fetching USGS earthquakes: {url}")

        attempt = 0
        last_exc: Exception | None = None
        while attempt < self.max_retries:
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()
                return data.get("features", [])
            except requests.exceptions.Timeout as e:
                last_exc = e
                attempt += 1
                if attempt >= self.max_retries:
                    logger.error("USGS request timeout (max retries reached)")
                    raise
                wait_time = self._calculate_backoff(attempt)
                logger.warning(f"USGS timeout, retrying in {wait_time}s (attempt {attempt})")
                time.sleep(wait_time)
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    last_exc = e
                    attempt += 1
                    if attempt >= self.max_retries:
                        logger.error("USGS rate limited (max retries reached)")
                        raise
                    wait_time = self._calculate_backoff(attempt)
                    logger.warning(f"USGS rate limited, retrying in {wait_time}s (attempt {attempt})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"USGS HTTP error: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"USGS request failed: {e}")
                raise

        if last_exc is not None:
            raise last_exc
        return []

    def _calculate_backoff(self, attempt: int) -> int:
        backoff = self.backoff_base**attempt
        return min(backoff, self.backoff_max)

    def run(self, db_session, process_callback=None, lookback_hours: int | None = None) -> dict[str, Any]:
        endtime = datetime.now(timezone.utc)
        lookback = timedelta(hours=lookback_hours) if lookback_hours else timedelta(minutes=5)
        starttime = endtime - lookback

        attempt = 0
        while attempt < self.max_retries:
            try:
                earthquakes = self.fetch_earthquakes(starttime, endtime)
                break
            except requests.exceptions.Timeout:
                attempt += 1
                if attempt >= self.max_retries:
                    logger.error("Max retries reached for USGS fetch")
                    raise
                wait_time = self._calculate_backoff(attempt)
                logger.warning(f"Timeout, retrying in {wait_time}s (attempt {attempt})")
                time.sleep(wait_time)
            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    attempt += 1
                    if attempt >= self.max_retries:
                        logger.error("Max retries reached for USGS fetch (rate limited)")
                        raise
                    wait_time = self._calculate_backoff(attempt)
                    logger.warning(f"Rate limited, retrying in {wait_time}s (attempt {attempt})")
                    time.sleep(wait_time)
                else:
                    raise

        processed = 0
        quarantined = 0
        duplicates = 0

        callback = process_callback or process_and_upsert_event

        for eq in earthquakes:
            try:
                event = normalize_usgs_event(eq)

                validation = validate_event(event)

                if not validation.is_valid:
                    insert_quarantine(
                        session=db_session,
                        source="usgs",
                        raw_payload=eq,
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
                logger.error(f"Error processing earthquake: {e}")
                quarantined += 1

        return {
            "processed": processed,
            "quarantined": quarantined,
            "duplicates": duplicates,
            "total_fetched": len(earthquakes),
        }


def run_polling():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
    Session = sessionmaker(bind=engine)

    ingestor = USGSIngestor()

    while True:
        session = Session()
        try:
            result = ingestor.run(session)
            logger.info(f"USGS poll result: {result}")
        except Exception as e:
            logger.error(f"USGS polling failed: {e}")
        finally:
            session.close()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_polling()