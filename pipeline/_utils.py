"""Pipeline helper utilities for mode-key execution."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.mode_registry import ModeDefinition, get_mode_definition, list_mode_definitions

MODE_KEYS = frozenset(mode.mode_key for mode in list_mode_definitions())


def make_output_path(storage_cfg: dict[str, Any], prefix: str) -> str:
    """Create a timestamped WAV path under the recordings directory."""

    recordings_dir = Path(storage_cfg["recordings_dir"])
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return str(recordings_dir / f"{prefix}_{int(time.time())}.wav")


def resolve_mode_definition(requested_mode: str) -> ModeDefinition:
    """Resolve one frozen mode_key."""

    if requested_mode in MODE_KEYS:
        return get_mode_definition(requested_mode)

    supported = ", ".join(sorted(MODE_KEYS))
    raise ValueError(f"不支持的管线模式: {requested_mode!r}; 支持: {supported}")


def get_input_text(kwargs: dict[str, Any]) -> str | None:
    """Return normalized text input if one was provided."""

    return kwargs.get("input_text")


def get_input_audio_path(kwargs: dict[str, Any]) -> str | None:
    """Return normalized audio input path if one was provided."""

    return kwargs.get("input_audio_path")


def build_base_result(mode: ModeDefinition) -> dict[str, Any]:
    """Create the normalized result envelope for one conversion."""

    return {
        "mode_key": mode.mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "input_type": mode.input_type,
        "output_type": mode.output_type,
        "pipeline_chain": mode.pipeline_chain,
        "source_text": None,
        "output_text": None,
        "input_audio_path": None,
        "output_audio_path": None,
        "error": None,
    }


def history_payload(mode: ModeDefinition, normalized_result: dict[str, Any]) -> dict[str, Any]:
    """Translate normalized pipeline output into the current history-manager shape."""

    source_text = normalized_result.get("source_text")
    target_text = normalized_result.get("output_text")
    stores_intermediate_asr_text = mode.input_type == "audio" and "mt" in mode.pipeline_chain
    input_text = source_text if mode.input_type == "text" or stores_intermediate_asr_text else None

    return {
        "record_type": mode.mode_key,
        "mode_key": mode.mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "source_text": source_text,
        "target_text": target_text,
        "input_text": input_text,
        "output_text": target_text,
        "input_audio_path": normalized_result.get("input_audio_path"),
        "output_audio_path": normalized_result.get("output_audio_path"),
    }
