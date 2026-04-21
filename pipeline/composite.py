"""Multi-step pipeline composition for cross-language leaf modes."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any

from app.mode_registry import ModeDefinition, get_mode_definition
from pipeline._utils import build_base_result
from pipeline.operations import capture_audio, recognize_audio, synthesize_text, translate_text
from pipeline.speech_mt_chunking import (
    assemble_speech_mt_output,
    guard_repeated_tail_translation,
    inspect_speech_mt_chunking,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpeechMtTranslationPlan:
    """Internal scaffold for future segmented speech->MT translation."""

    source_text: str
    mt_inputs: tuple[str, ...]
    planned_mt_inputs: tuple[str, ...] = ()
    source_atomic_units: tuple[str, ...] = ()


def _should_segment_speech_mt(mode: ModeDefinition) -> bool:
    """Return whether the ASR cross-language chain should use the speech->MT seam."""

    return (
        mode.pipeline_chain[0] == "asr"
        and "mt" in mode.pipeline_chain
        and mode.source_lang in {"zh", "en"}
        and mode.target_lang in {"zh", "en"}
        and mode.source_lang != mode.target_lang
    )


def _build_segmented_speech_mt_plan(text: str, mode: ModeDefinition) -> SpeechMtTranslationPlan:
    """Build the future segmented-translation plan.

    PR2 computes deterministic atomic-unit chunk planning while preserving the
    current single-shot runtime input until PR3 rolls out chunk-by-chunk MT.
    """

    inspection = inspect_speech_mt_chunking(
        text,
        source_lang=mode.source_lang,
        target_lang=mode.target_lang,
    )
    return SpeechMtTranslationPlan(
        source_text=text,
        mt_inputs=(inspection.single_shot_mt_input,),
        planned_mt_inputs=inspection.packed_chunks,
        source_atomic_units=inspection.atomic_units,
    )


def run_composite_mode(
    mode: ModeDefinition,
    *,
    config: dict[str, Any],
    input_text: str | None = None,
    input_audio_path: str | None = None,
    playback: bool = True,
) -> dict[str, Any]:
    """Execute a multi-step frozen mode definition."""

    result = build_base_result(mode)
    start = time.monotonic()

    try:
        if mode.pipeline_chain[0] == "asr":
            recorded_path = input_audio_path or capture_audio(config=config, prefix=f"{mode.mode_key}_input")
            result["input_audio_path"] = recorded_path
            source_text = recognize_audio(config=config, audio_path=recorded_path, lang=mode.source_lang)
        else:
            source_text = input_text or ""
        result["source_text"] = source_text

        current_text = source_text
        if "mt" in mode.pipeline_chain:
            mt_input = current_text
            if _should_segment_speech_mt(mode):
                translation_plan = _build_segmented_speech_mt_plan(current_text, mode)
                planned_mt_inputs = translation_plan.planned_mt_inputs or translation_plan.mt_inputs
                if len(planned_mt_inputs) <= 1:
                    mt_input = translation_plan.mt_inputs[0]
                    current_text = translate_text(
                        text=mt_input,
                        source_lang=mode.source_lang,
                        target_lang=mode.target_lang,
                    )
                else:
                    translated_chunks = [
                        translate_text(
                            text=chunk,
                            source_lang=mode.source_lang,
                            target_lang=mode.target_lang,
                        )
                        for chunk in planned_mt_inputs
                    ]
                    current_text = assemble_speech_mt_output(translated_chunks, target_lang=mode.target_lang)
                    current_text = guard_repeated_tail_translation(
                        current_text,
                        target_lang=mode.target_lang,
                        source_atomic_units=translation_plan.source_atomic_units,
                        source_packed_chunks=planned_mt_inputs,
                    )
            else:
                current_text = translate_text(
                    text=mt_input,
                    source_lang=mode.source_lang,
                    target_lang=mode.target_lang,
                )
            result["output_text"] = current_text
        elif mode.output_type == "text":
            result["output_text"] = current_text

        if mode.pipeline_chain[-1] == "tts":
            result["output_audio_path"] = synthesize_text(
                config=config,
                text=current_text,
                lang=mode.target_lang,
                prefix=f"{mode.mode_key}_output",
                playback=playback,
            )
    except Exception as exc:  # noqa: BLE001 - pipeline returns structured errors
        result["error"] = str(exc)

    elapsed = time.monotonic() - start
    logger.info(
        "run_composite_mode complete: mode_key=%s, elapsed=%.2fs, error=%s",
        mode.mode_key,
        elapsed,
        result.get("error"),
    )
    return result


def run_mt_tts(
    text: str,
    source_lang: str,
    target_lang: str,
    config: dict[str, Any],
    *,
    playback: bool = True,
) -> dict[str, Any]:
    """Forward wrapper for text-to-audio cross-language modes."""

    mode = get_mode_definition(f"mt_tts_{source_lang}_{target_lang}")
    return run_composite_mode(mode, config=config, input_text=text, playback=playback)


def run_mt(text: str, source_lang: str, target_lang: str, config: dict[str, Any]) -> dict[str, Any]:
    """Forward wrapper for pure MT modes."""

    mode = get_mode_definition(f"mt_{source_lang}_{target_lang}")
    return run_composite_mode(mode, config=config, input_text=text, playback=False)


def run_asr_mt_text(
    source_lang: str,
    target_lang: str,
    config: dict[str, Any],
    *,
    input_audio_path: str | None = None,
) -> dict[str, Any]:
    """Forward wrapper for audio-to-text cross-language modes."""

    mode = get_mode_definition(f"asr_mt_{source_lang}_{target_lang}")
    return run_composite_mode(mode, config=config, input_audio_path=input_audio_path, playback=False)


def run_asr_mt_tts(
    source_lang: str,
    target_lang: str,
    config: dict[str, Any],
    *,
    input_audio_path: str | None = None,
    playback: bool = True,
) -> dict[str, Any]:
    """Forward wrapper for audio-to-audio cross-language modes."""

    mode = get_mode_definition(f"asr_mt_tts_{source_lang}_{target_lang}")
    return run_composite_mode(
        mode,
        config=config,
        input_audio_path=input_audio_path,
        playback=playback,
    )


__all__ = [
    "run_asr_mt_text",
    "run_asr_mt_tts",
    "run_composite_mode",
    "run_mt",
    "run_mt_tts",
]
