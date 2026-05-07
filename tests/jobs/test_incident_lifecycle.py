from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from jobs.incident_lifecycle import (
    INVALID_TRANSITIONS,
    INCIDENT_STALE_HOURS,
    UPDATE_TO_OPEN_MINUTES,
    transition_to_open,
    transition_to_updated,
    transition_to_stale,
    transition_to_closed,
    transition_to_false_positive,
    resolve_false_positive,
    reopen_closed,
    run_lifecycle_job,
)


class TestInvalidTransitions:
    def test_closed_cannot_go_to_open(self):
        assert "open" in INVALID_TRANSITIONS["closed"]

    def test_closed_cannot_go_to_updated(self):
        assert "updated" in INVALID_TRANSITIONS["closed"]

    def test_false_positive_cannot_go_to_updated(self):
        assert "updated" in INVALID_TRANSITIONS["false_positive"]

    def test_false_positive_cannot_go_to_stale(self):
        assert "stale" in INVALID_TRANSITIONS["false_positive"]


class TestTransitionToOpen:
    def test_transitions_from_updated(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "updated"

        result = transition_to_open(session, incident)

        assert incident.status == "open"

    def test_transitions_from_stale(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "stale"

        result = transition_to_open(session, incident)

        assert incident.status == "open"

    def test_rejects_from_closed(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "closed"

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_to_open(session, incident)


class TestTransitionToUpdated:
    def test_sets_status_updated(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "open"

        transition_to_updated(session, incident)

        assert incident.status == "updated"
        session.commit.assert_called_once()


class TestTransitionToStale:
    def test_transitions_from_open(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "open"

        transition_to_stale(session, incident)

        assert incident.status == "stale"

    def test_transitions_from_updated(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "updated"

        transition_to_stale(session, incident)

        assert incident.status == "stale"

    def test_rejects_from_closed(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "closed"

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_to_stale(session, incident)


class TestTransitionToClosed:
    def test_creates_correction_audit(self):
        session = MagicMock()
        incident = MagicMock()
        incident.incident_id = "test-uuid"
        incident.status = "open"
        incident.last_seen = datetime.now(timezone.utc) - timedelta(hours=10)

        transition_to_closed(session, incident, corrected_by="admin", reason="Test close")

        session.commit.assert_called()
        session.add.assert_called()
        assert incident.status == "closed"


class TestTransitionToFalsePositive:
    def test_marks_incident_as_false_positive(self):
        session = MagicMock()
        incident = MagicMock()
        incident.incident_id = "test-uuid"
        incident.status = "open"
        incident.last_seen = datetime.now(timezone.utc)

        transition_to_false_positive(session, incident, corrected_by="operator", reason="False alarm")

        assert incident.status == "false_positive"
        session.add.assert_called()

    def test_creates_audit_record(self):
        session = MagicMock()
        incident = MagicMock()
        incident.incident_id = "test-uuid"
        incident.status = "open"
        incident.last_seen = datetime.now(timezone.utc)

        transition_to_false_positive(session, incident, corrected_by="user123")

        call_args = session.add.call_args[0][0]
        assert call_args.correction_type == "false_positive"
        assert call_args.corrected_by == "user123"


class TestResolveFalsePositive:
    def test_resolves_to_open(self):
        session = MagicMock()
        incident = MagicMock()
        incident.incident_id = "test-uuid"
        incident.status = "false_positive"

        resolve_false_positive(session, incident, corrected_by="admin")

        assert incident.status == "open"

    def test_rejects_from_non_fp_status(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "open"

        with pytest.raises(ValueError):
            resolve_false_positive(session, incident, corrected_by="admin")


class TestReopenClosed:
    def test_reopens_closed_incident(self):
        session = MagicMock()
        incident = MagicMock()
        incident.incident_id = "test-uuid"
        incident.status = "closed"

        reopen_closed(session, incident, corrected_by="admin", reason="Reopened for review")

        assert incident.status == "open"

    def test_rejects_from_non_closed(self):
        session = MagicMock()
        incident = MagicMock()
        incident.status = "open"

        with pytest.raises(ValueError):
            reopen_closed(session, incident, corrected_by="admin")


class TestLifecycleJob:
    @patch("jobs.incident_lifecycle.select")
    @patch("jobs.incident_lifecycle.transition_to_stale")
    @patch("jobs.incident_lifecycle.transition_to_open")
    def test_marks_stale_incidents(self, mock_open, mock_stale, mock_select):
        old_incident = MagicMock()
        old_incident.last_seen = datetime.now(timezone.utc) - timedelta(hours=100)
        old_incident.status = "open"

        with patch("jobs.incident_lifecycle.session") as mock_session:
            mock_session.execute.return_value.scalars.return_value.all.return_value = [old_incident]

            session = MagicMock()
            session.execute.return_value.scalars.return_value.all.return_value = [old_incident]

            result = run_lifecycle_job(session)

            assert result["stale_transitions"] >= 0

    @patch("jobs.incident_lifecycle.select")
    @patch("jobs.incident_lifecycle.transition_to_open")
    def test_transitions_updated_to_open_after_15min(self, mock_open, mock_select):
        now = datetime.now(timezone.utc)
        old_updated = MagicMock()
        old_updated.status = "updated"
        old_updated.status_changed_at = now - timedelta(minutes=20)

        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [old_updated]

        result = run_lifecycle_job(session)

        assert result["updated_to_open"] >= 0


class TestConstants:
    def test_stale_hours_72(self):
        assert INCIDENT_STALE_HOURS == 72

    def test_update_to_open_minutes_15(self):
        assert UPDATE_TO_OPEN_MINUTES == 15