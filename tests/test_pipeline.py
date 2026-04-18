"""管线集成测试 — run_pipeline() 调用链验证"""

# 1. Standard library
from unittest.mock import MagicMock, patch, call

# 2. Third-party
import pytest

# 3. Local
from pipeline import run_pipeline


@pytest.fixture
def config(mock_config):
    """Reuse conftest mock_config fixture."""
    return mock_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_history_manager(record_id: int = 1) -> MagicMock:
    mgr = MagicMock()
    mgr.add_record.return_value = {"id": record_id}
    return mgr


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

def test_run_pipeline_tts(config):
    tts_result = {"text": "hello", "audio_path": "/tmp/out.wav", "error": None}

    with patch("pipeline.run_tts", return_value=tts_result) as mock_tts, \
         patch("pipeline.HistoryManager", return_value=_make_history_manager(1)):

        result = run_pipeline("tts", config, text="hello", lang="en")

    mock_tts.assert_called_once_with(text="hello", lang="en", config=config)
    assert result["audio_path"] == "/tmp/out.wav"
    assert result["history_id"] == 1


# ---------------------------------------------------------------------------
# ASR
# ---------------------------------------------------------------------------

def test_run_pipeline_asr(config):
    asr_result = {"text": "你好", "audio_path": "/tmp/rec.wav", "error": None}

    with patch("pipeline.run_asr", return_value=asr_result) as mock_asr, \
         patch("pipeline.HistoryManager", return_value=_make_history_manager(2)):

        result = run_pipeline("asr", config, lang="zh")

    mock_asr.assert_called_once_with(lang="zh", config=config)
    assert result["text"] == "你好"
    assert result["history_id"] == 2


# ---------------------------------------------------------------------------
# MT_TTS
# ---------------------------------------------------------------------------

def test_run_pipeline_mt_tts(config):
    mt_tts_result = {
        "source_text": "hello",
        "translated_text": "你好",
        "audio_path": "/tmp/mt_tts.wav",
        "error": None,
    }

    with patch("pipeline.run_mt_tts", return_value=mt_tts_result) as mock_mt_tts, \
         patch("pipeline.HistoryManager", return_value=_make_history_manager(3)):

        result = run_pipeline(
            "mt_tts", config,
            text="hello", source_lang="en", target_lang="zh",
        )

    mock_mt_tts.assert_called_once_with(
        text="hello", source_lang="en", target_lang="zh", config=config
    )
    assert result["translated_text"] == "你好"
    assert result["history_id"] == 3


# ---------------------------------------------------------------------------
# ASR_MT
# ---------------------------------------------------------------------------

def test_run_pipeline_asr_mt(config):
    asr_mt_result = {
        "source_text": "你好",
        "translated_text": "hello",
        "audio_path": "/tmp/asr_mt.wav",
        "error": None,
    }

    with patch("pipeline.run_asr_mt", return_value=asr_mt_result) as mock_asr_mt, \
         patch("pipeline.HistoryManager", return_value=_make_history_manager(4)):

        result = run_pipeline(
            "asr_mt", config,
            source_lang="zh", target_lang="en",
        )

    mock_asr_mt.assert_called_once_with(
        source_lang="zh", target_lang="en", config=config
    )
    assert result["source_text"] == "你好"
    assert result["history_id"] == 4


# ---------------------------------------------------------------------------
# Invalid mode
# ---------------------------------------------------------------------------

def test_run_pipeline_invalid_mode_raises_value_error(config):
    with pytest.raises(ValueError, match="不支持的管线模式"):
        run_pipeline("invalid_mode", config)


# ---------------------------------------------------------------------------
# History auto-save
# ---------------------------------------------------------------------------

def test_run_pipeline_saves_history_record(config):
    """Verify HistoryManager.add_record is called with correct arguments."""
    tts_result = {"text": "test", "audio_path": "/tmp/test.wav", "error": None}
    mock_mgr = _make_history_manager(99)

    with patch("pipeline.run_tts", return_value=tts_result), \
         patch("pipeline.HistoryManager", return_value=mock_mgr) as MockMgr:

        result = run_pipeline("tts", config, text="test", lang="zh")

    MockMgr.assert_called_once_with(
        history_dir=config["storage"]["history_dir"],
        max_records=config["storage"]["max_history"],
    )
    mock_mgr.add_record.assert_called_once_with(
        record_type="tts",
        source_lang="zh",
        target_lang=None,
        source_text="test",
        target_text=None,
        audio_path="/tmp/test.wav",
    )
    assert result["history_id"] == 99


def test_run_pipeline_history_save_failure_does_not_raise(config):
    """History save failure must not propagate — main result still returned."""
    tts_result = {"text": "test", "audio_path": None, "error": None}
    mock_mgr = MagicMock()
    mock_mgr.add_record.side_effect = OSError("disk full")

    with patch("pipeline.run_tts", return_value=tts_result), \
         patch("pipeline.HistoryManager", return_value=mock_mgr):

        result = run_pipeline("tts", config, text="test", lang="en")

    # history_id should be absent since save failed
    assert "history_id" not in result
    assert result["text"] == "test"
