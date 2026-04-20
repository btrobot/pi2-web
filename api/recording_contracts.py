"""Shared DTO helpers for recording API contracts."""

from __future__ import annotations

from typing import Any


def recording_item_dto(recording: dict[str, Any]) -> dict[str, Any]:
    recording_id = recording["id"]
    return {
        "id": recording_id,
        "created_at": recording["created_at"],
        "duration_seconds": recording["duration_seconds"],
        "audio_url": f"/api/recordings/{recording_id}/audio",
        "reuse": {"recording_id": recording_id},
    }
