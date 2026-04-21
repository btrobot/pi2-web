"""Pi5-local media state and control routes."""

from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify, request

from audio.media_coordinator import MediaBusyError, MediaCoordinatorError, Pi5MediaCoordinator
from api.recording_contracts import recording_item_dto

pi5_media_bp = Blueprint("pi5_media", __name__)
_STATE_RESPONSE_KEYS = {
    "media": "pi5_media",
    "recording": "pi5_recording",
}


def _get_coordinator() -> Pi5MediaCoordinator:
    coordinator = current_app.extensions.get("pi5_media_coordinator")
    if coordinator is None:  # pragma: no cover - create_app always wires this
        raise RuntimeError("pi5 media coordinator is not configured")
    return coordinator


def _state_payload(resource_key: str, *, state: dict[str, object] | None = None) -> dict[str, object]:
    coordinator_state = state if state is not None else _get_coordinator().get_state()
    return {_STATE_RESPONSE_KEYS[resource_key]: coordinator_state}


def _state_response(
    resource_key: str,
    *,
    status_code: int = 200,
    state: dict[str, object] | None = None,
    **payload: object,
) -> tuple[Response, int]:
    return jsonify({**payload, **_state_payload(resource_key, state=state)}), status_code


def _recording_stop_error_status(message: str) -> int:
    return 409 if message == "Pi5 recording is not active" else 500


def _recording_category_from_request() -> str:
    payload = request.get_json(silent=True) or {}
    scope = payload.get("scope")
    if scope is None:
        scope = request.form.get("scope")
    return "speech_input" if scope == "speech" else "standalone"


@pi5_media_bp.route("/api/pi5/media/state", methods=["GET"])
def get_pi5_media_state() -> tuple[Response, int]:
    return _state_response("media")


@pi5_media_bp.route("/api/pi5/media/stop", methods=["POST"])
def stop_pi5_media() -> tuple[Response, int]:
    state = _get_coordinator().stop_playback()
    return _state_response("media", ok=True, state=state)


@pi5_media_bp.route("/api/pi5/recordings/state", methods=["GET"])
def get_pi5_recording_state() -> tuple[Response, int]:
    return _state_response("recording")


@pi5_media_bp.route("/api/pi5/recordings/start", methods=["POST"])
def start_pi5_recording() -> tuple[Response, int]:
    coordinator = _get_coordinator()
    try:
        state = coordinator.start_recording(category=_recording_category_from_request())
    except MediaBusyError as exc:
        return _state_response(
            "recording",
            error=str(exc),
            state=coordinator.get_busy_state(requested_action="recording"),
            status_code=409,
        )
    except MediaCoordinatorError as exc:
        return jsonify({"error": f"Pi5 recording failed to start: {exc}"}), 500

    return _state_response("recording", state=state)


@pi5_media_bp.route("/api/pi5/recordings/stop", methods=["POST"])
def stop_pi5_recording() -> tuple[Response, int]:
    coordinator = _get_coordinator()
    try:
        recording = coordinator.stop_recording()
    except MediaCoordinatorError as exc:
        message = str(exc)
        return _state_response(
            "recording",
            error=message,
            state=coordinator.get_state(),
            status_code=_recording_stop_error_status(message),
        )

    return _state_response(
        "recording",
        recording=recording_item_dto(recording),
        state=coordinator.get_state(),
    )
