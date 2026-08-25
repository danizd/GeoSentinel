from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "backend"
for _p in (str(ROOT), str(BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.api.main import app  # noqa: E402


EVENTS_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": 1,
            "geometry": {"type": "Point", "coordinates": [36.8, 47.9]},
            "properties": {"id": 1, "title": "Ataque con dron", "countryCode": "UKR", "flagImage": "flag-UKR"},
        },
        {
            "type": "Feature",
            "id": 2,
            "geometry": {"type": "Point", "coordinates": [-43.4, -22.7]},
            "properties": {"id": 2, "title": "Operación policial", "countryCode": "BRA", "flagImage": "flag-BRA"},
        },
        {
            "type": "Feature",
            "id": 3,
            "geometry": {"type": "Point", "coordinates": [37.5, 55.7]},
            "properties": {"id": 3, "title": "Bombardeo FAB", "countryCode": "RUS", "flagImage": "flag-RUS"},
        },
        {
            "type": "Feature",
            "id": 4,
            "geometry": {"type": "Point", "coordinates": [-3.7, 40.4]},
            "properties": {"id": 4, "title": "Protesta en Madrid", "countryCode": "ESP", "flagImage": "flag-ESP"},
        },
    ],
}

ROADS_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": 100,
            "geometry": {"type": "LineString", "coordinates": [[36.0, 49.0], [36.5, 49.5]]},
            "properties": {"id": 100, "roadName": "M14", "severity": "CRITICAL", "countryCode": "UKR"},
        },
        {
            "type": "Feature",
            "id": 101,
            "geometry": {"type": "LineString", "coordinates": [[-100.2, 19.9], [-101.5, 19.4]]},
            "properties": {"id": 101, "roadName": "Michoacán", "severity": "CRITICAL", "countryCode": "MEX"},
        },
        {
            "type": "Feature",
            "id": 102,
            "geometry": {"type": "LineString", "coordinates": [[37.3, 55.7], [37.6, 55.9]]},
            "properties": {"id": 102, "roadName": "M9", "severity": "HIGH", "countryCode": "RUS"},
        },
    ],
}

REGIONS_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": 200,
            "geometry": {"type": "Polygon", "coordinates": [[[36.0, 49.0], [36.5, 49.5], [36.2, 49.8], [36.0, 49.0]]]},
            "properties": {"id": 200, "popupTitle": "Óblast de Járkov", "conflictName": "Guerra en Ucrania", "countryCode": "UKR", "fillColor": "#ff0000", "fillOpacity": 0.4},
        },
        {
            "type": "Feature",
            "id": 201,
            "geometry": {"type": "Polygon", "coordinates": [[[36.0, 49.0], [36.5, 49.5], [36.2, 49.8], [36.0, 49.0]]]},
            "properties": {"id": 201, "popupTitle": "Michoacán", "countryCode": "MEX", "fillColor": "#ffd600", "fillOpacity": 0.4},
        },
        {
            "type": "Feature",
            "id": 202,
            "geometry": {"type": "Polygon", "coordinates": [[[36.0, 49.0], [36.5, 49.5], [36.2, 49.8], [36.0, 49.0]]]},
            "properties": {"id": 202, "popupTitle": "Madrid", "countryCode": "ESP", "fillColor": "#00ff00", "fillOpacity": 0.4},
        },
    ],
}

DETAIL_PAYLOAD = {
    "id": 1,
    "title": "Ataque con dron",
    "description": "Descripción traducida",
    "countryCode": "UKR",
    "lat": 47.9,
    "lng": 36.8,
    "confidence": 10,
    "force": {"id": 185, "name": "Ejército de Ucrania", "countryCode": "UKR"},
    "criminalGroup": None,
    "media": [{"id": 23947, "eventId": 1, "publicId": "cr360/g4jxr6vvgmd8ozh4xvbb", "type": "image"}],
    "urlX": "https://x.com/example/status/1",
}


@pytest.fixture
def client():
    from backend.api.routes.cr360 import _cache, _cache_lock

    with _cache_lock:
        _cache.clear()
    return TestClient(app)


def _mock_ok(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


class TestCr360Routes:

    @patch("backend.api.routes.cr360.requests.get")
    def test_events_filtered_by_country(self, mock_get, client):
        mock_get.return_value = _mock_ok(EVENTS_PAYLOAD)
        response = client.get("/v1/cr360/events", params={"countries": "ESP,RUS,UKR"})
        assert response.status_code == 200
        data = response.json()
        codes = {f["properties"]["countryCode"] for f in data["features"]}
        assert codes == {"UKR", "RUS", "ESP"}
        assert "BRA" not in codes

    @patch("backend.api.routes.cr360.requests.get")
    def test_events_cache_avoids_second_upstream_call(self, mock_get, client):
        mock_get.return_value = _mock_ok(EVENTS_PAYLOAD)
        client.get("/v1/cr360/events", params={"countries": "UKR"})
        client.get("/v1/cr360/events", params={"countries": "UKR,RUS"})
        assert mock_get.call_count == 1

    def test_events_invalid_countries_returns_422(self, client):
        response = client.get("/v1/cr360/events", params={"countries": "esp,rus"})
        assert response.status_code == 422

    def test_events_missing_countries_returns_422(self, client):
        response = client.get("/v1/cr360/events")
        assert response.status_code == 422

    @patch("backend.api.routes.cr360.requests.get")
    def test_event_detail_returns_payload(self, mock_get, client):
        mock_get.return_value = _mock_ok(DETAIL_PAYLOAD)
        response = client.get("/v1/cr360/events/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["countryCode"] == "UKR"
        assert data["media"][0]["publicId"] == "cr360/g4jxr6vvgmd8ozh4xvbb"

    @patch("backend.api.routes.cr360.requests.get")
    def test_roads_filtered_by_country(self, mock_get, client):
        mock_get.return_value = _mock_ok(ROADS_PAYLOAD)
        response = client.get("/v1/cr360/roads", params={"countries": "ESP,RUS,UKR"})
        assert response.status_code == 200
        data = response.json()
        codes = {f["properties"]["countryCode"] for f in data["features"]}
        assert codes == {"UKR", "RUS"}
        assert "MEX" not in codes

    @patch("backend.api.routes.cr360.requests.get")
    def test_regions_filtered_by_country(self, mock_get, client):
        mock_get.return_value = _mock_ok(REGIONS_PAYLOAD)
        response = client.get("/v1/cr360/regions", params={"countries": "ESP,RUS,UKR"})
        assert response.status_code == 200
        data = response.json()
        codes = {f["properties"]["countryCode"] for f in data["features"]}
        assert codes == {"UKR", "ESP"}
        assert "MEX" not in codes

    @patch("backend.api.routes.cr360.requests.get")
    def test_upstream_error_returns_502(self, mock_get, client):
        import requests

        mock_get.side_effect = requests.RequestException("upstream down")
        response = client.get("/v1/cr360/events", params={"countries": "UKR"})
        assert response.status_code == 502
        assert "CR360 upstream error" in response.json()["detail"]
