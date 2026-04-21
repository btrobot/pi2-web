"""Focused rule tests for speech-MT atomic segmentation and chunk packing."""

from __future__ import annotations

from pipeline.speech_mt_chunking import (
    EN_CHUNK_BUDGET,
    EN_FALLBACK_BUCKET_TOKENS,
    MAX_ATOMIC_UNITS_PER_CHUNK,
    TAIL_REPEAT_MIN_NORMALIZED_LENGTH,
    ZH_CHUNK_BUDGET,
    ZH_FALLBACK_BUCKET_CHARS,
    assemble_speech_mt_output,
    guard_repeated_tail_translation,
    inspect_speech_mt_chunking,
)


def test_chunking_prefers_punctuation_split_and_packs_at_four_units_per_chunk():
    text = "alpha. beta? gamma! delta: epsilon; zeta"

    inspection = inspect_speech_mt_chunking(text, source_lang="en", target_lang="zh")

    assert inspection.normalized_text == text
    assert inspection.atomic_units == ("alpha.", "beta?", "gamma!", "delta:", "epsilon;", "zeta")
    assert inspection.packed_chunks == ("alpha. beta? gamma! delta:", "epsilon; zeta")
    assert inspection.used_punctuation_split is True
    assert inspection.fallback_strategy is None
    assert inspection.chunk_budget == EN_CHUNK_BUDGET
    assert inspection.max_atomic_units_per_chunk == MAX_ATOMIC_UNITS_PER_CHUNK


def test_chunking_packs_four_short_atomic_units_before_starting_next_chunk():
    text = "one. two. three. four. five."

    inspection = inspect_speech_mt_chunking(text, source_lang="en", target_lang="zh")

    assert inspection.atomic_units == ("one.", "two.", "three.", "four.", "five.")
    assert inspection.packed_chunks == ("one. two. three. four.", "five.")


def test_chunking_uses_zh_char_buckets_when_no_punctuation_exists():
    text = ("甲" * 24) + ("乙" * 24) + ("丙" * 24) + ("丁" * 3)

    inspection = inspect_speech_mt_chunking(text, source_lang="zh", target_lang="en")

    assert inspection.atomic_units == (
        "甲" * ZH_FALLBACK_BUCKET_CHARS,
        "乙" * ZH_FALLBACK_BUCKET_CHARS,
        "丙" * ZH_FALLBACK_BUCKET_CHARS,
        "丁" * 3,
    )
    assert inspection.packed_chunks == (
        ("甲" * ZH_FALLBACK_BUCKET_CHARS)
        + " "
        + ("乙" * ZH_FALLBACK_BUCKET_CHARS)
        + " "
        + ("丙" * ZH_FALLBACK_BUCKET_CHARS),
        "丁" * 3,
    )
    assert inspection.used_punctuation_split is False
    assert inspection.fallback_strategy == "zh_char_bucket"


def test_chunking_uses_en_token_buckets_when_no_punctuation_exists():
    tokens = [f"word{index}" for index in range(1, 49)]
    text = " ".join(tokens)

    inspection = inspect_speech_mt_chunking(text, source_lang="en", target_lang="zh")

    assert inspection.atomic_units == (
        " ".join(tokens[0:EN_FALLBACK_BUCKET_TOKENS]),
        " ".join(tokens[EN_FALLBACK_BUCKET_TOKENS:EN_FALLBACK_BUCKET_TOKENS * 2]),
        " ".join(tokens[EN_FALLBACK_BUCKET_TOKENS * 2:EN_FALLBACK_BUCKET_TOKENS * 3]),
        " ".join(tokens[EN_FALLBACK_BUCKET_TOKENS * 3:EN_FALLBACK_BUCKET_TOKENS * 4]),
    )
    assert inspection.packed_chunks == (
        " ".join(tokens[0:EN_FALLBACK_BUCKET_TOKENS * 3]),
        " ".join(tokens[EN_FALLBACK_BUCKET_TOKENS * 3:EN_FALLBACK_BUCKET_TOKENS * 4]),
    )
    assert inspection.used_punctuation_split is False
    assert inspection.fallback_strategy == "en_token_bucket"
    assert inspection.chunk_budget == EN_CHUNK_BUDGET


def test_chunking_respects_budget_before_three_unit_cap():
    unit = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi"
    text = f"{unit}. {unit}. {unit}. {unit}."

    inspection = inspect_speech_mt_chunking(text, source_lang="en", target_lang="zh")

    assert inspection.atomic_units == (f"{unit}.", f"{unit}.", f"{unit}.", f"{unit}.")
    assert inspection.packed_chunks == (
        f"{unit}. {unit}.",
        f"{unit}. {unit}.",
    )


def test_chunking_preserves_current_single_shot_runtime_inputs_by_language_pair():
    zh_text = "你好。你好。世界。今天。天气。很好。"
    en_text = "hello hello world today weather is good"

    zh_inspection = inspect_speech_mt_chunking(zh_text, source_lang="zh", target_lang="en")
    en_inspection = inspect_speech_mt_chunking(en_text, source_lang="en", target_lang="zh")

    assert zh_inspection.single_shot_mt_input == "你好. 世界. 今天. 天气. 很好."
    assert en_inspection.single_shot_mt_input == en_text


def test_chunking_inspection_is_idempotent_for_clean_punctuated_input():
    text = "hello world. this is steady. chunk planning stays stable."

    first = inspect_speech_mt_chunking(text, source_lang="en", target_lang="zh")
    second = inspect_speech_mt_chunking(first.normalized_text, source_lang="en", target_lang="zh")

    assert first.packed_chunks == (text,)
    assert second.normalized_text == first.normalized_text
    assert second.atomic_units == first.atomic_units
    assert second.packed_chunks == first.packed_chunks
    assert second.fallback_strategy == first.fallback_strategy


def test_assemble_speech_mt_output_joins_english_chunks_with_single_spaces():
    assert assemble_speech_mt_output(
        ["hello   world", " from   pi ", " five"],
        target_lang="en",
    ) == "hello world from pi five"


def test_assemble_speech_mt_output_dense_joins_chinese_chunks_and_cleans_punctuation_spacing():
    assert assemble_speech_mt_output(
        ["你好 ", " 世界 ！", " 再见。"],
        target_lang="zh",
    ) == "你好世界！再见。"


def test_guard_repeated_tail_translation_trims_spaced_suffix_loops():
    prefix = " ".join(f"word{index}" for index in range(1, 23))
    repeated_unit = "and on"
    text = f"{prefix} {repeated_unit} {repeated_unit} {repeated_unit} {repeated_unit}"

    assert len(text) >= TAIL_REPEAT_MIN_NORMALIZED_LENGTH
    assert guard_repeated_tail_translation(
        text,
        target_lang="en",
        source_atomic_units=("alpha.", "beta.", "gamma."),
        source_packed_chunks=("alpha beta gamma", "delta epsilon zeta"),
    ) == f"{prefix} {repeated_unit}"


def test_guard_repeated_tail_translation_trims_dense_suffix_loops():
    prefix = "这是一个很长的翻译结果" * 10
    repeated_unit = "继续测试"
    text = f"{prefix}{repeated_unit}{repeated_unit}{repeated_unit}"

    assert guard_repeated_tail_translation(
        text,
        target_lang="zh",
        source_atomic_units=("第一句。", "第二句。", "第三句。"),
        source_packed_chunks=("第一句。 第二句。", "第三句。 第四句。"),
    ) == f"{prefix}{repeated_unit}"


def test_guard_repeated_tail_translation_preserves_legitimate_source_tail_repetition():
    prefix = " ".join(f"word{index}" for index in range(1, 23))
    repeated_unit = "again now"
    text = f"{prefix} {repeated_unit} {repeated_unit} {repeated_unit}"

    assert guard_repeated_tail_translation(
        text,
        target_lang="en",
        source_atomic_units=("重复。", "重复。", "重复。"),
        source_packed_chunks=("chunk-a", "chunk-b"),
    ) == text


def test_guard_repeated_tail_translation_ignores_short_outputs():
    text = "short tail short tail short tail"

    assert guard_repeated_tail_translation(
        text,
        target_lang="en",
        source_atomic_units=(),
        source_packed_chunks=(),
    ) == text
