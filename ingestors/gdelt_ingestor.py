import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobs.event_processing import process_and_upsert_event
from normalizers.gdelt_mapper import normalize_gdelt_event
from validation.validator import insert_quarantine, validate_event

logger = logging.getLogger(__name__)

GDELT_BASE_URL = "https://gdeltcloud.com/api/v2"
POLL_INTERVAL_SECONDS = 300

DEFAULT_BACKOFF_BASE = 2
DEFAULT_BACKOFF_MAX = 120
DEFAULT_MAX_RETRIES = 5

CONFLICT_ZONES = [
    "Ukraine",
    "Israel",
    "Palestine",
    "Gaza",
    "Syria",
    "Yemen",
    "Sudan",
    "Mali",
    "Burkina Faso",
    "Niger",
    "Colombia",
    "Myanmar",
]


class GDELTCloudIngestor:
    def __init__(
        self,
        session: requests.Session | None = None,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        api_key: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: int = DEFAULT_BACKOFF_BASE,
        backoff_max: int = DEFAULT_BACKOFF_MAX,
    ):
        self.poll_interval = poll_interval
        self.api_key = api_key or os.getenv("GDELT_API_KEY")
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.session = session or self._create_session(max_retries)

        if not self.api_key:
            raise ValueError("GDELT_API_KEY not provided")

    def _create_session(self, max_retries: int) -> requests.Session:
        http_session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http_session.mount("https://", adapter)
        http_session.mount("http://", adapter)
        return http_session

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _build_params(
        self,
        date_start: datetime,
        date_end: datetime,
        country: str | None = None,
        event_family: str = "conflict",
        has_fatalities: bool | None = None,
        search: str | None = None,
        sort: str = "recent",
        limit: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "date_start": date_start.strftime("%Y-%m-%d"),
            "date_end": date_end.strftime("%Y-%m-%d"),
            "event_family": event_family,
            "sort": sort,
            "limit": limit,
        }
        if country:
            params["country"] = country
        if has_fatalities is not None:
            params["has_fatalities"] = "true" if has_fatalities else "false"
        if search:
            params["search"] = search
        return params

    def fetch_events(
        self,
        date_start: datetime,
        date_end: datetime,
        country: str | None = None,
        has_fatalities: bool | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params = self._build_params(
            date_start=date_start,
            date_end=date_end,
            country=country,
            has_fatalities=has_fatalities,
            search=search,
            limit=limit,
        )
        headers = self._get_headers()

        logger.info(f"Fetching GDELT Cloud events: {date_start.date()} -> {date_end.date()}" +
                   (f" country={country}" if country else ""))

        try:
            response = self.session.get(
                f"{GDELT_BASE_URL}/events",
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                error_msg = data.get("error", "Unknown error")
                error_code = data.get("code", "UNKNOWN")
                logger.error(f"GDELT API error: {error_code} - {error_msg}")
                return []

            return data.get("data", [])
        except requests.exceptions.Timeout:
            logger.error("GDELT request timeout")
            raise
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                logger.warning(f"GDELT rate limited (429), Retry-After={retry_after}s")
                raise
            if e.response is not None and e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    if error_data.get("code") == "DATE_WINDOW_TOO_LARGE":
                        logger.warning("GDELT date window exceeds 30 days")
                        return []
                except Exception:
                    pass
            logger.error(f"GDELT HTTP error: {e}")
            raise
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"GDELT malformed JSON response: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"GDELT request failed: {e}")
            raise

    def _calculate_backoff(self, attempt: int) -> int:
        backoff = self.backoff_base**attempt
        return min(backoff, self.backoff_max)

    def run(self, db_session, process_callback=None, lookback_days: int = 1) -> dict[str, Any]:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=lookback_days)

        events: list[dict[str, Any]] = []
        attempt = 0

        while attempt < self.max_retries:
            try:
                events = self.fetch_events(start_time, end_time)
                break
            except requests.exceptions.Timeout:
                attempt += 1
                if attempt >= self.max_retries:
                    logger.error("Max retries reached for GDELT fetch (timeout)")
                    raise
                wait_time = self._calculate_backoff(attempt)
                logger.warning(f"Timeout, retrying in {wait_time}s (attempt {attempt})")
                time.sleep(wait_time)
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", self._calculate_backoff(attempt + 1)))
                    attempt += 1
                    if attempt >= self.max_retries:
                        logger.error("Max retries reached for GDELT fetch (rate limited)")
                        raise
                    logger.warning(f"Rate limited, retrying in {retry_after}s (attempt {attempt})")
                    time.sleep(retry_after)
                else:
                    raise
            except requests.exceptions.RequestException:
                attempt += 1
                if attempt >= self.max_retries:
                    logger.error("Max retries reached for GDELT fetch")
                    raise
                wait_time = self._calculate_backoff(attempt)
                time.sleep(wait_time)

        processed = 0
        quarantined = 0
        duplicates = 0

        callback = process_callback or process_and_upsert_event

        for raw_event in events:
            try:
                event = normalize_gdelt_event(raw_event)
                validation = validate_event(event)

                if not validation.is_valid:
                    insert_quarantine(
                        session=db_session,
                        source="gdelt",
                        raw_payload=raw_event,
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
                logger.error(f"Error processing GDELT event: {e}")
                quarantined += 1

        return {
            "processed": processed,
            "quarantined": quarantined,
            "duplicates": duplicates,
            "total_fetched": len(events),
        }

    def run_all_zones(self, db_session, process_callback=None, lookback_days: int = 1) -> dict[str, Any]:
        end_time = datetime.now(timezone.utc)

        total_processed = 0
        total_quarantined = 0
        total_duplicates = 0
        total_fetched = 0

        callback = process_callback or process_and_upsert_event

        for country in CONFLICT_ZONES:
            events = []
            attempt = 0

            while attempt < self.max_retries and not events:
                try:
                    start_time = end_time - timedelta(days=lookback_days)
                    events = self.fetch_events(
                        start_time, end_time,
                        country=country,
                        has_fatalities=True,
                        limit=100,
                    )
                    break
                except requests.exceptions.HTTPError as e:
                    attempt += 1
                    if attempt >= self.max_retries:
                        logger.error(f"Max retries for {country}: {e}")
                        break
                    time.sleep(self._calculate_backoff(attempt))
                except Exception as e:
                    attempt += 1
                    if attempt >= self.max_retries:
                        logger.error(f"Max retries for {country}: {e}")
                        break
                    time.sleep(self._calculate_backoff(attempt))

            zone_processed = 0
            zone_quarantined = 0
            zone_duplicates = 0

            for raw_event in events:
                try:
                    event = normalize_gdelt_event(raw_event)
                    validation = validate_event(event)

                    if not validation.is_valid:
                        insert_quarantine(
                            session=db_session,
                            source="gdelt",
                            raw_payload=raw_event,
                            rejection_code=validation.rejection_code,
                            rejection_detail=validation.rejection_detail,
                        )
                        zone_quarantined += 1
                        continue

                    result = callback(db_session, event)
                    if result.get("duplicate"):
                        zone_duplicates += 1
                    else:
                        zone_processed += 1

                except Exception as e:
                    logger.error(f"Error processing GDELT event in {country}: {e}")
                    zone_quarantined += 1

            logger.info(f"{country}: {zone_processed} processed, {zone_duplicates} duplicates")
            total_processed += zone_processed
            total_quarantined += zone_quarantined
            total_duplicates += zone_duplicates
            total_fetched += len(events)

        return {
            "processed": total_processed,
            "quarantined": total_quarantined,
            "duplicates": total_duplicates,
            "total_fetched": total_fetched,
        }


def run_polling():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
    Session = sessionmaker(bind=engine)

    ingestor = GDELTCloudIngestor()

    while True:
        session = Session()
        try:
            result = ingestor.run(session)
            logger.info(f"GDELT Cloud poll result: {result}")
        except Exception as e:
            logger.error(f"GDELT polling failed: {e}")
        finally:
            session.close()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_polling()
