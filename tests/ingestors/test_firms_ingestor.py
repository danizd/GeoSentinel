import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from normalizers.firms_mapper import (
    _generate_event_id,
    _normalize_severity,
    _parse_datetime,
    normalize_firms_row,
)
from ingestors.firms_ingestor import FIRMSIngestor


def make_firms_row(
    latitude: float = 40.0,
    longitude: float = -3.0,
    acq_date: str = "2026-05-07",
    acq_time: str = "1400",
    satellite: str = "NPP",
    confidence: str = "high",
    frp: float = 15.0,
    fire_type: int = 0,
    instrument: str = "VIIRS",
) -> dict:
    return {
        "latitude": str(latitude),
        "longitude": str(longitude),
        "acq_date": acq_date,
        "acq_time": acq_time,
        "satellite": satellite,
        "confidence": confidence,
        "frp": str(frp),
        "type": str(fire_type),
        "instrument": instrument,
        "brightness": "310",
    }


class TestFIRMSMapper:
    def test_generate_event_id(self):
        event_id = _generate_event_id(40.0, -3.0, "2026-05-07", "1400", "NPP")
        assert len(event_id) == 32

        same_event = _generate_event_id(40.0, -3.0, "2026-05-07", "1400", "NPP")
        assert event_id == same_event

        different = _generate_event_id(41.0, -3.0, "2026-05-07", "1400", "NPP")
        assert event_id != different

    def test_generate_event_id_deterministic(self):
        key = "40.0|-3.0|2026-05-07|1400|NPP"
        expected = hashlib.sha256(key.encode()).hexdigest()[:32]
        assert _generate_event_id(40.0, -3.0, "2026-05-07", "1400", "NPP") == expected

    def test_parse_datetime(self):
        dt = _parse_datetime("2026-05-07", "1400")
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 7
        assert dt.hour == 14
        assert dt.minute == 0
        assert dt.tzinfo == timezone.utc

    def test_parse_datetime_with_leading_zeros(self):
        dt = _parse_datetime("2026-05-07", "0930")
        assert dt.hour == 9
        assert dt.minute == 30

    def test_normalize_valid_row_wildfire(self):
        row = make_firms_row(latitude=35.0, longitude=-120.0, confidence="high", frp=20.0)

        event = normalize_firms_row(row)

        assert event.source == "firms"
        assert event.event_type == "wildfire_hotspot"
        assert event.category.value == "wildfire"
        assert event.latitude == 35.0
        assert event.longitude == -120.0
        assert event.severity == 5.0
        assert event.confidence == 8.0
        assert event.location_accuracy_km == 0.375

    def test_normalize_valid_row_nominal_confidence(self):
        row = make_firms_row(confidence="nominal", frp=8.0)

        event = normalize_firms_row(row)

        assert event.confidence == 6.0

    def test_normalize_rejects_low_confidence(self):
        row = make_firms_row(confidence="low")

        with pytest.raises(ValueError, match="Confidence"):
            normalize_firms_row(row)

    def test_normalize_rejects_very_low_confidence(self):
        row = make_firms_row(confidence="n/a")

        with pytest.raises(ValueError, match="Confidence"):
            normalize_firms_row(row)

    def test_normalize_volcano_type(self):
        row = make_firms_row(fire_type=1)

        event = normalize_firms_row(row)

        assert event.event_type == "volcanic_hotspot"

    def test_normalize_offshore_type(self):
        row = make_firms_row(fire_type=3)

        event = normalize_firms_row(row)

        assert event.event_type == "offshore_hotspot"

    def test_normalize_other_type(self):
        row = make_firms_row(fire_type=2)

        event = normalize_firms_row(row)

        assert event.event_type == "other_hotspot"

    def test_normalize_severity_frp_mappings(self):
        assert _normalize_severity(0) == 1.0
        assert _normalize_severity(3) == 1.0
        assert _normalize_severity(5) == 2.5
        assert _normalize_severity(10) == 5.0
        assert _normalize_severity(25) == 7.5
        assert _normalize_severity(50) == 10.0
        assert _normalize_severity(100) == 10.0

    def test_normalize_source_refs_includes_satellite(self):
        row = make_firms_row(satellite="Terra", instrument="MODIS")

        event = normalize_firms_row(row)

        assert "satellite: Terra" in event.source_refs
        assert "instrument: MODIS" in event.source_refs
        assert "brightness: 310K" in event.source_refs

    def test_normalize_location_accuracy_viirs(self):
        row = make_firms_row()

        event = normalize_firms_row(row, product="VIIRS_SNPP_NRT")

        assert event.location_accuracy_km == 0.375

    def test_normalize_location_accuracy_modis(self):
        row = make_firms_row()

        event = normalize_firms_row(row, product="MODIS_NRT")

        assert event.location_accuracy_km == 1.0


class TestFIRMSIngestor:
    @patch("ingestors.firms_ingestor.requests.Session")
    def test_fetch_hotspots(self, mock_session_class):
        csv_content = """latitude,longitude,acq_date,acq_time,satellite,confidence,frp,type,instrument,brightness
40.0,-3.0,2026-05-07,1400,NPP,high,15.0,0,VIIRS,310
41.0,-2.0,2026-05-07,1405,NPP,nominal,8.0,0,VIIRS,300"""

        mock_response = MagicMock()
        mock_response.text = csv_content
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        ingestor = FIRMSIngestor(map_key="test_key", session=mock_session)
        result = ingestor.fetch_hotspots(bbox=(-180, -90, 180, 90), days=1)

        assert len(result) == 2

    @patch("ingestors.firms_ingestor.requests.Session")
    def test_fetch_timeout(self, mock_session_class):
        import requests
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.Timeout()
        mock_session_class.return_value = mock_session

        ingestor = FIRMSIngestor(map_key="test_key", session=mock_session)

        with pytest.raises(requests.exceptions.Timeout):
            ingestor.fetch_hotspots(bbox=(-180, -90, 180, 90))

    @patch("ingestors.firms_ingestor.requests.Session")
    def test_fetch_429(self, mock_session_class):
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_session_class.return_value = mock_session

        ingestor = FIRMSIngestor(map_key="test_key", session=mock_session)

        with pytest.raises(requests.exceptions.HTTPError):
            ingestor.fetch_hotspots(bbox=(-180, -90, 180, 90))

    @patch("ingestors.firms_ingestor.validate_event")
    @patch("ingestors.firms_ingestor.insert_quarantine")
    @patch("ingestors.firms_ingestor.FIRMSIngestor.fetch_hotspots")
    def test_run_valid_event(self, mock_fetch, mock_quarantine, mock_validate):
        mock_fetch.return_value = [make_firms_row()]
        mock_validate.return_value = MagicMock(is_valid=True, event=MagicMock())

        mock_db_session = MagicMock()
        mock_process = MagicMock(return_value={"duplicate": False})

        ingestor = FIRMSIngestor(map_key="test_key")
        result = ingestor.run(mock_db_session, process_callback=mock_process)

        assert result["processed"] == 1
        assert result["quarantined"] == 0

    @patch("ingestors.firms_ingestor.validate_event")
    @patch("ingestors.firms_ingestor.insert_quarantine")
    @patch("ingestors.firms_ingestor.FIRMSIngestor.fetch_hotspots")
    def test_run_invalid_coords_quarantined(self, mock_fetch, mock_quarantine, mock_validate):
        row = make_firms_row(latitude=95.0)
        mock_fetch.return_value = [row]
        mock_validate.return_value = MagicMock(
            is_valid=False,
            rejection_code="INVALID_COORDS",
        )
        mock_quarantine.return_value = MagicMock(success=True)

        mock_db_session = MagicMock()

        ingestor = FIRMSIngestor(map_key="test_key")
        result = ingestor.run(mock_db_session)

        assert result["quarantined"] == 1
        mock_quarantine.assert_called_once()

    @patch("ingestors.firms_ingestor.FIRMSIngestor.fetch_hotspots")
    def test_run_filters_low_confidence(self, mock_fetch):
        mock_fetch.return_value = [
            make_firms_row(confidence="high"),
            make_firms_row(confidence="low"),
            make_firms_row(confidence="nominal"),
        ]

        mock_db_session = MagicMock()

        ingestor = FIRMSIngestor(map_key="test_key")
        result = ingestor.run(mock_db_session)

        assert result["skipped_low_confidence"] == 1

    @patch("ingestors.firms_ingestor.FIRMSIngestor.fetch_hotspots")
    def test_run_empty_response(self, mock_fetch):
        mock_fetch.return_value = []

        mock_db_session = MagicMock()

        ingestor = FIRMSIngestor(map_key="test_key")
        result = ingestor.run(mock_db_session)

        assert result["total_fetched"] == 0
        assert result["processed"] == 0

    def test_requires_map_key(self):
        with pytest.raises(ValueError, match="FIRMS_MAP_KEY not provided"):
            FIRMSIngestor(map_key=None)

    def test_build_url(self):
        ingestor = FIRMSIngestor(map_key="test_key", product="VIIRS_SNPP_NRT")
        url = ingestor._build_url((-180, -90, 180, 90), 1)

        assert "firms.modaps.eosdis.nasa.gov" in url
        assert "test_key" in url
        assert "VIIRS_SNPP_NRT" in url
        assert "-180,-90,180,90" in url
        assert "1/" in url

    def test_backoff_calculation(self):
        ingestor = FIRMSIngestor(map_key="test_key", backoff_base=2, backoff_max=60)

        assert ingestor._calculate_backoff(1) == 2
        assert ingestor._calculate_backoff(2) == 4
        assert ingestor._calculate_backoff(3) == 8
        assert ingestor._calculate_backoff(10) == 60