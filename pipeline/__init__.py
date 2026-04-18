"""Unified pipeline entrypoint driven by frozen req1 mode keys."""

from __future__ import annotations

import logging
from typing import Any

from app.mode_registry import ModeDefinition
from pipeline._utils import (
    build_base_result,
    get_input_audio_path,
    get_input_text,
    history_payload,
    resolve_mode_definition,
)
from pipeline.composite import (
    run_asr_mt,
    run_asr_mt_text,
    run_asr_mt_tts,
    run_composite_mode,
    run_mt,
    run_mt_tts,
)
from pipeline.single import run_asr, run_single_mode, run_tts
from storage.history import HistoryManager

logger = logging.getLogger(__name__)

_history_cache: dict[str, HistoryManager] = {}


def _select_runner(mode: ModeDefinition):
    """Select the correct composition runner for a frozen mode."""

    if mode.pipeline_chain in {("tts",), ("asr",)}:
        return run_single_mode
    return run_composite_mode


def _run_legacy_compat(
    legacy_mode: str,
    *,
    config: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Execute the temporary legacy selector path for current callers/tests."""

    if legacy_mode == "tts":
        return run_tts(
            text=kwargs["text"],
            lang=kwargs["lang"],
            config=config,
            playback=kwargs.get("playback", True),
        )
    if legacy_mode == "asr":
        return run_asr(
            lang=kwargs["lang"],
            config=config,
            input_audio_path=kwargs.get("input_audio_path"),
        )
    if legacy_mode == "mt_tts":
        return run_mt_tts(
            text=kwargs["text"],
            source_lang=kwargs["source_lang"],
            target_lang=kwargs["target_lang"],
            config=config,
            playback=kwargs.get("playback", True),
        )
    return run_asr_mt(
        source_lang=kwargs["source_lang"],
        target_lang=kwargs["target_lang"],
        config=config,
        input_audio_path=kwargs.get("input_audio_path"),
        playback=kwargs.get("playback", True),
    )


def _enrich_legacy_result(
    mode_definition: ModeDefinition,
    legacy_mode: str,
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    """Overlay legacy wrapper output onto the normalized result contract."""

    result = build_base_result(mode_definition)

    if mode_definition.pipeline_chain == ("tts",):
        result["source_text"] = raw_result.get("source_text") or raw_result.get("text")
        result["output_audio_path"] = raw_result.get("output_audio_path") or raw_result.get("audio_path")
    elif mode_definition.pipeline_chain == ("asr",):
        text_value = raw_result.get("output_text") or raw_result.get("source_text") or raw_result.get("text")
        result["source_text"] = text_value
        result["output_text"] = text_value
        result["input_audio_path"] = raw_result.get("input_audio_path") or raw_result.get("audio_path")
    else:
        result["source_text"] = raw_result.get("source_text")
        result["output_text"] = raw_result.get("output_text") or raw_result.get("translated_text")
        if mode_definition.input_type == "audio":
            result["input_audio_path"] = raw_result.get("input_audio_path")
        if mode_definition.output_type == "audio":
            result["output_audio_path"] = raw_result.get("output_audio_path") or raw_result.get("audio_path")

    result["error"] = raw_result.get("error")
    result.update(raw_result)
    result["legacy_mode"] = legacy_mode
    return result


def run_pipeline(mode: str, config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Run one conversion using a frozen mode_key or temporary legacy alias."""

    mode_definition, legacy_mode = resolve_mode_definition(mode, kwargs)
    logger.info("run_pipeline start: requested=%s, mode_key=%s", mode, mode_definition.mode_key)

    if legacy_mode:
        result = _enrich_legacy_result(
            mode_definition,
            legacy_mode,
            _run_legacy_compat(legacy_mode, config=config, kwargs=kwargs),
        )
    else:
        runner = _select_runner(mode_definition)
        result = runner(
            mode_definition,
            config=config,
            input_text=get_input_text(kwargs),
            input_audio_path=get_input_audio_path(kwargs),
            playback=kwargs.get("playback", True),
        )

    _save_history(
        config=config,
        mode_definition=mode_definition,
        legacy_mode=legacy_mode,
        result=result,
    )

    logger.info(
        "run_pipeline complete: requested=%s, mode_key=%s, error=%s",
        mode,
        mode_definition.mode_key,
        result.get("error"),
    )
    return result


def _save_history(
    *,
    config: dict[str, Any],
    mode_definition: ModeDefinition,
    legacy_mode: str | None,
    result: dict[str, Any],
) -> None:
    """Persist history using the current legacy storage contract."""

    storage_cfg = config["storage"]
    cache_key = storage_cfg["history_dir"]
    payload = history_payload(mode_definition, result, legacy_mode)

    try:
        if cache_key not in _history_cache:
            _history_cache[cache_key] = HistoryManager(
                history_dir=storage_cfg["history_dir"],
                max_records=storage_cfg["max_history"],
            )
        manager = _history_cache[cache_key]
        record = manager.add_record(**payload)
        result["history_id"] = record["id"]
    except Exception as exc:  # pragma: no cover - defensive compatibility path
        logger.error("history save failed: mode_key=%s, error=%s", mode_definition.mode_key, str(exc))


__all__ = [
    "run_asr",
    "run_asr_mt",
    "run_asr_mt_text",
    "run_asr_mt_tts",
    "run_composite_mode",
    "run_mt",
    "run_mt_tts",
    "run_pipeline",
    "run_single_mode",
    "run_tts",
]
