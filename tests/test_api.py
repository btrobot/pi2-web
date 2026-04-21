"""API 端点测试 — Flask test client"""

# 1. Standard library
import io
import os
import re
import zipfile
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

# 2. Third-party
import pytest
from werkzeug.datastructures import FileStorage

# 3. Local
from api.audio_ingest import AudioIngressError, stage_browser_wav_upload
from audio.media_coordinator import MediaBusyError, MediaCoordinatorError, Pi5MediaCoordinator
from app.mode_registry import get_mode_definition, list_mode_definitions
from api.app import create_app
from storage.history import HistoryManager
from storage.recordings import RecordingManager


class _StubPi5MediaCoordinator:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, object]] = []
        self.recording_start_calls: list[str] = []
        self.start_error: Exception | None = None
        self.recording_start_error: Exception | None = None
        self.recording_stop_error: Exception | None = None
        self.recording_result = {
            "id": 7,
            "created_at": "2026-04-20T12:07:00",
            "duration_seconds": 1.2,
        }
        self.state_payload = {
            "status": "idle",
            "device": "plughw:2,0",
            "active_kind": None,
            "playback": None,
            "recording": None,
            "error": None,
        }

    def get_state(self) -> dict[str, object]:
        return dict(self.state_payload)

    def get_busy_state(self, *, requested_action: str) -> dict[str, object]:
        payload = self.get_state()
        payload["status"] = "busy"
        payload["requested_action"] = requested_action
        return payload

    def start_playback(
        self,
        wav_path: str,
        *,
        mode_key: str,
        history_id: int,
        audio_url: str | None,
    ) -> dict[str, object]:
        self.start_calls.append(
            {
                "wav_path": wav_path,
                "mode_key": mode_key,
                "history_id": history_id,
                "audio_url": audio_url,
            }
        )
        if self.start_error is not None:
            raise self.start_error
        return self.get_state()

    def stop_playback(self) -> dict[str, object]:
        self.state_payload = {
            **self.state_payload,
            "status": "idle",
            "active_kind": None,
            "playback": None,
            "error": None,
        }
        return self.get_state()

    def start_recording(self, *, category: str = "standalone") -> dict[str, object]:
        self.recording_start_calls.append(category)
        if self.recording_start_error is not None:
            raise self.recording_start_error
        self.state_payload = {
            **self.state_payload,
            "status": "recording",
            "active_kind": "recording",
            "playback": None,
            "recording": {
                "started_at": "2026-04-20T12:06:00Z",
                "device": "plughw:2,0",
                "max_duration_seconds": 180,
                "pending_save": False,
            },
            "error": None,
        }
        return self.get_state()

    def stop_recording(self) -> dict[str, object]:
        if self.recording_stop_error is not None:
            raise self.recording_stop_error
        self.state_payload = {
            **self.state_payload,
            "status": "idle",
            "active_kind": None,
            "recording": None,
            "error": None,
        }
        return dict(self.recording_result)


class _FakePlaybackProcess:
    def __init__(self) -> None:
        self.pid = 4321
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = -9


@pytest.fixture
def app(mock_config):
    """Create Flask test app with mock config."""
    with patch("api.app._run_startup_checks", return_value={"mt": {"ok": True, "issues": [], "package_dir": "models/data/argos"}}):
        flask_app = create_app(mock_config)
    flask_app.config["TESTING"] = True
    flask_app.extensions["pi5_media_coordinator"] = _StubPi5MediaCoordinator()
    return flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


def _get_index_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def _get_index_script(html):
    script_match = re.search(r"<script>(?P<script>.*)</script>\s*</body>", html, flags=re.S)
    assert script_match is not None
    return script_match.group("script")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_returns_200(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["checks"]["pipeline"]["ok"] is True
    assert data["checks"]["mt"]["ok"] is True


def test_health_returns_503_when_startup_mt_check_fails(mock_config):
    with patch(
        "api.app._run_startup_checks",
        return_value={
            "mt": {
                "ok": False,
                "issues": ["MT sentence tokenizer unavailable for zh→en: missing stanza model"],
                "package_dir": "models/data/argos",
            }
        },
    ):
        flask_app = create_app(mock_config)
        flask_app.config["TESTING"] = True

    client = flask_app.test_client()
    resp = client.get("/api/health")

    assert resp.status_code == 503
    data = resp.get_json()
    assert data["status"] == "error"
    assert data["checks"]["mt"]["ok"] is False
    assert data["checks"]["mt"]["issues"] == ["MT sentence tokenizer unavailable for zh→en: missing stanza model"]


def test_real_pi5_media_coordinator_persists_recording_on_stop(mock_config, tmp_audio_file):
    coordinator = Pi5MediaCoordinator(config=mock_config)

    def _fake_capture_audio(*, config, prefix, stop_flag, output_path, max_duration):  # noqa: ARG001
        Path(output_path).write_bytes(tmp_audio_file.read_bytes())
        assert stop_flag is not None
        stop_flag.wait(timeout=0.05)
        return output_path

    with patch("audio.media_coordinator.capture_audio", side_effect=_fake_capture_audio):
        start_state = coordinator.start_recording()
        saved = coordinator.stop_recording()

    assert start_state["status"] == "recording"
    assert saved["id"] == 1
    assert saved["duration_seconds"] == 1.0
    manager = _recording_manager(mock_config)
    stored = manager.get_recording(1)
    assert stored is not None
    assert manager.get_audio_path(1) is not None
    assert coordinator.get_state() == {
        "status": "idle",
        "device": "plughw:2,0",
        "active_kind": None,
        "playback": None,
        "recording": None,
        "error": None,
    }


def test_real_pi5_media_coordinator_keeps_speech_input_captures_out_of_standalone_recordings(
    mock_config,
    tmp_audio_file,
):
    coordinator = Pi5MediaCoordinator(config=mock_config)

    def _fake_capture_audio(*, config, prefix, stop_flag, output_path, max_duration):  # noqa: ARG001
        Path(output_path).write_bytes(tmp_audio_file.read_bytes())
        assert stop_flag is not None
        stop_flag.wait(timeout=0.05)
        return output_path

    with patch("audio.media_coordinator.capture_audio", side_effect=_fake_capture_audio):
        coordinator.start_recording(category="speech_input")
        saved = coordinator.stop_recording()

    manager = _recording_manager(mock_config)
    assert manager.list_recordings() == []
    assert [item["id"] for item in manager.list_recordings(category=None)] == [saved["id"]]
    assert manager.get_audio_path(saved["id"]) is not None


def test_real_pi5_media_coordinator_enforces_standalone_recording_limit(mock_config, tmp_audio_file):
    coordinator = Pi5MediaCoordinator(config=mock_config)

    def _fake_capture_audio(*, config, prefix, stop_flag, output_path, max_duration):  # noqa: ARG001
        Path(output_path).write_bytes(tmp_audio_file.read_bytes())
        assert stop_flag is not None
        stop_flag.wait(timeout=0.05)
        return output_path

    with patch("audio.media_coordinator.capture_audio", side_effect=_fake_capture_audio):
        for _ in range(6):
            coordinator.start_recording(category="standalone")
            coordinator.stop_recording()

    manager = _recording_manager(mock_config)
    items = manager.list_recordings(category="standalone")
    assert [item["id"] for item in items] == [2, 3, 4, 5, 6]
    assert manager.get_audio_path(1, category="standalone") is None


def test_real_pi5_media_coordinator_reports_recording_before_worker_runs(mock_config):
    coordinator = Pi5MediaCoordinator(config=mock_config)

    with patch("threading.Thread.start", autospec=True, return_value=None):
        start_state = coordinator.start_recording()
        snapshot = coordinator.get_state()

    assert start_state == {
        "status": "recording",
        "device": "plughw:2,0",
        "active_kind": "recording",
        "playback": None,
        "recording": {
            "started_at": start_state["recording"]["started_at"],
            "device": "plughw:2,0",
            "max_duration_seconds": 180,
            "pending_save": False,
        },
        "error": None,
    }
    assert snapshot == start_state


def test_real_pi5_media_coordinator_rolls_back_when_thread_start_fails(mock_config):
    coordinator = Pi5MediaCoordinator(config=mock_config)

    with patch("threading.Thread.start", autospec=True, side_effect=RuntimeError("thread boom")):
        with pytest.raises(MediaCoordinatorError, match="Pi5 recording failed to start: thread boom"):
            coordinator.start_recording()

    assert coordinator.get_state() == {
        "status": "idle",
        "device": "plughw:2,0",
        "active_kind": None,
        "playback": None,
        "recording": None,
        "error": None,
    }


def test_real_pi5_media_coordinator_blocks_immediate_restart_after_stop(mock_config, tmp_audio_file):
    coordinator = Pi5MediaCoordinator(config=mock_config)
    playback_proc = _FakePlaybackProcess()
    clock = {"now": 100.0}

    with (
        patch("audio.media_coordinator.play_wav", return_value=playback_proc),
        patch("audio.media_coordinator.time.monotonic", side_effect=lambda: clock["now"]),
        patch.object(Pi5MediaCoordinator, "_watch_playback", autospec=True, return_value=None),
    ):
        start_state = coordinator.start_playback(
            str(tmp_audio_file),
            mode_key="tts_zh_zh",
            history_id=1,
            audio_url="/api/history/1/artifacts/output_audio",
        )
        stop_state = coordinator.stop_playback()

        assert start_state["status"] == "playing"
        assert stop_state["status"] == "busy"
        with pytest.raises(MediaBusyError, match="Pi5 media is busy with playback"):
            coordinator.start_recording()

        clock["now"] = 100.36
        assert coordinator.get_state() == {
            "status": "idle",
            "device": "plughw:2,0",
            "active_kind": None,
            "playback": None,
            "recording": None,
            "error": None,
        }


def test_real_pi5_media_coordinator_blocks_immediate_restart_after_playback_finishes(mock_config, tmp_audio_file):
    coordinator = Pi5MediaCoordinator(config=mock_config)
    playback_proc = _FakePlaybackProcess()
    clock = {"now": 200.0}

    with (
        patch("audio.media_coordinator.play_wav", return_value=playback_proc),
        patch("audio.media_coordinator.time.monotonic", side_effect=lambda: clock["now"]),
        patch.object(Pi5MediaCoordinator, "_watch_playback", autospec=True, return_value=None),
    ):
        start_state = coordinator.start_playback(
            str(tmp_audio_file),
            mode_key="tts_en_en",
            history_id=2,
            audio_url="/api/history/2/artifacts/output_audio",
        )
        playback_proc.returncode = 0
        settled_state = coordinator.get_state()

        assert start_state["status"] == "playing"
        assert settled_state["status"] == "busy"
        with pytest.raises(MediaBusyError, match="Pi5 media is busy with playback"):
            coordinator.start_recording()

        clock["now"] = 200.36
        assert coordinator.get_state() == {
            "status": "idle",
            "device": "plughw:2,0",
            "active_kind": None,
            "playback": None,
            "recording": None,
            "error": None,
        }


def test_pi5_media_state_and_stop_routes_return_stable_payload(client, app):
    coordinator = app.extensions["pi5_media_coordinator"]
    coordinator.state_payload = {
        "status": "playing",
        "device": "plughw:2,0",
        "active_kind": "playback",
        "playback": {
            "mode_key": "tts_zh_zh",
            "history_id": 9,
            "audio_url": "/api/history/9/artifacts/output_audio",
            "wav_path": "E:/tmp/output.wav",
            "device": "plughw:2,0",
            "started_at": "2026-04-20T12:05:00Z",
            "pid": 1234,
        },
        "recording": None,
        "error": None,
    }
    expected_state = dict(coordinator.state_payload)

    state_resp = client.get("/api/pi5/media/state")
    stop_resp = client.post("/api/pi5/media/stop")

    assert state_resp.status_code == 200
    assert state_resp.get_json() == {"pi5_media": expected_state}
    assert stop_resp.status_code == 200
    assert stop_resp.get_json() == {
        "ok": True,
        "pi5_media": {
            "status": "idle",
            "device": "plughw:2,0",
            "active_kind": None,
            "playback": None,
            "recording": None,
            "error": None,
        },
    }


def test_pi5_media_and_recording_state_routes_share_same_coordinator_snapshot(client, app):
    coordinator = app.extensions["pi5_media_coordinator"]
    coordinator.state_payload = {
        "status": "busy",
        "device": "plughw:2,0",
        "active_kind": "playback",
        "playback": {
            "mode_key": "mt_tts_zh_en",
            "history_id": 11,
            "audio_url": "/api/history/11/artifacts/output_audio",
            "wav_path": "E:/tmp/output.wav",
            "device": "plughw:2,0",
            "started_at": "2026-04-20T12:06:00Z",
            "pid": 4567,
        },
        "recording": None,
        "error": None,
    }
    expected_state = dict(coordinator.state_payload)

    media_resp = client.get("/api/pi5/media/state")
    recording_resp = client.get("/api/pi5/recordings/state")

    assert media_resp.status_code == 200
    assert recording_resp.status_code == 200
    assert media_resp.get_json() == {"pi5_media": expected_state}
    assert recording_resp.get_json() == {"pi5_recording": expected_state}
    assert media_resp.get_json()["pi5_media"] == recording_resp.get_json()["pi5_recording"]


def test_pi5_recording_start_stop_and_state_routes_return_stable_payload(client, app):
    start_resp = client.post("/api/pi5/recordings/start")
    state_resp = client.get("/api/pi5/recordings/state")
    stop_resp = client.post("/api/pi5/recordings/stop")

    assert start_resp.status_code == 200
    assert start_resp.get_json() == {
        "pi5_recording": {
            "status": "recording",
            "device": "plughw:2,0",
            "active_kind": "recording",
            "playback": None,
            "recording": {
                "started_at": "2026-04-20T12:06:00Z",
                "device": "plughw:2,0",
                "max_duration_seconds": 180,
                "pending_save": False,
            },
            "error": None,
        }
    }
    assert state_resp.status_code == 200
    assert state_resp.get_json() == start_resp.get_json()
    assert stop_resp.status_code == 200
    assert stop_resp.get_json() == {
        "recording": {
            "id": 7,
            "created_at": "2026-04-20T12:07:00",
            "duration_seconds": 1.2,
            "audio_url": "/api/recordings/7/audio",
            "reuse": {"recording_id": 7},
        },
        "pi5_recording": {
            "status": "idle",
            "device": "plughw:2,0",
            "active_kind": None,
            "playback": None,
            "recording": None,
            "error": None,
        },
    }
    coordinator = app.extensions["pi5_media_coordinator"]
    assert coordinator.recording_start_calls == ["standalone"]


def test_pi5_recording_start_returns_busy_payload_when_playback_is_active(client, app):
    coordinator = app.extensions["pi5_media_coordinator"]
    coordinator.recording_start_error = MediaBusyError("Pi5 media is busy with playback")
    coordinator.state_payload = {
        "status": "playing",
        "device": "plughw:2,0",
        "active_kind": "playback",
        "playback": {"mode_key": "tts_zh_zh"},
        "recording": None,
        "error": None,
    }

    resp = client.post("/api/pi5/recordings/start")

    assert resp.status_code == 409
    assert resp.get_json() == {
        "error": "Pi5 media is busy with playback",
        "pi5_recording": {
            "status": "busy",
            "device": "plughw:2,0",
            "active_kind": "playback",
            "playback": {"mode_key": "tts_zh_zh"},
            "recording": None,
            "error": None,
            "requested_action": "recording",
        },
    }


def test_pi5_recording_stop_surfaces_failure_state(client, app):
    coordinator = app.extensions["pi5_media_coordinator"]
    coordinator.recording_stop_error = MediaCoordinatorError("Pi5 recording did not finish cleanly")
    coordinator.state_payload = {
        "status": "error",
        "device": "plughw:2,0",
        "active_kind": None,
        "playback": None,
        "recording": {
            "started_at": "2026-04-20T12:06:00Z",
            "device": "plughw:2,0",
            "max_duration_seconds": 180,
            "pending_save": True,
        },
        "error": "Pi5 recording did not finish cleanly",
    }

    resp = client.post("/api/pi5/recordings/stop")

    assert resp.status_code == 500
    assert resp.get_json() == {
        "error": "Pi5 recording did not finish cleanly",
        "pi5_recording": coordinator.state_payload,
    }


def test_real_pi5_media_coordinator_keeps_public_state_shape_stable_while_nested_devices_remain_specific(
    mock_config,
    tmp_audio_file,
):
    coordinator = Pi5MediaCoordinator(config=mock_config)
    playback_proc = _FakePlaybackProcess()

    with (
        patch("audio.media_coordinator.play_wav", return_value=playback_proc),
        patch.object(Pi5MediaCoordinator, "_watch_playback", autospec=True, return_value=None),
    ):
        playback_state = coordinator.start_playback(
            str(tmp_audio_file),
            mode_key="tts_zh_zh",
            history_id=3,
            audio_url="/api/history/3/artifacts/output_audio",
        )

    base_state = coordinator.get_state()
    assert "playback_device" not in base_state
    assert "record_device" not in base_state
    assert playback_state["device"] == "plughw:2,0"
    assert playback_state["playback"]["device"] == "plughw:2,0"

    recording_coordinator = Pi5MediaCoordinator(config=mock_config)

    with patch("threading.Thread.start", autospec=True, return_value=None):
        recording_state = recording_coordinator.start_recording()

    assert "playback_device" not in recording_state
    assert "record_device" not in recording_state
    assert recording_state["device"] == "plughw:2,0"
    assert recording_state["recording"]["device"] == "plughw:2,0"


def test_index_uses_task_header_without_breadcrumb(client):
    html = _get_index_html(client)
    assert 'id="app-task-header"' in html
    assert 'id="task-header-direction"' in html
    assert 'id="app-breadcrumb"' not in html
    assert 'id="active-mode-key"' not in html


def test_index_uses_workbench_layout_without_control_panel(client):
    html = _get_index_html(client)
    assert 'id="app-shell-grid"' in html
    assert 'workbench-grid' in html
    assert 'id="app-control-panel"' not in html
    assert 'id="app-input-panel"' in html
    assert 'id="input-panel-caption"' in html
    assert 'id="mode-picker-label"' in html
    assert 'id="app-output-panel"' in html
    assert 'id="app-history-panel"' in html
    assert 'id="text-flow-status"' in html


def test_index_workbench_layout_contract_keeps_output_primary_and_history_bottom(client):
    html = _get_index_html(client)

    assert re.search(
        r"\.workbench-grid\s*\{.*?"
        r"grid-template-columns:\s*minmax\(0,\s*0\.42fr\)\s+minmax\(0,\s*0\.58fr\);"
        r".*?grid-template-areas:\s*'input output'\s*'history history';"
        r".*?\}",
        html,
        flags=re.S,
    )
    assert re.search(r"#app-input-panel\s*\{\s*grid-area:\s*input;\s*\}", html)
    assert re.search(r"#app-output-panel\s*\{\s*grid-area:\s*output;\s*\}", html)
    assert re.search(r"#app-history-panel\s*\{\s*grid-area:\s*history;\s*\}", html)
    assert re.search(
        r"@media \(max-width:\s*980px\)\s*\{.*?"
        r"\.workbench-grid\s*\{.*?"
        r"grid-template-areas:\s*'input'\s*'output'\s*'history';"
        r".*?\}",
        html,
        flags=re.S,
    )


def test_index_input_panel_contract_integrates_mode_picker_and_actions(client):
    html = _get_index_html(client)

    assert re.search(
        r'<section id="app-input-panel" class="shell-card" aria-labelledby="input-panel-title">.*?'
        r'<p id="input-panel-caption" class="section-caption" data-i18n="panel.input_caption"></p>.*?'
        r'<div id="mode-picker-block" class="mode-picker-block">.*?'
        r'<p id="mode-picker-label" class="field-label" data-i18n="text.mode_picker"></p>.*?'
        r'<div id="text-mode-picker" class="mode-picker" role="tablist" data-i18n-attr="aria-label:a11y.mode_picker"></div>.*?'
        r'<div id="input-actions" class="panel-stack input-actions">.*?'
        r'id="text-start-button".*?'
        r'id="text-reset-button".*?'
        r'id="text-save-button".*?'
        r'id="text-flow-status"'
        r'.*?</section>',
        html,
        flags=re.S,
    )


def test_index_task_header_contract_surfaces_task_direction_and_human_label(client):
    html = _get_index_html(client)
    script = _get_index_script(html)

    assert 'id="task-header-direction"' in html
    assert re.search(
        r"function renderTaskHeader\(\)\s*\{.*?"
        r"const direction = document\.getElementById\('task-header-direction'\);"
        r".*?direction\.hidden = true;"
        r".*?direction\.textContent = '';"
        r".*?if \(state\.activeKind === 'recordings'\) \{.*?return;\s*\}"
        r".*?if \(state\.activeKind === 'history'\) \{.*?return;\s*\}"
        r".*?if \(state\.pendingReuseRecording\) \{.*?caption\.textContent = getPendingReusePrompt\(state\.pendingReuseRecording\.id\);.*?return;\s*\}"
        r".*?title\.textContent = activeMode \? getTaskLabel\(activeMode\) : '--';"
        r".*?if \(!activeMode\) \{.*?caption\.textContent = getMessage\('task_header\.pick_direction'\);.*?return;\s*\}"
        r".*?direction\.hidden = false;"
        r".*?direction\.textContent = getDirectionLabel\(activeMode\);"
        r".*?caption\.textContent = getLeafLabel\(activeMode\.mode_key\);"
        r".*?\}",
        script,
        flags=re.S,
    )


def test_index_task_header_status_contract_uses_flow_state_while_footer_tracks_health(client):
    html = _get_index_html(client)
    script = _get_index_script(html)

    assert re.search(
        r"function renderStatus\(\)\s*\{"
        r"\s*const taskStatus = document\.getElementById\('task-header-status'\);"
        r"\s*const taskStatusLabel = document\.getElementById\('task-header-status-label'\);"
        r"\s*const taskLabelKey = state\.flowStatus\.tone === 'processing'"
        r"\s*\?\s*'status\.processing'"
        r"\s*:\s*state\.flowStatus\.tone === 'error'"
        r"\s*\?\s*'status\.error'"
        r"\s*:\s*'status\.ready';"
        r"\s*taskStatusLabel\.textContent = getMessage\(taskLabelKey\);"
        r"\s*taskStatus\.classList\.toggle\('is-processing', state\.flowStatus\.tone === 'processing'\);"
        r"\s*taskStatus\.classList\.toggle\('is-error', state\.flowStatus\.tone === 'error'\);"
        r"\s*const footerLabelKey = state\.healthOk \? 'status\.ready' : 'status\.error';"
        r"\s*document\.getElementById\('footer-status-label'\)\.textContent = getMessage\(footerLabelKey\);"
        r"\s*document\.getElementById\('footer-status'\)\.classList\.toggle\('is-error', !state\.healthOk\);"
        r"\s*\}",
        script,
        flags=re.S,
    )


def test_index_result_narrative_contract_keeps_final_result_first_and_actions_adjacent(client):
    script = _get_index_script(_get_index_html(client))

    assert re.search(
        r"function buildResultNarrative\(mode, sourceText, outputText, inputAudioUrl, outputAudioUrl\)\s*\{.*?"
        r"if \(outputAudioUrl\) \{.*?labelKey: 'result\.label\.final_audio'.*?\} else if \(outputText\) \{.*?labelKey: 'result\.label\.final_text'.*?\}"
        r".*?if \(outputAudioUrl && outputText\) \{.*?labelKey: 'result\.label\.target_text'.*?\}"
        r".*?if \(inputAudioUrl && sourceText && sourceText !== outputText\) \{.*?labelKey: 'result\.label\.transcript'.*?\}"
        r".*?if \(mode\.input_type === 'text' && sourceText\) \{.*?labelKey: 'result\.label\.original_text'.*?\}"
        r".*?if \(mode\.input_type === 'audio' && inputAudioUrl\) \{.*?labelKey: 'result\.label\.original_audio'.*?\}"
        r".*?return narrative;\s*\}",
        script,
        flags=re.S,
    )
    render_start = script.index("function renderResult() {")
    render_end = script.index("\n\n    function openHistoryView", render_start)
    render_body = script[render_start:render_end]

    for marker in (
        "const resultNodes = [sourceAudioBlock, sourceBlock, outputBlock, audioBlock, actionRow];",
        "const narrative = buildResultNarrative(activeMode, sourceText, outputText, inputAudioUrl, outputAudioUrl);",
        "if (!orderedChildren.includes(block)) {",
        "if (index === 0 && !actionRow.hidden && !orderedChildren.includes(actionRow)) {",
        "if (!orderedChildren.length && !actionRow.hidden) {",
        "resultNodes.forEach((node) => {",
        "result.append(...orderedChildren);",
    ):
        assert marker in render_body

    assert "result.replaceChildren(...orderedChildren);" not in render_body


def test_index_recording_reuse_contract_preserves_current_speech_direction_when_available(client):
    script = _get_index_script(_get_index_html(client))

    helper_start = script.index("function applyRecordingReuse(recording, mode) {")
    helper_end = script.index("\n\n    function resetResultForModeChange", helper_start)
    helper_body = script[helper_start:helper_end]
    assert "clearPendingReuseRecording();" in helper_body
    assert "state.activeModeKey = mode.mode_key;" in helper_body
    assert "setSpeechInputSource({" in helper_body
    assert "setFlowStatus('speech.recording_selected', 'ready'" in helper_body

    recordings_start = script.index("function renderRecordingsList() {")
    recordings_end = script.index("\n\n    function renderInputPanel()", recordings_start)
    recordings_body = script[recordings_start:recordings_end]
    assert "const currentMode = getActiveMode();" in recordings_body
    assert "if (isSpeechReuseMode(currentMode)) {" in recordings_body
    assert "applyRecordingReuse(recording, currentMode);" in recordings_body
    assert "state.pendingReuseRecording = {" in recordings_body


def test_index_recordings_view_contract_exposes_start_finish_and_back_controls(client):
    html = _get_index_html(client)
    script = _get_index_script(html)

    assert 'id="recordings-back-button"' in html
    assert 'id="mode-picker-block"' in html
    assert 'id="input-actions"' in html
    assert 'id="speech-input-label"' in html
    assert 'id="speech-recordings-label"' in html
    assert re.search(
        r"function renderViewVisibility\(\)\s*\{.*?"
        r"const outputPanel = document\.getElementById\('app-output-panel'\);.*?"
        r"const recentHistoryPanel = document\.getElementById\('app-history-panel'\);.*?"
        r"const isRecordingsView = state\.activeKind === 'recordings';.*?"
        r"shellGrid\.classList\.toggle\('is-recordings-view', isRecordingsView\);.*?"
        r"outputPanel\.hidden = isRecordingsView;.*?"
        r"recentHistoryPanel\.hidden = isRecordingsView;",
        script,
        flags=re.S,
    )
    assert re.search(
        r"function renderInputPanel\(\)\s*\{.*?"
        r"const isRecordingsView = state\.activeKind === 'recordings';.*?"
        r"const isSpeechSurface = isSpeech \|\| isRecordingsView;.*?"
        r"const inputPanelTitle = document\.getElementById\('input-panel-title'\);.*?"
        r"const inputPanelCaption = document\.getElementById\('input-panel-caption'\);.*?"
        r"modePickerBlock\.hidden = state\.activeKind !== 'group';.*?"
        r"inputActions\.hidden = isRecordingsView;.*?"
        r"speechSection\.hidden = !isSpeechSurface;.*?"
        r"inputPanelTitle\.textContent = getMessage\(isRecordingsView \? 'recordings\.panel_title' : 'panel\.input'\);.*?"
        r"inputPanelCaption\.textContent = getMessage\(isRecordingsView \? 'recordings\.panel_caption' : 'panel\.input_caption'\);.*?"
        r"speechRecordButton\.textContent = isRecordingsView \? getMessage\('recordings\.start'\) : getMessage\('speech\.record_start'\);.*?"
        r"speechStopButton\.textContent = isRecordingsView \? getMessage\('recordings\.finish'\) : getMessage\('speech\.record_stop'\);.*?"
        r"speechRecordButton\.hidden = isRecordingsView \? pi5RecordingActive : false;.*?"
        r"speechStopButton\.hidden = isRecordingsView \? !pi5RecordingActive : false;.*?"
        r"recordingsBackButton\.hidden = !isRecordingsView;",
        script,
        flags=re.S,
    )


def test_index_recordings_view_handlers_allow_recording_without_active_conversion_mode(client):
    script = _get_index_script(_get_index_html(client))

    record_start = script.index("async function handleRecordStart() {")
    record_stop = script.index("\n\n    async function handleRecordStop()", record_start)
    start_body = script[record_start:record_stop]
    assert "const recordingsView = state.activeKind === 'recordings';" in start_body
    assert "if (isPi5RecordingActive() || (!recordingsView && !isSpeechMode(activeMode))) {" in start_body
    assert "setFlowStatus('recordings.active', 'processing');" in start_body

    stop_start = script.index("async function handleRecordStop() {")
    stop_end = script.index("\n\n    function waitForDuration", stop_start)
    stop_body = script[stop_start:stop_end]
    assert "const recordingsView = state.activeKind === 'recordings';" in stop_body
    assert "if (recordingsView) {" in stop_body
    assert "clearSpeechInputSource();" in stop_body
    assert "setFlowStatus('recordings.saved', 'ready'" in stop_body


def test_index_recordings_view_contract_uses_recording_menu_copy_instead_of_reuse_copy(client):
    script = _get_index_script(_get_index_html(client))

    recordings_start = script.index("function renderRecordingsList() {")
    recordings_end = script.index("\n\n    function getRecordingsViewStatus()", recordings_start)
    recordings_body = script[recordings_start:recordings_end]
    assert "const isRecordingsView = state.activeKind === 'recordings';" in recordings_body
    assert "getMessage(isRecordingsView ? 'recordings.empty' : 'speech.no_recordings')" in recordings_body
    assert "getMessage(isRecordingsView ? 'recordings.download' : 'text.download_audio')" in recordings_body
    assert "getMessage('recordings.delete')" in recordings_body
    assert "handleDeleteRecording(recording.id)" in recordings_body

    input_start = script.index("function renderInputPanel() {")
    input_end = script.index("\n\n    function renderShell()", input_start)
    input_body = script[input_start:input_end]
    assert "const speechInputLabel = document.getElementById('speech-input-label');" in input_body
    assert "speechInputLabel.textContent = getMessage(isRecordingsView ? 'recordings.controls_label' : 'speech.input_label');" in input_body
    assert "const recordingsLabel = document.getElementById('speech-recordings-label');" in input_body
    assert "recordingsLabel.textContent = getMessage(isRecordingsView ? 'recordings.recent_label' : 'speech.recordings_label');" in input_body

    delete_start = script.index("async function handleDeleteRecording(recordId) {")
    delete_end = script.index("\n\n    async function loadRecordings()", delete_start)
    delete_body = script[delete_start:delete_end]
    assert "window.confirm(getMessage('recordings.delete_confirm'))" in delete_body
    assert "await fetchJson(`/api/recordings/${recordId}`" in delete_body
    assert "setFlowStatus('recordings.delete_success', 'ready'" in delete_body


@pytest.mark.parametrize(
    ("mode_key", "group_key"),
    [
        ("asr_mt_zh_en", "cross_speech_to_text"),
        ("asr_mt_en_zh", "cross_speech_to_text"),
        ("asr_mt_tts_zh_en", "cross_speech_to_speech"),
        ("asr_mt_tts_en_zh", "cross_speech_to_speech"),
    ],
)
def test_index_recording_reuse_contract_covers_cross_speech_modes(client, mode_key, group_key):
    script = _get_index_script(_get_index_html(client))

    assert f"'{mode_key}'" in script

    helper_start = script.index("function applyRecordingReuse(recording, mode) {")
    helper_end = script.index("\n\n    function resetResultForModeChange", helper_start)
    helper_body = script[helper_start:helper_end]
    assert "state.activeGroupKey = mode.group_key;" in helper_body
    assert "state.activeModeKey = mode.mode_key;" in helper_body

    mode_lookup = f"state.activeGroupKey = '{group_key}';"
    assert mode_lookup not in helper_body


def test_index_flow_copy_contract_uses_task_language_helpers(client):
    script = _get_index_script(_get_index_html(client))

    assert "function getTargetResultLabel(mode)" in script
    assert "function getTaskFlowMessage(mode, stageOrKey)" in script
    assert "function getResultPanelMessage(mode)" in script
    assert re.search(
        r"function setFlowStatus\(key, tone = 'info', raw = ''\)\s*\{"
        r"\s*if \(!raw && key\.startsWith\('flow\.'\)\) \{"
        r"\s*raw = getTaskFlowMessage\(getActiveMode\(\), key\);"
        r"\s*\}"
        r"\s*state\.flowStatus = \{ key, tone, raw \};",
        script,
        flags=re.S,
    )
    assert re.search(
        r"function describeSpeechSelection\(\)\s*\{.*?"
        r"const resultLabel = getTargetResultLabel\(activeMode\);"
        r".*?return getTaskFlowMessage\(activeMode, 'idle'\);"
        r".*?\}",
        script,
        flags=re.S,
    )
    assert re.search(
        r"function renderInputPanel\(\)\s*\{.*?"
        r"if \(isText && activeMode\) \{.*?outputCaption\.textContent = getResultPanelMessage\(activeMode\);.*?\} else if \(isSpeech\) \{.*?outputCaption\.textContent = getResultPanelMessage\(activeMode\);"
        r".*?\}",
        script,
        flags=re.S,
    )


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


def test_bootstrap_i18n_contains_required_shell_and_text_flow_keys(client):
    resp = client.get("/api/bootstrap")
    data = resp.get_json()

    required_keys = {
        "header.title",
        "header.user_settings",
        "header.help",
        "header.language_switch",
        "a11y.primary_navigation",
        "a11y.breadcrumb",
        "a11y.current_mode_summary",
        "a11y.current_task_header",
        "a11y.mode_picker",
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
        "panel.input",
        "panel.input_caption",
        "panel.control",
        "panel.output",
        "panel.history",
        "panel.history_pending",
        "panel.help",
        "panel.settings",
        "help.caption",
        "help.text_title",
        "help.text_desc",
        "help.speech_title",
        "help.speech_desc",
        "help.history_title",
        "help.history_desc",
        "help.settings_note",
        "settings.caption",
        "settings.locale_label",
        "settings.locale_hint",
        "settings.locale_zh",
        "settings.locale_en",
        "settings.current_view",
        "settings.constraints",
        "settings.max_record_seconds",
        "settings.max_history",
        "settings.max_recordings",
        "common.language.zh",
        "common.language.en",
        "common.input_type.text",
        "common.input_type.audio",
        "common.output_type.text",
        "common.output_type.audio",
        "task.text_to_speech",
        "task.speech_to_text",
        "task.text_to_text",
        "task.speech_to_speech",
        "task_header.current_task",
        "task_header.pick_direction",
        "task_header.recordings_caption",
        "flow.idle.text_to_speech",
        "flow.idle.text_to_text",
        "flow.idle.speech_to_text",
        "flow.idle.speech_to_speech",
        "flow.processing.text_to_speech",
        "flow.processing.text_to_text",
        "flow.processing.speech_to_text",
        "flow.processing.speech_to_speech",
        "flow.ready.text_to_speech",
        "flow.ready.text_to_text",
        "flow.ready.speech_to_text",
        "flow.ready.speech_to_speech",
        "result.caption.text_to_speech",
        "result.caption.text_to_text",
        "result.caption.speech_to_text",
        "result.caption.speech_to_speech",
        "result.empty.text",
        "result.empty.audio",
        "result.label.final_text",
        "result.label.final_audio",
        "result.label.target_text",
        "result.label.transcript",
        "result.label.original_text",
        "result.label.original_audio",
        "common.unit_seconds",
        "common.unit_sets",
        "history.recent_caption",
        "history.recent_loading",
        "history.recent_empty",
        "history.recent_failed",
        "history.failed",
        "history.view_all",
        "history.full_title",
        "history.full_caption",
        "history.loading",
        "history.empty",
        "history.refresh",
        "history.export",
        "history.open_item",
        "history.delete",
        "history.delete_confirm",
        "history.delete_success",
        "history.delete_failed",
        "history.manifest",
        "history.input_text",
        "history.output_text",
        "history.input_audio",
        "history.output_audio",
        "history.output_audio_only",
        "history.source_preview",
        "history.output_preview",
        "text.input_label",
        "text.upload_txt",
        "text.clear",
        "text.start",
        "text.reset",
        "text.save_input",
        "text.input_hint",
        "text.input_saved",
        "text.input_required",
        "text.result_empty",
        "text.result_source",
        "text.result_output",
        "text.result_audio",
        "text.copy_output",
        "text.download_audio",
        "text.processing",
        "text.result_ready",
        "text.speech_pending",
        "text.non_text_mode_pending",
        "text.mode_picker",
        "speech.input_label",
        "speech.upload_wav",
        "speech.record_start",
        "speech.record_stop",
        "speech.clear_audio",
        "speech.input_hint",
        "speech.source_audio",
        "speech.source_selected",
        "speech.input_required",
        "speech.processing",
        "speech.result_ready",
        "speech.save_recording",
        "speech.save_recording_success",
        "speech.save_recording_failed",
        "speech.recording_permission_denied",
        "speech.recording_unsupported",
        "speech.upload_invalid",
        "speech.upload_failed",
        "speech.recording_status_idle",
        "speech.recording_status_active",
        "speech.recording_status_ready",
        "speech.recordings_label",
        "speech.recordings_loading",
        "speech.recordings_failed",
        "speech.no_recordings",
        "speech.use_recording",
        "speech.recording_selected",
        "speech.pi5_media_label",
        "speech.pi5_media_idle",
        "speech.pi5_media_recording",
        "speech.pi5_media_playing",
        "speech.pi5_media_busy",
        "speech.pi5_media_error_prefix",
        "speech.pi5_stop_playback",
        "speech.pi5_playback_stopped",
        "speech.pi5_playback_stop_failed",
        "speech.pi5_recording_starting",
        "speech.pi5_recording_saved",
        "speech.pi5_recording_failed",
        "speech.pi5_input_archive_hint",
        "speech.pi5_output_playback_hint",
        "recordings.start",
        "recordings.finish",
        "recordings.back_to_main",
        "recordings.hint",
        "recordings.idle",
        "recordings.active",
        "recordings.saved",
        "recordings.empty",
        "recordings.recent_label",
        "recordings.download",
        "recordings.delete",
        "recordings.delete_confirm",
        "recordings.delete_success",
        "recordings.delete_failed",
        "recordings.panel_title",
        "recordings.panel_caption",
        "recordings.controls_label",
    }

    assert set(data["i18n"].keys()) == {"zh-CN", "en-US"}
    for locale in ("zh-CN", "en-US"):
        messages = data["i18n"][locale]
        assert required_keys <= set(messages.keys())
        assert all(isinstance(value, str) and value for value in messages.values())


def test_bootstrap_i18n_contains_mode_labels_for_all_leaf_modes(client):
    resp = client.get("/api/bootstrap")
    data = resp.get_json()

    for locale in ("zh-CN", "en-US"):
        messages = data["i18n"][locale]
        for mode in list_mode_definitions():
            key = f"mode.{mode.mode_key}"
            assert key in messages
            assert isinstance(messages[key], str) and messages[key]


def test_bootstrap_i18n_keeps_bilingual_labels_human_readable(client):
    resp = client.get("/api/bootstrap")
    data = resp.get_json()

    zh = data["i18n"]["zh-CN"]
    en = data["i18n"]["en-US"]

    assert zh["header.title"] == "语音文本处理中心"
    assert zh["nav.same_text_to_speech"] == "同语·文字→语音"
    assert zh["task.text_to_speech"] == "文字→语音"
    assert zh["panel.input_caption"] == "选择语言方向、准备输入内容，然后开始转换。"
    assert zh["task_header.current_task"] == "当前工作流"
    assert zh["task_header.pick_direction"] == "选择语言方向后开始"
    assert zh["task_header.recordings_caption"].startswith("可在这里开始 Pi5 本地录音")
    assert zh["flow.processing.text_to_speech"] == "正在生成目标语音，请稍候。"
    assert zh["flow.ready.speech_to_text"] == "目标文本已生成，可复制或继续核对；原始语音保留在下方供回听。"
    assert zh["result.caption.speech_to_speech"] == "这里会先显示最终语音结果，播放与下载操作紧随其后；中间文本与原始语音保留在后面供核对。"
    assert zh["result.empty.audio"] == "最终语音结果会优先显示在这里。"
    assert zh["result.label.target_text"] == "中间目标文本"
    assert zh["text.copy_output"] == "复制最终文本"
    assert zh["text.download_audio"] == "下载音频归档"
    assert zh["panel.input"] == "输入与操作"
    assert zh["panel.output"] == "输出结果"
    assert zh["speech.record_start"] == "开始录音"
    assert zh["recordings.finish"] == "输入完毕"
    assert zh["recordings.back_to_main"] == "返回主菜单"
    assert zh["recordings.empty"] == '当前还没有已保存的“录制音频”。'
    assert zh["recordings.recent_label"] == "最近录音"
    assert zh["recordings.panel_title"] == "录音菜单"
    assert zh["recordings.controls_label"] == "录音操作"
    assert zh["speech.input_hint"] == "浏览器只负责控制；请在 Pi5 麦克风旁开始/停止录音，或复用已保存的 Pi5 录音。"
    assert zh["help.speech_desc"] == "在语音输入模式中，浏览器只负责控制；请在 Pi5 麦克风旁录音、复用录音库中的 Pi5 录音，并在 Pi5 侧收听播放。"
    assert zh["speech.pi5_media_label"] == "Pi5 设备状态"
    assert zh["speech.pi5_stop_playback"] == "停止 Pi5 播放"
    assert zh["speech.pi5_output_playback_hint"] == "输出 WAV 已交给 Pi5 本地 ALSA 播放；浏览器仅提供下载归档。"
    assert "?" not in zh["flow.ready.speech_to_text"]

    assert en["header.language_switch"] == "中文"
    assert en["a11y.current_task_header"] == "Current task header"
    assert en["panel.input_caption"] == "Choose a language direction, prepare the input, then start the conversion."
    assert en["task_header.current_task"] == "Current workflow"
    assert en["task_header.pick_direction"] == "Choose a language direction to begin"
    assert en["task_header.recordings_caption"].startswith("Start a Pi5 local recording here")
    assert en["flow.processing.text_to_speech"] == "Generating the final audio result. Please wait."
    assert en["flow.ready.speech_to_text"] == "The final text result is ready to copy or review, with the source audio kept below for replay."
    assert en["result.caption.speech_to_speech"] == "The final audio result appears first, with play and download actions right after it; intermediate text and the source audio stay after it for review."
    assert en["result.empty.audio"] == "The final audio result will appear here first."
    assert en["result.label.target_text"] == "Intermediate target text"
    assert en["text.copy_output"] == "Copy final text"
    assert en["text.download_audio"] == "Download audio archive"
    assert en["panel.input"] == "Input & actions"
    assert en["recordings.finish"] == "Finish input"
    assert en["recordings.back_to_main"] == "Back to main menu"
    assert en["recordings.empty"] == "No saved recordings are available in the recordings folder yet."
    assert en["recordings.recent_label"] == "Recent recordings"
    assert en["recordings.download"] == "Download recording"
    assert en["recordings.delete"] == "Delete recording"
    assert en["recordings.panel_title"] == "Recording menu"
    assert en["recordings.controls_label"] == "Recording controls"
    assert en["panel.output"] == "Results"
    assert en["speech.use_recording"] == "Use this recording"
    assert en["task.speech_to_text"] == "Speech→Text"
    assert en["speech.input_hint"] == "The browser is control-plane only. Start/stop recording near the Pi5 microphone, or reuse a saved Pi5 recording before you start."
    assert en["help.speech_desc"] == "In speech-input modes, the browser is control-plane only: record near the Pi5 microphone, reuse saved Pi5 recordings, and listen for playback on the Pi5 itself."
    assert en["speech.pi5_media_label"] == "Pi5 device state"
    assert en["speech.pi5_stop_playback"] == "Stop Pi5 playback"
    assert en["speech.pi5_output_playback_hint"] == "The output WAV has been handed to Pi5 local ALSA playback; the browser only exposes a download archive."
    assert en["history.full_title"] == "History management"
    assert en["history.export"] == "Export history"
    assert en["panel.settings"] == "Settings panel"
    assert en["settings.locale_en"] == "English UI"


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
            "source_text": "??",
            "output_text": output_text,
        },
    }

    with patch("api.conversion_routes.HistoryManager") as mock_mgr:
        mock_mgr.return_value.get_manifest.return_value = manifest
        resp = client.post(
            "/api/conversions/text",
            json={
                "mode_key": mode_key,
                "input_text": "??",
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
        "source_text": "??",
        "output_text": manifest["values"]["output_text"],
        "output_audio_url": "/api/history/12/artifacts/output_audio" if mode.output_type == "audio" else None,
    }
    app.config["PIPELINE_FN"].assert_called_once_with(
        mode_key,
        app.config["APP_CONFIG"],
        input_text="??",
        input_audio_path=None,
        playback=False,
    )


def test_pi5_recording_start_uses_speech_scope_for_translation_capture(client, app):
    coordinator = app.extensions["pi5_media_coordinator"]

    resp = client.post("/api/pi5/recordings/start", json={"scope": "speech"})

    assert resp.status_code == 200
    assert coordinator.recording_start_calls == ["speech_input"]


def test_text_conversion_triggers_pi5_playback_for_audio_output_modes(client, app, tmp_audio_file):
    mode_key = "tts_zh_zh"
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 12})
    manifest = {
        "id": 12,
        "mode_key": mode_key,
        "group_key": "same_text_to_speech",
        "source_lang": "zh",
        "target_lang": "zh",
        "created_at": "2026-04-20T12:00:00",
        "artifacts": {
            "input_text": "input_text.txt",
            "output_text": None,
            "input_audio": None,
            "output_audio": "output_audio.wav",
        },
        "values": {
            "source_text": "你好",
            "output_text": None,
        },
    }

    with patch("api.conversion_routes.HistoryManager") as mock_mgr:
        mock_mgr.return_value.get_manifest.return_value = manifest
        mock_mgr.return_value.get_artifact_path.return_value = tmp_audio_file

        resp = client.post(
            "/api/conversions/text",
            json={
                "mode_key": mode_key,
                "input_text": "你好",
            },
        )

    assert resp.status_code == 200
    coordinator = app.extensions["pi5_media_coordinator"]
    assert coordinator.start_calls == [
        {
            "wav_path": str(tmp_audio_file),
            "mode_key": "tts_zh_zh",
            "history_id": 12,
            "audio_url": "/api/history/12/artifacts/output_audio",
        }
    ]


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


def test_speech_conversion_returns_busy_state_when_pi5_playback_is_occupied(client, app, tmp_audio_file):
    mode_key = "asr_mt_tts_zh_en"
    coordinator = app.extensions["pi5_media_coordinator"]
    coordinator.start_error = MediaBusyError("Pi5 media is busy with playback")
    app.config["PIPELINE_FN"] = MagicMock(return_value={"history_id": 14})
    manifest = {
        "id": 14,
        "mode_key": mode_key,
        "group_key": "cross_speech_to_speech",
        "source_lang": "zh",
        "target_lang": "en",
        "created_at": "2026-04-20T12:01:00",
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
        mock_history_mgr.return_value.get_artifact_path.return_value = tmp_audio_file
        resp = client.post(
            "/api/conversions/speech",
            data={
                "mode_key": mode_key,
                "recording_id": "3",
            },
            content_type="multipart/form-data",
        )

    assert resp.status_code == 409
    assert resp.get_json() == {
        "error": "Pi5 media is busy with playback",
        "record": {
            "id": 14,
            "mode_key": mode_key,
            "group_key": "cross_speech_to_speech",
            "source_lang": "zh",
            "target_lang": "en",
            "created_at": "2026-04-20T12:01:00",
            "artifacts": {
                "input_text_url": None,
                "output_text_url": "/api/history/14/artifacts/output_text",
                "input_audio_url": "/api/history/14/artifacts/input_audio",
                "output_audio_url": "/api/history/14/artifacts/output_audio",
            },
        },
        "result": {
            "source_text": "你好",
            "output_text": "Hello",
            "output_audio_url": "/api/history/14/artifacts/output_audio",
        },
        "pi5_media": {
            "status": "busy",
            "device": "plughw:2,0",
            "active_kind": None,
            "playback": None,
            "recording": None,
            "error": None,
            "requested_action": "playback",
        },
    }


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


def test_speech_conversion_rejects_upload_without_filename(client):
    resp = client.post(
        "/api/conversions/speech",
        data={
            "mode_key": "asr_zh_zh",
            "input_audio": (io.BytesIO(b"fake"), ""),
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "input_audio filename is required"


def test_speech_conversion_rejects_non_wav_upload_with_stable_error(client, app):
    app.config["PIPELINE_FN"] = MagicMock()

    resp = client.post(
        "/api/conversions/speech",
        data={
            "mode_key": "asr_mt_zh_en",
            "input_audio": (io.BytesIO(b"not-a-wav"), "input.wav"),
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "input_audio must be a valid WAV file"
    app.config["PIPELINE_FN"].assert_not_called()


def test_speech_conversion_rejects_zero_byte_wav_upload(client, app):
    app.config["PIPELINE_FN"] = MagicMock()

    resp = client.post(
        "/api/conversions/speech",
        data={
            "mode_key": "asr_mt_zh_en",
            "input_audio": (io.BytesIO(b""), "empty.wav"),
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "input_audio must be a valid WAV file"
    app.config["PIPELINE_FN"].assert_not_called()


def test_speech_conversion_rejects_upload_longer_than_max_record_seconds(client, app, long_tmp_audio_file, mock_config):
    app.config["PIPELINE_FN"] = MagicMock()

    with long_tmp_audio_file.open("rb") as handle:
        resp = client.post(
            "/api/conversions/speech",
            data={
                "mode_key": "asr_mt_zh_en",
                "input_audio": (handle, "too-long.wav"),
            },
            content_type="multipart/form-data",
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == _duration_limit_error(mock_config)
    app.config["PIPELINE_FN"].assert_not_called()


def test_stage_browser_wav_upload_cleans_temp_file_on_invalid_input(monkeypatch, tmp_path):
    created_paths: list[Path] = []

    class _FakeNamedTemporaryFile:
        def __init__(self, path: Path) -> None:
            self.name = str(path)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001 - context manager test seam
            return False

    def _fake_named_temporary_file(*, suffix: str, delete: bool):  # noqa: ARG001
        path = tmp_path / "bad-upload.wav"
        created_paths.append(path)
        return _FakeNamedTemporaryFile(path)

    monkeypatch.setattr("api.audio_ingest.tempfile.NamedTemporaryFile", _fake_named_temporary_file)

    upload = FileStorage(stream=io.BytesIO(b"not-a-wav"), filename="input.wav")

    with pytest.raises(AudioIngressError, match="input_audio must be a valid WAV file"):
        stage_browser_wav_upload(upload)

    assert created_paths == [tmp_path / "bad-upload.wav"]
    assert created_paths[0].exists() is False


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


def _post_recording_create(client, input_audio) -> object:
    data = {} if input_audio is None else {"input_audio": input_audio}
    return client.post("/api/recordings", data=data, content_type="multipart/form-data")


def _duration_limit_error(mock_config: dict) -> str:
    return f"input_audio duration must not exceed {mock_config['audio']['max_record_duration']} seconds"


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


def test_create_recording_accepts_wav_upload_and_returns_frozen_item(client, mock_config, tmp_audio_file):
    with tmp_audio_file.open("rb") as handle:
        resp = _post_recording_create(client, (handle, "recording.wav"))

    assert resp.status_code == 200
    assert resp.get_json() == {
        "recording": {
            "id": 1,
            "created_at": ANY,
            "duration_seconds": 1.0,
            "audio_url": "/api/recordings/1/audio",
            "reuse": {"recording_id": 1},
        }
    }

    manager = _recording_manager(mock_config)
    stored = manager.get_recording(1)
    assert stored is not None
    assert stored["duration_seconds"] == 1.0

    list_resp = client.get("/api/recordings")
    assert list_resp.status_code == 200
    assert list_resp.get_json()["items"] == [resp.get_json()["recording"]]

    audio_resp = client.get("/api/recordings/1/audio")
    assert audio_resp.status_code == 200
    assert audio_resp.mimetype == "audio/wav"
    assert "attachment;" in audio_resp.headers["Content-Disposition"]
    assert "recording_001.wav" in audio_resp.headers["Content-Disposition"]
    assert audio_resp.data == tmp_audio_file.read_bytes()


def test_create_recording_requires_input_audio(client):
    resp = _post_recording_create(client, None)

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "input_audio is required"


def test_create_recording_rejects_upload_without_filename(client):
    resp = _post_recording_create(client, (io.BytesIO(b"fake"), ""))

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "input_audio filename is required"


def test_create_recording_rejects_non_wav_upload_with_stable_error(client):
    resp = _post_recording_create(client, (io.BytesIO(b"not-a-wav"), "recording.wav"))

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "input_audio must be a valid WAV file"


def test_create_recording_rejects_upload_longer_than_max_record_seconds(client, long_tmp_audio_file, mock_config):
    with long_tmp_audio_file.open("rb") as handle:
        resp = _post_recording_create(client, (handle, "too-long.wav"))

    assert resp.status_code == 400
    assert resp.get_json()["error"] == _duration_limit_error(mock_config)


def test_create_recording_returns_500_when_storage_save_fails(client, tmp_audio_file):
    with patch("api.recording_routes.RecordingManager") as mock_manager:
        mock_manager.return_value.save_recording.side_effect = OSError("disk full")
        with tmp_audio_file.open("rb") as handle:
            resp = _post_recording_create(client, (handle, "recording.wav"))

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "failed to save recording"


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


def test_list_recordings_excludes_translation_scoped_captures_from_recordings_menu(client, mock_config, tmp_audio_file):
    manager = _recording_manager(mock_config)
    standalone = manager.save_recording(str(tmp_audio_file), category="standalone")
    manager.save_recording(str(tmp_audio_file), category="speech_input")

    resp = client.get("/api/recordings")

    assert resp.status_code == 200
    assert resp.get_json()["items"] == [
        {
            "id": standalone["id"],
            "created_at": standalone["created_at"],
            "duration_seconds": standalone["duration_seconds"],
            "audio_url": f"/api/recordings/{standalone['id']}/audio",
            "reuse": {"recording_id": standalone["id"]},
        }
    ]



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


def test_get_recording_audio_serves_files_when_storage_config_uses_relative_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_audio_file: Path,
):
    monkeypatch.chdir(tmp_path)
    relative_config = {
        "audio": {
            "device": "plughw:2,0",
            "sample_rate": 16000,
            "bit_depth": 16,
            "channels": 1,
            "max_record_duration": 180,
        },
        "models": {
            "asr": {
                "zh_model_path": "models/data/vosk-model-small-cn-0.22",
                "en_model_path": "models/data/vosk-model-small-en-us-0.15",
            },
            "mt": {
                "package_path": "models/data/argos",
            },
            "tts": {
                "zh_model_path": "models/data/piper/zh_CN-huayan-medium.onnx",
                "en_model_path": "models/data/piper/en_US-lessac-medium.onnx",
            },
        },
        "storage": {
            "history_dir": "data/history",
            "recordings_dir": "data/recordings",
            "max_history": 5,
            "max_recordings": 5,
        },
        "api": {
            "host": "0.0.0.0",
            "port": 5000,
        },
        "logging": {
            "level": "INFO",
        },
    }

    with patch("api.app._run_startup_checks", return_value={"mt": {"ok": True, "issues": [], "package_dir": "models/data/argos"}}):
        flask_app = create_app(relative_config)
    flask_app.config["TESTING"] = True
    flask_app.extensions["pi5_media_coordinator"] = _StubPi5MediaCoordinator()
    recording_manager = RecordingManager(
        relative_config["storage"]["recordings_dir"],
        relative_config["storage"]["max_recordings"],
    )
    recording_manager.save_recording(str(tmp_audio_file))

    with flask_app.test_client() as relative_client:
        resp = relative_client.get("/api/recordings/1/audio")

    assert resp.status_code == 200
    assert resp.mimetype == "audio/wav"
    assert resp.data == tmp_audio_file.read_bytes()
