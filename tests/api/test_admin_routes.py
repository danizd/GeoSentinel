from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
import pytest

from fastapi.testclient import TestClient

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (str(ROOT), str(ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestAdminRoutes:

    @patch("backend.api.routes.admin._background_job")
    def test_run_usgs_returns_202(self, mock_run, client):
        mock_run.return_value = MagicMock()
        response = client.post("/v1/admin/run/usgs")
        assert response.status_code == 202
        data = response.json()
        assert data["job"] == "usgs"
        assert data["status"] == "running"
        assert "job_id" in data
        assert "started_at" in data

    @patch("backend.api.routes.admin._background_job")
    def test_run_firms_returns_202(self, mock_run, client):
        mock_run.return_value = MagicMock()
        response = client.post("/v1/admin/run/firms")
        assert response.status_code == 202
        assert response.json()["job"] == "firms"

    @patch("backend.api.routes.admin._background_job")
    def test_run_gdelt_returns_202(self, mock_run, client):
        mock_run.return_value = MagicMock()
        response = client.post("/v1/admin/run/gdelt")
        assert response.status_code == 202
        assert response.json()["job"] == "gdelt"

    @patch("backend.api.routes.admin._background_job")
    def test_run_acled_returns_202(self, mock_run, client):
        mock_run.return_value = MagicMock()
        response = client.post("/v1/admin/run/acled")
        assert response.status_code == 202
        assert response.json()["job"] == "acled"

    @patch("backend.api.routes.admin._background_job")
    def test_run_clustering_returns_202(self, mock_run, client):
        mock_run.return_value = MagicMock()
        response = client.post("/v1/admin/run/clustering")
        assert response.status_code == 202
        assert response.json()["job"] == "clustering"

    @patch("backend.api.routes.admin._background_job")
    def test_run_lifecycle_returns_202(self, mock_run, client):
        mock_run.return_value = MagicMock()
        response = client.post("/v1/admin/run/lifecycle")
        assert response.status_code == 202
        assert response.json()["job"] == "lifecycle"

    @patch("backend.api.routes.admin._background_job")
    def test_run_all_returns_202(self, mock_run_all, client):
        mock_run_all.return_value = MagicMock()
        response = client.post("/v1/admin/run/all")
        assert response.status_code == 202
        assert response.json()["job"] == "all"

    def test_run_unknown_source_returns_400(self, client):
        response = client.post("/v1/admin/run/nonexistent")
        assert response.status_code == 400

    def test_get_status_unknown_job_returns_404(self, client):
        response = client.get("/v1/admin/run/status/nonexistent-job-id")
        assert response.status_code == 404

    def test_get_status_returns_correct_contract(self, client):
        job_id = str(uuid4())
        from backend.api.routes.admin import JOBS
        import asyncio

        async def _setup():
            JOBS[job_id] = {
                "job_id": job_id,
                "job": "usgs",
                "status": "completed",
                "started_at": "2026-05-14T10:00:00Z",
                "finished_at": "2026-05-14T10:01:00Z",
                "duration_sec": 60,
                "result": {
                    "events_fetched": 120,
                    "events_inserted": 118,
                    "events_quarantine": 2,
                    "incidents_created": 8,
                    "incidents_updated": 3,
                },
                "error": None,
            }

        asyncio.run(_setup())

        response = client.get(f"/v1/admin/run/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["job"] == "usgs"
        assert data["status"] == "completed"
        assert data["finished_at"] == "2026-05-14T10:01:00Z"
        assert data["duration_sec"] == 60
        assert data["result"]["events_fetched"] == 120
        assert data["result"]["events_inserted"] == 118
        assert data["result"]["events_quarantine"] == 2
        assert data["result"]["incidents_created"] == 8
        assert data["result"]["incidents_updated"] == 3
        assert data["error"] is None

    def test_get_status_failed_job_includes_error(self, client):
        job_id = str(uuid4())
        from backend.api.routes.admin import JOBS
        import asyncio

        async def _setup():
            JOBS[job_id] = {
                "job_id": job_id,
                "job": "gdelt",
                "status": "failed",
                "started_at": "2026-05-14T10:00:00Z",
                "finished_at": "2026-05-14T10:00:30Z",
                "duration_sec": 30,
                "result": None,
                "error": "Connection timeout after 30s",
            }

        asyncio.run(_setup())

        response = client.get(f"/v1/admin/run/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Connection timeout after 30s"

    @patch("backend.api.routes.admin._get_running_job")
    def test_concurrent_run_same_job_returns_409(self, mock_running, client):
        mock_running.return_value = {
            "job_id": "existing-job-id",
            "job": "usgs",
            "status": "running",
            "started_at": "2026-05-14T10:00:00Z",
        }

        response = client.post("/v1/admin/run/usgs")
        assert response.status_code == 409
        data = response.json()["detail"]
        assert data["error"] == "job_already_running"
        assert data["job"] == "usgs"
        assert data["job_id"] == "existing-job-id"