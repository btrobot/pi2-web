"""Locked regression corpus for zh->en speech-chain preprocessing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.mode_registry import get_mode_definition
from pipeline.composite import run_composite_mode
from pipeline.speech_mt_preprocess import inspect_speech_mt_text, prepare_speech_mt_text

_CORPUS_PATH = Path(__file__).parent / "fixtures" / "speech_chain" / "pr2b_regression_corpus.json"


def _load_corpus() -> dict:
    return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def config(mock_config):
    return mock_config


def test_speech_chain_regression_corpus_shape_is_locked():
    corpus = _load_corpus()

    assert set(corpus.keys()) == {"target_cases", "non_target_modes", "same_language_modes"}
    assert len(corpus["target_cases"]) == 8
    assert len(corpus["non_target_modes"]) == 4
    assert len(corpus["same_language_modes"]) == 2

    for case in corpus["target_cases"]:
        assert set(case.keys()) == {
            "id",
            "raw_text",
            "expected_output",
            "expected_candidate",
            "expected_fallback",
            "expected_fallback_reason",
        }
    for mode_case in corpus["non_target_modes"]:
        assert set(mode_case.keys()) in (
            {"mode_key", "input_text"},
            {"mode_key", "recognized_text"},
        )
    for mode_case in corpus["same_language_modes"]:
        assert set(mode_case.keys()) == {"mode_key", "recognized_text"}


@pytest.mark.parametrize("case", _load_corpus()["target_cases"], ids=lambda case: case["id"])
def test_speech_chain_regression_corpus_matches_expected_outputs(case):
    inspection = inspect_speech_mt_text(case["raw_text"])

    assert inspection.candidate_text == case["expected_candidate"]
    assert inspection.output_text == case["expected_output"]
    assert inspection.fallback_applied is case["expected_fallback"]
    assert inspection.fallback_reason == case["expected_fallback_reason"]
    assert prepare_speech_mt_text(case["raw_text"]) == case["expected_output"]
    assert prepare_speech_mt_text(case["expected_output"]) == case["expected_output"]


@pytest.mark.parametrize("mode_case", _load_corpus()["non_target_modes"], ids=lambda case: case["mode_key"])
def test_speech_chain_regression_non_target_modes_never_invoke_preprocess(config, mode_case):
    mode = get_mode_definition(mode_case["mode_key"])
    input_text = mode_case.get("input_text")
    recognized_text = mode_case.get("recognized_text")

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav") as mock_capture, \
         patch("pipeline.composite.recognize_audio", return_value=recognized_text) as mock_recognize, \
         patch("pipeline.composite._prepare_text_for_speech_mt") as mock_prepare, \
         patch("pipeline.composite.translate_text", return_value="translated") as mock_translate, \
         patch("pipeline.composite.synthesize_text", return_value="/tmp/output.wav"):
        result = run_composite_mode(mode, config=config, input_text=input_text)

    mock_prepare.assert_not_called()
    if mode.pipeline_chain[0] == "asr":
        mock_capture.assert_called_once()
        mock_recognize.assert_called_once()
        expected_text = recognized_text
    else:
        mock_capture.assert_not_called()
        mock_recognize.assert_not_called()
        expected_text = input_text
    mock_translate.assert_called_once_with(
        text=expected_text,
        source_lang=mode.source_lang,
        target_lang=mode.target_lang,
    )
    assert result["source_text"] == expected_text


@pytest.mark.parametrize("mode_case", _load_corpus()["same_language_modes"], ids=lambda case: case["mode_key"])
def test_speech_chain_regression_same_language_asr_modes_never_invoke_preprocess(config, mode_case):
    mode = get_mode_definition(mode_case["mode_key"])

    with patch("pipeline.composite.capture_audio", return_value="/tmp/input.wav"), \
         patch("pipeline.composite.recognize_audio", return_value=mode_case["recognized_text"]), \
         patch("pipeline.composite._prepare_text_for_speech_mt") as mock_prepare:
        result = run_composite_mode(mode, config=config)

    mock_prepare.assert_not_called()
    assert result["source_text"] == mode_case["recognized_text"]
    assert result["output_text"] == mode_case["recognized_text"]
