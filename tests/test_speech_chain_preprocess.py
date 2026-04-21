"""Focused rule tests for zh->en speech-chain preprocessing."""

from __future__ import annotations

from pipeline.speech_mt_preprocess import prepare_speech_mt_text


def test_speech_chain_preprocess_collapses_whitespace_and_normalizes_supported_punctuation():
    text = "  \u4f60\u597d\uff0c   \u4e16\u754c\u3002  \u518d\u89c1\uff1f  "

    assert prepare_speech_mt_text(text) == "\u4f60\u597d, \u4e16\u754c. \u518d\u89c1?"


def test_speech_chain_preprocess_limits_normalization_to_supported_punctuation():
    text = "\u4f60\u597d\u2014\u2014\u4e16\u754c\uff1f"

    assert prepare_speech_mt_text(text) == "\u4f60\u597d\u2014\u2014\u4e16\u754c?"


def test_speech_chain_preprocess_normalizes_ellipsis_variants():
    text = "\u4f60\u597d\u2026\u2026\u4e16\u754c..."

    assert prepare_speech_mt_text(text) == "\u4f60\u597d... \u4e16\u754c..."


def test_speech_chain_preprocess_normalizes_colon_and_semicolon_variants():
    text = "\u63d0\u793a\uff1a\u5148\u7b49\uff1b\u518d\u8bf4"

    assert prepare_speech_mt_text(text) == "\u63d0\u793a: \u5148\u7b49; \u518d\u8bf4"


def test_speech_chain_preprocess_dedupes_only_adjacent_exact_clauses():
    text = "\u4f60\u597d\u3002\u4f60\u597d\u3002\u4e16\u754c\u3002\u4eca\u5929\u3002\u5929\u6c14\u3002\u5f88\u597d\u3002"

    assert prepare_speech_mt_text(text) == "\u4f60\u597d. \u4e16\u754c. \u4eca\u5929. \u5929\u6c14. \u5f88\u597d."


def test_speech_chain_preprocess_keeps_non_adjacent_duplicate_clauses():
    text = "\u4f60\u597d\u3002\u4e16\u754c\u3002\u4f60\u597d\u3002\u4eca\u5929\u3002"

    assert prepare_speech_mt_text(text) == "\u4f60\u597d. \u4e16\u754c. \u4f60\u597d. \u4eca\u5929."


def test_speech_chain_preprocess_buckets_unpunctuated_text_at_24_chars():
    text = "\u7532" * 24 + "\u4e59" * 3

    assert prepare_speech_mt_text(text) == ("\u7532" * 24) + " " + ("\u4e59" * 3)


def test_speech_chain_preprocess_falls_back_to_raw_when_cleaned_output_is_empty():
    text = "  \uff0c  \u3002  \uff1f  "

    assert prepare_speech_mt_text(text) == text


def test_speech_chain_preprocess_falls_back_to_raw_when_cleaning_drops_more_than_20_percent():
    text = "\u4f60\u597d\u3002\u4f60\u597d\u3002\u4f60\u597d\u3002\u4f60\u597d\u3002\u518d\u89c1\u3002"

    assert prepare_speech_mt_text(text) == text


def test_speech_chain_preprocess_is_idempotent_for_clean_punctuated_input():
    text = "\u4f60\u597d, \u4e16\u754c. \u518d\u89c1?"

    assert prepare_speech_mt_text(text) == text
    assert prepare_speech_mt_text(prepare_speech_mt_text(text)) == text


def test_speech_chain_preprocess_is_idempotent_for_bucketed_input():
    text = ("\u7532" * 24) + " " + ("\u4e59" * 2)

    assert prepare_speech_mt_text(text) == text
    assert prepare_speech_mt_text(prepare_speech_mt_text(text)) == text
