"""Targeted preprocess helpers for zh->en speech-to-MT composite modes."""

from __future__ import annotations

from dataclasses import dataclass
import re

_ELLIPSIS = "..."
_MAX_BUCKET_CHARS = 24
_WHITESPACE_RE = re.compile(r"\s+")
_CLAUSE_BOUNDARY_RE = re.compile(r"\.\.\.|[,.?!:;]")
_PUNCT_TRANSLATIONS = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "？": "?",
        "！": "!",
        "：": ":",
        "；": ";",
    }
)


@dataclass(frozen=True)
class _Clause:
    text: str
    boundary: str = ""


@dataclass(frozen=True)
class SpeechMtPreprocessInspection:
    raw_text: str
    normalized_text: str
    candidate_text: str
    output_text: str
    used_clause_split: bool
    fallback_applied: bool
    fallback_reason: str | None
    raw_meaningful_char_count: int
    candidate_meaningful_char_count: int


def prepare_speech_mt_text(text: str) -> str:
    """Normalize zh ASR transcript text before handing it to MT."""

    return inspect_speech_mt_text(text).output_text


def inspect_speech_mt_text(text: str) -> SpeechMtPreprocessInspection:
    """Return the preprocess outcome plus internal gate details for tests/evidence."""

    normalized_text = _normalize_text(text)
    if not normalized_text:
        return SpeechMtPreprocessInspection(
            raw_text=text,
            normalized_text=normalized_text,
            candidate_text="",
            output_text=text,
            used_clause_split=False,
            fallback_applied=True,
            fallback_reason="empty",
            raw_meaningful_char_count=_meaningful_char_count(text),
            candidate_meaningful_char_count=0,
        )

    used_clause_split = bool(_CLAUSE_BOUNDARY_RE.search(normalized_text))
    if used_clause_split:
        candidate_text = _rejoin_clauses(_dedupe_adjacent_clauses(_split_clauses(normalized_text)))
    else:
        candidate_text = _bucket_text(normalized_text)

    raw_count = _meaningful_char_count(text)
    candidate_count = _meaningful_char_count(candidate_text)
    if not candidate_text:
        return SpeechMtPreprocessInspection(
            raw_text=text,
            normalized_text=normalized_text,
            candidate_text=candidate_text,
            output_text=text,
            used_clause_split=used_clause_split,
            fallback_applied=True,
            fallback_reason="empty",
            raw_meaningful_char_count=raw_count,
            candidate_meaningful_char_count=candidate_count,
        )

    fallback_reason: str | None = None
    output_text = candidate_text
    if raw_count and candidate_count < raw_count * 0.8:
        fallback_reason = "count_drop"
        output_text = text

    return SpeechMtPreprocessInspection(
        raw_text=text,
        normalized_text=normalized_text,
        candidate_text=candidate_text,
        output_text=output_text,
        used_clause_split=used_clause_split,
        fallback_applied=fallback_reason is not None,
        fallback_reason=fallback_reason,
        raw_meaningful_char_count=raw_count,
        candidate_meaningful_char_count=candidate_count,
    )


def _normalize_text(text: str) -> str:
    collapsed = _WHITESPACE_RE.sub(" ", text).strip()
    return collapsed.replace("……", _ELLIPSIS).translate(_PUNCT_TRANSLATIONS)


def _split_clauses(text: str) -> list[_Clause]:
    clauses: list[_Clause] = []
    start = 0

    for match in _CLAUSE_BOUNDARY_RE.finditer(text):
        clause_text = text[start:match.start()].strip()
        if clause_text:
            clauses.append(_Clause(text=clause_text, boundary=match.group(0)))
        start = match.end()

    trailing_text = text[start:].strip()
    if trailing_text:
        clauses.append(_Clause(text=trailing_text))
    return clauses


def _dedupe_adjacent_clauses(clauses: list[_Clause]) -> list[_Clause]:
    deduped: list[_Clause] = []
    for clause in clauses:
        if deduped and clause.text == deduped[-1].text:
            continue
        deduped.append(clause)
    return deduped


def _rejoin_clauses(clauses: list[_Clause]) -> str:
    parts: list[str] = []
    for clause in clauses:
        parts.append(f"{clause.text}{clause.boundary}")
    return " ".join(parts)


def _bucket_text(text: str) -> str:
    dense_text = text.replace(" ", "")
    if not dense_text:
        return ""

    buckets = [
        dense_text[index:index + _MAX_BUCKET_CHARS]
        for index in range(0, len(dense_text), _MAX_BUCKET_CHARS)
    ]
    return " ".join(buckets)


def _meaningful_char_count(text: str) -> int:
    normalized = _normalize_text(text)
    count = 0
    index = 0

    while index < len(normalized):
        if normalized[index].isspace():
            index += 1
            continue
        if normalized.startswith(_ELLIPSIS, index):
            index += len(_ELLIPSIS)
            continue
        if normalized[index] in ",.?!:;":
            index += 1
            continue
        count += 1
        index += 1

    return count


__all__ = ["SpeechMtPreprocessInspection", "inspect_speech_mt_text", "prepare_speech_mt_text"]
