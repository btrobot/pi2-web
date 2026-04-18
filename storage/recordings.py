"""录音文件管理 — FIFO 队列，最多保留 5 个"""

import io
import json
import logging
import os
import shutil
import wave
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RecordingManager:
    def __init__(self, recordings_dir: str, max_recordings: int = 5) -> None:
        self._dir = Path(recordings_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._dir / "metadata.json"
        self._max = max_recordings

    def _load_meta(self) -> list[dict[str, Any]]:
        if not self._meta_path.exists():
            return []
        with self._meta_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("recordings", [])

    def _save_meta(self, recordings: list[dict[str, Any]]) -> None:
        tmp = self._meta_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump({"recordings": recordings, "max_recordings": self._max}, f, ensure_ascii=False, indent=2)
        tmp.replace(self._meta_path)

    def _next_id(self, recordings: list[dict[str, Any]]) -> int:
        if not recordings:
            return 1
        return max(r["id"] for r in recordings) + 1

    def _get_wav_duration(self, wav_path: str) -> float:
        try:
            with wave.open(wav_path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / rate if rate > 0 else 0.0
        except (wave.Error, OSError):
            return 0.0

    def save_recording(self, wav_path: str) -> dict[str, Any]:
        if not os.path.exists(wav_path):
            raise FileNotFoundError(f"录音文件不存在: {wav_path}")

        recordings = self._load_meta()
        new_id = self._next_id(recordings)
        file_name = f"rec_{new_id:03d}.wav"

        shutil.copy2(wav_path, self._dir / file_name)
        file_size = os.path.getsize(self._dir / file_name)
        duration = self._get_wav_duration(wav_path)

        record: dict[str, Any] = {
            "id": new_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "duration_seconds": round(duration, 1),
            "file_name": file_name,
            "file_size_bytes": file_size,
        }
        recordings.append(record)

        while len(recordings) > self._max:
            oldest = recordings.pop(0)
            old_path = self._dir / oldest["file_name"]
            if old_path.exists():
                old_path.unlink()
                logger.info("FIFO淘汰录音: id=%d, file=%s", oldest["id"], oldest["file_name"])

        self._save_meta(recordings)
        logger.info("保存录音: id=%d, duration=%.1fs, size=%d", new_id, duration, file_size)
        return record

    def list_recordings(self) -> list[dict[str, Any]]:
        return self._load_meta()

    def get_recording(self, recording_id: int) -> dict[str, Any] | None:
        for r in self._load_meta():
            if r["id"] == recording_id:
                return r
        return None

    def get_audio_path(self, recording_id: int) -> Path | None:
        rec = self.get_recording(recording_id)
        if not rec:
            return None
        p = self._dir / rec["file_name"]
        return p if p.exists() else None

    def export_all(self) -> io.BytesIO:
        buf = io.BytesIO()
        recordings = self._load_meta()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps({"recordings": recordings}, ensure_ascii=False, indent=2))
            for r in recordings:
                p = self._dir / r["file_name"]
                if p.exists():
                    zf.write(p, r["file_name"])
        buf.seek(0)
        return buf
