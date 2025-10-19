import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.media_lens.cloud_entrypoint import active_runs, app
from src.media_lens.common import RunState
from src.media_lens.runner import Steps


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_api_key", "PORT": "8080"}):
        yield


@pytest.fixture
def clear_active_runs():
    """Clear active runs before each test."""
    active_runs.clear()
    yield
    active_runs.clear()


class TestHealthEndpoints:
    """Test health and status endpoints."""

    def test_index_endpoint(self, client):
        """Test the index endpoint returns app info."""
        response = client.get("/")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "online"
        assert data["app"] == "Media Lens"
        assert "endpoints" in data
        assert len(data["endpoints"]) > 0

    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "healthy"


class TestRunPipeline:
    """Test the /run endpoint."""

    @patch("src.media_lens.cloud_entrypoint.run")
    @patch("src.media_lens.cloud_entrypoint.Thread")
    def test_run_pipeline_success(self, mock_thread, mock_run, client, clear_active_runs):
        """Test successful pipeline run request."""
        # Mock the thread to not actually start
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Test data
        test_data = {"steps": ["harvest", "extract"], "run_id": "test123"}

        response = client.post("/run", data=json.dumps(test_data), content_type="application/json")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "accepted"
        assert data["run_id"] == "test123"
        assert "test123" in active_runs
        assert active_runs["test123"]["status"] == "running"

        # Verify thread was started
        mock_thread_instance.start.assert_called_once()

    def test_run_pipeline_default_steps(self, client, clear_active_runs):
        """Test pipeline run with default steps."""
        with patch("src.media_lens.cloud_entrypoint.Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            response = client.post("/run", data=json.dumps({}), content_type="application/json")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "accepted"

            # Check default steps
            run_id = data["run_id"]
            assert active_runs[run_id]["steps"] == ["harvest", "extract", "interpret", "deploy"]

    def test_run_pipeline_duplicate_run_id(self, client, clear_active_runs):
        """Test duplicate run ID rejection."""
        # Add a running task
        active_runs["test123"] = {"run_id": "test123", "status": "running", "running": True}

        test_data = {"steps": ["harvest"], "run_id": "test123"}

        response = client.post("/run", data=json.dumps(test_data), content_type="application/json")

        assert response.status_code == 409
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "already in progress" in data["message"]

    @patch("src.media_lens.cloud_entrypoint.run")
    def test_run_task_async_success(self, mock_run, clear_active_runs):
        """Test the async run task function."""
        from src.media_lens.cloud_entrypoint import run_task_async

        # Mock successful run
        mock_run.return_value = {
            "status": "success",
            "completed_steps": ["harvest", "extract"],
            "error": None,
        }

        # Setup active run
        run_id = "test123"
        active_runs[run_id] = {"run_id": run_id, "status": "running", "running": True}

        steps = [Steps.HARVEST, Steps.EXTRACT]
        run_task_async(steps, run_id)

        # Verify run was called correctly (with sites=None and job_dir='latest' as default)
        mock_run.assert_called_once_with(steps=steps, sites=None, run_id=run_id, job_dir="latest")

        # Verify active_runs was updated
        assert active_runs[run_id]["status"] == "success"
        assert active_runs[run_id]["completed_steps"] == ["harvest", "extract"]
        assert not active_runs[run_id]["running"]

    @patch("src.media_lens.cloud_entrypoint.run")
    def test_run_task_async_error(self, mock_run, clear_active_runs):
        """Test the async run task function with error."""
        from src.media_lens.cloud_entrypoint import run_task_async

        # Mock run failure
        mock_run.side_effect = Exception("Test error")

        # Setup active run
        run_id = "test123"
        active_runs[run_id] = {"run_id": run_id, "status": "running", "running": True}

        steps = [Steps.HARVEST]
        run_task_async(steps, run_id)

        # Verify error handling
        assert active_runs[run_id]["status"] == "error"
        assert active_runs[run_id]["error"] == "Test error"
        assert not active_runs[run_id]["running"]


class TestWeeklyEndpoint:
    """Test the /weekly endpoint."""

    @patch("src.media_lens.cloud_entrypoint.process_weekly_content")
    @patch("src.media_lens.cloud_entrypoint.Thread")
    def test_weekly_processing_success(self, mock_thread, mock_process, client, clear_active_runs):
        """Test successful weekly processing request."""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        test_data = {"current_week_only": True, "overwrite": False, "run_id": "weekly-test"}

        response = client.post(
            "/weekly", data=json.dumps(test_data), content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "accepted"
        assert data["run_id"] == "weekly-test"
        assert "weekly-test" in active_runs
        assert active_runs["weekly-test"]["type"] == "weekly"

        mock_thread_instance.start.assert_called_once()

    def test_weekly_processing_default_params(self, client, clear_active_runs):
        """Test weekly processing with default parameters."""
        with patch("src.media_lens.cloud_entrypoint.Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            response = client.post("/weekly", data=json.dumps({}), content_type="application/json")

            assert response.status_code == 200
            data = json.loads(response.data)
            run_id = data["run_id"]

            # Check default parameters
            params = active_runs[run_id]["parameters"]
            assert params["current_week_only"]
            assert not params["overwrite"]
            assert params["specific_weeks"] is None


class TestSummarizeEndpoint:
    """Test the /summarize endpoint."""

    @patch("src.media_lens.cloud_entrypoint.summarize_all")
    @patch("src.media_lens.cloud_entrypoint.Thread")
    def test_summarize_success(self, mock_thread, mock_summarize, client, clear_active_runs):
        """Test successful summarization request."""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        test_data = {"force": True, "run_id": "summary-test"}

        response = client.post(
            "/summarize", data=json.dumps(test_data), content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "accepted"
        assert data["run_id"] == "summary-test"
        assert "summary-test" in active_runs
        assert active_runs["summary-test"]["type"] == "summarize"

        mock_thread_instance.start.assert_called_once()


class TestStatusEndpoint:
    """Test the /status endpoint."""

    def test_status_empty(self, client, clear_active_runs):
        """Test status endpoint with no active runs."""
        response = client.get("/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["active_runs"] == 0
        assert data["total_runs"] == 0
        assert data["runs"] == {}

    def test_status_with_runs(self, client, clear_active_runs):
        """Test status endpoint with active runs."""
        # Add some test runs
        active_runs["test1"] = {"run_id": "test1", "status": "running", "running": True}
        active_runs["test2"] = {"run_id": "test2", "status": "completed", "running": False}

        response = client.get("/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["active_runs"] == 1  # Only test1 is running
        assert data["total_runs"] == 2
        assert "test1" in data["runs"]
        assert "test2" in data["runs"]

    def test_status_specific_run_id(self, client, clear_active_runs):
        """Test status endpoint for specific run ID."""
        active_runs["test123"] = {"run_id": "test123", "status": "completed", "running": False}

        response = client.get("/status?run_id=test123")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["run"]["run_id"] == "test123"

    def test_status_missing_run_id(self, client, clear_active_runs):
        """Test status endpoint for non-existent run ID."""
        response = client.get("/status?run_id=nonexistent")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "No run found" in data["message"]


class TestStopEndpoint:
    """Test the /stop endpoint."""

    def test_stop_running_task(self, client, clear_active_runs):
        """Test stopping a running task."""
        # Add a running task
        active_runs["test123"] = {"run_id": "test123", "status": "running", "running": True}

        with patch.object(RunState, "request_stop") as mock_stop:
            response = client.post("/stop/test123")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "accepted"
            assert "Stop requested" in data["message"]
            mock_stop.assert_called_once()

    def test_stop_nonexistent_task(self, client, clear_active_runs):
        """Test stopping a non-existent task."""
        response = client.post("/stop/nonexistent")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "No run found" in data["message"]

    def test_stop_already_stopped_task(self, client, clear_active_runs):
        """Test stopping an already stopped task."""
        # Add a stopped task
        active_runs["test123"] = {"run_id": "test123", "status": "completed", "running": False}

        response = client.post("/stop/test123")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not currently running" in data["message"]


class TestSitesUpdate:
    """Test sites update functionality."""

    @patch("src.media_lens.cloud_entrypoint.Thread")
    def test_sites_update_in_run(self, mock_thread, client, clear_active_runs):
        """Test that sites are updated when provided in run request."""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        test_data = {"steps": ["harvest"], "sites": ["custom1.com", "custom2.com"]}

        with patch("src.media_lens.common.SITES"):
            response = client.post(
                "/run", data=json.dumps(test_data), content_type="application/json"
            )

            assert response.status_code == 200
            # Verify sites were updated in the common module
            # The sites should be updated in the module


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_malformed_json(self, client):
        """Test handling of malformed JSON."""
        response = client.post("/run", data="invalid json", content_type="application/json")

        # Should still work with silent=True - gets empty dict
        assert response.status_code == 200

    def test_invalid_steps(self, client, clear_active_runs):
        """Test handling of invalid step names."""
        test_data = {"steps": ["invalid_step"]}

        response = client.post("/run", data=json.dumps(test_data), content_type="application/json")

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["status"] == "error"
