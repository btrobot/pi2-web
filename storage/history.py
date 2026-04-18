"""历史记录管理 — FIFO 队列，最多保留 5 条"""

import io
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class HistoryManager:
    def __init__(self, history_dir: str, max_records: int = 5) -> None:
        self._dir = Path(history_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._dir / "metadata.json"
        self._max = max_records

    def _load_meta(self) -> list[dict[str, Any]]:
        if not self._meta_path.exists():
            return []
        with self._meta_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("records", [])

    def _save_meta(self, records: list[dict[str, Any]]) -> None:
        tmp = self._meta_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump({"records": records, "max_records": self._max}, f, ensure_ascii=False, indent=2)
        tmp.replace(self._meta_path)

    def _next_id(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 1
        return max(r["id"] for r in records) + 1

    def add_record(
        self,
        record_type: str,
        source_lang: str,
        target_lang: str | None,
        source_text: str,
        target_text: str | None,
        audio_path: str | None,
    ) -> dict[str, Any]:
        records = self._load_meta()
        new_id = self._next_id(records)

        audio_file = None
        if audio_path and os.path.exists(audio_path):
            audio_file = f"history_{new_id:03d}.wav"
            shutil.copy2(audio_path, self._dir / audio_file)

        record: dict[str, Any] = {
            "id": new_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "type": record_type,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "source_text": source_text,
            "target_text": target_text,
            "audio_file": audio_file,
        }
        records.append(record)

        while len(records) > self._max:
            oldest = records.pop(0)
            if oldest.get("audio_file"):
                old_path = self._dir / oldest["audio_file"]
                if old_path.exists():
                    old_path.unlink()
                    logger.info("FIFO淘汰历史记录: id=%d, file=%s", oldest["id"], oldest["audio_file"])

        self._save_meta(records)
        logger.info("保存历史记录: id=%d, type=%s", new_id, record_type)
        return record

    def list_records(self) -> list[dict[str, Any]]:
        return self._load_meta()

    def get_record(self, record_id: int) -> dict[str, Any] | None:
        for r in self._load_meta():
            if r["id"] == record_id:
                return r
        return None

    def get_audio_path(self, record_id: int) -> Path | None:
        record = self.get_record(record_id)
        if not record or not record.get("audio_file"):
            return None
        p = self._dir / record["audio_file"]
        return p if p.exists() else None

    def export_all(self) -> io.BytesIO:
        buf = io.BytesIO()
        records = self._load_meta()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps({"records": records}, ensure_ascii=False, indent=2))
            for r in records:
                if r.get("audio_file"):
                    p = self._dir / r["audio_file"]
                    if p.exists():
                        zf.write(p, r["audio_file"])
        buf.seek(0)
        return buf
