import io
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobs.event_processing import process_and_upsert_event
from normalizers.firms_mapper import normalize_firms_row
from schemas.events import EventCanonicalCreate
from validation.validator import validate_event, insert_quarantine

logger = logging.getLogger(__name__)

FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
POLL_INTERVAL_SECONDS = 3600
DEFAULT_DAYS = 1

DEFAULT_BACKOFF_BASE = 2
DEFAULT_BACKOFF_MAX = 60
DEFAULT_MAX_RETRIES = 5


class FIRMSIngestor:
    def __init__(
        self,
        session: requests.Session | None = None,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        map_key: str | None = None,
        product: str = "VIIRS_SNPP_NRT",
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: int = DEFAULT_BACKOFF_BASE,
        backoff_max: int = DEFAULT_BACKOFF_MAX,
    ):
        self.session = session or self._create_session(max_retries)
        self.poll_interval = poll_interval
        self.map_key = map_key or os.getenv("FIRMS_MAP_KEY")
        self.product = product
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

        if not self.map_key:
            raise ValueError("FIRMS_MAP_KEY not provided")

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
        return session

    def _build_url(self, bbox: tuple[float, float, float, float], days: int = DEFAULT_DAYS) -> str:
        lon_min, lat_min, lon_max, lat_max = bbox
        coords = f"{lon_min},{lat_min},{lon_max},{lat_max}"
        return f"{FIRMS_BASE_URL}/{self.map_key}/{self.product}/{coords}/{days}/"

    def fetch_hotspots(
        self,
        bbox: tuple[float, float, float, float],
        days: int = DEFAULT_DAYS,
    ) -> list[dict[str, Any]]:
        url = self._build_url(bbox, days)
        logger.info(f"Fetching FIRMS hotspots: {url[:100]}...")

        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()

            content = response.text.strip()
            if not content:
                return []

            lines = content.split("\n")
            if len(lines) < 2:
                return []

            headers = lines[0].split(",")
            data_rows = []

            for line in lines[1:]:
                if not line.strip():
                    continue
                values = line.split(",")
                row = dict(zip(headers, values, strict=False))
                data_rows.append(row)

            return data_rows

        except requests.exceptions.Timeout:
            logger.error("FIRMS request timeout")
            raise
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                logger.warning("FIRMS rate limited (429)")
                raise
            logger.error(f"FIRMS HTTP error: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"FIRMS request failed: {e}")
            raise

    def _calculate_backoff(self, attempt: int) -> int:
        backoff = self.backoff_base**attempt
        return min(backoff, self.backoff_max)

    def run(
        self,
        db_session,
        bbox: tuple[float, float, float, float] | None = None,
        days: int = DEFAULT_DAYS,
        process_callback=None,
    ) -> dict[str, Any]:
        if bbox is None:
            bbox = (-180, -90, 180, 90)

        attempt = 0
        while attempt < self.max_retries:
            try:
                hotspots = self.fetch_hotspots(bbox, days)
                break
            except requests.exceptions.Timeout:
                attempt += 1
                if attempt >= self.max_retries:
                    logger.error("Max retries reached for FIRMS fetch")
                    raise
                wait_time = self._calculate_backoff(attempt)
                logger.warning(f"Timeout, retrying in {wait_time}s (attempt {attempt})")
                time.sleep(wait_time)
            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    attempt += 1
                    if attempt >= self.max_retries:
                        logger.error("Max retries reached for FIRMS fetch (rate limited)")
                        raise
                    wait_time = self._calculate_backoff(attempt)
                    logger.warning(f"Rate limited, retrying in {wait_time}s (attempt {attempt})")
                    time.sleep(wait_time)
                else:
                    raise

        processed = 0
        quarantined = 0
        duplicates = 0
        skipped_low_confidence = 0

        callback = process_callback or process_and_upsert_event

        for row in hotspots:
            try:
                event = normalize_firms_row(row, self.product)

                validation = validate_event(event)

                if not validation.is_valid:
                    insert_quarantine(
                        session=db_session,
                        source="firms",
                        raw_payload=row,
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

            except ValueError as e:
                if "Confidence" in str(e):
                    skipped_low_confidence += 1
                else:
                    logger.error(f"Error processing FIRMS row: {e}")
                    quarantined += 1
            except Exception as e:
                logger.error(f"Error processing FIRMS row: {e}")
                quarantined += 1

        return {
            "processed": processed,
            "quarantined": quarantined,
            "duplicates": duplicates,
            "skipped_low_confidence": skipped_low_confidence,
            "total_fetched": len(hotspots),
        }


def get_active_aois(session) -> list[tuple[float, float, float, float]]:
    from sqlalchemy import select, text
    from models.aoi import Aoi

    aois = session.execute(
        select(Aoi).where(Aoi.is_active == True)
    ).scalars().all()

    bboxes = []
    for aoi in aois:
        result = session.execute(
            text("SELECT ST_XMin(geometry), ST_YMin(geometry), ST_XMax(geometry), ST_YMax(geometry) FROM aoi WHERE aoi_id = :aoi_id"),
            {"aoi_id": str(aoi.aoi_id)}
        ).fetchone()
        if result and all(result):
            bboxes.append((result[0], result[1], result[2], result[3]))
    return bboxes


def run_polling():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
    Session = sessionmaker(bind=engine)

    map_key = os.getenv("FIRMS_MAP_KEY")
    if not map_key:
        logger.error("FIRMS_MAP_KEY not set")
        return

    ingestor = FIRMSIngestor(map_key=map_key)

    while True:
        session = Session()
        try:
            bboxes = get_active_aois(session)
            if not bboxes:
                bboxes = [(-180, -90, 180, 90)]

            for bbox in bboxes:
                result = ingestor.run(session, bbox=bbox)
                logger.info(f"FIRMS poll result for bbox {bbox}: {result}")
        except Exception as e:
            logger.error(f"FIRMS polling failed: {e}")
        finally:
            session.close()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_polling()