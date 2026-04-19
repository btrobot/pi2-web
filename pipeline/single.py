"""Single-step pipeline composition for same-language leaf modes."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.mode_registry import ModeDefinition
from pipeline._utils import build_base_result
from pipeline.operations import capture_audio, recognize_audio, synthesize_text

logger = logging.getLogger(__name__)


def run_single_mode(
    mode: ModeDefinition,
    *,
    config: dict[str, Any],
    input_text: str | None = None,
    input_audio_path: str | None = None,
    playback: bool = True,
) -> dict[str, Any]:
    """Execute a single-step frozen mode definition."""

    result = build_base_result(mode)
    start = time.monotonic()

    try:
        if mode.pipeline_chain == ("tts",):
            source_text = input_text or ""
            result["source_text"] = source_text
            result["output_audio_path"] = synthesize_text(
                config=config,
                text=source_text,
                lang=mode.target_lang,
                prefix=mode.mode_key,
                playback=playback,
            )
        elif mode.pipeline_chain == ("asr",):
            recorded_path = input_audio_path or capture_audio(config=config, prefix=mode.mode_key)
            result["input_audio_path"] = recorded_path
            recognized = recognize_audio(config=config, audio_path=recorded_path, lang=mode.source_lang)
            result["source_text"] = recognized
            result["output_text"] = recognized
        else:
            raise ValueError(f"run_single_mode does not support chain {mode.pipeline_chain!r}")
    except Exception as exc:  # noqa: BLE001 - pipeline returns structured errors
        result["error"] = str(exc)

    elapsed = time.monotonic() - start
    logger.info(
        "run_single_mode complete: mode_key=%s, elapsed=%.2fs, error=%s",
        mode.mode_key,
        elapsed,
        result.get("error"),
    )
    return result


__all__ = ["run_single_mode"]
