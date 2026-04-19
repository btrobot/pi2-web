"""CLI regression tests for the frozen mode-key entrypoints."""

from __future__ import annotations

from unittest.mock import patch

from app.cli import _run_asr, _run_asr_mt, _run_mt_tts, _run_tts


def test_run_tts_uses_frozen_mode_key_and_normalized_audio_output(mock_config) -> None:
    with (
        patch("app.cli._prompt_text", return_value="hello"),
        patch("app.cli.run_pipeline", return_value={"output_audio_path": "/tmp/out.wav"}) as run_pipeline,
        patch("builtins.print") as printer,
    ):
        _run_tts(mock_config, lang="en")

    run_pipeline.assert_called_once_with(mode="tts_en_en", config=mock_config, input_text="hello")
    printer.assert_called_with("朗读完成 | 音频: /tmp/out.wav")


def test_run_asr_uses_frozen_mode_key_and_normalized_text_output(mock_config) -> None:
    with (
        patch("app.cli.run_pipeline", return_value={"output_text": "hello world"}) as run_pipeline,
        patch("builtins.print") as printer,
    ):
        _run_asr(mock_config, lang="en")

    run_pipeline.assert_called_once_with(mode="asr_en_en", config=mock_config)
    printer.assert_any_call("识别结果: hello world")


def test_run_mt_tts_uses_frozen_mode_key_and_normalized_outputs(mock_config) -> None:
    with (
        patch("app.cli._prompt_text", return_value="你好"),
        patch(
            "app.cli.run_pipeline",
            return_value={"output_text": "hello", "output_audio_path": "/tmp/hello.wav"},
        ) as run_pipeline,
        patch("builtins.print") as printer,
    ):
        _run_mt_tts(mock_config)

    run_pipeline.assert_called_once_with(mode="mt_tts_zh_en", config=mock_config, input_text="你好")
    printer.assert_any_call("翻译结果: hello")
    printer.assert_any_call("音频: /tmp/hello.wav")


def test_run_asr_mt_uses_frozen_mode_key_and_normalized_outputs(mock_config) -> None:
    with (
        patch(
            "app.cli.run_pipeline",
            return_value={
                "source_text": "你好",
                "output_text": "hello",
                "output_audio_path": "/tmp/hello.wav",
            },
        ) as run_pipeline,
        patch("builtins.print") as printer,
    ):
        _run_asr_mt(mock_config)

    run_pipeline.assert_called_once_with(mode="asr_mt_tts_zh_en", config=mock_config)
    printer.assert_any_call("识别: 你好")
    printer.assert_any_call("翻译: hello")
    printer.assert_any_call("音频: /tmp/hello.wav")
