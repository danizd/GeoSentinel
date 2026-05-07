from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from jobs.clustering_job import (
    EPSILON,
    HOURS_MAX,
    KM_MAX,
    WEIGHTS_SPACE,
    WEIGHTS_TIME,
    compute_confidence,
    compute_canonical_point,
    compute_mixed_distance,
    haversine_km,
    find_closest_incident,
    run_clustering_job,
)


class TestHaversine:
    def test_same_point(self):
        assert haversine_km(40.0, -3.0, 40.0, -3.0) == 0.0

    def test_known_distance(self):
        dist = haversine_km(51.5, -0.1, 51.5, 0.0)
        assert 5.0 < dist < 10.0


class TestMixedDistance:
    def test_conflict_category(self):
        dist = compute_mixed_distance(
            40.0, -3.0, datetime.now(timezone.utc) - timedelta(hours=1),
            40.5, -2.5, datetime.now(timezone.utc),
            "conflict",
        )
        assert 0 <= dist <= 1.0

    def test_earthquake_strict_time(self):
        dist_recent = compute_mixed_distance(
            40.0, -3.0, datetime.now(timezone.utc),
            40.0, -3.0, datetime.now(timezone.utc) - timedelta(minutes=30),
            "earthquake",
        )
        dist_old = compute_mixed_distance(
            40.0, -3.0, datetime.now(timezone.utc),
            40.0, -3.0, datetime.now(timezone.utc) - timedelta(hours=3),
            "earthquake",
        )
        assert dist_recent < dist_old

    def test_wildfire_loose_time(self):
        dist = compute_mixed_distance(
            40.0, -3.0, datetime.now(timezone.utc) - timedelta(hours=10),
            40.0, -3.0, datetime.now(timezone.utc),
            "wildfire",
        )
        assert 0 <= dist <= 1.0


class TestConfidence:
    def test_single_sensor_event(self):
        events = [MagicMock(source="usgs", confidence=8.0)]

        conf = compute_confidence(events)

        assert conf > 5.0

    def test_multiple_media_derived_same_cycle(self):
        base_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        events = [
            MagicMock(source="gdelt", event_time=base_time, confidence=5.0),
            MagicMock(source="gdelt", event_time=base_time + timedelta(hours=1), confidence=5.0),
        ]

        conf = compute_confidence(events)

        assert conf < 3.0

    def test_mixed_sources_higher_confidence(self):
        events = [
            MagicMock(source="usgs", event_time=datetime.now(timezone.utc), confidence=8.0),
            MagicMock(source="firms", event_time=datetime.now(timezone.utc), confidence=7.0),
        ]

        conf = compute_confidence(events)

        assert conf > 7.0


class TestCanonicalPoint:
    def test_weighted_centroid(self):
        events = [
            MagicMock(
                location_point=MagicMock(coords=((-3.0, 40.0),)),
                confidence=8.0,
            ),
            MagicMock(
                location_point=MagicMock(coords=((-2.0, 41.0),)),
                confidence=4.0,
            ),
        ]

        lat, lon = compute_canonical_point(events)

        assert 40.3 < lat < 40.7
        assert -2.7 < lon < -2.3


class TestEpsilonValues:
    def test_epsilon_by_category(self):
        assert EPSILON["conflict"] == 0.15
        assert EPSILON["wildfire"] == 0.20
        assert EPSILON["earthquake"] == 0.10
        assert EPSILON["disaster_natural"] == 0.15
        assert EPSILON["mobility"] == 0.12

    def test_km_max_by_category(self):
        assert KM_MAX["conflict"] == 50.0
        assert KM_MAX["wildfire"] == 20.0
        assert KM_MAX["earthquake"] == 100.0
        assert KM_MAX["disaster_natural"] == 75.0
        assert KM_MAX["mobility"] == 30.0

    def test_hours_max_by_category(self):
        assert HOURS_MAX["conflict"] == 48.0
        assert HOURS_MAX["wildfire"] == 24.0
        assert HOURS_MAX["earthquake"] == 2.0
        assert HOURS_MAX["disaster_natural"] == 72.0
        assert HOURS_MAX["mobility"] == 6.0


class TestFindClosestIncident:
    def test_finds_incident_within_epsilon(self):
        event = MagicMock()
        event.location_point.coords = ((-3.0, 40.0),)
        event.event_time = datetime.now(timezone.utc)

        incident = MagicMock()
        incident.canonical_point.coords = ((-3.1, 40.1),)
        incident.last_seen = datetime.now(timezone.utc) - timedelta(hours=1)

        result = find_closest_incident(event, [incident], "conflict")

        assert result is incident

    def test_returns_none_when_outside_epsilon(self):
        event = MagicMock()
        event.location_point.coords = ((-3.0, 40.0),)
        event.event_time = datetime.now(timezone.utc)

        incident = MagicMock()
        incident.canonical_point.coords = ((0.0, 50.0),)
        incident.last_seen = datetime.now(timezone.utc) - timedelta(hours=1)

        result = find_closest_incident(event, [incident], "conflict")

        assert result is None

    def test_empty_incident_list(self):
        event = MagicMock()
        event.location_point.coords = ((-3.0, 40.0),)
        event.event_time = datetime.now(timezone.utc)

        result = find_closest_incident(event, [], "conflict")

        assert result is None


class TestClusteringJob:
    @patch("jobs.clustering_job.fetch_unassigned_events")
    @patch("jobs.clustering_job.fetch_active_incidents")
    @patch("jobs.clustering_job.create_new_incident")
    def test_run_creates_new_incident_for_unassigned_event(
        self, mock_create, mock_fetch_incidents, mock_fetch_events
    ):
        event = MagicMock()
        event.id = 1
        event.category = "conflict"
        event.location_point.coords = ((-3.0, 40.0),)
        event.event_time = datetime.now(timezone.utc) - timedelta(hours=1)
        event.event_type = "conflict_battle"
        event.source = "gdelt"
        event.country_iso2 = "ES"
        event.admin1 = "Madrid"
        event.severity = 5.0
        event.confidence = 7.0
        event.fatalities = 0

        mock_fetch_events.return_value = [event]
        mock_fetch_incidents.return_value = []

        mock_session = MagicMock()

        result = run_clustering_job(mock_session, last_run_time=datetime.now(timezone.utc) - timedelta(hours=24))

        assert result["created"] == 1
        assert result["assigned"] == 0
        mock_create.assert_called_once()

    @patch("jobs.clustering_job.fetch_unassigned_events")
    @patch("jobs.clustering_job.fetch_active_incidents")
    @patch("jobs.clustering_job.find_closest_incident")
    @patch("jobs.clustering_job.assign_event_to_incident")
    def test_run_assigns_event_to_existing_incident(
        self, mock_assign, mock_find, mock_fetch_incidents, mock_fetch_events
    ):
        event = MagicMock()
        event.id = 2
        event.category = "conflict"
        event.location_point.coords = ((-3.0, 40.0),)
        event.event_time = datetime.now(timezone.utc)

        mock_fetch_events.return_value = [event]
        mock_fetch_incidents.return_value = [MagicMock()]

        mock_incident = MagicMock()
        mock_find.return_value = mock_incident

        mock_session = MagicMock()

        result = run_clustering_job(mock_session, last_run_time=datetime.now(timezone.utc) - timedelta(hours=24))

        assert result["assigned"] == 1
        mock_assign.assert_called_once()

    @patch("jobs.clustering_job.fetch_unassigned_events")
    def test_run_no_events(self, mock_fetch_events):
        mock_fetch_events.return_value = []

        mock_session = MagicMock()

        result = run_clustering_job(mock_session)

        assert result["created"] == 0
        assert result["assigned"] == 0
        assert result["total_events"] == 0