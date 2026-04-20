"""Pi5-local media state and control routes."""

from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify

from audio.media_coordinator import MediaBusyError, MediaCoordinatorError, Pi5MediaCoordinator
from api.recording_contracts import recording_item_dto

pi5_media_bp = Blueprint("pi5_media", __name__)


def _get_coordinator() -> Pi5MediaCoordinator:
    coordinator = current_app.extensions.get("pi5_media_coordinator")
    if coordinator is None:  # pragma: no cover - create_app always wires this
        raise RuntimeError("pi5 media coordinator is not configured")
    return coordinator


@pi5_media_bp.route("/api/pi5/media/state", methods=["GET"])
def get_pi5_media_state() -> tuple[Response, int]:
    return jsonify({"pi5_media": _get_coordinator().get_state()}), 200


@pi5_media_bp.route("/api/pi5/media/stop", methods=["POST"])
def stop_pi5_media() -> tuple[Response, int]:
    state = _get_coordinator().stop_playback()
    return jsonify({"ok": True, "pi5_media": state}), 200


@pi5_media_bp.route("/api/pi5/recordings/state", methods=["GET"])
def get_pi5_recording_state() -> tuple[Response, int]:
    return jsonify({"pi5_recording": _get_coordinator().get_state()}), 200


@pi5_media_bp.route("/api/pi5/recordings/start", methods=["POST"])
def start_pi5_recording() -> tuple[Response, int]:
    coordinator = _get_coordinator()
    try:
        state = coordinator.start_recording()
    except MediaBusyError as exc:
        return jsonify({
            "error": str(exc),
            "pi5_recording": coordinator.get_busy_state(requested_action="recording"),
        }), 409
    except MediaCoordinatorError as exc:
        return jsonify({"error": f"Pi5 recording failed to start: {exc}"}), 500

    return jsonify({"pi5_recording": state}), 200


@pi5_media_bp.route("/api/pi5/recordings/stop", methods=["POST"])
def stop_pi5_recording() -> tuple[Response, int]:
    coordinator = _get_coordinator()
    try:
        recording = coordinator.stop_recording()
    except MediaCoordinatorError as exc:
        message = str(exc)
        status_code = 409 if message == "Pi5 recording is not active" else 500
        return jsonify({
            "error": message,
            "pi5_recording": coordinator.get_state(),
        }), status_code

    return jsonify({
        "recording": recording_item_dto(recording),
        "pi5_recording": coordinator.get_state(),
    }), 200
