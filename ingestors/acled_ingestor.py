import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobs.event_processing import process_and_upsert_event
from normalizers.acled_mapper import normalize_acled_event
from validation.validator import insert_quarantine, validate_event

logger = logging.getLogger(__name__)

ACLED_BASE_URL = "https://api.acleddata.com/acled/read"
POLL_INTERVAL_SECONDS = 86400
ACLED_PAGE_SIZE = 500

DEFAULT_BACKOFF_BASE = 2
DEFAULT_BACKOFF_MAX = 120
DEFAULT_MAX_RETRIES = 5


class ACLEDIngestor:
    """Ingestor para ACLED (F-ING-ACLED).

    Realiza descarga batch diaria con soporte de backfill para detectar
    actualizaciones retroactivas (lag real de 7-28 dias por region).
    Autenticacion mediante query params key + email.
    Source independence class: field_reported (factor de confianza x1.5).

    ACLED puede actualizar registros existentes (ej. corregir fatalities).
    El upsert por (source, event_id_source) maneja esto correctamente.

    Licencia: CC BY-NC 4.0 — solo uso no comercial.
    """

    def __init__(
        self,
        session: requests.Session | None = None,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        api_key: str | None = None,
        api_email: str | None = None,
        page_size: int = ACLED_PAGE_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: int = DEFAULT_BACKOFF_BASE,
        backoff_max: int = DEFAULT_BACKOFF_MAX,
    ):
        self.poll_interval = poll_interval
        self.api_key = api_key or os.getenv("ACLED_API_KEY")
        self.api_email = api_email or os.getenv("ACLED_EMAIL")
        self.page_size = page_size
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.session = session or self._create_session(max_retries)

        if not self.api_key:
            raise ValueError("ACLED_API_KEY not provided")
        if not self.api_email:
            raise ValueError("ACLED_EMAIL not provided")

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

    def _build_params(self, since_date: datetime, page: int) -> dict[str, Any]:
        return {
            "key": self.api_key,
            "email": self.api_email,
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

    def fetch_page(self, since_date: datetime, page: int) -> list[dict[str, Any]]:
        """Descarga una pagina de eventos ACLED desde since_date.

        Args:
            since_date: Fecha minima del evento (>=).
            page: Numero de pagina (1-based).

        Returns:
            Lista de eventos de la pagina solicitada.

        Raises:
            requests.exceptions.HTTPError: En errores HTTP no recuperables.
            requests.exceptions.Timeout: Si la solicitud supera el timeout.
        """
        params = self._build_params(since_date, page)
        logger.info(f"Fetching ACLED page {page} since {since_date.date()}")

        try:
            response = self.session.get(ACLED_BASE_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except requests.exceptions.Timeout:
            logger.error("ACLED request timeout")
            raise
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                logger.warning("ACLED rate limited (429)")
                raise
            logger.error(f"ACLED HTTP error: {e}")
            raise
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"ACLED malformed JSON response: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"ACLED request failed: {e}")
            raise

    def fetch_all_events(self, since_date: datetime) -> list[dict[str, Any]]:
        """Descarga todos los eventos paginando hasta agotar resultados.

        Args:
            since_date: Fecha minima de evento para la descarga.

        Returns:
            Lista completa de eventos del periodo.
        """
        all_events: list[dict[str, Any]] = []
        page = 1

        while True:
            attempt = 0
            page_events: list[dict[str, Any]] = []

            while attempt < self.max_retries:
                try:
                    page_events = self.fetch_page(since_date, page)
                    break
                except requests.exceptions.Timeout:
                    attempt += 1
                    if attempt >= self.max_retries:
                        logger.error("Max retries reached for ACLED fetch (timeout)")
                        raise
                    wait = min(self.backoff_base**attempt, self.backoff_max)
                    logger.warning(f"Timeout, retrying in {wait}s (attempt {attempt})")
                    time.sleep(wait)
                except requests.exceptions.HTTPError as e:
                    if e.response is not None and e.response.status_code == 429:
                        attempt += 1
                        if attempt >= self.max_retries:
                            logger.error("Max retries reached for ACLED fetch (rate limited)")
                            raise
                        wait = min(self.backoff_base**attempt, self.backoff_max)
                        logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt})")
                        time.sleep(wait)
                    else:
                        raise

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
        """Ejecuta la descarga batch, valida y persiste eventos ACLED.

        Por defecto descarga las ultimas 48h para capturar actualizaciones
        retroactivas recientes. Para backfill completo pasar since_date explicito.

        Args:
            db_session: Sesion SQLAlchemy activa.
            since_date: Fecha inicial de backfill. Por defecto: now() - 48h.
            process_callback: Funcion alternativa a process_and_upsert_event (tests).

        Returns:
            Diccionario con contadores: processed, quarantined, duplicates, total_fetched.
        """
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
    """Bucle principal de polling ACLED diario. Ejecutar como proceso independiente."""
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
