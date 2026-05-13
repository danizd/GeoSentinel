import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.jobs.event_processing import process_and_upsert_event
from backend.normalizers.acled_mapper import normalize_acled_event
from backend.validation.validator import insert_quarantine, validate_event

logger = logging.getLogger(__name__)

ACLED_API_URL = "https://api.acleddata.com/acled/read"
ACLED_TOKEN_URL = "https://acleddata.com/oauth/token"
POLL_INTERVAL_SECONDS = 86400
ACLED_PAGE_SIZE = 500
TOKEN_CACHE_FILE = ".acled_token_cache"

DEFAULT_BACKOFF_BASE = 2
DEFAULT_BACKOFF_MAX = 120
DEFAULT_MAX_RETRIES = 5


class ACLEDIngestor:
    def __init__(
        self,
        session: requests.Session | None = None,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        access_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        page_size: int = ACLED_PAGE_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: int = DEFAULT_BACKOFF_BASE,
        backoff_max: int = DEFAULT_BACKOFF_MAX,
    ):
        self.poll_interval = poll_interval
        self.access_token = access_token or os.getenv("ACLED_ACCESS_TOKEN")
        self.username = username or os.getenv("ACLED_USERNAME")
        self.password = password or os.getenv("ACLED_PASSWORD")
        self.page_size = page_size
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.session = session or self._create_session(max_retries)

        if not self.access_token:
            if not self.username or not self.password:
                raise ValueError("ACLED_ACCESS_TOKEN or ACLED_USERNAME/ACLED_PASSWORD required")
            self.access_token = self._get_token()

    def _create_session(self, max_retries: int) -> requests.Session:
        http_session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http_session.mount("https://", adapter)
        return http_session

    def _get_token(self) -> str:
        logger.info("Obteniendo token ACLED via OAuth2...")
        data = {
            "grant_type": "password",
            "client_id": "acled",
            "username": self.username,
            "password": self.password,
            "scope": "authenticated",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = self.session.post(ACLED_TOKEN_URL, data=data, headers=headers, timeout=60)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("No access_token en respuesta OAuth2")
        logger.info("Token ACLED obtenido correctamente")
        return access_token

    def _build_params(self, since_date: datetime, page: int) -> dict[str, Any]:
        return {
            "event_date": since_date.strftime("%Y-%m-%d"),
            "event_date_where": ">=",
            "limit": self.page_size,
            "page": page,
            "fields": (
                "data_id|event_date|event_type|latitude|longitude|"
                "fatalities|geo_precision|actor1|actor2|admin1|admin2|"
                "country|notes|source|source_url"
            ),
        }

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def fetch_page(self, since_date: datetime, page: int) -> list[dict[str, Any]]:
        params = self._build_params(since_date, page)
        headers = self._get_headers()
        logger.info(f"Fetching ACLED page {page} since {since_date.date()}")

        try:
            response = self.session.get(ACLED_API_URL, params=params, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 401:
                logger.warning("Token expirado, renovando...")
                self.access_token = self._get_token()
                return self.fetch_page(since_date, page)
            if e.response and e.response.status_code == 429:
                logger.warning("ACLED rate limited (429)")
                raise
            logger.error(f"ACLED HTTP error: {e}")
            raise
        except requests.exceptions.Timeout:
            logger.error("ACLED request timeout")
            raise
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"ACLED malformed JSON response: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"ACLED request failed: {e}")
            raise

    def fetch_all_events(self, since_date: datetime) -> list[dict[str, Any]]:
        all_events: list[dict[str, Any]] = []
        page = 1

        while True:
            attempt = 0
            page_events: list[dict[str, Any]] = []

            while attempt < self.max_retries:
                try:
                    page_events = self.fetch_page(since_date, page)
                    break
                except requests.exceptions.HTTPError as e:
                    if e.response and e.response.status_code == 429:
                        attempt += 1
                        if attempt >= self.max_retries:
                            logger.error("Max retries reached for ACLED fetch (rate limited)")
                            raise
                        wait = min(self.backoff_base**attempt, self.backoff_max)
                        logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt})")
                        time.sleep(wait)
                    else:
                        raise
                except requests.exceptions.Timeout:
                    attempt += 1
                    if attempt >= self.max_retries:
                        logger.error("Max retries reached for ACLED fetch (timeout)")
                        raise
                    wait = min(self.backoff_base**attempt, self.backoff_max)
                    logger.warning(f"Timeout, retrying in {wait}s (attempt {attempt})")
                    time.sleep(wait)

            if not page_events:
                break

            all_events.extend(page_events)
            logger.info(f"ACLED page {page}: {len(page_events)} events (total: {len(all_events)})")

            if len(page_events) < self.page_size:
                break

            page += 1

        return all_events

    def run(
        self,
        db_session,
        since_date: datetime | None = None,
        process_callback=None,
    ) -> dict[str, Any]:
        if since_date is None:
            since_date = datetime.now(timezone.utc) - timedelta(hours=48)

        events = self.fetch_all_events(since_date)

        processed = 0
        quarantined = 0
        duplicates = 0

        callback = process_callback or process_and_upsert_event

        for raw_event in events:
            try:
                event = normalize_acled_event(raw_event)
                validation = validate_event(event)

                if not validation.is_valid:
                    insert_quarantine(
                        session=db_session,
                        source="acled",
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
                logger.error(f"Error processing ACLED event: {e}")
                quarantined += 1

        return {
            "processed": processed,
            "quarantined": quarantined,
            "duplicates": duplicates,
            "total_fetched": len(events),
        }


def run_polling():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
    Session = sessionmaker(bind=engine)

    ingestor = ACLEDIngestor()

    while True:
        session = Session()
        try:
            result = ingestor.run(session)
            logger.info(f"ACLED poll result: {result}")
        except Exception as e:
            logger.error(f"ACLED polling failed: {e}")
        finally:
            session.close()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_polling()