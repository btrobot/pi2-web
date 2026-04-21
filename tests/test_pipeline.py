"""Pipeline tests for frozen mode-key execution and PR1 compatibility."""

# 1. Standard library
from dataclasses import asdict
import importlib
import os
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
from pipeline.composite import (
    SpeechMtTranslationPlan,
    _build_segmented_speech_mt_plan,
    _should_segment_speech_mt,
    run_composite_mode,
)
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


def test_should_segment_speech_mt_targets_only_cross_language_asr_mt_modes():
    target_map = {
        mode.mode_key: _should_segment_speech_mt(mode)
        for mode in list_mode_definitions()
    }

    assert target_map == {
        "tts_zh_zh": False,
        "tts_en_en": False,
        "asr_zh_zh": False,
        "asr_en_en": False,
        "mt_tts_zh_en": False,
        "mt_tts_en_zh": False,
        "asr_mt_zh_en": True,
        "asr_mt_en_zh": True,
        "mt_zh_en": False,
        "mt_en_zh": False,
        "asr_mt_tts_zh_en": True,
        "asr_mt_tts_en_zh": True,
    }


@pytest.mark.parametrize(
    ("mode_key", "raw_text", "expected_runtime_input", "expected_planned_chunks"),
    [
        (
            "asr_mt_zh_en",
            ("甲" * 24) + ("乙" * 24) + ("丙" * 24) + ("丁" * 3),
            ("甲" * 24) + " " + ("乙" * 24) + " " + ("丙" * 24) + " " + ("丁" * 3),
            (
                ("甲" * 24) + " " + ("乙" * 24) + " " + ("丙" * 24),
                "丁" * 3,
            ),
        ),
        (
            "asr_mt_en_zh",
            " ".join(f"word{index}" for index in range(1, 49)),
            " ".join(f"word{index}" for index in range(1, 49)),
            (
                " ".join(f"word{index}" for index in range(1, 37)),
                " ".join(f"word{index}" for index in range(37, 49)),
            ),
        ),
    ],
)
def test_build_segmented_speech_mt_plan_exposes_pr2_chunk_plan_without_changing_runtime_input(
    mode_key,
    raw_text,
    expected_runtime_input,
    expected_planned_chunks,
):
    mode = get_mode_definition(mode_key)

    plan = _build_segmented_speech_mt_plan(raw_text, mode)

    assert plan.source_text == raw_text
    assert plan.mt_inputs == (expected_runtime_input,)
    assert plan.planned_mt_inputs == expected_planned_chunks


@pytest.mark.parametrize(
    ("mode_key", "source_lang", "target_lang", "translated_text"),
    [
        ("asr_mt_zh_en", "zh", "en", "hello"),
        ("asr_mt_en_zh", "en", "zh", "你好"),
        ("asr_mt_tts_zh_en", "zh", "en", "hello"),
        ("asr_mt_tts_en_zh", "en", "zh", "你好"),
    ],
)
def test_run_composite_mode_uses_segmented_speech_mt_scaffold_for_target_modes(
    config,
    mode_key,
    source_lang,
    target_lang,
    translated_text,
):
    mode = get_mode_definition(mode_key)
    raw_text = "识别原文"
    planned_text = f"{mode_key}-planned"

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav") as mock_capture, \
         patch("pipeline.composite.recognize_audio", return_value=raw_text) as mock_recognize, \
         patch(
             "pipeline.composite._build_segmented_speech_mt_plan",
             return_value=SpeechMtTranslationPlan(
                 source_text=raw_text,
                 mt_inputs=(planned_text,),
                 planned_mt_inputs=("ignored-short-clean-chunk",),
             ),
         ) as mock_plan, \
         patch("pipeline.composite.translate_text", return_value=translated_text) as mock_translate, \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize:
        result = run_composite_mode(mode, config=config)

    mock_capture.assert_called_once()
    mock_recognize.assert_called_once_with(config=config, audio_path="/tmp/input.wav", lang=source_lang)
    mock_plan.assert_called_once_with(raw_text, mode)
    mock_translate.assert_called_once_with(text=planned_text, source_lang=source_lang, target_lang=target_lang)
    if mode.pipeline_chain[-1] == "tts":
        mock_synthesize.assert_called_once()
        assert result["output_audio_path"] == "/tmp/output.wav"
    else:
        mock_synthesize.assert_not_called()
        assert result["output_audio_path"] is None
    assert result["source_text"] == raw_text
    assert result["output_text"] == translated_text
    assert result["error"] is None


@pytest.mark.parametrize(
    ("mode_key", "planned_chunks", "translated_chunks", "expected_output_text"),
    [
        (
            "asr_mt_zh_en",
            ("第一句。 第二句。 第三句。", "第四句。 第五句。"),
            ("hello from", "pi five"),
            "hello from pi five",
        ),
        (
            "asr_mt_en_zh",
            ("first second third", "fourth fifth"),
            ("你好 世界 ！", " 再见。"),
            "你好世界！再见。",
        ),
        (
            "asr_mt_tts_zh_en",
            ("第一句。 第二句。 第三句。", "第四句。 第五句。"),
            ("hello from", "pi five"),
            "hello from pi five",
        ),
        (
            "asr_mt_tts_en_zh",
            ("first second third", "fourth fifth"),
            ("你好 世界 ！", " 再见。"),
            "你好世界！再见。",
        ),
    ],
)
def test_run_composite_mode_rolls_out_multi_chunk_segmented_speech_mt_in_order(
    config,
    mode_key,
    planned_chunks,
    translated_chunks,
    expected_output_text,
):
    mode = get_mode_definition(mode_key)
    raw_text = f"{mode_key}-raw"
    legacy_input = f"{mode_key}-legacy-single-shot"

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav") as mock_capture, \
         patch("pipeline.composite.recognize_audio", return_value=raw_text) as mock_recognize, \
         patch(
             "pipeline.composite._build_segmented_speech_mt_plan",
             return_value=SpeechMtTranslationPlan(
                 source_text=raw_text,
                 mt_inputs=(legacy_input,),
                 planned_mt_inputs=planned_chunks,
             ),
         ) as mock_plan, \
         patch("pipeline.composite.translate_text", side_effect=list(translated_chunks)) as mock_translate, \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize:
        result = run_composite_mode(mode, config=config, playback=False)

    mock_capture.assert_called_once()
    mock_recognize.assert_called_once_with(config=config, audio_path="/tmp/input.wav", lang=mode.source_lang)
    mock_plan.assert_called_once_with(raw_text, mode)
    assert [call.kwargs["text"] for call in mock_translate.call_args_list] == list(planned_chunks)
    assert all(call.kwargs["source_lang"] == mode.source_lang for call in mock_translate.call_args_list)
    assert all(call.kwargs["target_lang"] == mode.target_lang for call in mock_translate.call_args_list)
    if mode.pipeline_chain[-1] == "tts":
        mock_synthesize.assert_called_once_with(
            config=config,
            text=expected_output_text,
            lang=mode.target_lang,
            prefix=f"{mode_key}_output",
            playback=False,
        )
        assert result["output_audio_path"] == "/tmp/output.wav"
    else:
        mock_synthesize.assert_not_called()
        assert result["output_audio_path"] is None
    assert result["source_text"] == raw_text
    assert result["output_text"] == expected_output_text
    assert result["error"] is None


@pytest.mark.parametrize("mode_key", ["asr_mt_zh_en", "asr_mt_tts_zh_en"])
def test_run_composite_mode_trims_repeated_tail_for_multi_chunk_segmented_speech_mt(config, mode_key):
    mode = get_mode_definition(mode_key)
    raw_text = f"{mode_key}-raw"
    planned_chunks = ("第一句。 第二句。 第三句。", "第四句。 第五句。")
    translated_chunks = (
        " ".join(f"word{index}" for index in range(1, 16)),
        " ".join(f"word{index}" for index in range(16, 23)) + " and on and on and on and on",
    )
    expected_output_text = " ".join(f"word{index}" for index in range(1, 23)) + " and on"

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav"), \
         patch("pipeline.composite.recognize_audio", return_value=raw_text), \
         patch(
             "pipeline.composite._build_segmented_speech_mt_plan",
             return_value=SpeechMtTranslationPlan(
                 source_text=raw_text,
                 mt_inputs=(f"{mode_key}-legacy-single-shot",),
                 planned_mt_inputs=planned_chunks,
                 source_atomic_units=("第一句。", "第二句。", "第三句。", "第四句。", "第五句。"),
             ),
         ), \
         patch("pipeline.composite.translate_text", side_effect=list(translated_chunks)), \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize:
        result = run_composite_mode(mode, config=config, playback=False)

    if mode.pipeline_chain[-1] == "tts":
        mock_synthesize.assert_called_once_with(
            config=config,
            text=expected_output_text,
            lang=mode.target_lang,
            prefix=f"{mode_key}_output",
            playback=False,
        )
    else:
        mock_synthesize.assert_not_called()
    assert result["source_text"] == raw_text
    assert result["output_text"] == expected_output_text
    assert result["error"] is None


@pytest.mark.parametrize("mode_key", ["asr_mt_en_zh", "asr_mt_tts_en_zh"])
def test_run_composite_mode_preserves_tail_repetition_when_source_tail_repeats(config, mode_key):
    mode = get_mode_definition(mode_key)
    raw_text = f"{mode_key}-raw"
    planned_chunks = ("first second third", "fourth fifth sixth")
    repeated_tail = "继续测试"
    expected_output_text = ("这是一个很长的翻译结果" * 10) + (repeated_tail * 3)

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav"), \
         patch("pipeline.composite.recognize_audio", return_value=raw_text), \
         patch(
             "pipeline.composite._build_segmented_speech_mt_plan",
             return_value=SpeechMtTranslationPlan(
                 source_text=raw_text,
                 mt_inputs=(f"{mode_key}-legacy-single-shot",),
                 planned_mt_inputs=planned_chunks,
                 source_atomic_units=("重复。", "重复。", "重复。"),
             ),
         ), \
         patch(
             "pipeline.composite.translate_text",
             side_effect=("这是一个很长的翻译结果" * 10 + repeated_tail, repeated_tail * 2),
         ), \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize:
        result = run_composite_mode(mode, config=config, playback=False)

    if mode.pipeline_chain[-1] == "tts":
        mock_synthesize.assert_called_once_with(
            config=config,
            text=expected_output_text,
            lang=mode.target_lang,
            prefix=f"{mode_key}_output",
            playback=False,
        )
    else:
        mock_synthesize.assert_not_called()
    assert result["source_text"] == raw_text
    assert result["output_text"] == expected_output_text
    assert result["error"] is None


@pytest.mark.parametrize(
    ("mode_key", "input_text", "source_text"),
    [
        ("mt_zh_en", "你好", "你好"),
        ("mt_tts_zh_en", "你好", "你好"),
        ("mt_en_zh", "hello world", "hello world"),
        ("mt_tts_en_zh", "hello world", "hello world"),
    ],
)
def test_run_composite_mode_bypasses_segmented_speech_mt_scaffold_for_non_target_composites(
    config,
    mode_key,
    input_text,
    source_text,
):
    mode = get_mode_definition(mode_key)

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav") as mock_capture, \
         patch("pipeline.composite.recognize_audio", return_value=source_text) as mock_recognize, \
         patch("pipeline.composite._build_segmented_speech_mt_plan") as mock_plan, \
         patch("pipeline.composite.translate_text", return_value="translated") as mock_translate, \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize:
        result = run_composite_mode(mode, config=config, input_text=input_text)

    if mode.pipeline_chain[0] == "asr":
        mock_capture.assert_called_once()
        mock_recognize.assert_called_once()
    else:
        mock_capture.assert_not_called()
        mock_recognize.assert_not_called()
    mock_plan.assert_not_called()
    mock_translate.assert_called_once_with(
        text=source_text,
        source_lang=mode.source_lang,
        target_lang=mode.target_lang,
    )
    if mode.pipeline_chain[-1] == "tts":
        mock_synthesize.assert_called_once()
    else:
        mock_synthesize.assert_not_called()
    assert result["source_text"] == source_text
    assert result["output_text"] == "translated"
    assert result["error"] is None


@pytest.mark.parametrize("mode_key", ["asr_zh_zh", "asr_en_en"])
def test_same_language_asr_modes_never_touch_segmented_speech_mt_scaffold(config, mode_key):
    with patch("pipeline.composite._build_segmented_speech_mt_plan") as mock_plan, \
         patch("pipeline.single.capture_audio", return_value="/tmp/input.wav"), \
         patch("pipeline.single.recognize_audio", return_value="recognized"):
        result = run_pipeline(mode_key, config)

    mock_plan.assert_not_called()
    assert result["mode_key"] == mode_key
    assert result["source_text"] == "recognized"
    assert result["output_text"] == "recognized"
    assert result["error"] is None


@pytest.mark.parametrize(
    ("mode_key", "group_key", "output_audio_path"),
    [
        ("asr_mt_zh_en", "cross_speech_to_text", None),
        ("asr_mt_en_zh", "cross_speech_to_text", None),
        ("asr_mt_tts_zh_en", "cross_speech_to_speech", "/tmp/output.wav"),
        ("asr_mt_tts_en_zh", "cross_speech_to_speech", "/tmp/output.wav"),
    ],
)
def test_run_pipeline_persists_raw_source_text_while_segmented_speech_mt_scaffold_changes_transient_mt_input(
    config,
    mode_key,
    group_key,
    output_audio_path,
):
    raw_text = "原始识别"
    planned_text = f"{mode_key}-planned"
    mode = get_mode_definition(mode_key)
    translated_text = "hello" if mode.target_lang == "en" else "你好"
    history_manager = _make_history_manager(record_id=12)

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav"), \
         patch("pipeline.composite.recognize_audio", return_value=raw_text), \
         patch(
             "pipeline.composite._build_segmented_speech_mt_plan",
             return_value=SpeechMtTranslationPlan(
                 source_text=raw_text,
                 mt_inputs=(planned_text,),
                 planned_mt_inputs=("ignored-short-clean-chunk",),
             ),
         ) as mock_plan, \
         patch("pipeline.composite.translate_text", return_value=translated_text) as mock_translate, \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize, \
         patch("pipeline.HistoryManager", return_value=history_manager):
        result = run_pipeline(mode_key, config, playback=False)

    mock_plan.assert_called_once_with(raw_text, mode)
    mock_translate.assert_called_once_with(
        text=planned_text,
        source_lang=mode.source_lang,
        target_lang=mode.target_lang,
    )
    if output_audio_path is None:
        mock_synthesize.assert_not_called()
    else:
        mock_synthesize.assert_called_once_with(
            config=config,
            text=translated_text,
            lang=mode.target_lang,
            prefix=f"{mode_key}_output",
            playback=False,
        )
    history_manager.add_record.assert_called_once_with(
        record_type=mode_key,
        mode_key=mode_key,
        group_key=group_key,
        source_lang=mode.source_lang,
        target_lang=mode.target_lang,
        source_text=raw_text,
        target_text=translated_text,
        input_text=raw_text,
        output_text=translated_text,
        input_audio_path="/tmp/input.wav",
        output_audio_path=output_audio_path,
    )
    assert result["source_text"] == raw_text
    assert result["output_text"] == translated_text
    assert result["output_audio_path"] == output_audio_path
    assert result["history_id"] == 12


@pytest.mark.parametrize(
    ("mode_key", "expected_source_text", "expected_mt_input", "expected_output_text"),
    [
        ("asr_mt_zh_en", "你好。世界。今天。", "你好. 世界. 今天.", "hello world"),
        ("asr_mt_en_zh", "hello hello world today weather is good", "hello hello world today weather is good", "你好世界"),
        ("asr_mt_tts_zh_en", "你好。世界。今天。", "你好. 世界. 今天.", "hello world"),
        ("asr_mt_tts_en_zh", "hello hello world today weather is good", "hello hello world today weather is good", "你好世界"),
    ],
)
def test_run_pipeline_segmented_speech_mt_scaffold_preserves_current_single_shot_behavior(
    config,
    mode_key,
    expected_source_text,
    expected_mt_input,
    expected_output_text,
):
    mode = get_mode_definition(mode_key)
    history_manager = _make_history_manager(record_id=13)

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav"), \
         patch("pipeline.composite.recognize_audio", return_value=expected_source_text), \
         patch("pipeline.composite.translate_text", return_value=expected_output_text) as mock_translate, \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize, \
         patch("pipeline.HistoryManager", return_value=history_manager):
        result = run_pipeline(mode_key, config, playback=False)

    mock_translate.assert_called_once_with(
        text=expected_mt_input,
        source_lang=mode.source_lang,
        target_lang=mode.target_lang,
    )
    if mode.pipeline_chain[-1] == "tts":
        mock_synthesize.assert_called_once_with(
            config=config,
            text=expected_output_text,
            lang=mode.target_lang,
            prefix=f"{mode_key}_output",
            playback=False,
        )
    else:
        mock_synthesize.assert_not_called()
    history_manager.add_record.assert_called_once_with(
        record_type=mode_key,
        mode_key=mode_key,
        group_key=mode.group_key,
        source_lang=mode.source_lang,
        target_lang=mode.target_lang,
        source_text=expected_source_text,
        target_text=expected_output_text,
        input_text=expected_source_text,
        output_text=expected_output_text,
        input_audio_path="/tmp/input.wav",
        output_audio_path="/tmp/output.wav" if mode.pipeline_chain[-1] == "tts" else None,
    )
    assert result["source_text"] == expected_source_text
    assert result["output_text"] == expected_output_text
    assert result["output_audio_path"] == ("/tmp/output.wav" if mode.pipeline_chain[-1] == "tts" else None)
    assert result["history_id"] == 13


@pytest.mark.parametrize(
    ("mode_key", "planned_chunks", "translated_chunks", "expected_output_text", "output_audio_path"),
    [
        (
            "asr_mt_zh_en",
            ("第一句。 第二句。 第三句。", "第四句。 第五句。"),
            ("hello from", "pi five"),
            "hello from pi five",
            None,
        ),
        (
            "asr_mt_en_zh",
            ("first second third", "fourth fifth"),
            ("你好 世界 ！", " 再见。"),
            "你好世界！再见。",
            None,
        ),
        (
            "asr_mt_tts_zh_en",
            ("第一句。 第二句。 第三句。", "第四句。 第五句。"),
            ("hello from", "pi five"),
            "hello from pi five",
            "/tmp/output.wav",
        ),
        (
            "asr_mt_tts_en_zh",
            ("first second third", "fourth fifth"),
            ("你好 世界 ！", " 再见。"),
            "你好世界！再见。",
            "/tmp/output.wav",
        ),
    ],
)
def test_run_pipeline_segmented_speech_mt_persists_raw_source_text_during_multi_chunk_rollout(
    config,
    mode_key,
    planned_chunks,
    translated_chunks,
    expected_output_text,
    output_audio_path,
):
    mode = get_mode_definition(mode_key)
    raw_text = f"{mode_key}-recognized-raw"
    history_manager = _make_history_manager(record_id=14)

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav"), \
         patch("pipeline.composite.recognize_audio", return_value=raw_text), \
         patch(
             "pipeline.composite._build_segmented_speech_mt_plan",
             return_value=SpeechMtTranslationPlan(
                 source_text=raw_text,
                 mt_inputs=(f"{mode_key}-legacy-single-shot",),
                 planned_mt_inputs=planned_chunks,
             ),
         ) as mock_plan, \
         patch("pipeline.composite.translate_text", side_effect=list(translated_chunks)) as mock_translate, \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav") as mock_synthesize, \
         patch("pipeline.HistoryManager", return_value=history_manager):
        result = run_pipeline(mode_key, config, playback=False)

    mock_plan.assert_called_once_with(raw_text, mode)
    assert [call.kwargs["text"] for call in mock_translate.call_args_list] == list(planned_chunks)
    if output_audio_path is None:
        mock_synthesize.assert_not_called()
    else:
        mock_synthesize.assert_called_once_with(
            config=config,
            text=expected_output_text,
            lang=mode.target_lang,
            prefix=f"{mode_key}_output",
            playback=False,
        )
    history_manager.add_record.assert_called_once_with(
        record_type=mode_key,
        mode_key=mode_key,
        group_key=mode.group_key,
        source_lang=mode.source_lang,
        target_lang=mode.target_lang,
        source_text=raw_text,
        target_text=expected_output_text,
        input_text=raw_text,
        output_text=expected_output_text,
        input_audio_path="/tmp/input.wav",
        output_audio_path=output_audio_path,
    )
    assert result["source_text"] == raw_text
    assert result["output_text"] == expected_output_text
    assert result["output_audio_path"] == output_audio_path
    assert result["history_id"] == 14


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
    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.translate":
            return translate_module
        if name == "stanza":
            return stanza_module
        if name == "stanza.pipeline.core":
            return pipeline_core_module
        return real_import_module(name, package)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        issues = validate_mt_runtime(package_dir=tmp_path, allow_network=False, required_pairs=[("zh", "en")])

    assert issues == ["MT sentence tokenizer unavailable for zh->en: tokenizer missing"]


def test_configure_argos_environment_falls_back_to_default_package_dir(monkeypatch, tmp_path):
    from models.mt import configure_argos_environment

    configured_dir = tmp_path / "configured-argos"
    default_dir = tmp_path / "default-argos"
    translate_module = types.SimpleNamespace(
        get_installed_languages=types.SimpleNamespace(cache_clear=MagicMock()),
        installed_translates=[object()],
    )
    settings_module = types.SimpleNamespace(package_data_dir=None, package_dirs=[])
    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.settings":
            return settings_module
        return real_import_module(name, package)

    monkeypatch.setattr("models.mt._default_argos_package_dir", lambda: default_dir)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", translate_module)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        resolved = configure_argos_environment(configured_dir)

    assert resolved == configured_dir.resolve()
    assert os.environ["ARGOS_PACKAGES_DIR"] == str(configured_dir.resolve())
    assert settings_module.package_data_dir == configured_dir.resolve()
    assert settings_module.package_dirs == [configured_dir.resolve(), default_dir.resolve()]
    translate_module.get_installed_languages.cache_clear.assert_called_once_with()
    assert translate_module.installed_translates == []


def test_validate_mt_runtime_uses_default_argos_dir_when_configured_dir_is_empty(monkeypatch, tmp_path):
    from models.mt import validate_mt_runtime

    configured_dir = tmp_path / "configured-argos"
    default_dir = tmp_path / "default-argos"

    class _FakeTranslation:
        def __init__(self, package_path: Path) -> None:
            self.pkg = types.SimpleNamespace(
                package_path=package_path,
                packaged_sbd_path=None,
                from_code="zh",
            )

    class _FakeLanguage:
        def __init__(self, code: str, translation: object | None = None) -> None:
            self.code = code
            self._translation = translation

        def get_translation(self, other) -> object | None:  # noqa: ANN001
            return self._translation if other.code == "en" else None

    package_path = default_dir / "translate-zh_en"
    (package_path / "model").mkdir(parents=True)
    translation = _FakeTranslation(package_path)
    fake_languages = [_FakeLanguage("zh", translation), _FakeLanguage("en")]
    translate_module = types.SimpleNamespace(get_installed_languages=lambda: fake_languages)
    settings_module = types.SimpleNamespace(package_data_dir=None, package_dirs=[])
    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.translate":
            return translate_module
        if name == "argostranslate.settings":
            return settings_module
        return real_import_module(name, package)

    monkeypatch.setattr("models.mt._default_argos_package_dir", lambda: default_dir)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        issues = validate_mt_runtime(
            package_dir=configured_dir,
            allow_network=False,
            required_pairs=[("zh", "en")],
        )

    assert issues == []


def test_prepare_mt_runtime_downloads_packaged_stanza_resources(tmp_path):
    from models.mt import prepare_mt_runtime

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
    package_path.mkdir(parents=True)
    translation = _FakeTranslation(package_path)
    fake_languages = [_FakeLanguage("zh", translation), _FakeLanguage("en")]
    translate_module = types.SimpleNamespace(get_installed_languages=lambda: fake_languages)
    settings_module = types.SimpleNamespace(package_data_dir=None, package_dirs=[])
    stanza_module = types.SimpleNamespace(download=MagicMock())
    pipeline_core_module = types.SimpleNamespace(DownloadMethod=types.SimpleNamespace(NONE="none"))
    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.translate":
            return translate_module
        if name == "argostranslate.settings":
            return settings_module
        if name == "argostranslate.sbd":
            return types.SimpleNamespace(StanzaSentencizer=None)
        if name == "stanza":
            return stanza_module
        if name == "stanza.pipeline.core":
            return pipeline_core_module
        return real_import_module(name, package)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        issues = prepare_mt_runtime(package_dir=tmp_path, required_pairs=[("zh", "en")])

    assert issues == []
    stanza_module.download.assert_called_once_with(
        lang="zh",
        model_dir=str(package_path / "stanza"),
        processors="tokenize",
        logging_level="WARNING",
        verbose=False,
    )


def test_prepare_mt_runtime_skips_stanza_download_for_en_to_zh(tmp_path):
    from models.mt import prepare_mt_runtime

    class _FakeTranslation:
        def __init__(self, package_path: Path) -> None:
            self.pkg = types.SimpleNamespace(
                package_path=package_path,
                packaged_sbd_path=package_path / "stanza",
                from_code="en",
            )

    class _FakeLanguage:
        def __init__(self, code: str, translation: object | None = None) -> None:
            self.code = code
            self._translation = translation

        def get_translation(self, other) -> object | None:  # noqa: ANN001
            return self._translation if other.code == "zh" else None

    package_path = tmp_path / "translate-en_zh"
    package_path.mkdir(parents=True)
    translation = _FakeTranslation(package_path)
    fake_languages = [_FakeLanguage("en", translation), _FakeLanguage("zh")]
    translate_module = types.SimpleNamespace(get_installed_languages=lambda: fake_languages)
    settings_module = types.SimpleNamespace(package_data_dir=None, package_dirs=[])
    stanza_module = types.SimpleNamespace(download=MagicMock())
    pipeline_core_module = types.SimpleNamespace(DownloadMethod=types.SimpleNamespace(NONE="none"))
    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.translate":
            return translate_module
        if name == "argostranslate.settings":
            return settings_module
        if name == "argostranslate.sbd":
            return types.SimpleNamespace(StanzaSentencizer=None)
        if name == "stanza":
            return stanza_module
        if name == "stanza.pipeline.core":
            return pipeline_core_module
        return real_import_module(name, package)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        issues = prepare_mt_runtime(package_dir=tmp_path, required_pairs=[("en", "zh")])

    assert issues == []
    stanza_module.download.assert_not_called()


def test_configure_argos_environment_patches_argos_stanza_sentencizer_for_offline_mode(tmp_path):
    from models.mt import configure_argos_environment

    class _FakeStanzaSentencizer:
        def __init__(self, pkg) -> None:  # noqa: ANN001
            self.pkg = pkg
            self.stanza_lang_code = "en"
            self.stanza_pipeline = None

    pipeline_mock = MagicMock(return_value="pipeline")
    sbd_module = types.SimpleNamespace(
        StanzaSentencizer=_FakeStanzaSentencizer,
        stanza=types.SimpleNamespace(Pipeline=pipeline_mock),
        settings=types.SimpleNamespace(device="cpu"),
    )
    settings_module = types.SimpleNamespace(package_data_dir=None, package_dirs=[])
    pipeline_core_module = types.SimpleNamespace(DownloadMethod=types.SimpleNamespace(NONE="none"))
    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.settings":
            return settings_module
        if name == "argostranslate.sbd":
            return sbd_module
        if name == "stanza.pipeline.core":
            return pipeline_core_module
        return real_import_module(name, package)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        configure_argos_environment(tmp_path)

    pkg = types.SimpleNamespace(package_path=tmp_path / "translate-en_zh")
    sentencizer = _FakeStanzaSentencizer(pkg)
    assert sentencizer.lazy_pipeline() == "pipeline"
    pipeline_mock.assert_called_once_with(
        lang="en",
        dir=str(pkg.package_path / "stanza"),
        processors="tokenize",
        use_gpu=False,
        logging_level="WARNING",
        download_method="none",
    )


def test_mt_engine_fails_fast_when_offline_stanza_tokenizer_is_missing():
    from models.mt import MTEngine, TranslationError

    class _FakeLanguage:
        def __init__(self, code: str, translation: object | None = None) -> None:
            self.code = code
            self._translation = translation

        def get_translation(self, other) -> object | None:  # noqa: ANN001
            return self._translation if other.code == "en" else None

    translation = types.SimpleNamespace(translate=MagicMock(return_value="你好"))
    fake_languages = [_FakeLanguage("zh", translation), _FakeLanguage("en")]
    translate_module = types.SimpleNamespace(get_installed_languages=lambda: fake_languages)

    with patch.object(MTEngine, "_get_translate_module", return_value=translate_module), \
         patch("models.mt._validate_stanza_dependency", return_value="MT sentence tokenizer unavailable for zh->en: tokenizer missing"), \
         patch("models.mt.describe_argos_package_dirs", return_value="E:/fake/argos"):
        with pytest.raises(
            TranslationError,
            match="MT sentence tokenizer unavailable for zh->en: tokenizer missing",
        ):
            MTEngine().translate("你好", "zh", "en")

    translation.translate.assert_not_called()


def test_validate_mt_runtime_skips_stanza_for_en_to_zh(tmp_path):
    from models.mt import validate_mt_runtime

    class _FakeTranslation:
        def __init__(self, package_path: Path) -> None:
            self.pkg = types.SimpleNamespace(
                package_path=package_path,
                packaged_sbd_path=package_path / "stanza",
                from_code="en",
            )

    class _FakeLanguage:
        def __init__(self, code: str, translation: object | None = None) -> None:
            self.code = code
            self._translation = translation

        def get_translation(self, other) -> object | None:  # noqa: ANN001
            return self._translation if other.code == "zh" else None

    package_path = tmp_path / "translate-en_zh"
    (package_path / "model").mkdir(parents=True)
    translation = _FakeTranslation(package_path)
    fake_languages = [_FakeLanguage("en", translation), _FakeLanguage("zh")]
    translate_module = types.SimpleNamespace(get_installed_languages=lambda: fake_languages)
    settings_module = types.SimpleNamespace(package_data_dir=None, package_dirs=[])
    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.translate":
            return translate_module
        if name == "argostranslate.settings":
            return settings_module
        return real_import_module(name, package)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        issues = validate_mt_runtime(package_dir=tmp_path, allow_network=False, required_pairs=[("en", "zh")])

    assert issues == []


def test_mt_engine_uses_direct_argos_sentencizer_for_en_to_zh():
    from models.mt import MTEngine

    class _FakeLanguage:
        def __init__(self, code: str, translation: object | None = None) -> None:
            self.code = code
            self._translation = translation

        def get_translation(self, other) -> object | None:  # noqa: ANN001
            return self._translation if other.code == "zh" else None

    original_sentencizer = MagicMock()
    package_translation = types.SimpleNamespace(
        pkg=types.SimpleNamespace(package_path=Path("models/data/argos/translate-en_zh")),
        sentencizer=original_sentencizer,
        translate=MagicMock(return_value="你好"),
    )
    cached_translation = types.SimpleNamespace(
        underlying=package_translation,
        translate=package_translation.translate,
    )
    fake_languages = [_FakeLanguage("en", cached_translation), _FakeLanguage("zh")]
    translate_module = types.SimpleNamespace(get_installed_languages=lambda: fake_languages)

    with patch.object(MTEngine, "_get_translate_module", return_value=translate_module), \
         patch("models.mt.describe_argos_package_dirs", return_value="E:/fake/argos"), \
         patch("models.mt._validate_stanza_dependency", return_value=None) as mock_validate:
        result = MTEngine().translate("hello world", "en", "zh")

    assert result == "你好"
    assert package_translation.sentencizer is not original_sentencizer
    assert package_translation.sentencizer.split_sentences("hello world") == ["hello world"]
    mock_validate.assert_called_once_with(
        translation=cached_translation,
        source_lang="en",
        target_lang="zh",
        allow_network=False,
    )


def test_validate_mt_runtime_handles_cached_translation_wrappers(tmp_path):
    from models.mt import validate_mt_runtime

    class _FakeLanguage:
        def __init__(self, code: str, translation: object | None = None) -> None:
            self.code = code
            self._translation = translation

        def get_translation(self, other) -> object | None:  # noqa: ANN001
            return self._translation if other.code == "en" else None

    package_path = tmp_path / "translate-zh_en"
    (package_path / "model").mkdir(parents=True)
    package_translation = types.SimpleNamespace(
        pkg=types.SimpleNamespace(
            package_path=package_path,
            packaged_sbd_path=package_path / "stanza",
            from_code="zh",
        )
    )
    cached_translation = types.SimpleNamespace(underlying=package_translation)
    fake_languages = [_FakeLanguage("zh", cached_translation), _FakeLanguage("en")]
    translate_module = types.SimpleNamespace(get_installed_languages=lambda: fake_languages)
    settings_module = types.SimpleNamespace(package_data_dir=None, package_dirs=[])
    stanza_module = types.SimpleNamespace(Pipeline=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("tokenizer missing")))
    pipeline_core_module = types.SimpleNamespace(DownloadMethod=types.SimpleNamespace(NONE="none"))
    real_import_module = importlib.import_module

    def _fake_import_module(name: str, package=None):
        if name == "argostranslate.translate":
            return translate_module
        if name == "argostranslate.settings":
            return settings_module
        if name == "stanza":
            return stanza_module
        if name == "stanza.pipeline.core":
            return pipeline_core_module
        return real_import_module(name, package)

    with patch("models.mt.importlib.import_module", side_effect=_fake_import_module):
        issues = validate_mt_runtime(package_dir=tmp_path, allow_network=False, required_pairs=[("zh", "en")])

    assert issues == ["MT sentence tokenizer unavailable for zh->en: tokenizer missing"]
