"""System-level contract tests for server entry and basic BS reachability."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import pytest

import main
from api.app import create_app


@pytest.fixture()
def app(mock_config):
    flask_app = create_app(mock_config)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_root_route_is_reachable(client) -> None:
    resp = client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.content_type


def test_root_route_renders_req1_shell_landmarks(client) -> None:
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    for marker in (
        'id="app-shell"',
        'id="app-header"',
        'id="app-sidebar"',
        'id="app-main"',
        'id="app-shell-grid"',
        'id="app-task-header"',
        'id="task-header-direction"',
        'id="app-footer"',
        'id="app-input-panel"',
        'id="input-panel-caption"',
        'id="mode-picker-label"',
        'id="app-output-panel"',
        'id="app-history-panel"',
    ):
        assert marker in html
    assert 'id="app-control-panel"' not in html


def test_root_route_exposes_shell_navigation_and_header_controls(client) -> None:
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    assert html.count('data-group-key=') == 6
    assert html.count('data-nav-kind="recordings"') == 1
    assert html.count('data-nav-kind="history"') == 1
    assert 'id="header-settings-button"' in html
    assert 'id="header-help-button"' in html
    assert 'id="header-language-button"' in html
    assert 'id="app-help-panel"' in html
    assert 'id="app-settings-panel"' in html
    assert '/api/bootstrap' in html


def test_root_route_exposes_text_mode_controls(client) -> None:
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    for marker in (
        'id="text-mode-picker"',
        'id="text-input"',
        'id="text-upload-input"',
        'accept=".txt,text/plain"',
        'id="text-clear-button"',
        'id="text-start-button"',
        'id="text-reset-button"',
        'id="text-save-button"',
        'id="text-result"',
        'id="result-actions"',
        'id="text-copy-button"',
        'id="text-download-link"',
    ):
        assert marker in html

    assert '/api/conversions/text' in html
    assert "/api/translate" not in html
    assert "function isTextAudioMode(mode) {" in html
    assert "startButton.disabled = state.isSubmitting || (textAudioMode && pi5RecordingBusy);" in html
    assert "const readyForTextRestart = await preparePi5TextPlaybackRestart();" in html
    assert "if (isTextAudioMode(activeMode)) {" in html


def test_root_route_exposes_speech_mode_controls(client) -> None:
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    for marker in (
        'id="speech-input-section"',
        'id="speech-record-button"',
        'id="speech-stop-button"',
        'id="speech-clear-button"',
        'id="speech-recordings-list"',
        'id="pi5-media-panel"',
        'id="pi5-media-status"',
        'id="pi5-stop-playback-button"',
        'id="speech-source-status"',
        'id="result-source-audio-link"',
        'id="result-audio-link"',
    ):
        assert marker in html

    assert "/api/conversions/speech" in html
    assert "/api/recordings" in html
    assert "/api/pi5/recordings/start" in html
    assert "/api/pi5/recordings/stop" in html
    assert "/api/pi5/recordings/state" in html
    assert "/api/pi5/media/state" in html
    assert "/api/pi5/media/stop" in html
    assert "const PI5_RECORD_START_TIMEOUT_MS = 4000;" in html
    assert "const PI5_STATE_TIMEOUT_MS = 1500;" in html
    assert "const PI5_PLAYBACK_STOP_TIMEOUT_MS = 4500;" in html
    assert "const PI5_PLAYBACK_RESTART_TIMEOUT_MS = 5000;" in html
    assert "async function fetchJson(path, options = {}, { timeoutMs = 0 } = {})" in html
    assert "async function requestPi5PlaybackStop()" in html
    assert "async function waitForPi5PlaybackRestartWindow()" in html
    assert "async function preparePi5TextPlaybackRestart()" in html
    assert "if (state.isSubmitting) {" in html
    assert "await loadPi5RecordingState({ silent: true, timeoutMs: PI5_STATE_TIMEOUT_MS });" in html
    assert "if (recoveredState?.active_kind === 'recording') {" in html
    assert "return state.pi5Media;" in html
    assert "applyPi5MediaState(null);" not in html
    assert "loadPi5MediaState({ silent: true });" in html
    assert "function isPi5MediaBusy()" in html
    assert "await Promise.all([loadHistoryData(), loadPi5MediaState()]);" in html
    assert "if (isPi5MediaBusy()) {" in html
    assert "navigator.mediaDevices?.getUserMedia" not in html
    assert 'id="speech-upload-input"' not in html
    assert 'id="speech-preview-player"' not in html
    assert 'id="result-source-audio-player"' not in html
    assert 'id="result-audio-player"' not in html


def test_root_route_exposes_recording_reuse_mode_picker_contract(client) -> None:
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    assert "const SPEECH_REUSE_MODE_KEYS = [" in html
    for mode_key in (
        "asr_zh_zh",
        "asr_en_en",
        "asr_mt_zh_en",
        "asr_mt_en_zh",
        "asr_mt_tts_zh_en",
        "asr_mt_tts_en_zh",
    ):
        assert f"'{mode_key}'" in html

    assert "state.pendingReuseRecording = {" in html
    assert "getMessage('speech.use_recording')" in html
    assert "getPendingReusePrompt(" in html
    assert "formData.append('recording_id', String(state.speechInput.recordingId));" in html


def test_root_route_exposes_result_first_narrative_helpers(client) -> None:
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    for marker in (
        "function getTaskFlowKey(",
        "function getResultEmptyKey(",
        "function getTaskFlowMessage(",
        "function getResultPanelMessage(",
        "function buildResultNarrative(",
        "result.replaceChildren(...orderedChildren);",
    ):
        assert marker in html


def test_root_route_exposes_history_ui_controls(client) -> None:
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    for marker in (
        'id="recent-history-list"',
        'id="recent-history-count"',
        'id="history-view-all-button"',
        'id="history-export-link"',
        'id="history-full-section"',
        'id="history-refresh-button"',
        'id="history-full-export-link"',
        'id="history-full-list"',
    ):
        assert marker in html

    assert "/api/history/recent" in html
    assert "/api/history/export" in html
    assert "method: 'DELETE'" in html
    assert "function createActionLink(label, href, { download = false, newTab = true } = {})" in html
    assert "createActionLink(getMessage('text.download_audio'), url, { download: true, newTab: false })" in html
    assert "const isAudioArtifact = labelKey === 'history.input_audio' || labelKey === 'history.output_audio';" in html


def test_root_route_exposes_help_settings_and_locale_polish_controls(client) -> None:
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    for marker in (
        'id="help-panel-title"',
        'id="help-panel-list"',
        'id="settings-panel-title"',
        'id="settings-locale-zh"',
        'id="settings-locale-en"',
        'id="settings-current-view"',
        'id="settings-constraints-list"',
        'data-i18n-attr="aria-label:a11y.primary_navigation"',
        'data-i18n-attr="aria-label:a11y.current_task_header"',
        'data-i18n-attr="aria-label:a11y.mode_picker"',
    ):
        assert marker in html


def test_bootstrap_route_is_reachable(client) -> None:
    resp = client.get("/api/bootstrap")

    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {"app", "constraints", "modes", "i18n"}


def test_legacy_record_route_is_not_registered(app, client) -> None:
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/api/record" not in rules

    resp = client.post("/api/record")
    assert resp.status_code == 404


def test_legacy_translate_route_is_not_registered(app, client) -> None:
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    legacy_translate = "/api/" + "translate"

    assert legacy_translate not in rules

    resp = client.post(legacy_translate, json={"mode": 1, "text": "hello"})
    assert resp.status_code == 404


def test_main_defaults_to_server_mode(mock_config) -> None:
    with (
        patch("main._load_config", return_value=mock_config),
        patch("api.app.run_server") as run_server,
        patch("app.cli.run_cli") as run_cli,
        patch.object(sys, "argv", ["main.py"]),
    ):
        main.main()

    run_server.assert_called_once_with(mock_config)
    run_cli.assert_not_called()


def test_main_cli_flag_uses_debug_cli_path(mock_config) -> None:
    with (
        patch("main._load_config", return_value=mock_config),
        patch("api.app.run_server") as run_server,
        patch("app.cli.run_cli") as run_cli,
        patch.object(sys, "argv", ["main.py", "--cli"]),
    ):
        main.main()

    run_cli.assert_called_once_with(mock_config)
    run_server.assert_not_called()


def test_main_server_flag_remains_explicitly_supported(mock_config) -> None:
    with (
        patch("main._load_config", return_value=mock_config),
        patch("api.app.run_server") as run_server,
        patch("app.cli.run_cli") as run_cli,
        patch.object(sys, "argv", ["main.py", "--server"]),
    ):
        main.main()

    run_server.assert_called_once_with(mock_config)
    run_cli.assert_not_called()


def test_test_suite_does_not_depend_on_legacy_translate_endpoint_or_numeric_mode_key() -> None:
    legacy_translate = "/api/" + "translate"
    legacy_numeric_mode_key = "mode" + "_id"
    allowed_negative_assertion = f'assert "{legacy_translate}" not in html'
    current_file = Path(__file__)

    for path in Path("tests").glob("test_*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        translate_lines = [line.strip() for line in lines if legacy_translate in line]
        numeric_mode_lines = [line.strip() for line in lines if legacy_numeric_mode_key in line]

        if path.resolve() == current_file.resolve():
            assert translate_lines == [allowed_negative_assertion]
            assert numeric_mode_lines == []
            continue

        assert translate_lines == [], f"legacy endpoint dependency found in {path}"
        assert numeric_mode_lines == [], f"legacy numeric-mode dependency found in {path}"
