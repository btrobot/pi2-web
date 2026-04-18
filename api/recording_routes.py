"""Recording routes for frozen req1 recording contracts."""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, abort, current_app, jsonify, send_file

from storage.recordings import RecordingManager

logger = logging.getLogger(__name__)

recording_bp = Blueprint("recordings", __name__)


def _get_manager() -> RecordingManager:
    config = current_app.config["APP_CONFIG"]
    storage_cfg = config["storage"]
    return RecordingManager(
        recordings_dir=storage_cfg["recordings_dir"],
        max_recordings=storage_cfg["max_recordings"],
    )


def _error_response(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status_code


def _recording_item_dto(recording: dict[str, Any]) -> dict[str, Any]:
    recording_id = recording["id"]
    return {
        "id": recording_id,
        "created_at": recording["created_at"],
        "duration_seconds": recording["duration_seconds"],
        "audio_url": f"/api/recordings/{recording_id}/audio",
        "reuse": {"recording_id": recording_id},
    }


@recording_bp.route("/api/recordings", methods=["GET"])
def list_recordings() -> tuple[Response, int]:
    try:
        recordings = list(reversed(_get_manager().list_recordings()))[:5]
        return jsonify({"items": [_recording_item_dto(item) for item in recordings]}), 200
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to list recordings: error=%s", str(exc))
        return _error_response("failed to load recordings", 500)


@recording_bp.route("/api/recordings/<int:recording_id>/audio", methods=["GET"])
def get_recording_audio(recording_id: int) -> Response:
    try:
        path = _get_manager().get_audio_path(recording_id)
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to load recording audio: id=%d, error=%s", recording_id, str(exc))
        return _error_response("failed to load recording audio", 500)

    if path is None:
        abort(404, description="recording file not found")
    return send_file(path, mimetype="audio/wav")


@recording_bp.route("/api/recordings/<int:recording_id>", methods=["DELETE"])
def delete_recording(recording_id: int) -> tuple[Response, int]:
    try:
        deleted = _get_manager().delete_recording(recording_id)
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to delete recording: id=%d, error=%s", recording_id, str(exc))
        return _error_response("failed to delete recording", 500)

    if not deleted:
        return _error_response(f"recording {recording_id} not found", 404)

    return jsonify({"ok": True, "deleted_kind": "recording", "deleted_id": recording_id}), 200


@recording_bp.route("/api/recordings/export", methods=["GET"])
def export_recordings() -> Response:
    try:
        buf = _get_manager().export_contract()
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to export recordings: error=%s", str(exc))
        return _error_response("failed to export recordings", 500)

    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="recordings_export.zip",
    )
