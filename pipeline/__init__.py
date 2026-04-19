"""Unified pipeline entrypoint driven by frozen req1 mode keys."""

from __future__ import annotations

import logging
from typing import Any

from app.mode_registry import ModeDefinition
from pipeline._utils import get_input_audio_path, get_input_text, history_payload, resolve_mode_definition
from pipeline.composite import run_asr_mt_text, run_asr_mt_tts, run_composite_mode, run_mt
from pipeline.single import run_single_mode
from storage.history import HistoryManager

logger = logging.getLogger(__name__)

_history_cache: dict[str, HistoryManager] = {}


def _select_runner(mode: ModeDefinition):
    """Select the correct composition runner for a frozen mode."""

    if mode.pipeline_chain in {("tts",), ("asr",)}:
        return run_single_mode
    return run_composite_mode


def run_pipeline(mode: str, config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Run one conversion using a frozen mode_key."""

    mode_definition = resolve_mode_definition(mode)
    logger.info("run_pipeline start: requested=%s, mode_key=%s", mode, mode_definition.mode_key)

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
    result: dict[str, Any],
) -> None:
    """Persist history using the current normalized storage contract."""

    storage_cfg = config["storage"]
    cache_key = storage_cfg["history_dir"]
    payload = history_payload(mode_definition, result)

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
    "run_asr_mt_text",
    "run_asr_mt_tts",
    "run_composite_mode",
    "run_mt",
    "run_pipeline",
    "run_single_mode",
]
