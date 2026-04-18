"""Unit tests for storage.history and storage.recordings."""

import io
import wave
import zipfile
from pathlib import Path

import pytest

from storage.history import HistoryManager
from storage.recordings import RecordingManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_wav(path: Path, duration_seconds: float = 1.0) -> Path:
    """Write a minimal valid WAV file to *path* and return it."""
    sample_rate = 16000
    num_channels = 1
    sample_width = 2  # 16-bit
    num_frames = int(sample_rate * duration_seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * num_frames * num_channels * sample_width)
    return path


# ---------------------------------------------------------------------------
# HistoryManager tests
# ---------------------------------------------------------------------------

class TestHistoryManager:
    @pytest.fixture
    def history_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "history"
        d.mkdir()
        return d

    @pytest.fixture
    def manager(self, history_dir: Path) -> HistoryManager:
        return HistoryManager(str(history_dir), max_records=5)

    def _add(self, manager: HistoryManager, n: int = 1, audio_path: str | None = None) -> list[dict]:
        results = []
        for i in range(n):
            r = manager.add_record(
                record_type="translation",
                source_lang="zh",
                target_lang="en",
                source_text=f"你好 {i}",
                target_text=f"Hello {i}",
                audio_path=audio_path,
            )
            results.append(r)
        return results

    # --- add_record ---

    def test_add_record_returns_record_with_id(self, manager: HistoryManager) -> None:
        record = self._add(manager)[0]
        assert record["id"] == 1
        assert record["source_text"] == "你好 0"
        assert record["type"] == "translation"

    def test_add_record_persists(self, manager: HistoryManager) -> None:
        self._add(manager, 3)
        assert len(manager.list_records()) == 3

    def test_add_record_with_audio_copies_file(
        self, manager: HistoryManager, tmp_path: Path, history_dir: Path
    ) -> None:
        wav = make_wav(tmp_path / "input.wav")
        record = manager.add_record(
            record_type="asr",
            source_lang="zh",
            target_lang=None,
            source_text="测试",
            target_text=None,
            audio_path=str(wav),
        )
        assert record["audio_file"] is not None
        assert (history_dir / record["audio_file"]).exists()

    def test_add_record_without_audio(self, manager: HistoryManager) -> None:
        record = self._add(manager)[0]
        assert record["audio_file"] is None

    # --- list_records ---

    def test_list_records_empty(self, manager: HistoryManager) -> None:
        assert manager.list_records() == []

    def test_list_records_order(self, manager: HistoryManager) -> None:
        self._add(manager, 3)
        records = manager.list_records()
        ids = [r["id"] for r in records]
        assert ids == [1, 2, 3]

    # --- get_record ---

    def test_get_record_found(self, manager: HistoryManager) -> None:
        self._add(manager, 2)
        r = manager.get_record(2)
        assert r is not None
        assert r["id"] == 2

    def test_get_record_not_found(self, manager: HistoryManager) -> None:
        assert manager.get_record(99) is None

    # --- FIFO eviction ---

    def test_fifo_keeps_max_records(self, manager: HistoryManager) -> None:
        self._add(manager, 6)
        records = manager.list_records()
        assert len(records) == 5

    def test_fifo_removes_oldest_record(self, manager: HistoryManager) -> None:
        self._add(manager, 6)
        records = manager.list_records()
        ids = [r["id"] for r in records]
        assert 1 not in ids
        assert ids == [2, 3, 4, 5, 6]

    def test_fifo_deletes_audio_file_of_evicted_record(
        self, manager: HistoryManager, tmp_path: Path, history_dir: Path
    ) -> None:
        wav = make_wav(tmp_path / "audio.wav")
        # First record gets audio; it should be evicted when 6th is added
        manager.add_record(
            record_type="asr",
            source_lang="zh",
            target_lang=None,
            source_text="first",
            target_text=None,
            audio_path=str(wav),
        )
        first_audio = history_dir / "history_001.wav"
        assert first_audio.exists()

        # Add 5 more to push the first one out
        self._add(manager, 5)

        assert not first_audio.exists()

    # --- export_all ---

    def test_export_all_returns_bytesio(self, manager: HistoryManager) -> None:
        self._add(manager, 2)
        buf = manager.export_all()
        assert isinstance(buf, io.BytesIO)

    def test_export_all_is_valid_zip(self, manager: HistoryManager) -> None:
        self._add(manager, 2)
        buf = manager.export_all()
        assert zipfile.is_zipfile(buf)

    def test_export_all_contains_metadata(self, manager: HistoryManager) -> None:
        self._add(manager, 2)
        buf = manager.export_all()
        with zipfile.ZipFile(buf) as zf:
            assert "metadata.json" in zf.namelist()

    def test_export_all_includes_audio_files(
        self, manager: HistoryManager, tmp_path: Path
    ) -> None:
        wav = make_wav(tmp_path / "audio.wav")
        manager.add_record(
            record_type="asr",
            source_lang="zh",
            target_lang=None,
            source_text="test",
            target_text=None,
            audio_path=str(wav),
        )
        buf = manager.export_all()
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
        assert any(n.endswith(".wav") for n in names)


# ---------------------------------------------------------------------------
# RecordingManager tests
# ---------------------------------------------------------------------------

class TestRecordingManager:
    @pytest.fixture
    def recordings_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "recordings"
        d.mkdir()
        return d

    @pytest.fixture
    def manager(self, recordings_dir: Path) -> RecordingManager:
        return RecordingManager(str(recordings_dir), max_recordings=5)

    @pytest.fixture
    def wav_file(self, tmp_path: Path) -> Path:
        return make_wav(tmp_path / "rec.wav")

    # --- save_recording ---

    def test_save_recording_returns_record(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        record = manager.save_recording(str(wav_file))
        assert record["id"] == 1
        assert record["file_name"] == "rec_001.wav"
        assert record["duration_seconds"] == pytest.approx(1.0, abs=0.1)

    def test_save_recording_copies_file(
        self, manager: RecordingManager, wav_file: Path, recordings_dir: Path
    ) -> None:
        record = manager.save_recording(str(wav_file))
        assert (recordings_dir / record["file_name"]).exists()

    def test_save_recording_missing_file_raises(
        self, manager: RecordingManager
    ) -> None:
        with pytest.raises(FileNotFoundError):
            manager.save_recording("/nonexistent/path/audio.wav")

    # --- list_recordings ---

    def test_list_recordings_empty(self, manager: RecordingManager) -> None:
        assert manager.list_recordings() == []

    def test_list_recordings_returns_all(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        for _ in range(3):
            manager.save_recording(str(wav_file))
        assert len(manager.list_recordings()) == 3

    # --- get_recording ---

    def test_get_recording_found(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        manager.save_recording(str(wav_file))
        manager.save_recording(str(wav_file))
        r = manager.get_recording(2)
        assert r is not None
        assert r["id"] == 2

    def test_get_recording_not_found(self, manager: RecordingManager) -> None:
        assert manager.get_recording(99) is None

    # --- FIFO eviction ---

    def test_fifo_keeps_max_recordings(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        for _ in range(6):
            manager.save_recording(str(wav_file))
        assert len(manager.list_recordings()) == 5

    def test_fifo_removes_oldest_recording(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        for _ in range(6):
            manager.save_recording(str(wav_file))
        ids = [r["id"] for r in manager.list_recordings()]
        assert 1 not in ids
        assert ids == [2, 3, 4, 5, 6]

    def test_fifo_deletes_wav_file_of_evicted_recording(
        self, manager: RecordingManager, wav_file: Path, recordings_dir: Path
    ) -> None:
        for _ in range(6):
            manager.save_recording(str(wav_file))
        assert not (recordings_dir / "rec_001.wav").exists()

    # --- export_all ---

    def test_export_all_returns_bytesio(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        manager.save_recording(str(wav_file))
        buf = manager.export_all()
        assert isinstance(buf, io.BytesIO)

    def test_export_all_is_valid_zip(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        manager.save_recording(str(wav_file))
        buf = manager.export_all()
        assert zipfile.is_zipfile(buf)

    def test_export_all_contains_metadata(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        manager.save_recording(str(wav_file))
        buf = manager.export_all()
        with zipfile.ZipFile(buf) as zf:
            assert "metadata.json" in zf.namelist()

    def test_export_all_includes_wav_files(
        self, manager: RecordingManager, wav_file: Path
    ) -> None:
        manager.save_recording(str(wav_file))
        buf = manager.export_all()
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
        assert any(n.endswith(".wav") for n in names)

    def test_export_all_empty_is_valid_zip(self, manager: RecordingManager) -> None:
        buf = manager.export_all()
        assert zipfile.is_zipfile(buf)
