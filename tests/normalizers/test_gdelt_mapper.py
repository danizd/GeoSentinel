from datetime import timezone

import pytest

from normalizers.gdelt_mapper import (
    _derive_canonical_category,
    _map_category,
    _match_title_keywords,
    _normalize_severity,
    normalize_gdelt_event,
)
from schemas.events import CategoryEnum


def make_gdelt_event(
    event_id: str = "gdelt_001",
    category: str = "BATTLES",
    subcategory: str = "",
    title: str = "Armed forces clash near border",
    lat: float = 48.0,
    lon: float = 37.0,
    goldstein: float = -8.0,
    has_fatalities: bool = True,
    fatalities: int = 5,
    event_date: str = "2024-01-15",
) -> dict:
    return {
        "id": event_id,
        "event_date": event_date,
        "category": category,
        "subcategory": subcategory,
        "title": title,
        "geo": {"lat": lat, "lon": lon},
        "metrics": {"goldstein_scale": goldstein, "significance": 7},
        "has_fatalities": has_fatalities,
        "fatalities": fatalities,
        "url": "https://gdeltcloud.com/event/gdelt_001",
        "actors": [],
    }


class TestMapCategory:
    def test_subcategory_takes_priority_over_category(self):
        result = _map_category("PROTESTS", "ARMED_CONFLICT", "peaceful march")
        assert result == "conflict_battle"

    def test_category_used_when_no_subcategory(self):
        result = _map_category("BATTLES", "", None)
        assert result == "conflict_battle"

    def test_protests_category(self):
        result = _map_category("PROTESTS", "", None)
        assert result == "social_protest"

    def test_riots_category(self):
        result = _map_category("RIOTS", "", None)
        assert result == "social_riot"

    def test_explosions_category(self):
        result = _map_category("EXPLOSIONS", "", None)
        assert result == "conflict_explosion"

    def test_terrorism_category(self):
        result = _map_category("TERRORISM", "", None)
        assert result == "conflict_terror"

    def test_unknown_falls_back_to_title_keywords(self):
        result = _map_category("UNKNOWN", "", "Armed clash near border")
        assert result == "conflict_battle"

    def test_unknown_no_title_match_returns_conflict_unknown(self):
        result = _map_category("UNKNOWN", "", None)
        assert result == "conflict_unknown"

    def test_no_category_no_title_returns_conflict_unknown(self):
        result = _map_category(None, None, None)
        assert result == "conflict_unknown"


class TestMatchTitleKeywords:
    def test_false_positive_battle_against_drought(self):
        """'battle against drought' no debe clasificarse como conflict_battle."""
        result = _match_title_keywords("spain's battle against drought")
        assert result is None

    def test_false_positive_political_battle(self):
        """'political battle' no debe clasificarse como conflict_battle."""
        result = _match_title_keywords("political battle over pension reform in madrid")
        assert result is None

    def test_false_positive_strike_action(self):
        """'strike action' (huelga laboral) no debe clasificarse como conflicto armado."""
        result = _match_title_keywords("workers launch strike action over wages")
        assert result is None

    def test_false_positive_culture_clash(self):
        """'culture clash' no debe clasificarse como conflict_battle."""
        result = _match_title_keywords("culture clash in european capitals")
        assert result is None

    def test_false_positive_firefighting(self):
        """'firefighting' no debe clasificarse como conflict_battle."""
        result = _match_title_keywords("firefighting teams deployed to forest fire")
        assert result is None

    def test_true_positive_armed_clash(self):
        result = _match_title_keywords("armed clash near border kills 3")
        assert result == "conflict_battle"

    def test_true_positive_armed_battle(self):
        result = _match_title_keywords("armed battle erupts in eastern region")
        assert result == "conflict_battle"

    def test_true_positive_airstrike(self):
        result = _match_title_keywords("airstrike kills dozens in northern city")
        assert result == "conflict_airstrike"

    def test_true_positive_drone_strike(self):
        result = _match_title_keywords("drone strike targets military convoy")
        assert result == "conflict_airstrike"

    def test_true_positive_terrorist_attack(self):
        result = _match_title_keywords("terrorist attack on market kills 10")
        assert result == "conflict_terror"

    def test_true_positive_massacre(self):
        result = _match_title_keywords("massacre of civilians reported in village")
        assert result == "conflict_atrocity"

    def test_returns_none_for_empty_string(self):
        result = _match_title_keywords("")
        assert result is None


class TestDeriveCanonicalCategory:
    def test_conflict_battle_derives_conflict(self):
        assert _derive_canonical_category("conflict_battle") == CategoryEnum.CONFLICT

    def test_conflict_explosion_derives_conflict(self):
        assert _derive_canonical_category("conflict_explosion") == CategoryEnum.CONFLICT

    def test_conflict_terror_derives_conflict(self):
        assert _derive_canonical_category("conflict_terror") == CategoryEnum.CONFLICT

    def test_conflict_unknown_derives_conflict(self):
        assert _derive_canonical_category("conflict_unknown") == CategoryEnum.CONFLICT

    def test_social_protest_derives_other(self):
        assert _derive_canonical_category("social_protest") == CategoryEnum.OTHER

    def test_social_riot_derives_other(self):
        assert _derive_canonical_category("social_riot") == CategoryEnum.OTHER

    def test_unknown_type_defaults_to_conflict(self):
        assert _derive_canonical_category("some_unknown_type") == CategoryEnum.CONFLICT


class TestNormalizeSeverity:
    def test_very_negative_goldstein_max_severity(self):
        assert _normalize_severity(-9.0) == 10.0

    def test_goldstein_minus_7_high_severity(self):
        assert _normalize_severity(-7.0) == 8.5

    def test_goldstein_minus_5_medium_high(self):
        assert _normalize_severity(-5.0) == 6.5

    def test_goldstein_minus_3_medium(self):
        assert _normalize_severity(-3.0) == 4.5

    def test_goldstein_minus_1_low(self):
        assert _normalize_severity(-1.0) == 2.5

    def test_goldstein_positive_minimum(self):
        assert _normalize_severity(3.0) == 1.0

    def test_none_goldstein_returns_minimum(self):
        assert _normalize_severity(None) == 1.0


class TestNormalizeGdeltEvent:
    def test_normalize_basic_conflict_event(self):
        raw = make_gdelt_event()
        event = normalize_gdelt_event(raw)

        assert event.source == "gdelt"
        assert event.event_id_source == "gdelt_001"
        assert event.latitude == 48.0
        assert event.longitude == 37.0
        assert event.event_type == "conflict_battle"
        assert event.category == CategoryEnum.CONFLICT
        assert event.event_time.tzinfo == timezone.utc

    def test_normalize_protest_event_gets_other_category(self):
        raw = make_gdelt_event(category="PROTESTS", subcategory="", title="Large protest in city")
        event = normalize_gdelt_event(raw)

        assert event.event_type == "social_protest"
        assert event.category == CategoryEnum.OTHER

    def test_normalize_severity_from_goldstein(self):
        raw = make_gdelt_event(goldstein=-8.5)
        event = normalize_gdelt_event(raw)
        assert event.severity == 10.0

    def test_normalize_fatalities_present(self):
        raw = make_gdelt_event(has_fatalities=True, fatalities=12)
        event = normalize_gdelt_event(raw)
        assert event.fatalities == 12

    def test_normalize_fatalities_absent(self):
        raw = make_gdelt_event(has_fatalities=False, fatalities=0)
        event = normalize_gdelt_event(raw)
        assert event.fatalities is None

    def test_normalize_geo_from_nested_dict(self):
        raw = make_gdelt_event(lat=33.5, lon=44.2)
        event = normalize_gdelt_event(raw)
        assert event.latitude == 33.5
        assert event.longitude == 44.2

    def test_normalize_geo_fallback_flat_fields(self):
        raw = make_gdelt_event()
        raw.pop("geo")
        raw["latitude"] = 10.0
        raw["longitude"] = 20.0
        event = normalize_gdelt_event(raw)
        assert event.latitude == 10.0
        assert event.longitude == 20.0

    def test_normalize_source_refs_include_url(self):
        raw = make_gdelt_event()
        event = normalize_gdelt_event(raw)
        assert any("gdelt_url" in ref for ref in event.source_refs)

    def test_normalize_event_date_utc(self):
        raw = make_gdelt_event(event_date="2024-06-01")
        event = normalize_gdelt_event(raw)
        assert event.event_time.year == 2024
        assert event.event_time.month == 6
        assert event.event_time.day == 1
        assert event.event_time.tzinfo == timezone.utc

    def test_false_positive_political_battle_in_spain(self):
        """Noticia de 'batalla política' en España no debe clasificarse como conflict."""
        raw = make_gdelt_event(
            category="UNKNOWN",
            subcategory="",
            title="Spain's political battle over housing law heats up",
            lat=40.4,
            lon=-3.7,
            goldstein=1.0,
            has_fatalities=False,
            fatalities=0,
        )
        event = normalize_gdelt_event(raw)
        assert event.event_type == "conflict_unknown"
        assert event.category == CategoryEnum.CONFLICT
