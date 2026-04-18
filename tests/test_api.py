"""API 端点测试 — Flask test client"""

# 1. Standard library
import io
from unittest.mock import MagicMock, patch

# 2. Third-party
import pytest

# 3. Local
from api.app import create_app


@pytest.fixture
def app(mock_config):
    """Create Flask test app with mock config."""
    flask_app = create_app(mock_config)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_returns_200(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def test_list_history_returns_json_list(client):
    mock_records = [
        {"id": 1, "type": "tts", "source_text": "hello"},
        {"id": 2, "type": "asr", "source_text": "world"},
    ]
    with patch("api.history_routes.HistoryManager") as MockMgr:
        MockMgr.return_value.list_records.return_value = mock_records
        resp = client.get("/api/history")

    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["id"] == 1


def test_list_history_returns_empty_list(client):
    with patch("api.history_routes.HistoryManager") as MockMgr:
        MockMgr.return_value.list_records.return_value = []
        resp = client.get("/api/history")

    assert resp.status_code == 200
    assert resp.get_json() == []


# ---------------------------------------------------------------------------
# Recordings
# ---------------------------------------------------------------------------

def test_list_recordings_returns_json_list(client):
    mock_recordings = [
        {"id": 1, "filename": "rec_001.wav", "duration": 5.0},
    ]
    with patch("api.recording_routes.RecordingManager") as MockMgr:
        MockMgr.return_value.list_recordings.return_value = mock_recordings
        resp = client.get("/api/recordings")

    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["id"] == 1


def test_list_recordings_returns_empty_list(client):
    with patch("api.recording_routes.RecordingManager") as MockMgr:
        MockMgr.return_value.list_recordings.return_value = []
        resp = client.get("/api/recordings")

    assert resp.status_code == 200
    assert resp.get_json() == []


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export_history_returns_zip(client):
    fake_zip = io.BytesIO(b"PK\x03\x04fake_zip_content")
    with patch("api.history_routes.HistoryManager") as MockMgr:
        MockMgr.return_value.export_all.return_value = fake_zip
        resp = client.get("/api/history/export")

    assert resp.status_code == 200
    assert resp.content_type == "application/zip"


def test_export_recordings_returns_zip(client):
    fake_zip = io.BytesIO(b"PK\x03\x04fake_zip_content")
    with patch("api.recording_routes.RecordingManager") as MockMgr:
        MockMgr.return_value.export_all.return_value = fake_zip
        resp = client.get("/api/recordings/export")

    assert resp.status_code == 200
    assert resp.content_type == "application/zip"


# ---------------------------------------------------------------------------
# Audio 404
# ---------------------------------------------------------------------------

def test_get_history_audio_404_when_not_found(client):
    with patch("api.history_routes.HistoryManager") as MockMgr:
        MockMgr.return_value.get_audio_path.return_value = None
        resp = client.get("/api/history/999/audio")

    assert resp.status_code == 404
