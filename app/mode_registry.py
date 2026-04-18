"""Canonical req1 mode registry.

This module is intentionally declarative-only for M0-PR1.
It freezes the approved 12 leaf modes as metadata without changing
runtime pipeline execution behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

ModeKey = Literal[
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
]

GroupKey = Literal[
    "same_text_to_speech",
    "same_speech_to_text",
    "cross_text_to_speech",
    "cross_speech_to_text",
    "cross_text_to_text",
    "cross_speech_to_speech",
]

InputType = Literal["text", "audio"]
OutputType = Literal["text", "audio"]
LanguageCode = Literal["zh", "en"]
PipelineStep = Literal["tts", "asr", "mt"]


@dataclass(frozen=True, slots=True)
class ModeDefinition:
    """Frozen internal mode metadata shape for M0-PR1."""

    mode_key: ModeKey
    group_key: GroupKey
    input_type: InputType
    output_type: OutputType
    source_lang: LanguageCode
    target_lang: LanguageCode
    pipeline_chain: tuple[PipelineStep, ...]


MODE_REGISTRY: Final[tuple[ModeDefinition, ...]] = (
    ModeDefinition(
        mode_key="tts_zh_zh",
        group_key="same_text_to_speech",
        input_type="text",
        output_type="audio",
        source_lang="zh",
        target_lang="zh",
        pipeline_chain=("tts",),
    ),
    ModeDefinition(
        mode_key="tts_en_en",
        group_key="same_text_to_speech",
        input_type="text",
        output_type="audio",
        source_lang="en",
        target_lang="en",
        pipeline_chain=("tts",),
    ),
    ModeDefinition(
        mode_key="asr_zh_zh",
        group_key="same_speech_to_text",
        input_type="audio",
        output_type="text",
        source_lang="zh",
        target_lang="zh",
        pipeline_chain=("asr",),
    ),
    ModeDefinition(
        mode_key="asr_en_en",
        group_key="same_speech_to_text",
        input_type="audio",
        output_type="text",
        source_lang="en",
        target_lang="en",
        pipeline_chain=("asr",),
    ),
    ModeDefinition(
        mode_key="mt_tts_zh_en",
        group_key="cross_text_to_speech",
        input_type="text",
        output_type="audio",
        source_lang="zh",
        target_lang="en",
        pipeline_chain=("mt", "tts"),
    ),
    ModeDefinition(
        mode_key="mt_tts_en_zh",
        group_key="cross_text_to_speech",
        input_type="text",
        output_type="audio",
        source_lang="en",
        target_lang="zh",
        pipeline_chain=("mt", "tts"),
    ),
    ModeDefinition(
        mode_key="asr_mt_zh_en",
        group_key="cross_speech_to_text",
        input_type="audio",
        output_type="text",
        source_lang="zh",
        target_lang="en",
        pipeline_chain=("asr", "mt"),
    ),
    ModeDefinition(
        mode_key="asr_mt_en_zh",
        group_key="cross_speech_to_text",
        input_type="audio",
        output_type="text",
        source_lang="en",
        target_lang="zh",
        pipeline_chain=("asr", "mt"),
    ),
    ModeDefinition(
        mode_key="mt_zh_en",
        group_key="cross_text_to_text",
        input_type="text",
        output_type="text",
        source_lang="zh",
        target_lang="en",
        pipeline_chain=("mt",),
    ),
    ModeDefinition(
        mode_key="mt_en_zh",
        group_key="cross_text_to_text",
        input_type="text",
        output_type="text",
        source_lang="en",
        target_lang="zh",
        pipeline_chain=("mt",),
    ),
    ModeDefinition(
        mode_key="asr_mt_tts_zh_en",
        group_key="cross_speech_to_speech",
        input_type="audio",
        output_type="audio",
        source_lang="zh",
        target_lang="en",
        pipeline_chain=("asr", "mt", "tts"),
    ),
    ModeDefinition(
        mode_key="asr_mt_tts_en_zh",
        group_key="cross_speech_to_speech",
        input_type="audio",
        output_type="audio",
        source_lang="en",
        target_lang="zh",
        pipeline_chain=("asr", "mt", "tts"),
    ),
)


def list_mode_definitions() -> tuple[ModeDefinition, ...]:
    """Return the frozen internal mode registry."""

    return MODE_REGISTRY


def get_mode_definition(mode_key: ModeKey) -> ModeDefinition:
    """Look up one mode definition by key."""

    for mode in MODE_REGISTRY:
        if mode.mode_key == mode_key:
            return mode
    raise KeyError(f"Unknown mode_key: {mode_key}")
