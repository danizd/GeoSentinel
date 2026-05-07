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

GDELT_BASE_URL = "https://api.gdeltcloud.com/v2/"
POLL_INTERVAL_SECONDS = 300

DEFAULT_BACKOFF_BASE = 2
DEFAULT_BACKOFF_MAX = 60
DEFAULT_MAX_RETRIES = 5


class GDELTIngestor:
    """Ingestor para GDELT Cloud Events v2 (F-ING-GDELT).

    Realiza pull polling cada 5 minutos filtrando por event_family=conflict.
    Autenticacion mediante header X-API-Key (variable GDELT_API_KEY).
    Source independence class: media_derived (factor de confianza x0.5).
    """

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
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http_session.mount("https://", adapter)
        http_session.mount("http://", adapter)
        return http_session

    def _build_params(self, start_time: datetime, end_time: datetime) -> dict[str, Any]:
        return {
            "event_family": "conflict",
            "start_date": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_date": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "format": "json",
        }

    def fetch_events(self, start_time: datetime, end_time: datetime) -> list[dict[str, Any]]:
        """Descarga eventos de conflicto del periodo indicado desde GDELT Cloud v2.

        Args:
            start_time: Inicio del intervalo UTC.
            end_time: Fin del intervalo UTC.

        Returns:
            Lista de eventos en formato GDELT.

        Raises:
            requests.exceptions.HTTPError: En errores HTTP no recuperables.
            requests.exceptions.Timeout: Si la solicitud supera el timeout.
        """
        params = self._build_params(start_time, end_time)
        headers = {"X-API-Key": self.api_key}

        logger.info(f"Fetching GDELT events {start_time.isoformat()} -> {end_time.isoformat()}")

        try:
            response = self.session.get(GDELT_BASE_URL, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("events", data) if isinstance(data, dict) else data
        except requests.exceptions.Timeout:
            logger.error("GDELT request timeout")
            raise
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                logger.warning(f"GDELT rate limited (429), Retry-After={retry_after}s")
                raise
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

    def run(self, db_session, process_callback=None) -> dict[str, Any]:
        """Ejecuta un ciclo de polling: descarga, valida y persiste eventos GDELT.

        Args:
            db_session: Sesion SQLAlchemy activa.
            process_callback: Funcion alternativa a process_and_upsert_event (tests).

        Returns:
            Diccionario con contadores: processed, quarantined, duplicates, total_fetched.
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=5)

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


def run_polling():
    """Bucle principal de polling GDELT. Ejecutar como proceso independiente."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
    Session = sessionmaker(bind=engine)

    ingestor = GDELTIngestor()

    while True:
        session = Session()
        try:
            result = ingestor.run(session)
            logger.info(f"GDELT poll result: {result}")
        except Exception as e:
            logger.error(f"GDELT polling failed: {e}")
        finally:
            session.close()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_polling()
