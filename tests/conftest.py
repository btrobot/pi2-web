import struct
import wave
import pytest
from pathlib import Path


@pytest.fixture
def tmp_audio_file(tmp_path: Path) -> Path:
    """Generate a temporary 16kHz, 16-bit, mono, 1-second silent WAV file."""
    sample_rate = 16000
    num_channels = 1
    sample_width = 2  # 16-bit
    num_frames = sample_rate  # 1 second

    wav_path = tmp_path / "test_audio.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * num_frames * num_channels * sample_width)

    return wav_path


@pytest.fixture
def tmp_storage_dir(tmp_path: Path) -> Path:
    """Temporary storage directory with history/ and recordings/ subdirectories."""
    history_dir = tmp_path / "history"
    recordings_dir = tmp_path / "recordings"
    history_dir.mkdir()
    recordings_dir.mkdir()
    return tmp_path


@pytest.fixture
def mock_config(tmp_storage_dir: Path) -> dict:
    """Test configuration dictionary pointing to temporary directories."""
    return {
        "audio": {
            "device": "plughw:2,0",
            "sample_rate": 16000,
            "bit_depth": 16,
            "channels": 1,
            "max_record_duration": 180,
        },
        "models": {
            "asr": {
                "zh_model_path": "models/data/vosk-model-small-cn-0.22",
                "en_model_path": "models/data/vosk-model-small-en-us-0.15",
            },
            "mt": {
                "package_path": "models/data/argos",
            },
            "tts": {
                "zh_model_path": "models/data/piper/zh_CN-huayan-medium.onnx",
                "en_model_path": "models/data/piper/en_US-lessac-medium.onnx",
            },
        },
        "storage": {
            "history_dir": str(tmp_storage_dir / "history"),
            "recordings_dir": str(tmp_storage_dir / "recordings"),
            "max_history": 5,
            "max_recordings": 5,
        },
        "api": {
            "host": "0.0.0.0",
            "port": 5000,
        },
        "logging": {
            "level": "INFO",
        },
    }
