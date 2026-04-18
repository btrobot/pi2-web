"""Independent recording storage with FIFO metadata and export support."""

from __future__ import annotations

import io
import json
import logging
import shutil
import wave
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RecordingManager:
    """Persist standalone recordings separately from conversion history."""

    def __init__(self, recordings_dir: str, max_recordings: int = 5) -> None:
        self._dir = Path(recordings_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._dir / "metadata.json"
        self._max = max_recordings

    def _load_meta(self) -> list[dict[str, Any]]:
        if not self._meta_path.exists():
            return []
        with self._meta_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
        return data.get("items") or data.get("recordings") or []

    def _save_meta(self, recordings: list[dict[str, Any]]) -> None:
        payload = {"items": recordings, "max_recordings": self._max}
        tmp = self._meta_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        tmp.replace(self._meta_path)

    def _next_id(self, recordings: list[dict[str, Any]]) -> int:
        if not recordings:
            return 1
        return max(item["id"] for item in recordings) + 1

    def _recording_path(self, recording_id: int) -> Path:
        return self._dir / f"recording_{recording_id:03d}.wav"

    def _get_wav_duration(self, wav_path: Path) -> float:
        try:
            with wave.open(str(wav_path), "rb") as handle:
                frames = handle.getnframes()
                rate = handle.getframerate()
                return frames / rate if rate > 0 else 0.0
        except (wave.Error, OSError):
            return 0.0

    def _enrich_recording(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            **record,
            "timestamp": record["created_at"],
            "filename": record["file_name"],
        }

    def save_recording(self, wav_path: str) -> dict[str, Any]:
        source = Path(wav_path)
        if not source.exists():
            raise FileNotFoundError(f"recording file does not exist: {wav_path}")

        recordings = self._load_meta()
        recording_id = self._next_id(recordings)
        destination = self._recording_path(recording_id)

        shutil.copy2(source, destination)
        record = {
            "id": recording_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "duration_seconds": round(self._get_wav_duration(destination), 1),
            "file_name": destination.name,
            "file_size_bytes": destination.stat().st_size,
        }
        recordings.append(record)

        while len(recordings) > self._max:
            oldest = recordings.pop(0)
            old_path = self._dir / oldest["file_name"]
            if old_path.exists():
                old_path.unlink()

        self._save_meta(recordings)
        logger.info("saved recording: id=%d, file=%s", recording_id, destination.name)
        return self._enrich_recording(record)

    def list_recordings(self) -> list[dict[str, Any]]:
        return [self._enrich_recording(item) for item in self._load_meta()]

    def get_recording(self, recording_id: int) -> dict[str, Any] | None:
        for record in self._load_meta():
            if record["id"] == recording_id:
                return self._enrich_recording(record)
        return None

    def get_audio_path(self, recording_id: int) -> Path | None:
        record = self.get_recording(recording_id)
        if not record:
            return None
        path = self._dir / record["file_name"]
        return path if path.exists() else None

    def delete_recording(self, recording_id: int) -> bool:
        recordings = self._load_meta()
        remaining = [item for item in recordings if item["id"] != recording_id]
        if len(remaining) == len(recordings):
            return False

        path = self._recording_path(recording_id)
        if path.exists():
            path.unlink()
        self._save_meta(remaining)
        logger.info("deleted recording: id=%d", recording_id)
        return True

    def export_all(self) -> io.BytesIO:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            if self._meta_path.exists():
                archive.write(self._meta_path, "metadata.json")
            else:
                archive.writestr(
                    "metadata.json",
                    json.dumps({"items": [], "max_recordings": self._max}, ensure_ascii=False, indent=2),
                )

            for record in self._load_meta():
                path = self._dir / record["file_name"]
                if path.exists():
                    archive.write(path, path.name)
        buf.seek(0)
        return buf

    def export_contract(self) -> io.BytesIO:
        """Canonical alias for the frozen recordings export ZIP."""

        return self.export_all()
