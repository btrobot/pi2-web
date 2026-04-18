"""API 端点测试 — Flask test client"""

# 1. Standard library
import io
import os
import zipfile
from unittest.mock import MagicMock, patch

# 2. Third-party
import pytest

# 3. Local
from app.mode_registry import get_mode_definition, list_mode_definitions
from api.app import create_app
from storage.history import HistoryManager
from storage.recordings import RecordingManager


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


def test_bootstrap_returns_atomic_contract(client, mock_config):
    resp = client.get("/api/bootstrap")

    assert resp.status_code == 200

    data = resp.get_json()
    assert set(data.keys()) == {"app", "constraints", "modes", "i18n"}
    assert data["app"] == {
        "default_locale": "zh-CN",
        "supported_locales": ["zh-CN", "en-US"],
    }
    assert data["constraints"] == {
        "max_record_seconds": mock_config["audio"]["max_record_duration"],
        "max_history": mock_config["storage"]["max_history"],
        "max_recordings": mock_config["storage"]["max_recordings"],
    }

    expected_modes = [
        {
            "mode_key": mode.mode_key,
            "group_key": mode.group_key,
            "input_type": mode.input_type,
            "output_type": mode.output_type,
            "source_lang": mode.source_lang,
            "target_lang": mode.target_lang,
        }
        for mode in list_mode_definitions()
    ]
    assert data["modes"] == expected_modes
    assert len(data["modes"]) == 12
    for mode in data["modes"]:
        assert set(mode.keys()) == {
            "mode_key",
            "group_key",
            "input_type",
            "output_type",
            "source_lang",
            "target_lang",
        }
        assert "pipeline_chain" not in mode
        assert "mode" not in mode
        assert "id" not in mode


def test_bootstrap_i18n_contains_exact_frozen_shell_keys(client):
    resp = client.get("/api/bootstrap")
    data = resp.get_json()

    expected_keys = {
        "header.title",
        "header.user_settings",
        "header.help",
        "header.language_switch",
        "nav.same_text_to_speech",
        "nav.same_speech_to_text",
        "nav.cross_text_to_speech",
        "nav.cross_speech_to_text",
        "nav.cross_text_to_text",
        "nav.cross_speech_to_speech",
        "nav.recordings",
        "nav.history",
        "breadcrumb.current_location",
        "status.ready",
        "status.processing",
        "status.error",
        "footer.constraints_hint",
    }

    assert set(data["i18n"].keys()) == {"zh-CN", "en-US"}
    for locale in ("zh-CN", "en-US"):
        messages = data["i18n"][locale]
        assert set(messages.keys()) == expected_keys
        assert all(isinstance(value, str) and value for value in messages.values())


# ---------------------------------------------------------------------------
# Conversions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "mode_key",
    [
        "tts_zh_zh",
        "tts_en_en",
        "mt_tts_zh_en",
        "mt_tts_en_zh",
        "mt_zh_en",
        "mt_en_zh",
    ],
)
def test_text_conversion_returns_frozen_record_and_result_dto(client, app, mode_key):
    mode = get_mode_definition(mode_key)
    output_text = "Hello" if mode.output_type == "text" or "mt" in mode.pipeline_chain else None
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 12})
    manifest = {
        "id": 12,
        "mode_key": mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "created_at": "2026-04-18T17:00:00",
        "artifacts": {
            "input_text": "input_text.txt",
            "output_text": "output_text.txt" if mode.output_type == "text" or "mt" in mode.pipeline_chain else None,
            "input_audio": None,
            "output_audio": "output_audio.wav" if mode.output_type == "audio" else None,
        },
        "values": {
            "source_text": "你好",
            "output_text": output_text,
        },
    }

    with patch("api.conversion_routes.HistoryManager") as mock_mgr:
        mock_mgr.return_value.get_manifest.return_value = manifest
        resp = client.post(
            "/api/conversions/text",
            json={
                "mode_key": mode_key,
                "input_text": "你好",
                "persist_input": True,
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {"record", "result"}
    assert data["record"] == {
        "id": 12,
        "mode_key": mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "created_at": "2026-04-18T17:00:00",
        "artifacts": {
            "input_text_url": "/api/history/12/artifacts/input_text",
            "output_text_url": "/api/history/12/artifacts/output_text" if manifest["artifacts"]["output_text"] else None,
            "input_audio_url": None,
            "output_audio_url": "/api/history/12/artifacts/output_audio" if mode.output_type == "audio" else None,
        },
    }
    assert data["result"] == {
        "source_text": "你好",
        "output_text": manifest["values"]["output_text"],
        "output_audio_url": "/api/history/12/artifacts/output_audio" if mode.output_type == "audio" else None,
    }
    app.config["PIPELINE_FN"].assert_called_once_with(
        mode_key,
        app.config["APP_CONFIG"],
        input_text="你好",
        input_audio_path=None,
        playback=False,
    )


def test_text_conversion_rejects_invalid_mode_key(client):
    resp = client.post(
        "/api/conversions/text",
        json={"mode_key": "asr_zh_zh", "input_text": "你好"},
    )

    assert resp.status_code == 400
    assert "mode_key must be one of" in resp.get_json()["error"]


@pytest.mark.parametrize("payload", [{"mode_key": "mt_zh_en"}, {"mode_key": "mt_zh_en", "input_text": ""}])
def test_text_conversion_requires_non_empty_input_text(client, payload):
    resp = client.post("/api/conversions/text", json=payload)

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "input_text must be a non-empty string"


def test_text_conversion_requires_valid_mode_key_before_other_validation(client):
    resp = client.post("/api/conversions/text", json={})

    assert resp.status_code == 400
    assert "mode_key must be one of" in resp.get_json()["error"]


def test_text_conversion_returns_503_when_pipeline_is_unavailable(client, app):
    app.config["PIPELINE_FN"] = None

    resp = client.post(
        "/api/conversions/text",
        json={"mode_key": "mt_zh_en", "input_text": "你好"},
    )

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "conversion service unavailable"


@pytest.mark.parametrize(
    ("pipeline_result", "expected_error"),
    [
        ({"error": "boom"}, "conversion failed: boom"),
        ({}, "conversion history was not persisted"),
    ],
)
def test_text_conversion_surfaces_pipeline_and_persistence_failures(client, app, pipeline_result, expected_error):
    app.config["PIPELINE_FN"] = MagicMock(return_value=pipeline_result)

    resp = client.post(
        "/api/conversions/text",
        json={"mode_key": "mt_zh_en", "input_text": "你好"},
    )

    assert resp.status_code == 500
    assert resp.get_json()["error"] == expected_error


def test_text_conversion_returns_500_when_pipeline_raises(client, app):
    app.config["PIPELINE_FN"] = MagicMock(side_effect=RuntimeError("bad pipeline"))

    resp = client.post(
        "/api/conversions/text",
        json={"mode_key": "mt_zh_en", "input_text": "你好"},
    )

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "conversion failed: bad pipeline"


def test_text_conversion_returns_500_when_persisted_manifest_is_missing(client, app):
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 21})

    with patch("api.conversion_routes.HistoryManager") as mock_mgr:
        mock_mgr.return_value.get_manifest.return_value = None
        resp = client.post(
            "/api/conversions/text",
            json={"mode_key": "mt_zh_en", "input_text": "你好"},
        )

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "conversion record not found after persistence"


def test_text_conversion_returns_500_when_persisted_manifest_mode_mismatches_request(client, app):
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 23})

    with patch("api.conversion_routes.HistoryManager") as mock_mgr:
        mock_mgr.return_value.get_manifest.return_value = {
            "id": 23,
            "mode_key": "mt_en_zh",
            "group_key": "cross_text_to_text",
            "source_lang": "en",
            "target_lang": "zh",
            "created_at": "2026-04-18T17:03:00",
            "artifacts": {},
            "values": {},
        }
        resp = client.post(
            "/api/conversions/text",
            json={"mode_key": "mt_zh_en", "input_text": "你好"},
        )

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "conversion record not found after persistence"


@pytest.mark.parametrize(
    "mode_key",
    [
        "asr_zh_zh",
        "asr_en_en",
        "asr_mt_zh_en",
        "asr_mt_en_zh",
        "asr_mt_tts_zh_en",
        "asr_mt_tts_en_zh",
    ],
)
def test_speech_conversion_accepts_audio_upload_and_returns_frozen_dto(
    client,
    app,
    mode_key,
    tmp_audio_file,
):
    mode = get_mode_definition(mode_key)
    output_text = "Hello"
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 13})
    manifest = {
        "id": 13,
        "mode_key": mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "created_at": "2026-04-18T17:01:00",
        "artifacts": {
            "input_text": None,
            "output_text": "output_text.txt",
            "input_audio": "input_audio.wav",
            "output_audio": "output_audio.wav" if mode.output_type == "audio" else None,
        },
        "values": {
            "source_text": "你好",
            "output_text": output_text,
        },
    }

    with patch("api.conversion_routes.HistoryManager") as mock_history_mgr:
        mock_history_mgr.return_value.get_manifest.return_value = manifest
        with tmp_audio_file.open("rb") as handle:
            resp = client.post(
                "/api/conversions/speech",
                data={
                    "mode_key": mode_key,
                    "input_audio": (handle, "input.wav"),
                },
                content_type="multipart/form-data",
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["record"] == {
        "id": 13,
        "mode_key": mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "created_at": "2026-04-18T17:01:00",
        "artifacts": {
            "input_text_url": None,
            "output_text_url": "/api/history/13/artifacts/output_text",
            "input_audio_url": "/api/history/13/artifacts/input_audio",
            "output_audio_url": "/api/history/13/artifacts/output_audio" if mode.output_type == "audio" else None,
        },
    }
    assert data["result"] == {
        "source_text": "你好",
        "output_text": output_text,
        "output_audio_url": "/api/history/13/artifacts/output_audio" if mode.output_type == "audio" else None,
    }

    app.config["PIPELINE_FN"].assert_called_once()
    call_args = app.config["PIPELINE_FN"].call_args
    assert call_args.args == (mode_key, app.config["APP_CONFIG"])
    assert call_args.kwargs["input_text"] is None
    assert call_args.kwargs["playback"] is False
    temp_input_path = call_args.kwargs["input_audio_path"]
    assert isinstance(temp_input_path, str)
    assert temp_input_path.endswith(".wav")
    assert os.path.exists(temp_input_path) is False


def test_speech_conversion_accepts_recording_id_reuse(client, app, tmp_audio_file):
    mode_key = "asr_mt_tts_zh_en"
    mode = get_mode_definition(mode_key)
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 14})
    manifest = {
        "id": 14,
        "mode_key": mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "created_at": "2026-04-18T17:02:00",
        "artifacts": {
            "input_text": None,
            "output_text": "output_text.txt",
            "input_audio": "input_audio.wav",
            "output_audio": "output_audio.wav",
        },
        "values": {
            "source_text": "你好",
            "output_text": "Hello",
        },
    }

    with patch("api.conversion_routes.RecordingManager") as mock_recording_mgr, \
         patch("api.conversion_routes.HistoryManager") as mock_history_mgr:
        mock_recording_mgr.return_value.get_audio_path.return_value = tmp_audio_file
        mock_history_mgr.return_value.get_manifest.return_value = manifest
        resp = client.post(
            "/api/conversions/speech",
            data={
                "mode_key": mode_key,
                "recording_id": "3",
            },
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    assert resp.get_json()["record"]["id"] == 14
    app.config["PIPELINE_FN"].assert_called_once_with(
        mode_key,
        app.config["APP_CONFIG"],
        input_text=None,
        input_audio_path=str(tmp_audio_file),
        playback=False,
    )


def test_speech_conversion_rejects_invalid_mode_key(client):
    resp = client.post(
        "/api/conversions/speech",
        data={"mode_key": "mt_zh_en"},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert "mode_key must be one of" in resp.get_json()["error"]


def test_speech_conversion_requires_exactly_one_audio_source(client, tmp_audio_file):
    resp_missing = client.post(
        "/api/conversions/speech",
        data={"mode_key": "asr_zh_zh"},
        content_type="multipart/form-data",
    )

    assert resp_missing.status_code == 400
    assert resp_missing.get_json()["error"] == "provide exactly one of input_audio or recording_id"

    with tmp_audio_file.open("rb") as handle:
        resp_both = client.post(
            "/api/conversions/speech",
            data={
                "mode_key": "asr_zh_zh",
                "recording_id": "1",
                "input_audio": (handle, "input.wav"),
            },
            content_type="multipart/form-data",
        )

    assert resp_both.status_code == 400
    assert resp_both.get_json()["error"] == "provide exactly one of input_audio or recording_id"


def test_speech_conversion_rejects_non_integer_recording_id(client):
    resp = client.post(
        "/api/conversions/speech",
        data={"mode_key": "asr_zh_zh", "recording_id": "abc"},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "recording_id must be an integer"


def test_speech_conversion_returns_404_when_recording_id_is_missing(client):
    with patch("api.conversion_routes.RecordingManager") as mock_recording_mgr:
        mock_recording_mgr.return_value.get_audio_path.return_value = None
        resp = client.post(
            "/api/conversions/speech",
            data={"mode_key": "asr_mt_zh_en", "recording_id": "99"},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 404
    assert resp.get_json()["error"] == "recording_id 99 not found"


@pytest.mark.parametrize(
    ("pipeline_result", "expected_error"),
    [
        ({"error": "speech boom"}, "conversion failed: speech boom"),
        ({}, "conversion history was not persisted"),
    ],
)
def test_speech_conversion_surfaces_pipeline_and_persistence_failures(
    client,
    app,
    tmp_audio_file,
    pipeline_result,
    expected_error,
):
    app.config["PIPELINE_FN"] = MagicMock(return_value=pipeline_result)

    with tmp_audio_file.open("rb") as handle:
        resp = client.post(
            "/api/conversions/speech",
            data={
                "mode_key": "asr_mt_zh_en",
                "input_audio": (handle, "input.wav"),
            },
            content_type="multipart/form-data",
        )

    assert resp.status_code == 500
    assert resp.get_json()["error"] == expected_error


def test_speech_conversion_returns_503_when_pipeline_is_unavailable(client, app, tmp_audio_file):
    app.config["PIPELINE_FN"] = None

    with tmp_audio_file.open("rb") as handle:
        resp = client.post(
            "/api/conversions/speech",
            data={
                "mode_key": "asr_mt_zh_en",
                "input_audio": (handle, "input.wav"),
            },
            content_type="multipart/form-data",
        )

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "conversion service unavailable"


def test_speech_conversion_returns_500_when_persisted_manifest_is_missing(client, app, tmp_audio_file):
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 22})

    with patch("api.conversion_routes.HistoryManager") as mock_mgr:
        mock_mgr.return_value.get_manifest.return_value = None
        with tmp_audio_file.open("rb") as handle:
            resp = client.post(
                "/api/conversions/speech",
                data={
                    "mode_key": "asr_mt_tts_zh_en",
                    "input_audio": (handle, "input.wav"),
                },
                content_type="multipart/form-data",
            )

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "conversion record not found after persistence"


def test_speech_conversion_returns_500_when_persisted_manifest_mode_mismatches_request(client, app, tmp_audio_file):
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 24})

    with patch("api.conversion_routes.HistoryManager") as mock_mgr:
        mock_mgr.return_value.get_manifest.return_value = {
            "id": 24,
            "mode_key": "asr_mt_en_zh",
            "group_key": "cross_speech_to_text",
            "source_lang": "en",
            "target_lang": "zh",
            "created_at": "2026-04-18T17:04:00",
            "artifacts": {},
            "values": {},
        }
        with tmp_audio_file.open("rb") as handle:
            resp = client.post(
                "/api/conversions/speech",
                data={
                    "mode_key": "asr_mt_zh_en",
                    "input_audio": (handle, "input.wav"),
                },
                content_type="multipart/form-data",
            )

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "conversion record not found after persistence"


# ---------------------------------------------------------------------------
# History / recordings helpers
# ---------------------------------------------------------------------------


def _history_manager(mock_config) -> HistoryManager:
    storage_cfg = mock_config["storage"]
    return HistoryManager(storage_cfg["history_dir"], storage_cfg["max_history"])


def _recording_manager(mock_config) -> RecordingManager:
    storage_cfg = mock_config["storage"]
    return RecordingManager(storage_cfg["recordings_dir"], storage_cfg["max_recordings"])


def _seed_history_record(manager: HistoryManager, mode_key: str, index: int, audio_path: str) -> dict:
    mode = get_mode_definition(mode_key)
    source_text = f"source-{index}-{mode_key}"
    output_text = f"output-{index}-{mode_key}" if ("mt" in mode.pipeline_chain or mode.output_type == "text") else None
    kwargs = {
        "mode_key": mode.mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "source_text": source_text,
        "target_text": output_text,
        "input_text": source_text if mode.input_type == "text" else None,
        "output_text": output_text,
        "input_audio_path": audio_path if mode.input_type == "audio" else None,
        "output_audio_path": audio_path if mode.output_type == "audio" else None,
    }
    return manager.add_record(**kwargs)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def test_recent_history_returns_latest_three_summary_items(client, mock_config, tmp_audio_file):
    manager = _history_manager(mock_config)
    mode_keys = [
        "tts_zh_zh",
        "mt_zh_en",
        "asr_en_en",
        "mt_tts_zh_en",
        "asr_mt_en_zh",
        "asr_mt_tts_zh_en",
    ]
    for index, mode_key in enumerate(mode_keys, start=1):
        _seed_history_record(manager, mode_key, index, str(tmp_audio_file))

    resp = client.get("/api/history/recent")

    assert resp.status_code == 200
    data = resp.get_json()
    assert list(data.keys()) == ["items"]
    assert [item["id"] for item in data["items"]] == [6, 5, 4]
    assert all(set(item.keys()) == {
        "id",
        "mode_key",
        "group_key",
        "created_at",
        "source_preview",
        "output_preview",
        "output_kind",
        "artifact_urls",
    } for item in data["items"])
    assert data["items"][0]["mode_key"] == "asr_mt_tts_zh_en"
    assert data["items"][0]["output_kind"] == "audio"
    assert data["items"][0]["artifact_urls"] == {
        "input_text_url": None,
        "output_text_url": "/api/history/6/artifacts/output_text",
        "input_audio_url": "/api/history/6/artifacts/input_audio",
        "output_audio_url": "/api/history/6/artifacts/output_audio",
    }



def test_history_returns_latest_five_full_items(client, mock_config, tmp_audio_file):
    manager = _history_manager(mock_config)
    mode_keys = [
        "tts_zh_zh",
        "mt_zh_en",
        "asr_en_en",
        "mt_tts_zh_en",
        "asr_mt_en_zh",
        "asr_mt_tts_zh_en",
    ]
    for index, mode_key in enumerate(mode_keys, start=1):
        _seed_history_record(manager, mode_key, index, str(tmp_audio_file))

    resp = client.get("/api/history")

    assert resp.status_code == 200
    data = resp.get_json()
    assert list(data.keys()) == ["items"]
    assert [item["id"] for item in data["items"]] == [6, 5, 4, 3, 2]
    first = data["items"][0]
    assert set(first.keys()) == {
        "id",
        "mode_key",
        "group_key",
        "source_lang",
        "target_lang",
        "created_at",
        "values",
        "artifacts",
        "artifact_urls",
    }
    assert first["mode_key"] == "asr_mt_tts_zh_en"
    assert first["values"]["source_text"] == "source-6-asr_mt_tts_zh_en"
    assert first["values"]["output_text"] == "output-6-asr_mt_tts_zh_en"
    assert first["artifacts"] == {
        "input_text": None,
        "output_text": "output_text.txt",
        "input_audio": "input_audio.wav",
        "output_audio": "output_audio.wav",
    }
    assert first["artifact_urls"] == {
        "input_text_url": None,
        "output_text_url": "/api/history/6/artifacts/output_text",
        "input_audio_url": "/api/history/6/artifacts/input_audio",
        "output_audio_url": "/api/history/6/artifacts/output_audio",
        "manifest_url": "/api/history/6/artifacts/manifest",
    }



def test_history_artifact_routes_serve_text_and_manifest_files(client, mock_config, tmp_audio_file):
    manager = _history_manager(mock_config)
    _seed_history_record(manager, "mt_tts_zh_en", 1, str(tmp_audio_file))

    text_resp = client.get("/api/history/1/artifacts/input_text")
    manifest_resp = client.get("/api/history/1/artifacts/manifest")

    assert text_resp.status_code == 200
    assert text_resp.mimetype == "text/plain"
    assert text_resp.get_data(as_text=True) == "source-1-mt_tts_zh_en"
    assert manifest_resp.status_code == 200
    assert manifest_resp.mimetype == "application/json"
    assert '"mode_key": "mt_tts_zh_en"' in manifest_resp.get_data(as_text=True)



def test_history_artifact_route_rejects_invalid_kind_and_missing_artifact(client, mock_config, tmp_audio_file):
    manager = _history_manager(mock_config)
    _seed_history_record(manager, "mt_zh_en", 1, str(tmp_audio_file))

    invalid_resp = client.get("/api/history/1/artifacts/not-real")
    missing_resp = client.get("/api/history/1/artifacts/input_audio")

    assert invalid_resp.status_code == 400
    assert missing_resp.status_code == 404



def test_delete_history_returns_unified_delete_dto(client, mock_config, tmp_audio_file):
    manager = _history_manager(mock_config)
    _seed_history_record(manager, "asr_mt_tts_zh_en", 1, str(tmp_audio_file))

    resp = client.delete("/api/history/1")

    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "deleted_kind": "history", "deleted_id": 1}
    assert manager.get_record(1) is None



def test_export_history_returns_frozen_zip_structure(client, mock_config, tmp_audio_file):
    manager = _history_manager(mock_config)
    _seed_history_record(manager, "asr_mt_tts_zh_en", 1, str(tmp_audio_file))

    resp = client.get("/api/history/export")

    assert resp.status_code == 200
    assert resp.content_type.startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(resp.data)) as archive:
        names = set(archive.namelist())
    assert "index.json" in names
    assert "record_001/manifest.json" in names
    assert "record_001/input_audio.wav" in names
    assert "record_001/output_audio.wav" in names
    assert "record_001/output_text.txt" in names


# ---------------------------------------------------------------------------
# Recordings
# ---------------------------------------------------------------------------


def test_list_recordings_returns_latest_five_frozen_items(client, mock_config, tmp_audio_file):
    manager = _recording_manager(mock_config)
    for _ in range(6):
        manager.save_recording(str(tmp_audio_file))

    resp = client.get("/api/recordings")

    assert resp.status_code == 200
    data = resp.get_json()
    assert list(data.keys()) == ["items"]
    assert [item["id"] for item in data["items"]] == [6, 5, 4, 3, 2]
    assert all(set(item.keys()) == {"id", "created_at", "duration_seconds", "audio_url", "reuse"} for item in data["items"])
    assert data["items"][0]["audio_url"] == "/api/recordings/6/audio"
    assert data["items"][0]["reuse"] == {"recording_id": 6}



def test_delete_recording_returns_unified_delete_dto(client, mock_config, tmp_audio_file):
    manager = _recording_manager(mock_config)
    manager.save_recording(str(tmp_audio_file))

    resp = client.delete("/api/recordings/1")

    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "deleted_kind": "recording", "deleted_id": 1}
    assert manager.get_recording(1) is None



def test_export_recordings_returns_frozen_zip_structure(client, mock_config, tmp_audio_file):
    manager = _recording_manager(mock_config)
    manager.save_recording(str(tmp_audio_file))

    resp = client.get("/api/recordings/export")

    assert resp.status_code == 200
    assert resp.content_type.startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(resp.data)) as archive:
        names = set(archive.namelist())
    assert "metadata.json" in names
    assert "recording_001.wav" in names


# ---------------------------------------------------------------------------
# Audio 404
# ---------------------------------------------------------------------------


def test_get_recording_audio_404_when_not_found(client):
    resp = client.get("/api/recordings/999/audio")

    assert resp.status_code == 404
