"""History routes for frozen req1 history contracts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, abort, current_app, jsonify, send_file

from storage.history import HistoryManager

logger = logging.getLogger(__name__)

history_bp = Blueprint("history", __name__)

_ARTIFACT_KINDS = ("input_text", "output_text", "input_audio", "output_audio")
_ALLOWED_ARTIFACT_KINDS = (*_ARTIFACT_KINDS, "manifest")


def _get_manager() -> HistoryManager:
    config = current_app.config["APP_CONFIG"]
    storage_cfg = config["storage"]
    return HistoryManager(
        history_dir=storage_cfg["history_dir"],
        max_records=storage_cfg["max_history"],
    )


def _artifact_url(record_id: int, artifact_kind: str, file_name: str | None) -> str | None:
    if not file_name:
        return None
    return f"/api/history/{record_id}/artifacts/{artifact_kind}"


def _artifact_urls(
    record_id: int,
    artifacts: dict[str, str | None],
    *,
    include_manifest: bool,
) -> dict[str, str | None]:
    payload = {
        f"{artifact_kind}_url": _artifact_url(record_id, artifact_kind, artifacts.get(artifact_kind))
        for artifact_kind in _ARTIFACT_KINDS
    }
    if include_manifest:
        payload["manifest_url"] = f"/api/history/{record_id}/artifacts/manifest"
    return payload


def _preview_value(value: str | None) -> str | None:
    if not value:
        return None
    return value


def _recent_item_dto(manifest: dict[str, Any]) -> dict[str, Any]:
    values = manifest.get("values", {})
    artifacts = manifest.get("artifacts", {})
    output_audio = artifacts.get("output_audio")
    return {
        "id": manifest["id"],
        "mode_key": manifest["mode_key"],
        "group_key": manifest["group_key"],
        "created_at": manifest["created_at"],
        "source_preview": _preview_value(values.get("source_text")),
        "output_preview": _preview_value(values.get("output_text")) or _preview_value(values.get("source_text")),
        "output_kind": "audio" if output_audio else "text",
        "artifact_urls": _artifact_urls(manifest["id"], artifacts, include_manifest=False),
    }


def _history_item_dto(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts", {})
    return {
        "id": manifest["id"],
        "mode_key": manifest["mode_key"],
        "group_key": manifest["group_key"],
        "source_lang": manifest["source_lang"],
        "target_lang": manifest["target_lang"],
        "created_at": manifest["created_at"],
        "values": manifest.get("values", {}),
        "artifacts": artifacts,
        "artifact_urls": _artifact_urls(manifest["id"], artifacts, include_manifest=True),
    }


def _ordered_manifests(limit: int) -> list[dict[str, Any]]:
    manifests = _get_manager().list_manifests()
    return list(reversed(manifests))[:limit]


def _history_limit() -> int:
    storage_cfg = current_app.config["APP_CONFIG"]["storage"]
    return int(storage_cfg["max_history"])


def _error_response(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status_code


def _artifact_mimetype(artifact_kind: str, path: Path) -> str | None:
    if artifact_kind in ("input_audio", "output_audio"):
        return "audio/wav"
    if artifact_kind == "manifest":
        return "application/json"
    if path.suffix == ".txt":
        return "text/plain; charset=utf-8"
    return None


@history_bp.route("/api/history/recent", methods=["GET"])
def list_recent_history() -> tuple[Response, int]:
    try:
        return jsonify({"items": [_recent_item_dto(item) for item in _ordered_manifests(limit=3)]}), 200
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to list recent history: error=%s", str(exc))
        return _error_response("failed to load recent history", 500)


@history_bp.route("/api/history", methods=["GET"])
def list_history() -> tuple[Response, int]:
    try:
        return jsonify({"items": [_history_item_dto(item) for item in _ordered_manifests(limit=_history_limit())]}), 200
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to list history: error=%s", str(exc))
        return _error_response("failed to load history", 500)


@history_bp.route("/api/history/<int:record_id>/artifacts/<artifact_kind>", methods=["GET"])
def get_history_artifact(record_id: int, artifact_kind: str) -> Response:
    if artifact_kind not in _ALLOWED_ARTIFACT_KINDS:
        abort(400, description=f"unsupported artifact kind: {artifact_kind}")

    try:
        path = _get_manager().get_artifact_path(record_id, artifact_kind)
    except ValueError:
        abort(400, description=f"unsupported artifact kind: {artifact_kind}")
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error(
            "failed to load history artifact: id=%d, artifact_kind=%s, error=%s",
            record_id,
            artifact_kind,
            str(exc),
        )
        return _error_response("failed to load history artifact", 500)

    if path is None:
        abort(404, description="history artifact not found")

    return send_file(path, mimetype=_artifact_mimetype(artifact_kind, path))


@history_bp.route("/api/history/<int:record_id>/audio", methods=["GET"])
def get_history_audio(record_id: int) -> Response:
    """Legacy compatibility alias for history audio retrieval."""

    try:
        path = _get_manager().get_audio_path(record_id)
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to load history audio: id=%d, error=%s", record_id, str(exc))
        return _error_response("failed to load history audio", 500)

    if path is None:
        abort(404, description="history audio not found")
    return send_file(path, mimetype="audio/wav")


@history_bp.route("/api/history/<int:record_id>", methods=["DELETE"])
def delete_history(record_id: int) -> tuple[Response, int]:
    try:
        deleted = _get_manager().delete_record(record_id)
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to delete history record: id=%d, error=%s", record_id, str(exc))
        return _error_response("failed to delete history record", 500)

    if not deleted:
        return _error_response(f"history record {record_id} not found", 404)

    return jsonify({"ok": True, "deleted_kind": "history", "deleted_id": record_id}), 200


@history_bp.route("/api/history/export", methods=["GET"])
def export_history() -> Response:
    try:
        buf = _get_manager().export_contract()
    except Exception as exc:  # noqa: BLE001 - route must surface JSON error
        logger.error("failed to export history: error=%s", str(exc))
        return _error_response("failed to export history", 500)

    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="history_export.zip",
    )
