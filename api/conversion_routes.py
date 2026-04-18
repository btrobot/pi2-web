"""Forward conversion API routes for frozen req1 mode-key contracts."""

from __future__ import annotations

import logging
import os
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from api.audio_ingest import AudioIngressError, stage_browser_wav_upload
from app.mode_registry import list_mode_definitions
from storage.history import HistoryManager
from storage.recordings import RecordingManager

logger = logging.getLogger(__name__)

conversion_bp = Blueprint("conversions", __name__)

_TEXT_MODE_KEYS = frozenset(
    mode.mode_key
    for mode in list_mode_definitions()
    if mode.input_type == "text"
)
_SPEECH_MODE_KEYS = frozenset(
    mode.mode_key
    for mode in list_mode_definitions()
    if mode.input_type == "audio"
)
_ARTIFACT_KINDS = ("input_text", "output_text", "input_audio", "output_audio")


def _get_config() -> dict[str, Any]:
    return current_app.config["APP_CONFIG"]


def _get_max_record_seconds() -> int:
    return int(_get_config()["audio"]["max_record_duration"])


def _get_history_manager() -> HistoryManager:
    storage_cfg = _get_config()["storage"]
    return HistoryManager(
        history_dir=storage_cfg["history_dir"],
        max_records=storage_cfg["max_history"],
    )


def _get_recording_manager() -> RecordingManager:
    storage_cfg = _get_config()["storage"]
    return RecordingManager(
        recordings_dir=storage_cfg["recordings_dir"],
        max_recordings=storage_cfg["max_recordings"],
    )


def _artifact_url(record_id: int, artifact_kind: str, file_name: str | None) -> str | None:
    if not file_name:
        return None
    return f"/api/history/{record_id}/artifacts/{artifact_kind}"


def _error_response(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status_code


def _validate_mode_key(mode_key: str, supported_modes: frozenset[str]) -> str | None:
    if mode_key in supported_modes:
        return None

    supported = ", ".join(sorted(supported_modes))
    return f"mode_key must be one of: {supported}"


def _record_artifact_urls(manifest: dict[str, Any]) -> dict[str, str | None]:
    record_id = manifest["id"]
    artifacts = manifest.get("artifacts", {})
    return {
        f"{artifact_kind}_url": _artifact_url(record_id, artifact_kind, artifacts.get(artifact_kind))
        for artifact_kind in _ARTIFACT_KINDS
    }


def _record_dto(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": manifest["id"],
        "mode_key": manifest["mode_key"],
        "group_key": manifest["group_key"],
        "source_lang": manifest["source_lang"],
        "target_lang": manifest["target_lang"],
        "created_at": manifest["created_at"],
        "artifacts": _record_artifact_urls(manifest),
    }


def _result_dto(manifest: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    values = manifest.get("values", {})
    artifact_urls = _record_artifact_urls(manifest)
    return {
        "source_text": values.get("source_text", result.get("source_text")),
        "output_text": values.get("output_text", result.get("output_text")),
        "output_audio_url": artifact_urls["output_audio_url"],
    }


def _lookup_conversion_manifest(history_id: int, mode_key: str) -> dict[str, Any] | None:
    manifest = _get_history_manager().get_manifest(history_id)
    if manifest is None:
        logger.error("conversion history lookup failed: mode_key=%s, history_id=%s", mode_key, history_id)
        return None

    persisted_mode_key = manifest.get("mode_key")
    if persisted_mode_key != mode_key:
        logger.error(
            "conversion history mode mismatch: requested=%s, history_id=%s, persisted=%s",
            mode_key,
            history_id,
            persisted_mode_key,
        )
        return None

    return manifest


def _resolve_recording_audio_path(recording_id_raw: str) -> tuple[str | None, tuple[Response, int] | None]:
    try:
        recording_id = int(recording_id_raw)
    except ValueError:
        return None, _error_response("recording_id must be an integer", 400)

    recording_path = _get_recording_manager().get_audio_path(recording_id)
    if recording_path is None:
        return None, _error_response(f"recording_id {recording_id} not found", 404)

    return str(recording_path), None


def _run_conversion(
    *,
    mode_key: str,
    input_text: str | None = None,
    input_audio_path: str | None = None,
) -> tuple[dict[str, Any], int]:
    run_fn = current_app.config.get("PIPELINE_FN")
    if run_fn is None:
        return {"error": "conversion service unavailable"}, 503

    try:
        result = run_fn(
            mode_key,
            _get_config(),
            input_text=input_text,
            input_audio_path=input_audio_path,
            playback=False,
        )
    except Exception as exc:  # noqa: BLE001 - surface route failure as JSON
        logger.error("conversion failed: mode_key=%s, error=%s", mode_key, str(exc))
        return {"error": f"conversion failed: {exc}"}, 500

    if result.get("error"):
        return {"error": f"conversion failed: {result['error']}"}, 500

    history_id = result.get("history_id")
    if not isinstance(history_id, int):
        logger.error("conversion did not persist history: mode_key=%s", mode_key)
        return {"error": "conversion history was not persisted"}, 500

    manifest = _lookup_conversion_manifest(history_id, mode_key)
    if manifest is None:
        return {"error": "conversion record not found after persistence"}, 500

    return {
        "record": _record_dto(manifest),
        "result": _result_dto(manifest, result),
    }, 200


@conversion_bp.route("/api/conversions/text", methods=["POST"])
def convert_text() -> tuple[Any, int]:
    body = request.get_json(silent=True) or {}
    mode_key = body.get("mode_key", "")
    input_text = body.get("input_text")

    mode_error = _validate_mode_key(mode_key, _TEXT_MODE_KEYS)
    if mode_error:
        return _error_response(mode_error, 400)

    if not isinstance(input_text, str) or not input_text:
        return _error_response("input_text must be a non-empty string", 400)

    payload, status_code = _run_conversion(mode_key=mode_key, input_text=input_text)
    return jsonify(payload), status_code


@conversion_bp.route("/api/conversions/speech", methods=["POST"])
def convert_speech() -> tuple[Any, int]:
    mode_key = request.form.get("mode_key", "")
    upload = request.files.get("input_audio")
    recording_id_raw = request.form.get("recording_id", "").strip()
    has_upload = upload is not None
    has_recording_id = bool(recording_id_raw)

    mode_error = _validate_mode_key(mode_key, _SPEECH_MODE_KEYS)
    if mode_error:
        return _error_response(mode_error, 400)

    if has_upload == has_recording_id:
        return _error_response("provide exactly one of input_audio or recording_id", 400)

    temp_path: str | None = None
    input_audio_path: str | None = None

    try:
        if has_recording_id:
            input_audio_path, error_response = _resolve_recording_audio_path(recording_id_raw)
            if error_response:
                return error_response
        else:
            try:
                temp_path = stage_browser_wav_upload(upload, max_duration_seconds=_get_max_record_seconds())
            except AudioIngressError as exc:
                return _error_response(str(exc), 400)
            input_audio_path = temp_path

        payload, status_code = _run_conversion(
            mode_key=mode_key,
            input_audio_path=input_audio_path,
        )
        return jsonify(payload), status_code
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError as exc:  # pragma: no cover - defensive cleanup
                logger.warning("failed to delete temp upload: path=%s, error=%s", temp_path, str(exc))
