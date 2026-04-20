"""Pipeline tests for frozen mode-key execution and PR1 compatibility."""

# 1. Standard library
from dataclasses import asdict
import importlib
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock, patch

# 2. Third-party
import pytest

# Lightweight import stubs so declarative tests can run without Pi/audio/model
# dependencies installed in the current environment.
try:
    import alsaaudio  # type: ignore  # noqa: F401
except ModuleNotFoundError:
    alsaaudio_stub = types.ModuleType("alsaaudio")

    class _StubALSAAudioError(Exception):
        pass

    class _StubPCM:
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            return None

    alsaaudio_stub.PCM = _StubPCM
    alsaaudio_stub.ALSAAudioError = _StubALSAAudioError
    alsaaudio_stub.PCM_FORMAT_S16_LE = 1
    alsaaudio_stub.PCM_CAPTURE = 1
    alsaaudio_stub.PCM_NORMAL = 1
    sys.modules["alsaaudio"] = alsaaudio_stub

try:
    import vosk  # type: ignore  # noqa: F401
except ModuleNotFoundError:
    vosk_stub = types.ModuleType("vosk")

    class _StubModel:
        def __init__(self, *args, **kwargs):
            pass

    class _StubRecognizer:
        def __init__(self, *args, **kwargs):
            pass

        def SetWords(self, *args, **kwargs):
            return None

        def AcceptWaveform(self, *args, **kwargs):
            return False

        def Result(self):
            return '{"text": ""}'

        def FinalResult(self):
            return '{"text": ""}'

    vosk_stub.Model = _StubModel
    vosk_stub.KaldiRecognizer = _StubRecognizer
    sys.modules["vosk"] = vosk_stub

try:
    import argostranslate.translate  # type: ignore  # noqa: F401
except ModuleNotFoundError:
    argos_pkg = types.ModuleType("argostranslate")
    argos_translate = types.ModuleType("argostranslate.translate")
    argos_translate.get_installed_languages = lambda: []
    argos_pkg.translate = argos_translate
    sys.modules["argostranslate"] = argos_pkg
    sys.modules["argostranslate.translate"] = argos_translate

# 3. Local
import pipeline
from app.mode_registry import get_mode_definition, list_mode_definitions
from pipeline import run_pipeline
from pipeline._utils import build_base_result
from pipeline.composite import run_composite_mode
from pipeline.single import run_single_mode


@pytest.fixture(autouse=True)
def clear_pipeline_history_cache():
    pipeline._history_cache.clear()
    yield
    pipeline._history_cache.clear()


@pytest.fixture
def config(mock_config):
    return mock_config


def _make_history_manager(record_id: int = 1) -> MagicMock:
    mgr = MagicMock()
    mgr.add_record.return_value = {"id": record_id}
    return mgr


def _result_for_mode(mode_key: str) -> dict:
    mode = get_mode_definition(mode_key)
    result = build_base_result(mode)

    if mode.input_type == "text":
        result["source_text"] = "hello"
    else:
        result["source_text"] = "recognized"
        result["input_audio_path"] = "/tmp/input.wav"

    if mode.pipeline_chain == ("asr",):
        result["output_text"] = result["source_text"]
    elif "mt" in mode.pipeline_chain:
        result["output_text"] = "translated"

    if mode.output_type == "audio":
        result["output_audio_path"] = "/tmp/output.wav"

    return result


# ---------------------------------------------------------------------------
# Mode registry (M0 lock)
# ---------------------------------------------------------------------------

def test_mode_registry_contains_exactly_12_leaf_modes():
    registry = list_mode_definitions()
    mode_keys = {item.mode_key for item in registry}

    assert len(registry) == 12
    assert mode_keys == {
        "tts_zh_zh",
        "tts_en_en",
        "asr_zh_zh",
        "asr_en_en",
        "mt_tts_zh_en",
        "mt_tts_en_zh",
        "asr_mt_zh_en",
        "asr_mt_en_zh",
        "mt_zh_en",
        "mt_en_zh",
        "asr_mt_tts_zh_en",
        "asr_mt_tts_en_zh",
    }


def test_mode_registry_entries_match_internal_shape():
    expected_keys = {
        "mode_key",
        "group_key",
        "input_type",
        "output_type",
        "source_lang",
        "target_lang",
        "pipeline_chain",
    }

    for item in list_mode_definitions():
        item_dict = asdict(item)
        assert set(item_dict.keys()) == expected_keys
        assert item.input_type in {"text", "audio"}
        assert item.output_type in {"text", "audio"}
        assert item.source_lang in {"zh", "en"}
        assert item.target_lang in {"zh", "en"}
        assert isinstance(item.pipeline_chain, tuple)
        assert item.pipeline_chain
        assert all(step in {"asr", "mt", "tts"} for step in item.pipeline_chain)


def test_mode_registry_contains_no_numeric_identifiers():
    for item in list_mode_definitions():
        item_dict = asdict(item)
        assert "mode" not in item_dict
        assert "id" not in item_dict
        assert all(not isinstance(value, int) for value in item_dict.values())


def test_get_mode_definition_returns_expected_entry():
    mode = get_mode_definition("asr_mt_tts_zh_en")

    assert mode.mode_key == "asr_mt_tts_zh_en"
    assert mode.group_key == "cross_speech_to_speech"
    assert mode.input_type == "audio"
    assert mode.output_type == "audio"
    assert mode.source_lang == "zh"
    assert mode.target_lang == "en"
    assert mode.pipeline_chain == ("asr", "mt", "tts")


# ---------------------------------------------------------------------------
# Frozen mode-key dispatch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("mode_key", "kwargs", "runner_name"),
    [
        ("tts_zh_zh", {"input_text": "你好"}, "run_single_mode"),
        ("tts_en_en", {"input_text": "hello"}, "run_single_mode"),
        ("asr_zh_zh", {}, "run_single_mode"),
        ("asr_en_en", {}, "run_single_mode"),
        ("mt_tts_zh_en", {"input_text": "你好"}, "run_composite_mode"),
        ("mt_tts_en_zh", {"input_text": "hello"}, "run_composite_mode"),
        ("asr_mt_zh_en", {}, "run_composite_mode"),
        ("asr_mt_en_zh", {}, "run_composite_mode"),
        ("mt_zh_en", {"input_text": "你好"}, "run_composite_mode"),
        ("mt_en_zh", {"input_text": "hello"}, "run_composite_mode"),
        ("asr_mt_tts_zh_en", {}, "run_composite_mode"),
        ("asr_mt_tts_en_zh", {}, "run_composite_mode"),
    ],
)
def test_run_pipeline_dispatches_all_frozen_mode_keys(config, mode_key, kwargs, runner_name):
    fake_result = _result_for_mode(mode_key)
    mode = get_mode_definition(mode_key)
    patch_target = f"pipeline.{runner_name}"

    with patch(patch_target, return_value=fake_result) as mock_runner, \
         patch("pipeline.HistoryManager", return_value=_make_history_manager(7)):
        result = run_pipeline(mode_key, config, **kwargs)

    mock_runner.assert_called_once()
    called_mode = mock_runner.call_args.kwargs["mode"] if "mode" in mock_runner.call_args.kwargs else mock_runner.call_args.args[0]
    assert called_mode == mode
    assert result["mode_key"] == mode_key
    assert result["group_key"] == mode.group_key
    assert result["input_type"] == mode.input_type
    assert result["output_type"] == mode.output_type
    assert result["history_id"] == 7


def test_text_input_modes_do_not_require_audio_input(config):
    mode_key = "mt_tts_zh_en"
    fake_result = _result_for_mode(mode_key)

    with patch("pipeline.run_composite_mode", return_value=fake_result) as mock_runner, \
         patch("pipeline.HistoryManager", return_value=_make_history_manager(8)):
        run_pipeline(mode_key, config, input_text="你好")

    assert mock_runner.call_args.kwargs["input_text"] == "你好"
    assert mock_runner.call_args.kwargs["input_audio_path"] is None


def test_speech_input_modes_do_not_require_text_input(config):
    mode_key = "asr_mt_tts_en_zh"
    fake_result = _result_for_mode(mode_key)

    with patch("pipeline.run_composite_mode", return_value=fake_result) as mock_runner, \
         patch("pipeline.HistoryManager", return_value=_make_history_manager(9)):
        run_pipeline(mode_key, config)

    assert mock_runner.call_args.kwargs["input_text"] is None
    assert mock_runner.call_args.kwargs["input_audio_path"] is None


def test_run_pipeline_invalid_mode_raises_value_error(config):
    with pytest.raises(ValueError, match="不支持的管线模式"):
        run_pipeline("invalid_mode", config)


# ---------------------------------------------------------------------------
# Legacy aliases removed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("legacy_mode", ["tts", "asr", "mt_tts", "asr_mt"])
def test_run_pipeline_rejects_removed_legacy_aliases(config, legacy_mode):
    with pytest.raises(ValueError, match="不支持的管线模式"):
        run_pipeline(legacy_mode, config)


# ---------------------------------------------------------------------------
# Single / composite composition semantics
# ---------------------------------------------------------------------------

def test_run_single_mode_tts_returns_audio_only(config):
    mode = get_mode_definition("tts_zh_zh")

    with patch("pipeline.single.synthesize_text", return_value="/tmp/tts.wav") as mock_synthesize:
        result = run_single_mode(mode, config=config, input_text="你好")

    mock_synthesize.assert_called_once()
    assert result["source_text"] == "你好"
    assert result["output_text"] is None
    assert result["input_audio_path"] is None
    assert result["output_audio_path"] == "/tmp/tts.wav"
    assert result["error"] is None


def test_run_single_mode_asr_returns_text_without_audio_output(config):
    mode = get_mode_definition("asr_en_en")

    with patch("pipeline.single.capture_audio", return_value="/tmp/in.wav") as mock_capture, \
         patch("pipeline.single.recognize_audio", return_value="hello world") as mock_recognize:
        result = run_single_mode(mode, config=config)

    mock_capture.assert_called_once()
    mock_recognize.assert_called_once_with(config=config, audio_path="/tmp/in.wav", lang="en")
    assert result["source_text"] == "hello world"
    assert result["output_text"] == "hello world"
    assert result["input_audio_path"] == "/tmp/in.wav"
    assert result["output_audio_path"] is None
    assert result["error"] is None


def test_run_composite_mode_mt_does_not_emit_audio(config):
    mode = get_mode_definition("mt_zh_en")

    with patch("pipeline.composite.translate_text", return_value="hello") as mock_translate, \
         patch("pipeline.composite.synthesize_text") as mock_synthesize:
        result = run_composite_mode(mode, config=config, input_text="你好", playback=False)

    mock_translate.assert_called_once_with(text="你好", source_lang="zh", target_lang="en")
    mock_synthesize.assert_not_called()
    assert result["source_text"] == "你好"
    assert result["output_text"] == "hello"
    assert result["output_audio_path"] is None
    assert result["error"] is None


def test_run_composite_mode_asr_mt_tts_returns_text_and_audio(config):
    mode = get_mode_definition("asr_mt_tts_zh_en")

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav") as mock_capture, \
         patch("pipeline.composite.recognize_audio", return_value="你好") as mock_recognize, \
         patch("pipeline.composite.translate_text", return_value="hello") as mock_translate, \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize:
        result = run_composite_mode(mode, config=config)

    mock_capture.assert_called_once()
    mock_recognize.assert_called_once_with(config=config, audio_path="/tmp/input.wav", lang="zh")
    mock_translate.assert_called_once_with(text="你好", source_lang="zh", target_lang="en")
    mock_synthesize.assert_called_once()
    assert result["source_text"] == "你好"
    assert result["output_text"] == "hello"
    assert result["input_audio_path"] == "/tmp/input.wav"
    assert result["output_audio_path"] == "/tmp/output.wav"
    assert result["error"] is None


def test_same_language_modes_do_not_add_translation_output(config):
    mode = get_mode_definition("tts_en_en")

    with patch("pipeline.single.synthesize_text", return_value="/tmp/out.wav"):
        result = run_single_mode(mode, config=config, input_text="hello")

    assert result["source_text"] == "hello"
    assert result["output_text"] is None


# ---------------------------------------------------------------------------
# History save failure remains non-fatal
# ---------------------------------------------------------------------------

def test_run_pipeline_history_save_failure_does_not_raise(config):
    fake_result = _result_for_mode("tts_en_en")
    mock_mgr = MagicMock()
    mock_mgr.add_record.side_effect = OSError("disk full")

    with patch("pipeline.run_single_mode", return_value=fake_result), \
         patch("pipeline.HistoryManager", return_value=mock_mgr):
        result = run_pipeline("tts_en_en", config, input_text="hello")

    assert "history_id" not in result
    assert result["mode_key"] == "tts_en_en"


def test_mt_engine_returns_actionable_error_when_argostranslate_is_missing():
    from models.mt import MTEngine, TranslationError

    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.translate":
            raise ModuleNotFoundError("No module named 'argostranslate'")
        return real_import_module(name, package)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        with pytest.raises(
            TranslationError,
            match="translation engine unavailable: argostranslate is not installed",
        ):
            MTEngine().translate("hello", "en", "zh")


def test_validate_mt_runtime_reports_missing_stanza_tokenizer(tmp_path):
    from models.mt import validate_mt_runtime

    class _FakeTranslation:
        def __init__(self, package_path: Path) -> None:
            self.pkg = types.SimpleNamespace(
                package_path=package_path,
                packaged_sbd_path=package_path / "stanza",
                from_code="zh",
            )

    class _FakeLanguage:
        def __init__(self, code: str, translation: object | None = None) -> None:
            self.code = code
            self._translation = translation

        def get_translation(self, other) -> object | None:  # noqa: ANN001
            return self._translation if other.code == "en" else None

    package_path = tmp_path / "translate-zh_en"
    (package_path / "model").mkdir(parents=True)
    translation = _FakeTranslation(package_path)
    fake_languages = [_FakeLanguage("zh", translation), _FakeLanguage("en")]
    translate_module = types.SimpleNamespace(get_installed_languages=lambda: fake_languages)
    stanza_module = types.SimpleNamespace(Pipeline=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("tokenizer missing")))
    pipeline_core_module = types.SimpleNamespace(DownloadMethod=types.SimpleNamespace(NONE="none"))

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.translate":
            return translate_module
        if name == "stanza":
            return stanza_module
        if name == "stanza.pipeline.core":
            return pipeline_core_module
        return importlib.import_module(name, package)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        issues = validate_mt_runtime(package_dir=tmp_path, allow_network=False, required_pairs=[("zh", "en")])

    assert issues == ["MT sentence tokenizer unavailable for zh→en: tokenizer missing"]
