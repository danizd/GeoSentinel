from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.ingestors.military_ingestor import MilitaryIngestor
from services.military_relay.military_filter import (
    is_callsign_military,
    is_hex_military,
    is_military,
    normalize_hex,
    reload_military_hex_cache,
)


class TestMilitaryFilter:
    def setup_method(self):
        reload_military_hex_cache()

    def test_callsign_prefix_full_match(self):
        assert is_callsign_military("RCH123") is True
        assert is_callsign_military("REACH456") is True
        assert is_callsign_military("MOOSE789") is True
        assert is_callsign_military("EVAC001") is True
        assert is_callsign_military("DUSTOFF") is True
        assert is_callsign_military("AWACS101") is True
        assert is_callsign_military("NAVY123") is True
        assert is_callsign_military("USAF456") is True
        assert is_callsign_military("USN789") is True

    def test_callsign_prefix_short_with_digits(self):
        assert is_callsign_military("AE123") is True
        assert is_callsign_military("RF456") is True
        assert is_callsign_military("TF789") is True
        assert is_callsign_military("PAT001") is True
        assert is_callsign_military("SAM101") is True

    def test_callsign_prefix_short_without_digits_rejected(self):
        assert is_callsign_military("AE") is False
        assert is_callsign_military("RF") is False
        assert is_callsign_military("TF") is False
        assert is_callsign_military("PAT") is False
        assert is_callsign_military("SAM") is False
        assert is_callsign_military("OPS") is False

    def test_callsign_non_military(self):
        assert is_callsign_military("BAW123") is False
        assert is_callsign_military("UAL456") is False
        assert is_callsign_military("DLH789") is False
        assert is_callsign_military("AFL") is False

    def test_hex_in_military_list(self):
        assert is_hex_military("AE01F2") is True
        assert is_hex_military("AE1498") is True
        assert is_hex_military("C00003") is True
        assert is_hex_military("E4E6E6") is True

    def test_hex_outside_military_list(self):
        assert is_hex_military("ABCDEF") is False
        assert is_hex_military("123456") is False
        assert is_hex_military("FFFFFF") is False

    def test_hex_lowercase_normalized(self):
        assert is_hex_military("ae01f2") is True
        assert is_hex_military("ae1498") is True
        assert normalize_hex("ae01f2") == "AE01F2"
        assert normalize_hex("AE01F2") == "AE01F2"
        assert normalize_hex("Ae01F2") == "AE01F2"
        assert normalize_hex(None) is None
        assert normalize_hex("") is None

    def test_military_combined_hex_plus_callsign(self):
        assert is_military("AE01F2", "RCH123") is True
        assert is_military("ABCDEF", "RCH123") is True
        assert is_military("AE01F2", "BAW123") is True

    def test_military_hex_only(self):
        assert is_military("AE01F2", None) is True
        assert is_military("AE01F2", "") is True


class TestMilitaryIngestorDeduplication:
    def test_event_id_60s_bucket(self):
        ingestor = MilitaryIngestor()

        ts1 = "2026-05-13T10:30:25+00:00"
        ts2 = "2026-05-13T10:30:45+00:00"
        ts3 = "2026-05-13T10:31:15+00:00"

        id1 = ingestor.military_event_id("AE01F2", ts1)
        id2 = ingestor.military_event_id("AE01F2", ts2)
        id3 = ingestor.military_event_id("AE01F2", ts3)

        assert id1 == id2
        assert id1.split(":")[1] == id2.split(":")[1]
        assert int(id3.split(":")[1]) - int(id1.split(":")[1]) == 60

    def test_deduplication_same_hex_different_calls(self):
        ingestor = MilitaryIngestor()

        ts = "2026-05-13T10:30:25+00:00"

        id1 = ingestor.military_event_id("AE01F2", ts)
        id2 = ingestor.military_event_id("AE01F2", ts)

        assert id1 == id2


class TestMilitaryIngestorFallback:
    @patch("backend.ingestors.military_ingestor.requests.Session.get")
    def test_relay_returns_stale_header(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "flights": [
                {
                    "id": "AE01F2:1747127400",
                    "callsign": "RCH123",
                    "hexCode": "AE01F2",
                    "location": {"latitude": 40.0, "longitude": -3.0},
                    "altitude": 35000,
                    "heading": 270,
                    "speed": 450,
                    "lastSeenAt": "2026-05-13T10:30:00+00:00",
                }
            ],
            "clusters": [],
        }
        mock_response.headers = {"X-Stale": "true"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        ingestor = MilitaryIngestor(relay_url="http://localhost:8000")
        result = ingestor.fetch_from_relay(45.0, 10.0, 35.0, -5.0)

        assert result.get("_is_stale") is True
        assert len(result["flights"]) == 1

    @patch("backend.ingestors.military_ingestor.requests.Session.get")
    def test_relay_failure_returns_empty(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        ingestor = MilitaryIngestor(relay_url="http://localhost:8000")

        with pytest.raises(requests.exceptions.ConnectionError):
            ingestor.fetch_from_relay(45.0, 10.0, 35.0, -5.0)


class TestMilitaryIngestorAnomaly:
    def test_proximity_check_returns_true_for_nearby_incident(self):
        mock_session = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 1

        mock_session.execute.return_value = mock_result

        ingestor = MilitaryIngestor()
        result = ingestor.check_incident_proximity(mock_session, 40.0, -3.0)

        assert result is True
        mock_session.execute.assert_called_once()

    def test_proximity_check_returns_false_for_no_incident(self):
        mock_session = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 0

        mock_session.execute.return_value = mock_result

        ingestor = MilitaryIngestor()
        result = ingestor.check_incident_proximity(mock_session, 40.0, -3.0)

        assert result is False

    def test_cluster_check_true_for_enough_aircraft(self):
        flights = [
            {"location": {"latitude": 40.0, "longitude": -3.0}},
            {"location": {"latitude": 40.1, "longitude": -3.1}},
            {"location": {"latitude": 40.05, "longitude": -3.05}},
            {"location": {"latitude": 35.0, "longitude": -8.0}},
        ]

        ingestor = MilitaryIngestor()
        result = ingestor.check_cluster(flights, 40.0, -3.0)

        assert result is True

    def test_cluster_check_false_for_insufficient_aircraft(self):
        flights = [
            {"location": {"latitude": 40.0, "longitude": -3.0}},
            {"location": {"latitude": 35.0, "longitude": -8.0}},
        ]

        ingestor = MilitaryIngestor()
        result = ingestor.check_cluster(flights, 40.0, -3.0)

        assert result is False


class TestMilitaryIngestorMapping:
    def test_map_to_canonical_basic_fields(self):
        flight = {
            "hexCode": "AE01F2",
            "callsign": "RCH123",
            "location": {"latitude": 40.0, "longitude": -3.0},
            "altitude": 35000,
            "heading": 270,
            "speed": 450,
            "lastSeenAt": "2026-05-13T10:30:00+00:00",
            "operator": "USAF",
            "operatorCountry": "US",
            "aircraftType": "C130",
            "isInteresting": False,
            "confidence": 8.5,
        }

        ingestor = MilitaryIngestor()
        event = ingestor.map_to_canonical(flight, is_stale=False)

        assert event.event_id_source.startswith("AE01F2:")
        assert event.source == "military"
        assert event.event_type == "military_flight"
        assert event.category.value == "mobility"
        assert event.latitude == 40.0
        assert event.longitude == -3.0
        assert event.confidence == 8.5
        assert event.actors[0].role == "military_aircraft"
        assert event.actors[0].name == "RCH123"

    def test_map_to_canonical_adds_stale_ref(self):
        flight = {
            "hexCode": "AE01F2",
            "callsign": "RCH123",
            "location": {"latitude": 40.0, "longitude": -3.0},
            "altitude": 35000,
            "heading": 270,
            "speed": 450,
            "lastSeenAt": "2026-05-13T10:30:00+00:00",
        }

        ingestor = MilitaryIngestor()
        event = ingestor.map_to_canonical(flight, is_stale=True)

        assert "stale_cache" in event.source_refs

    def test_map_to_canonical_severity_increases_with_interesting(self):
        flight = {
            "hexCode": "AE01F2",
            "callsign": "RCH123",
            "location": {"latitude": 40.0, "longitude": -3.0},
            "altitude": 35000,
            "heading": 270,
            "speed": 450,
            "lastSeenAt": "2026-05-13T10:30:00+00:00",
            "isInteresting": True,
        }

        ingestor = MilitaryIngestor()
        event = ingestor.map_to_canonical(flight, is_stale=False)

        assert event.severity >= 6.0


class TestMilitaryIngestorBackoff:
    def test_backoff_calculation(self):
        ingestor = MilitaryIngestor(backoff_base=2, backoff_max=60)

        assert ingestor._calculate_backoff(1) == 2
        assert ingestor._calculate_backoff(2) == 4
        assert ingestor._calculate_backoff(3) == 8
        assert ingestor._calculate_backoff(10) == 60


class TestMilitaryIngestorRun:
    @patch("backend.ingestors.military_ingestor.MilitaryIngestor.get_active_aois")
    @patch("backend.ingestors.military_ingestor.MilitaryIngestor.fetch_from_relay")
    @patch("backend.ingestors.military_ingestor.MilitaryIngestor.check_incident_proximity")
    @patch("backend.ingestors.military_ingestor.MilitaryIngestor.check_cluster")
    @patch("backend.ingestors.military_ingestor.validate_event")
    @patch("backend.ingestors.military_ingestor.insert_quarantine")
    def test_run_processes_flights(
        self,
        mock_quarantine,
        mock_validate,
        mock_cluster,
        mock_proximity,
        mock_fetch,
        mock_aois,
    ):
        mock_aois.return_value = [
            {"aoi_id": "123", "name": "TestAOI", "max_lat": 45.0, "max_lon": 10.0, "min_lat": 35.0, "min_lon": -5.0}
        ]
        mock_fetch.return_value = {
            "flights": [
                {
                    "hexCode": "AE01F2",
                    "callsign": "RCH123",
                    "location": {"latitude": 40.0, "longitude": -3.0},
                    "altitude": 35000,
                    "heading": 270,
                    "speed": 450,
                    "lastSeenAt": "2026-05-13T10:30:00+00:00",
                    "isInteresting": False,
                }
            ],
            "clusters": [],
            "_is_stale": False,
        }
        mock_proximity.return_value = False
        mock_cluster.return_value = False

        from backend.schemas.events import EventCanonicalCreate
        mock_validate.return_value = MagicMock(
            is_valid=True,
            event=EventCanonicalCreate(
                event_id_source="test",
                source="military",
                event_time=datetime.now(timezone.utc),
                event_type="military_flight",
                category="mobility",
                latitude=40.0,
                longitude=-3.0,
                severity=3.0,
                confidence=8.0,
            )
        )

        mock_db_session = MagicMock()
        mock_process = MagicMock(return_value={"duplicate": False})

        ingestor = MilitaryIngestor()
        result = ingestor.run(mock_db_session, process_callback=mock_process)

        assert result["processed"] == 1
        assert result["quarantined"] == 0

    @patch("backend.ingestors.military_ingestor.MilitaryIngestor.get_active_aois")
    @patch("backend.ingestors.military_ingestor.MilitaryIngestor.fetch_from_relay")
    @patch("backend.ingestors.military_ingestor.validate_event")
    @patch("backend.ingestors.military_ingestor.insert_quarantine")
    def test_run_no_active_aois(
        self,
        mock_quarantine,
        mock_validate,
        mock_fetch,
        mock_aois,
    ):
        mock_aois.return_value = []

        mock_db_session = MagicMock()

        ingestor = MilitaryIngestor()
        result = ingestor.run(mock_db_session)

        assert result["processed"] == 0
        assert result["total_fetched"] == 0
        mock_fetch.assert_not_called()