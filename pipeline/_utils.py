"""Pipeline helper utilities for mode-key execution."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.mode_registry import ModeDefinition, get_mode_definition, list_mode_definitions

MODE_KEYS = frozenset(mode.mode_key for mode in list_mode_definitions())
LEGACY_MODES = frozenset({"tts", "asr", "mt_tts", "asr_mt"})


def make_output_path(storage_cfg: dict[str, Any], prefix: str) -> str:
    """Create a timestamped WAV path under the recordings directory."""

    recordings_dir = Path(storage_cfg["recordings_dir"])
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return str(recordings_dir / f"{prefix}_{int(time.time())}.wav")


def resolve_mode_definition(requested_mode: str, kwargs: dict[str, Any]) -> tuple[ModeDefinition, str | None]:
    """Resolve either a frozen mode_key or a temporary legacy alias to a mode."""

    if requested_mode in MODE_KEYS:
        return get_mode_definition(requested_mode), None

    if requested_mode not in LEGACY_MODES:
        supported = ", ".join(sorted(MODE_KEYS | LEGACY_MODES))
        raise ValueError(f"不支持的管线模式: {requested_mode!r}; 支持: {supported}")

    if requested_mode in {"tts", "asr"}:
        lang = kwargs.get("lang")
        if lang not in {"zh", "en"}:
            raise ValueError(f"旧模式 {requested_mode!r} 需要 lang='zh' 或 'en'")
        return get_mode_definition(f"{requested_mode}_{lang}_{lang}"), requested_mode

    source_lang = kwargs.get("source_lang")
    target_lang = kwargs.get("target_lang")
    if source_lang not in {"zh", "en"} or target_lang not in {"zh", "en"}:
        raise ValueError(
            f"旧模式 {requested_mode!r} 需要 source_lang/target_lang 属于 {{'zh', 'en'}}",
        )

    if requested_mode == "mt_tts":
        return get_mode_definition(f"mt_tts_{source_lang}_{target_lang}"), requested_mode

    return get_mode_definition(f"asr_mt_tts_{source_lang}_{target_lang}"), requested_mode


def get_input_text(kwargs: dict[str, Any]) -> str | None:
    """Return normalized text input from new or legacy argument names."""

    if "input_text" in kwargs:
        return kwargs["input_text"]
    return kwargs.get("text")


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


def history_payload(mode: ModeDefinition, normalized_result: dict[str, Any], legacy_mode: str | None) -> dict[str, Any]:
    """Translate normalized pipeline output into the current history-manager shape."""

    source_text = normalized_result.get("source_text")
    target_text = normalized_result.get("output_text")

    return {
        "record_type": legacy_mode or mode.mode_key,
        "mode_key": mode.mode_key,
        "group_key": mode.group_key,
        "source_lang": mode.source_lang,
        "target_lang": mode.target_lang,
        "source_text": source_text,
        "target_text": target_text,
        "input_text": source_text if mode.input_type == "text" else None,
        "output_text": target_text,
        "input_audio_path": normalized_result.get("input_audio_path"),
        "output_audio_path": normalized_result.get("output_audio_path"),
    }
