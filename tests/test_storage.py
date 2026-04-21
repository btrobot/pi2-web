"""Storage tests for frozen history-manifest and recording metadata contracts."""

from __future__ import annotations

import io
import json
import wave
import zipfile
from pathlib import Path

import pytest

from storage.history import HistoryManager
from storage.recordings import RecordingManager


def make_wav(path: Path, duration_seconds: float = 1.0) -> Path:
    """Write a minimal valid WAV file."""

    sample_rate = 16000
    channels = 1
    sample_width = 2
    frames = int(sample_rate * duration_seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(sample_width)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00" * frames * channels * sample_width)
    return path


class TestHistoryManager:
    @pytest.fixture
    def history_dir(self, tmp_path: Path) -> Path:
        path = tmp_path / "history"
        path.mkdir()
        return path

    @pytest.fixture
    def manager(self, history_dir: Path) -> HistoryManager:
        return HistoryManager(str(history_dir), max_records=5)

    def test_add_record_creates_manifest_directory(self, manager: HistoryManager, history_dir: Path) -> None:
        record = manager.add_record(
            mode_key="mt_tts_zh_en",
            group_key="cross_text_to_speech",
            source_lang="zh",
            target_lang="en",
            source_text="你好",
            target_text="Hello",
            input_text="你好",
            output_text="Hello",
            output_audio_path=None,
        )

        record_dir = history_dir / "record_001"
        manifest_path = record_dir / "manifest.json"

        assert record["id"] == 1
        assert record["mode_key"] == "mt_tts_zh_en"
        assert record_dir.exists()
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["group_key"] == "cross_text_to_speech"
        assert manifest["source_lang"] == "zh"
        assert manifest["target_lang"] == "en"
        assert manifest["artifacts"]["input_text"] == "input_text.txt"
        assert manifest["artifacts"]["output_text"] == "output_text.txt"
        assert manifest["artifacts"]["input_audio"] is None
        assert manifest["artifacts"]["output_audio"] is None
        assert manifest["values"] == {"source_text": "你好", "output_text": "Hello"}

    def test_optional_artifact_combinations_follow_mode_shape(
        self,
        manager: HistoryManager,
        history_dir: Path,
        tmp_path: Path,
    ) -> None:
        input_audio = make_wav(tmp_path / "input.wav")
        output_audio = make_wav(tmp_path / "output.wav")

        asr_record = manager.add_record(
            mode_key="asr_en_en",
            group_key="same_speech_to_text",
            source_lang="en",
            target_lang="en",
            source_text="hello world",
            target_text="hello world",
            input_audio_path=str(input_audio),
        )
        s2s_record = manager.add_record(
            mode_key="asr_mt_tts_zh_en",
            group_key="cross_speech_to_speech",
            source_lang="zh",
            target_lang="en",
            source_text="你好",
            target_text="Hello",
            input_text="recognized-zh",
            input_audio_path=str(input_audio),
            output_audio_path=str(output_audio),
        )

        asr_manifest = json.loads((history_dir / "record_001" / "manifest.json").read_text(encoding="utf-8"))
        s2s_manifest = json.loads((history_dir / "record_002" / "manifest.json").read_text(encoding="utf-8"))

        assert asr_record["artifacts"]["input_audio"] == "input_audio.wav"
        assert asr_record["artifacts"]["output_audio"] is None
        assert asr_manifest["artifacts"]["output_text"] == "output_text.txt"
        assert asr_manifest["values"]["output_text"] == "hello world"

        assert s2s_record["artifacts"]["input_audio"] == "input_audio.wav"
        assert s2s_record["artifacts"]["output_audio"] == "output_audio.wav"
        assert s2s_manifest["artifacts"]["input_text"] == "input_text.txt"
        assert s2s_manifest["artifacts"]["output_text"] == "output_text.txt"
        assert s2s_manifest["values"]["output_text"] == "Hello"

    def test_list_and_get_records_return_enriched_manifest_shape(self, manager: HistoryManager) -> None:
        manager.add_record(
            mode_key="mt_zh_en",
            group_key="cross_text_to_text",
            source_lang="zh",
            target_lang="en",
            source_text="你好",
            target_text="Hello",
            input_text="你好",
            output_text="Hello",
        )

        records = manager.list_records()
        record = manager.get_record(1)

        assert len(records) == 1
        assert record is not None
        assert record["type"] == "mt_zh_en"
        assert record["source_text"] == "你好"
        assert record["target_text"] == "Hello"
        assert record["timestamp"] == record["created_at"]

    def test_fifo_eviction_removes_full_oldest_record_directory(
        self,
        history_dir: Path,
        tmp_path: Path,
    ) -> None:
        manager = HistoryManager(str(history_dir), max_records=2)
        output_audio = make_wav(tmp_path / "out.wav")

        manager.add_record(
            mode_key="tts_zh_zh",
            group_key="same_text_to_speech",
            source_lang="zh",
            target_lang="zh",
            source_text="first",
            target_text=None,
            input_text="first",
            output_audio_path=str(output_audio),
        )
        assert (history_dir / "record_001").exists()

        for index in range(2):
            manager.add_record(
                mode_key="mt_zh_en",
                group_key="cross_text_to_text",
                source_lang="zh",
                target_lang="en",
                source_text=f"text-{index}",
                target_text=f"Hello-{index}",
                input_text=f"text-{index}",
                output_text=f"Hello-{index}",
            )

        assert not (history_dir / "record_001").exists()
        assert [item["id"] for item in manager.list_records()] == [2, 3]

    def test_get_artifact_path_and_get_audio_path_resolve_frozen_artifacts(
        self,
        manager: HistoryManager,
        tmp_path: Path,
    ) -> None:
        input_audio = make_wav(tmp_path / "input.wav")
        output_audio = make_wav(tmp_path / "output.wav")
        manager.add_record(
            mode_key="asr_mt_tts_en_zh",
            group_key="cross_speech_to_speech",
            source_lang="en",
            target_lang="zh",
            source_text="hello",
            target_text="你好",
            input_audio_path=str(input_audio),
            output_audio_path=str(output_audio),
        )

        assert manager.get_artifact_path(1, "manifest") is not None
        assert manager.get_artifact_path(1, "input_audio") is not None
        assert manager.get_artifact_path(1, "output_audio") is not None
        assert manager.get_audio_path(1) == manager.get_artifact_path(1, "output_audio")

    def test_delete_record_removes_entire_group_and_index(self, manager: HistoryManager, history_dir: Path) -> None:
        manager.add_record(
            mode_key="mt_zh_en",
            group_key="cross_text_to_text",
            source_lang="zh",
            target_lang="en",
            source_text="你好",
            target_text="Hello",
            input_text="你好",
            output_text="Hello",
        )

        deleted = manager.delete_record(1)

        assert deleted is True
        assert manager.get_record(1) is None
        assert not (history_dir / "record_001").exists()
        index = json.loads((history_dir / "index.json").read_text(encoding="utf-8"))
        assert index["items"] == []

    def test_export_all_contains_index_manifests_and_artifacts(
        self,
        manager: HistoryManager,
        tmp_path: Path,
    ) -> None:
        input_audio = make_wav(tmp_path / "input.wav")
        output_audio = make_wav(tmp_path / "output.wav")
        manager.add_record(
            mode_key="asr_mt_tts_zh_en",
            group_key="cross_speech_to_speech",
            source_lang="zh",
            target_lang="en",
            source_text="你好",
            target_text="Hello",
            input_text="recognized-zh",
            input_audio_path=str(input_audio),
            output_audio_path=str(output_audio),
        )

        exported = manager.export_all()

        assert isinstance(exported, io.BytesIO)
        assert zipfile.is_zipfile(exported)
        with zipfile.ZipFile(exported) as archive:
            names = set(archive.namelist())

        assert "index.json" in names
        assert "record_001/manifest.json" in names
        assert "record_001/input_text.txt" in names
        assert "record_001/input_audio.wav" in names
        assert "record_001/output_audio.wav" in names
        assert "record_001/output_text.txt" in names


class TestRecordingManager:
    @pytest.fixture
    def recordings_dir(self, tmp_path: Path) -> Path:
        path = tmp_path / "recordings"
        path.mkdir()
        return path

    @pytest.fixture
    def manager(self, recordings_dir: Path) -> RecordingManager:
        return RecordingManager(str(recordings_dir), max_recordings=5)

    @pytest.fixture
    def wav_file(self, tmp_path: Path) -> Path:
        return make_wav(tmp_path / "recording.wav")

    def test_save_recording_returns_frozen_metadata_shape(
        self,
        manager: RecordingManager,
        recordings_dir: Path,
        wav_file: Path,
    ) -> None:
        record = manager.save_recording(str(wav_file))

        assert record["id"] == 1
        assert record["file_name"] == "recording_001.wav"
        assert record["filename"] == "recording_001.wav"
        assert record["duration_seconds"] == pytest.approx(1.0, abs=0.1)
        assert (recordings_dir / "recording_001.wav").exists()

        metadata = json.loads((recordings_dir / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["items"][0]["file_name"] == "recording_001.wav"

    def test_list_and_get_recordings_return_enriched_shape(self, manager: RecordingManager, wav_file: Path) -> None:
        manager.save_recording(str(wav_file))

        items = manager.list_recordings()
        record = manager.get_recording(1)

        assert len(items) == 1
        assert record is not None
        assert record["timestamp"] == record["created_at"]
        assert record["filename"] == record["file_name"]

    def test_list_recordings_hides_speech_input_captures_from_standalone_archive(
        self,
        manager: RecordingManager,
        wav_file: Path,
    ) -> None:
        standalone = manager.save_recording(str(wav_file), category="standalone")
        speech_input = manager.save_recording(str(wav_file), category="speech_input")

        standalone_items = manager.list_recordings()
        all_items = manager.list_recordings(category=None)

        assert [item["id"] for item in standalone_items] == [standalone["id"]]
        assert [item["id"] for item in all_items] == [standalone["id"], speech_input["id"]]
        assert all(item["category"] == "standalone" for item in standalone_items)
        assert manager.get_audio_path(speech_input["id"]) is not None

    def test_load_meta_repairs_history_shaped_items_out_of_recording_archive(self, recordings_dir: Path) -> None:
        metadata_path = recordings_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "id": 1,
                            "created_at": "2026-04-21T10:00:00",
                            "duration_seconds": 1.0,
                            "file_name": "recording_001.wav",
                            "file_size_bytes": 32,
                        },
                        {
                            "id": 99,
                            "mode_key": "mt_zh_en",
                            "group_key": "cross_text_to_text",
                            "created_at": "2026-04-21T10:01:00",
                            "artifacts": {},
                            "values": {},
                        },
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        make_wav(recordings_dir / "recording_001.wav")

        manager = RecordingManager(str(recordings_dir), max_recordings=5)

        items = manager.list_recordings()
        repaired = json.loads(metadata_path.read_text(encoding="utf-8"))

        assert [item["id"] for item in items] == [1]
        assert [item["id"] for item in repaired["items"]] == [1]

    def test_fifo_eviction_removes_oldest_recording_file(
        self,
        recordings_dir: Path,
        wav_file: Path,
    ) -> None:
        manager = RecordingManager(str(recordings_dir), max_recordings=2)
        for _ in range(3):
            manager.save_recording(str(wav_file))

        assert [item["id"] for item in manager.list_recordings()] == [2, 3]
        assert not (recordings_dir / "recording_001.wav").exists()

    def test_fifo_eviction_is_isolated_per_recording_category(
        self,
        recordings_dir: Path,
        wav_file: Path,
    ) -> None:
        manager = RecordingManager(str(recordings_dir), max_recordings=2)
        standalone = manager.save_recording(str(wav_file), category="standalone")
        for _ in range(3):
            manager.save_recording(str(wav_file), category="speech_input")

        assert [item["id"] for item in manager.list_recordings()] == [standalone["id"]]
        assert len(manager.list_recordings(category=None)) == 3
        assert manager.get_audio_path(standalone["id"]) is not None

    def test_delete_recording_removes_file_and_metadata(
        self,
        manager: RecordingManager,
        recordings_dir: Path,
        wav_file: Path,
    ) -> None:
        manager.save_recording(str(wav_file))

        deleted = manager.delete_recording(1)

        assert deleted is True
        assert manager.get_recording(1) is None
        assert not (recordings_dir / "recording_001.wav").exists()
        metadata = json.loads((recordings_dir / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["items"] == []

    def test_export_all_contains_metadata_and_recording_files(self, manager: RecordingManager, wav_file: Path) -> None:
        manager.save_recording(str(wav_file), category="standalone")
        manager.save_recording(str(wav_file), category="speech_input")

        exported = manager.export_all(category="standalone")

        assert isinstance(exported, io.BytesIO)
        assert zipfile.is_zipfile(exported)
        with zipfile.ZipFile(exported) as archive:
            names = set(archive.namelist())

        assert "metadata.json" in names
        assert "recording_001.wav" in names
        assert "recording_002.wav" not in names

    def test_missing_recording_raises_file_not_found(self, manager: RecordingManager) -> None:
        with pytest.raises(FileNotFoundError):
            manager.save_recording("/nonexistent/audio.wav")
