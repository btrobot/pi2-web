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

_DEFAULT_RECORDING_CATEGORY = "standalone"
_ALL_RECORDING_CATEGORIES = frozenset({"standalone", "speech_input"})


class RecordingManager:
    """Persist standalone recordings separately from conversion history."""

    def __init__(self, recordings_dir: str, max_recordings: int = 5) -> None:
        self._dir = Path(recordings_dir).expanduser().resolve()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._dir / "metadata.json"
        self._max = max_recordings

    def _normalize_record(self, record: Any) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None

        try:
            recording_id = int(record["id"])
            created_at = str(record["created_at"])
            duration_seconds = round(float(record["duration_seconds"]), 1)
            file_name = str(record["file_name"])
        except (KeyError, TypeError, ValueError):
            return None

        if not created_at or not file_name:
            return None

        category = str(record.get("category") or _DEFAULT_RECORDING_CATEGORY)
        if category not in _ALL_RECORDING_CATEGORIES:
            category = _DEFAULT_RECORDING_CATEGORY

        file_size_bytes_raw = record.get("file_size_bytes", 0)
        try:
            file_size_bytes = int(file_size_bytes_raw)
        except (TypeError, ValueError):
            file_size_bytes = 0

        return {
            "id": recording_id,
            "created_at": created_at,
            "duration_seconds": duration_seconds,
            "file_name": file_name,
            "file_size_bytes": file_size_bytes,
            "category": category,
        }

    def _load_meta(self) -> list[dict[str, Any]]:
        if not self._meta_path.exists():
            return []
        with self._meta_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            raw_items = data
        else:
            raw_items = data.get("items") or data.get("recordings") or []

        normalized = [item for item in (self._normalize_record(record) for record in raw_items) if item is not None]
        if len(normalized) != len(raw_items):
            self._save_meta(normalized)
        return normalized

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

    def _remove_recording_file(self, record: dict[str, Any]) -> None:
        path = self._dir / record["file_name"]
        if path.exists():
            path.unlink()

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

    def save_recording(self, wav_path: str, *, category: str = _DEFAULT_RECORDING_CATEGORY) -> dict[str, Any]:
        source = Path(wav_path)
        if not source.exists():
            raise FileNotFoundError(f"recording file does not exist: {wav_path}")

        if category not in _ALL_RECORDING_CATEGORIES:
            raise ValueError(f"unsupported recording category: {category}")

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
            "category": category,
        }
        recordings.append(record)

        same_category_items = [item for item in recordings if item.get("category") == category]
        while len(same_category_items) > self._max:
            oldest = same_category_items.pop(0)
            recordings = [item for item in recordings if item["id"] != oldest["id"]]
            self._remove_recording_file(oldest)

        self._save_meta(recordings)
        logger.info("saved recording: id=%d, file=%s", recording_id, destination.name)
        return self._enrich_recording(record)

    def list_recordings(self, *, category: str | None = _DEFAULT_RECORDING_CATEGORY) -> list[dict[str, Any]]:
        recordings = self._load_meta()
        if category is not None:
            recordings = [item for item in recordings if item.get("category") == category]
        return [self._enrich_recording(item) for item in recordings]

    def get_recording(
        self,
        recording_id: int,
        *,
        category: str | None = None,
    ) -> dict[str, Any] | None:
        for record in self._load_meta():
            if record["id"] == recording_id:
                if category is not None and record.get("category") != category:
                    continue
                return self._enrich_recording(record)
        return None

    def get_audio_path(self, recording_id: int, *, category: str | None = None) -> Path | None:
        record = self.get_recording(recording_id, category=category)
        if not record:
            return None
        path = self._dir / record["file_name"]
        return path if path.exists() else None

    def delete_recording(self, recording_id: int, *, category: str | None = _DEFAULT_RECORDING_CATEGORY) -> bool:
        recordings = self._load_meta()
        deleted_record = None
        remaining = []
        for item in recordings:
            if item["id"] == recording_id and deleted_record is None and (category is None or item.get("category") == category):
                deleted_record = item
                continue
            remaining.append(item)
        if deleted_record is None:
            return False

        self._remove_recording_file(deleted_record)
        self._save_meta(remaining)
        logger.info("deleted recording: id=%d", recording_id)
        return True

    def export_all(self, *, category: str | None = _DEFAULT_RECORDING_CATEGORY) -> io.BytesIO:
        buf = io.BytesIO()
        recordings = self._load_meta()
        if category is not None:
            recordings = [item for item in recordings if item.get("category") == category]
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            if self._meta_path.exists():
                archive.writestr(
                    "metadata.json",
                    json.dumps({"items": recordings, "max_recordings": self._max}, ensure_ascii=False, indent=2),
                )
            else:
                archive.writestr(
                    "metadata.json",
                    json.dumps({"items": [], "max_recordings": self._max}, ensure_ascii=False, indent=2),
                )

            for record in recordings:
                path = self._dir / record["file_name"]
                if path.exists():
                    archive.write(path, path.name)
        buf.seek(0)
        return buf

    def export_contract(self, *, category: str | None = _DEFAULT_RECORDING_CATEGORY) -> io.BytesIO:
        """Canonical alias for the frozen recordings export ZIP."""

        return self.export_all(category=category)
