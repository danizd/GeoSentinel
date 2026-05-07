from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.exceptions import HTTPError, Timeout

from ingestors.usgs_ingestor import USGSIngestor
from normalizers.usgs_mapper import normalize_usgs_event, _normalize_severity


def make_usgs_feature(
    lat: float = 40.0,
    lon: float = -3.0,
    mag: float = 5.5,
    event_time_ms: int | None = None,
    eq_type: str = "earthquake",
    place: str = "Test location",
    eq_id: str = "usgs12345",
) -> dict:
    if event_time_ms is None:
        event_time_ms = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000)

    return {
        "id": eq_id,
        "type": "Feature",
        "properties": {
            "time": event_time_ms,
            "mag": mag,
            "place": place,
            "type": eq_type,
            "ids": f"{eq_id},other123",
            "url": "https://earthquake.usgs.gov/event/us12345",
            "horizontalError": 5.0,
        },
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat, 10.0],
        },
    }


class TestUSGSIngestorFetch:
    @patch("ingestors.usgs_ingestrator.requests.Session.get")
    def test_fetch_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [
                make_usgs_feature(),
                make_usgs_feature(lat=41.0, eq_id="usgs67890"),
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        session = requests.Session()
        mock_get.side_effect = [mock_response]

        with patch("ingestors.usgs_ingestor.USGSIngestor._create_session") as mock_create:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_create.return_value = mock_session

            ingestor = USGSIngestor(session=mock_session)
            result = ingestor.fetch_earthquakes(
                starttime=datetime.now(timezone.utc) - timedelta(minutes=5),
                endtime=datetime.now(timezone.utc),
            )

        assert len(result) == 2

    @patch("ingestors.usgs_ingestor.requests.Session")
    def test_fetch_timeout_raises(self, mock_session_class):
        mock_session = MagicMock()
        mock_session.get.side_effect = Timeout("Connection timeout")
        mock_session_class.return_value = mock_session

        ingestor = USGSIngestor(session=mock_session)

        with pytest.raises(Timeout):
            ingestor.fetch_earthquakes(
                starttime=datetime.now(timezone.utc) - timedelta(minutes=5),
                endtime=datetime.now(timezone.utc),
            )

    @patch("ingestors.usgs_ingestor.requests.Session")
    def test_fetch_429_rate_limit_raises(self, mock_session_class):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)

        mock_session = MagicMock()
        mock_session.get.side_effect = HTTPError(response=mock_response)
        mock_session_class.return_value = mock_session

        ingestor = USGSIngestor(session=mock_session)

        with pytest.raises(HTTPError):
            ingestor.fetch_earthquakes(
                starttime=datetime.now(timezone.utc) - timedelta(minutes=5),
                endtime=datetime.now(timezone.utc),
            )

    @patch("ingestors.usgs_ingestor.requests.Session")
    def test_fetch_timeout_with_retry(self, mock_session_class):
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            Timeout("timeout 1"),
            Timeout("timeout 2"),
            MagicMock(json=lambda: {"features": [make_usgs_feature()]}),
        ]
        mock_session_class.return_value = mock_session

        ingestor = USGSIngestor(session=mock_session, max_retries=3, backoff_base=1)

        result = ingestor.fetch_earthquakes(
            starttime=datetime.now(timezone.utc) - timedelta(minutes=5),
            endtime=datetime.now(timezone.utc),
        )

        assert len(result) == 1

    @patch("ingestors.usgs_ingestor.requests.Session")
    def test_fetch_429_with_retry_success(self, mock_session_class):
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        mock_response = MagicMock()
        mock_response.json.return_value = {"features": [make_usgs_feature()]}

        mock_session = MagicMock()
        mock_session.get.side_effect = [
            HTTPError(response=mock_response_429),
            mock_response,
        ]
        mock_session_class.return_value = mock_session

        ingestor = USGSIngestor(session=mock_session, max_retries=3, backoff_base=1)

        result = ingestor.fetch_earthquakes(
            starttime=datetime.now(timezone.utc) - timedelta(minutes=5),
            endtime=datetime.now(timezone.utc),
        )

        assert len(result) == 1


class TestUSGSMapper:
    def test_normalize_valid_earthquake(self):
        feature = make_usgs_feature(lat=35.0, lon=-120.0, mag=5.8, event_time_ms=1700000000000)

        event = normalize_usgs_event(feature)

        assert event.source == "usgs"
        assert event.event_type == "earthquake"
        assert event.category.value == "disaster_natural"
        assert event.latitude == 35.0
        assert event.longitude == -120.0
        assert event.severity == 6.0
        assert event.confidence == 8.0

    def test_normalize_deduplication_key(self):
        feature = make_usgs_feature(eq_id="usgs12345")

        event = normalize_usgs_event(feature)

        assert event.event_id_source == "usgs12345"

    def test_normalize_coordinates_invalid_lat(self):
        feature = make_usgs_feature(lat=91.0, lon=-120.0)

        event = normalize_usgs_event(feature)

        assert event.latitude == 91.0

    def test_normalize_coordinates_invalid_lon(self):
        feature = make_usgs_feature(lat=40.0, lon=200.0)

        event = normalize_usgs_event(feature)

        assert event.longitude == 200.0

    def test_normalize_future_date(self):
        future_time = int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp() * 1000)
        feature = make_usgs_feature(event_time_ms=future_time)

        event = normalize_usgs_event(feature)

        assert event.event_time > datetime.now(timezone.utc)

    def test_normalize_explosion_type(self):
        feature = make_usgs_feature(eq_type="explosion", place="Test explosion")

        event = normalize_usgs_event(feature)

        assert event.event_type == "explosion_seismic"
        assert event.category.value == "disaster_natural"

    def test_normalize_severity_mappings(self):
        assert _normalize_severity(4.0) == 2.0
        assert _normalize_severity(5.5) == 4.0
        assert _normalize_severity(6.5) == 6.0
        assert _normalize_severity(7.5) == 8.0
        assert _normalize_severity(8.5) == 10.0

    def test_normalize_source_refs_includes_depth(self):
        feature = make_usgs_feature()
        feature["geometry"]["coordinates"][2] = 15.5

        event = normalize_usgs_event(feature)

        assert any("depth" in ref for ref in event.source_refs)

    def test_normalize_source_refs_includes_place(self):
        feature = make_usgs_feature(place="Test Place, Region")

        event = normalize_usgs_event(feature)

        assert "Test Place, Region" in event.source_refs

    def test_normalize_unknown_type(self):
        feature = make_usgs_feature(eq_type="unknown_type")

        event = normalize_usgs_event(feature)

        assert event.event_type == "earthquake"
        assert event.category == "other"


class TestUSGSIngestorBackoff:
    def test_backoff_calculation(self):
        ingestor = USGSIngestor(backoff_base=2, backoff_max=60)

        assert ingestor._calculate_backoff(1) == 2
        assert ingestor._calculate_backoff(2) == 4
        assert ingestor._calculate_backoff(3) == 8
        assert ingestor._calculate_backoff(10) == 60
        assert ingestor._calculate_backoff(100) == 60


class TestUSGSIngestorRun:
    @patch("ingestors.usgs_ingestor.validate_event")
    @patch("ingestors.usgs_ingestor.insert_quarantine")
    @patch("ingestors.usgs_ingestor.USGSIngestor.fetch_earthquakes")
    def test_run_valid_event(self, mock_fetch, mock_quarantine, mock_validate):
        mock_fetch.return_value = [make_usgs_feature()]
        mock_validate.return_value = MagicMock(is_valid=True, event=MagicMock())

        mock_db_session = MagicMock()
        mock_process = MagicMock(return_value={"duplicate": False})

        ingestor = USGSIngestor()
        result = ingestor.run(mock_db_session, process_callback=mock_process)

        assert result["processed"] == 1
        assert result["quarantined"] == 0
        mock_quarantine.assert_not_called()

    @patch("ingestors.usgs_ingestor.validate_event")
    @patch("ingestors.usgs_ingestor.insert_quarantine")
    @patch("ingestors.usgs_ingestor.USGSIngestor.fetch_earthquakes")
    def test_run_invalid_coords_quarantined(self, mock_fetch, mock_quarantine, mock_validate):
        mock_fetch.return_value = [make_usgs_feature(lat=91.0)]
        mock_validate.return_value = MagicMock(
            is_valid=False,
            rejection_code="INVALID_COORDS",
            rejection_detail="latitude out of range",
        )
        mock_quarantine.return_value = MagicMock(success=True)

        mock_db_session = MagicMock()

        ingestor = USGSIngestor()
        result = ingestor.run(mock_db_session)

        assert result["quarantined"] == 1
        mock_quarantine.assert_called_once()

    @patch("ingestors.usgs_ingestor.validate_event")
    @patch("ingestors.usgs_ingestor.insert_quarantine")
    @patch("ingestors.usgs_ingestor.USGSIngestor.fetch_earthquakes")
    def test_run_future_date_quarantined(self, mock_fetch, mock_quarantine, mock_validate):
        future_time = int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp() * 1000)
        mock_fetch.return_value = [make_usgs_feature(event_time_ms=future_time)]
        mock_validate.return_value = MagicMock(
            is_valid=False,
            rejection_code="FUTURE_DATE",
            rejection_detail="event_time is more than 1 hour in the future",
        )
        mock_quarantine.return_value = MagicMock(success=True)

        mock_db_session = MagicMock()

        ingestor = USGSIngestor()
        result = ingestor.run(mock_db_session)

        assert result["quarantined"] == 1
        mock_quarantine.assert_called_once()

    @patch("ingestors.usgs_ingestor.USGSIngestor.fetch_earthquakes")
    def test_run_empty_response(self, mock_fetch):
        mock_fetch.return_value = []

        mock_db_session = MagicMock()

        ingestor = USGSIngestor()
        result = ingestor.run(mock_db_session)

        assert result["processed"] == 0
        assert result["quarantined"] == 0
        assert result["total_fetched"] == 0