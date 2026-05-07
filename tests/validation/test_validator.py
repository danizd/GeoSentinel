from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from schemas.events import EventCanonicalCreate
from validation.validator import (
    REJECTION_CODES,
    insert_quarantine,
    validate_and_quarantine,
    validate_event,
)


def make_event(**overrides) -> EventCanonicalCreate:
    base = {
        "event_id_source": "test_001",
        "source": "gdelt",
        "event_time": datetime.now(timezone.utc) - timedelta(hours=2),
        "event_type": "conflict_battle",
        "category": "conflict",
        "latitude": 40.0,
        "longitude": -3.0,
        "severity": 5.0,
        "confidence": 7.0,
    }
    base.update(overrides)
    return EventCanonicalCreate(**base)


class TestValidateEvent:
    def test_valid_event_passes(self):
        event = make_event()
        result = validate_event(event)
        assert result.is_valid is True
        assert result.rejection_code is None
        assert result.event is not None

    def test_invalid_coords_latitude_above_90(self):
        event = make_event(latitude=91.0)
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "INVALID_COORDS"
        assert "91.0" in result.rejection_detail

    def test_invalid_coords_latitude_below_minus_90(self):
        event = make_event(latitude=-91.0)
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "INVALID_COORDS"
        assert "-91.0" in result.rejection_detail

    def test_invalid_coords_longitude_above_180(self):
        event = make_event(longitude=181.0)
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "INVALID_COORDS"
        assert "181.0" in result.rejection_detail

    def test_invalid_coords_longitude_below_minus_180(self):
        event = make_event(longitude=-181.0)
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "INVALID_COORDS"
        assert "-181.0" in result.rejection_detail

    def test_latitude_at_boundary_positive(self):
        event = make_event(latitude=90.0)
        result = validate_event(event)
        assert result.is_valid is True

    def test_latitude_at_boundary_negative(self):
        event = make_event(latitude=-90.0)
        result = validate_event(event)
        assert result.is_valid is True

    def test_longitude_at_boundary_positive(self):
        event = make_event(longitude=180.0)
        result = validate_event(event)
        assert result.is_valid is True

    def test_longitude_at_boundary_negative(self):
        event = make_event(longitude=-180.0)
        result = validate_event(event)
        assert result.is_valid is True

    def test_future_date_more_than_1_hour(self):
        event = make_event(event_time=datetime.now(timezone.utc) + timedelta(hours=2))
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "FUTURE_DATE"

    def test_future_date_exactly_1_hour(self):
        event = make_event(
            event_time=datetime.now(timezone.utc) + timedelta(hours=1, minutes=0)
        )
        result = validate_event(event)
        assert result.is_valid is False

    def test_future_date_within_1_hour_allowed(self):
        event = make_event(
            event_time=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        result = validate_event(event)
        assert result.is_valid is True

    def test_null_event_type_empty_string(self):
        event = make_event(event_type="")
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "NULL_EVENT_TYPE"

    def test_null_event_type_whitespace_only(self):
        event = make_event(event_type="   ")
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "NULL_EVENT_TYPE"

    def test_null_event_type_none(self):
        event = make_event(event_type=None)
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "NULL_EVENT_TYPE"

    def test_negative_fatalities_below_minus_1(self):
        event = make_event(fatalities=-2)
        result = validate_event(event)
        assert result.is_valid is False
        assert result.rejection_code == "NEGATIVE_FATALITIES"

    def test_fatalities_minus_1_allowed(self):
        event = make_event(fatalities=-1)
        result = validate_event(event)
        assert result.is_valid is True

    def test_fatalities_zero_allowed(self):
        event = make_event(fatalities=0)
        result = validate_event(event)
        assert result.is_valid is True

    def test_fatalities_positive_allowed(self):
        event = make_event(fatalities=10)
        result = validate_event(event)
        assert result.is_valid is True

    def test_fatalities_none_allowed(self):
        event = make_event(fatalities=None)
        result = validate_event(event)
        assert result.is_valid is True


class TestInsertQuarantine:
    @patch("validation.validator.Session")
    def test_insert_quarantine_success(self, mock_session_class):
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        result = insert_quarantine(
            session=mock_session,
            source="gdelt",
            raw_payload={"test": "data"},
            rejection_code="INVALID_COORDS",
            rejection_detail="latitude out of range",
        )

        assert result.success is True
        assert result.quarantine_id is not None
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("validation.validator.Session")
    def test_insert_quarantine_failure(self, mock_session_class):
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.commit.side_effect = Exception("Database error")

        result = insert_quarantine(
            session=mock_session,
            source="gdelt",
            raw_payload={"test": "data"},
            rejection_code="INVALID_COORDS",
        )

        assert result.success is False
        assert result.error is not None
        mock_session.rollback.assert_called_once()


class TestValidateAndQuarantine:
    @patch("validation.validator.insert_quarantine")
    @patch("validation.validator.validate_event")
    def test_valid_event_not_quarantined(self, mock_validate, mock_insert):
        mock_validate.return_value = MagicMock(is_valid=True)

        event = make_event()
        mock_session = MagicMock()

        result = validate_and_quarantine(mock_session, event)

        assert result.is_valid is True
        mock_insert.assert_not_called()

    @patch("validation.validator.insert_quarantine")
    @patch("validation.validator.validate_event")
    def test_invalid_event_quarantined(self, mock_validate, mock_insert):
        mock_validate.return_value = MagicMock(
            is_valid=False,
            rejection_code="INVALID_COORDS",
            rejection_detail="test detail",
        )
        mock_insert.return_value = MagicMock(success=True, quarantine_id=1)

        event = make_event()
        mock_session = MagicMock()

        result = validate_and_quarantine(mock_session, event)

        assert result.is_valid is False
        mock_insert.assert_called_once()


class TestRejectionCodes:
    def test_all_expected_codes_exist(self):
        expected_codes = [
            "INVALID_COORDS",
            "NULL_COORDS",
            "FUTURE_DATE",
            "NULL_EVENT_TYPE",
            "NEGATIVE_FATALITIES",
            "SCHEMA_ERROR",
        ]
        for code in expected_codes:
            assert code in REJECTION_CODES
            assert REJECTION_CODES[code] is not None

    def test_invalid_coords_message(self):
        assert "coordinates" in REJECTION_CODES["INVALID_COORDS"].lower()

    def test_future_date_message(self):
        assert "future" in REJECTION_CODES["FUTURE_DATE"].lower()

    def test_null_event_type_message(self):
        assert "event_type" in REJECTION_CODES["NULL_EVENT_TYPE"].lower()

    def test_negative_fatalities_message(self):
        assert "fatalities" in REJECTION_CODES["NEGATIVE_FATALITIES"].lower()

    def test_schema_error_message(self):
        assert "parse" in REJECTION_CODES["SCHEMA_ERROR"].lower() or "schema" in REJECTION_CODES["SCHEMA_ERROR"].lower()