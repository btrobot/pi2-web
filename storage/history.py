"""Conversion history storage using record directories and manifests."""

from __future__ import annotations

import io
import json
import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.mode_registry import get_mode_definition

logger = logging.getLogger(__name__)

_ARTIFACT_KINDS = ("input_text", "output_text", "input_audio", "output_audio")


class HistoryManager:
    """Persist conversion history as `record_{id}/manifest.json` groups."""

    def __init__(self, history_dir: str, max_records: int = 5) -> None:
        self._dir = Path(history_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"
        self._max = max_records

    def _record_dir(self, record_id: int) -> Path:
        return self._dir / f"record_{record_id:03d}"

    def _manifest_path(self, record_id: int) -> Path:
        return self._record_dir(record_id) / "manifest.json"

    def _load_index(self) -> list[dict[str, Any]]:
        if not self._index_path.exists():
            return []

        with self._index_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if isinstance(data, list):
            return data
        return data.get("items") or data.get("records") or []

    def _save_index(self, items: list[dict[str, Any]]) -> None:
        payload = {"items": items, "max_records": self._max}
        tmp = self._index_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        tmp.replace(self._index_path)

    def _next_id(self, items: list[dict[str, Any]]) -> int:
        if not items:
            return 1
        return max(item["id"] for item in items) + 1

    def _resolve_mode_key(
        self,
        *,
        record_type: str | None,
        mode_key: str | None,
        source_lang: str,
        target_lang: str | None,
        has_output_audio: bool,
    ) -> str:
        if mode_key:
            return mode_key
        if not record_type:
            return "legacy_record"
        if "_" in record_type and record_type.count("_") >= 2:
            return record_type
        if record_type == "tts":
            return f"tts_{source_lang}_{source_lang}"
        if record_type == "asr":
            return f"asr_{source_lang}_{source_lang}"
        if record_type == "mt":
            return f"mt_{source_lang}_{target_lang or source_lang}"
        if record_type == "mt_tts":
            return f"mt_tts_{source_lang}_{target_lang or source_lang}"
        if record_type == "asr_mt":
            suffix = "asr_mt_tts" if has_output_audio else "asr_mt"
            return f"{suffix}_{source_lang}_{target_lang or source_lang}"
        return record_type

    def _resolve_group_key(self, mode_key: str, group_key: str | None) -> str:
        if group_key:
            return group_key
        try:
            return get_mode_definition(mode_key).group_key
        except KeyError:
            return "legacy"

    def _infer_text_artifacts(
        self,
        *,
        mode_key: str,
        source_text: str | None,
        target_text: str | None,
        input_text: str | None,
        output_text: str | None,
    ) -> tuple[str | None, str | None]:
        try:
            mode = get_mode_definition(mode_key)
        except KeyError:
            mode = None

        effective_input_text = input_text
        if effective_input_text is None and mode and mode.input_type == "text":
            effective_input_text = source_text

        effective_output_text = output_text
        if effective_output_text is None:
            if target_text is not None:
                effective_output_text = target_text
            elif mode and mode.output_type == "text":
                effective_output_text = source_text

        return effective_input_text, effective_output_text

    def _copy_text_artifact(self, record_dir: Path, name: str, value: str | None) -> str | None:
        if value is None:
            return None
        file_name = f"{name}.txt"
        (record_dir / file_name).write_text(value, encoding="utf-8")
        return file_name

    def _copy_audio_artifact(self, record_dir: Path, name: str, source_path: str | None) -> str | None:
        if not source_path:
            return None
        source = Path(source_path)
        if not source.exists():
            return None
        file_name = f"{name}.wav"
        shutil.copy2(source, record_dir / file_name)
        return file_name

    def _read_manifest(self, record_id: int) -> dict[str, Any] | None:
        manifest_path = self._manifest_path(record_id)
        if not manifest_path.exists():
            return None
        with manifest_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _enrich_record(self, manifest: dict[str, Any]) -> dict[str, Any]:
        values = manifest.get("values", {})
        artifacts = manifest.get("artifacts", {})
        audio_file = artifacts.get("output_audio") or artifacts.get("input_audio")

        return {
            **manifest,
            "type": manifest["mode_key"],
            "timestamp": manifest["created_at"],
            "source_text": values.get("source_text"),
            "target_text": values.get("output_text"),
            "audio_file": audio_file,
        }

    def add_record(
        self,
        *,
        record_type: str | None = None,
        mode_key: str | None = None,
        group_key: str | None = None,
        source_lang: str,
        target_lang: str | None,
        source_text: str | None,
        target_text: str | None,
        audio_path: str | None = None,
        input_text: str | None = None,
        output_text: str | None = None,
        input_audio_path: str | None = None,
        output_audio_path: str | None = None,
    ) -> dict[str, Any]:
        """Create one history record group and update FIFO/index state."""

        items = self._load_index()
        record_id = self._next_id(items)
        record_dir = self._record_dir(record_id)
        record_dir.mkdir(parents=True, exist_ok=True)

        output_audio_source = output_audio_path or audio_path
        input_audio_source = input_audio_path if input_audio_path is not None else (
            audio_path if output_audio_source is None else None
        )

        resolved_mode_key = self._resolve_mode_key(
            record_type=record_type,
            mode_key=mode_key,
            source_lang=source_lang,
            target_lang=target_lang,
            has_output_audio=bool(output_audio_source),
        )
        resolved_group_key = self._resolve_group_key(resolved_mode_key, group_key)
        created_at = datetime.now().isoformat(timespec="seconds")

        effective_input_text, effective_output_text = self._infer_text_artifacts(
            mode_key=resolved_mode_key,
            source_text=source_text,
            target_text=target_text,
            input_text=input_text,
            output_text=output_text,
        )

        artifacts = {
            "input_text": self._copy_text_artifact(record_dir, "input_text", effective_input_text),
            "output_text": self._copy_text_artifact(record_dir, "output_text", effective_output_text),
            "input_audio": self._copy_audio_artifact(record_dir, "input_audio", input_audio_source),
            "output_audio": self._copy_audio_artifact(record_dir, "output_audio", output_audio_source),
        }

        manifest = {
            "id": record_id,
            "mode_key": resolved_mode_key,
            "group_key": resolved_group_key,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "created_at": created_at,
            "artifacts": artifacts,
            "values": {
                "source_text": source_text,
                "output_text": effective_output_text,
            },
        }

        with self._manifest_path(record_id).open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)

        items.append(manifest)
        while len(items) > self._max:
            oldest = items.pop(0)
            self._delete_record_dir(oldest["id"])

        self._save_index(items)
        logger.info("saved history record: id=%d, mode_key=%s", record_id, resolved_mode_key)
        return self._enrich_record(manifest)

    def create_record(self, **kwargs: Any) -> dict[str, Any]:
        """Canonical alias for future route/storage callers."""

        return self.add_record(**kwargs)

    def _delete_record_dir(self, record_id: int) -> None:
        record_dir = self._record_dir(record_id)
        if record_dir.exists():
            shutil.rmtree(record_dir)

    def list_records(self) -> list[dict[str, Any]]:
        return [self._enrich_record(item) for item in self._load_index()]

    def list_manifests(self) -> list[dict[str, Any]]:
        """Return raw manifest-shaped summaries from the index."""

        return self._load_index()

    def get_record(self, record_id: int) -> dict[str, Any] | None:
        manifest = self._read_manifest(record_id)
        if manifest is None:
            return None
        return self._enrich_record(manifest)

    def get_manifest(self, record_id: int) -> dict[str, Any] | None:
        """Return one raw manifest by id."""

        return self._read_manifest(record_id)

    def get_artifact_path(self, record_id: int, artifact_kind: str) -> Path | None:
        if artifact_kind not in (*_ARTIFACT_KINDS, "manifest"):
            raise ValueError(f"unsupported artifact kind: {artifact_kind}")

        if artifact_kind == "manifest":
            manifest_path = self._manifest_path(record_id)
            return manifest_path if manifest_path.exists() else None

        manifest = self._read_manifest(record_id)
        if manifest is None:
            return None

        file_name = manifest.get("artifacts", {}).get(artifact_kind)
        if not file_name:
            return None

        artifact_path = self._record_dir(record_id) / file_name
        return artifact_path if artifact_path.exists() else None

    def get_audio_path(self, record_id: int) -> Path | None:
        return self.get_artifact_path(record_id, "output_audio") or self.get_artifact_path(record_id, "input_audio")

    def delete_record(self, record_id: int) -> bool:
        items = self._load_index()
        remaining = [item for item in items if item["id"] != record_id]
        if len(remaining) == len(items):
            return False

        self._delete_record_dir(record_id)
        self._save_index(remaining)
        logger.info("deleted history record: id=%d", record_id)
        return True

    def export_all(self) -> io.BytesIO:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            if self._index_path.exists():
                archive.write(self._index_path, "index.json")
            else:
                archive.writestr("index.json", json.dumps({"items": [], "max_records": self._max}, ensure_ascii=False, indent=2))

            for item in self._load_index():
                record_dir = self._record_dir(item["id"])
                if not record_dir.exists():
                    continue
                for path in sorted(record_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(self._dir).as_posix())
        buf.seek(0)
        return buf

    def export_contract(self) -> io.BytesIO:
        """Canonical alias for the frozen history export ZIP."""

        return self.export_all()
