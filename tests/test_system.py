"""System-level contract tests for server entry and basic BS reachability."""

from __future__ import annotations

from pathlib import Path
import re
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


def _js_block_after(html: str, signature: str) -> str:
    start = html.index(signature)
    brace_start = html.index("{", start)
    depth = 0

    for index in range(brace_start, len(html)):
        char = html[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[brace_start + 1:index]

    raise AssertionError(f"unable to find closing brace for {signature!r}")


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
    assert "if (state.isSubmitting) {" in html
    assert "applyPi5MediaState(null);" not in html
    assert "navigator.mediaDevices?.getUserMedia" not in html
    assert 'id="speech-upload-input"' not in html
    assert 'id="speech-preview-player"' not in html
    assert 'id="result-source-audio-player"' not in html
    assert 'id="result-audio-player"' not in html


def test_root_route_keeps_view_switching_side_effect_free(client) -> None:
    html = client.get("/").get_data(as_text=True)
    change_active_view_body = _js_block_after(html, "function changeActiveView(kind, groupKey = state.activeGroupKey)")
    open_history_view_body = _js_block_after(html, "function openHistoryView(recordId = null)")

    assert "clearPendingReuseRecording();" in change_active_view_body
    assert "renderShell();" in change_active_view_body
    for forbidden in (
        "/api/pi5/",
        "fetchJson(",
        "syncPi5State(",
        "requestPi5PlaybackStop(",
        "handleRecordStart(",
        "handleRecordStop(",
    ):
        assert forbidden not in change_active_view_body
        assert forbidden not in open_history_view_body

    assert "state.history.focusId = recordId;" in open_history_view_body
    assert "changeActiveView('history');" in open_history_view_body


def test_root_route_locks_pi5_text_restart_contract(client) -> None:
    html = client.get("/").get_data(as_text=True)
    handle_start_body = _js_block_after(html, "async function handleStart()")

    refresh_match = re.search(r"await\s+\w+\('media',\s*\{\s*silent:\s*true\s*\}\);", handle_start_body)
    restart_match = re.search(r"const\s+\w+\s*=\s*await\s+\w+\(\);", handle_start_body)
    reject_match = re.search(r"if\s+\(!\w+\.ready\)\s*\{", handle_start_body)
    assert refresh_match is not None
    assert restart_match is not None
    assert reject_match is not None
    assert "setFlowStatus('', 'error'," in handle_start_body

    load_index = refresh_match.start()
    restart_index = restart_match.start()
    reject_index = reject_match.start()
    processing_index = handle_start_body.index("setFlowStatus(getTaskFlowKey(activeMode, 'processing'), 'processing');")
    submit_index = handle_start_body.index("await submitTextConversion(activeMode);")
    assert load_index < restart_index < reject_index < processing_index < submit_index


def test_root_route_removes_pr2_second_truth_markers(client) -> None:
    html = client.get("/").get_data(as_text=True)

    assert "preparePi5TextPlaybackRestart" not in html
    assert "state.isRecording" not in html


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
        "result.append(...orderedChildren);",
    ):
        assert marker in html


def test_root_route_keeps_result_skeleton_stable_for_repeat_text_to_speech_runs(client) -> None:
    html = client.get("/").get_data(as_text=True)
    render_result_body = _js_block_after(html, "function renderResult()")

    assert "const resultNodes = [sourceAudioBlock, sourceBlock, outputBlock, audioBlock, actionRow];" in render_result_body
    assert "result.replaceChildren(...orderedChildren);" not in render_result_body
    assert "result.append(...orderedChildren);" in render_result_body
    assert "sourceTextNode.textContent = '';" in render_result_body
    assert "outputTextNode.textContent = '';" in render_result_body
    assert "resultNodes.forEach((node) => {" in render_result_body
    assert "if (!orderedChildren.includes(node)) {" in render_result_body


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
