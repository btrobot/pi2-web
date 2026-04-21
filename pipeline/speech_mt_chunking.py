"""Deterministic speech->MT atomic segmentation and chunk packing helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re

from pipeline.speech_mt_preprocess import prepare_speech_mt_text

_ELLIPSIS = "..."
_WHITESPACE_RE = re.compile(r"\s+")
_CLAUSE_BOUNDARY_RE = re.compile(r"\.\.\.|[,.?!:;]")
_ZH_CHAR_RE = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_ZH_PUNCTUATION = "，。！？；：、"
_SPACE_BETWEEN_ZH_CHARS_RE = re.compile(rf"([{_ZH_CHAR_RE}])\s+([{_ZH_CHAR_RE}])")
_SPACE_BEFORE_ZH_PUNCT_RE = re.compile(rf"\s+([{_ZH_PUNCTUATION}])")
_SPACE_AFTER_ZH_PUNCT_RE = re.compile(rf"([{_ZH_PUNCTUATION}])\s+([{_ZH_CHAR_RE}])")
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

ZH_FALLBACK_BUCKET_CHARS = 24
EN_FALLBACK_BUCKET_TOKENS = 12
ZH_CHUNK_BUDGET = 72
EN_CHUNK_BUDGET = 40
MAX_ATOMIC_UNITS_PER_CHUNK = 4
TAIL_REPEAT_MIN_NORMALIZED_LENGTH = 120
TAIL_REPEAT_MIN_REPETITIONS = 3
TAIL_REPEAT_MIN_SPACED_TOKENS = 2
TAIL_REPEAT_MAX_SPACED_TOKENS = 12
TAIL_REPEAT_MIN_DENSE_CHARS = 4
TAIL_REPEAT_MAX_DENSE_CHARS = 24


@dataclass(frozen=True)
class SpeechMtChunkingInspection:
    """Inspection surface for deterministic speech-MT chunk planning."""

    raw_text: str
    normalized_text: str
    source_lang: str
    target_lang: str
    atomic_units: tuple[str, ...]
    packed_chunks: tuple[str, ...]
    used_punctuation_split: bool
    fallback_strategy: str | None
    single_shot_mt_input: str
    chunk_budget: int
    max_atomic_units_per_chunk: int


def inspect_speech_mt_chunking(
    text: str,
    *,
    source_lang: str,
    target_lang: str,
) -> SpeechMtChunkingInspection:
    """Return atomic speech units and packed MT chunks for the given transcript."""

    normalized_text = _normalize_text(text)
    atomic_units: tuple[str, ...] = ()
    used_punctuation_split = False
    fallback_strategy: str | None = None

    if normalized_text:
        has_clause_boundary = bool(_CLAUSE_BOUNDARY_RE.search(normalized_text))
        punctuated_units = _split_atomic_units(normalized_text) if has_clause_boundary else ()
        if punctuated_units:
            atomic_units = punctuated_units
            used_punctuation_split = True
        elif source_lang == "zh":
            atomic_units = _bucket_zh_atomic_units(normalized_text)
            fallback_strategy = "zh_char_bucket"
        else:
            atomic_units = _bucket_en_atomic_units(normalized_text)
            fallback_strategy = "en_token_bucket"
    else:
        fallback_strategy = "empty"

    packed_chunks = _pack_atomic_units(atomic_units, source_lang=source_lang)
    return SpeechMtChunkingInspection(
        raw_text=text,
        normalized_text=normalized_text,
        source_lang=source_lang,
        target_lang=target_lang,
        atomic_units=atomic_units,
        packed_chunks=packed_chunks,
        used_punctuation_split=used_punctuation_split,
        fallback_strategy=fallback_strategy,
        single_shot_mt_input=_legacy_single_shot_mt_input(text, source_lang=source_lang, target_lang=target_lang),
        chunk_budget=_chunk_budget_for_lang(source_lang),
        max_atomic_units_per_chunk=MAX_ATOMIC_UNITS_PER_CHUNK,
    )


def _legacy_single_shot_mt_input(text: str, *, source_lang: str, target_lang: str) -> str:
    if source_lang == "zh" and target_lang == "en":
        return prepare_speech_mt_text(text)
    return text


def _normalize_text(text: str) -> str:
    collapsed = _WHITESPACE_RE.sub(" ", text).strip()
    return collapsed.replace("……", _ELLIPSIS).translate(_PUNCT_TRANSLATIONS)


def _split_atomic_units(text: str) -> tuple[str, ...]:
    units: list[str] = []
    start = 0

    for match in _CLAUSE_BOUNDARY_RE.finditer(text):
        clause_text = text[start:match.start()].strip()
        if clause_text:
            units.append(f"{clause_text}{match.group(0)}")
        start = match.end()

    trailing_text = text[start:].strip()
    if trailing_text:
        units.append(trailing_text)
    return tuple(units)


def _bucket_zh_atomic_units(text: str) -> tuple[str, ...]:
    dense_text = text.replace(" ", "")
    if not dense_text:
        return ()
    return tuple(
        dense_text[index:index + ZH_FALLBACK_BUCKET_CHARS]
        for index in range(0, len(dense_text), ZH_FALLBACK_BUCKET_CHARS)
    )


def _bucket_en_atomic_units(text: str) -> tuple[str, ...]:
    tokens = tuple(token for token in text.split(" ") if token)
    if not tokens:
        return ()
    return tuple(
        " ".join(tokens[index:index + EN_FALLBACK_BUCKET_TOKENS])
        for index in range(0, len(tokens), EN_FALLBACK_BUCKET_TOKENS)
    )


def _pack_atomic_units(units: tuple[str, ...], *, source_lang: str) -> tuple[str, ...]:
    if not units:
        return ()

    budget = _chunk_budget_for_lang(source_lang)
    packed_units: list[tuple[str, ...]] = []
    current_chunk: list[str] = []
    current_size = 0

    for unit in units:
        unit_size = _unit_size(unit, source_lang=source_lang)
        would_exceed_budget = bool(current_chunk) and current_size + unit_size > budget
        would_exceed_unit_limit = len(current_chunk) >= MAX_ATOMIC_UNITS_PER_CHUNK

        if would_exceed_budget or would_exceed_unit_limit:
            packed_units.append(tuple(current_chunk))
            current_chunk = []
            current_size = 0

        current_chunk.append(unit)
        current_size += unit_size

    if current_chunk:
        packed_units.append(tuple(current_chunk))

    return tuple(_join_atomic_units(chunk_units) for chunk_units in packed_units)


def _join_atomic_units(units: tuple[str, ...]) -> str:
    return _WHITESPACE_RE.sub(" ", " ".join(units)).strip()


def _chunk_budget_for_lang(source_lang: str) -> int:
    return ZH_CHUNK_BUDGET if source_lang == "zh" else EN_CHUNK_BUDGET


def _unit_size(unit: str, *, source_lang: str) -> int:
    if source_lang == "zh":
        return _meaningful_char_count(unit)
    return _token_count(unit)


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


def _token_count(text: str) -> int:
    return len([token for token in text.split(" ") if token])


def assemble_speech_mt_output(chunks: tuple[str, ...] | list[str], *, target_lang: str) -> str:
    """Reassemble chunk-by-chunk MT output using pinned target-language rules."""

    cleaned_chunks = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
    if not cleaned_chunks:
        return ""
    if target_lang == "en":
        return _assemble_en_output(cleaned_chunks)
    return _assemble_zh_output(cleaned_chunks)


def _assemble_en_output(chunks: list[str]) -> str:
    return _WHITESPACE_RE.sub(" ", " ".join(chunks)).strip()


def _assemble_zh_output(chunks: list[str]) -> str:
    assembled = "".join(chunks)
    assembled = _WHITESPACE_RE.sub(" ", assembled).strip()
    assembled = _SPACE_BEFORE_ZH_PUNCT_RE.sub(r"\1", assembled)
    assembled = _SPACE_AFTER_ZH_PUNCT_RE.sub(r"\1\2", assembled)
    assembled = _SPACE_BETWEEN_ZH_CHARS_RE.sub(r"\1\2", assembled)
    return assembled.strip()


def guard_repeated_tail_translation(
    text: str,
    *,
    target_lang: str,
    source_atomic_units: tuple[str, ...] = (),
    source_packed_chunks: tuple[str, ...] = (),
) -> str:
    """Trim exact repeated suffix loops from long multi-chunk MT output."""

    cleaned = text.strip()
    if not cleaned:
        return ""
    if _normalized_guard_length(cleaned, target_lang=target_lang) < TAIL_REPEAT_MIN_NORMALIZED_LENGTH:
        return cleaned
    if target_lang == "en":
        return _guard_spaced_tail_repeat(
            cleaned,
            source_atomic_units=source_atomic_units,
            source_packed_chunks=source_packed_chunks,
        )
    return _guard_dense_tail_repeat(
        cleaned,
        source_atomic_units=source_atomic_units,
        source_packed_chunks=source_packed_chunks,
    )


def _normalized_guard_length(text: str, *, target_lang: str) -> int:
    if target_lang == "en":
        return len(_WHITESPACE_RE.sub(" ", text).strip())
    return len(re.sub(r"\s+", "", text))


def _guard_spaced_tail_repeat(
    text: str,
    *,
    source_atomic_units: tuple[str, ...],
    source_packed_chunks: tuple[str, ...],
) -> str:
    tokens = [token for token in text.split(" ") if token]
    if len(tokens) < TAIL_REPEAT_MIN_SPACED_TOKENS * TAIL_REPEAT_MIN_REPETITIONS:
        return text

    best_candidate: tuple[int, int, int] | None = None
    max_span_len = min(TAIL_REPEAT_MAX_SPACED_TOKENS, len(tokens) // TAIL_REPEAT_MIN_REPETITIONS)
    for span_len in range(max_span_len, TAIL_REPEAT_MIN_SPACED_TOKENS - 1, -1):
        repeat_count, start_index = _count_repeated_token_suffix(tokens, span_len=span_len)
        if repeat_count < TAIL_REPEAT_MIN_REPETITIONS:
            continue
        if _source_tail_has_repeat_evidence(
            source_atomic_units,
            source_packed_chunks,
            min_repeat_count=repeat_count,
        ):
            return text
        total_tail_len = span_len * repeat_count
        candidate = (total_tail_len, span_len, start_index)
        if best_candidate is None or candidate > best_candidate:
            best_candidate = candidate

    if best_candidate is None:
        return text
    _, span_len, start_index = best_candidate
    trimmed_tokens = tokens[:start_index] + tokens[-span_len:]
    return " ".join(trimmed_tokens).strip()


def _count_repeated_token_suffix(tokens: list[str], *, span_len: int) -> tuple[int, int]:
    unit = tokens[-span_len:]
    start_index = len(tokens) - span_len
    repeat_count = 1

    while start_index - span_len >= 0 and tokens[start_index - span_len:start_index] == unit:
        repeat_count += 1
        start_index -= span_len
    return repeat_count, start_index


def _guard_dense_tail_repeat(
    text: str,
    *,
    source_atomic_units: tuple[str, ...],
    source_packed_chunks: tuple[str, ...],
) -> str:
    if len(text) < TAIL_REPEAT_MIN_DENSE_CHARS * TAIL_REPEAT_MIN_REPETITIONS:
        return text

    best_candidate: tuple[int, int, int] | None = None
    max_span_len = min(TAIL_REPEAT_MAX_DENSE_CHARS, len(text) // TAIL_REPEAT_MIN_REPETITIONS)
    for span_len in range(max_span_len, TAIL_REPEAT_MIN_DENSE_CHARS - 1, -1):
        repeat_count, start_index = _count_repeated_char_suffix(text, span_len=span_len)
        if repeat_count < TAIL_REPEAT_MIN_REPETITIONS:
            continue
        if _source_tail_has_repeat_evidence(
            source_atomic_units,
            source_packed_chunks,
            min_repeat_count=repeat_count,
        ):
            return text
        total_tail_len = span_len * repeat_count
        candidate = (total_tail_len, span_len, start_index)
        if best_candidate is None or candidate > best_candidate:
            best_candidate = candidate

    if best_candidate is None:
        return text
    _, span_len, start_index = best_candidate
    return f"{text[:start_index]}{text[-span_len:]}".strip()


def _count_repeated_char_suffix(text: str, *, span_len: int) -> tuple[int, int]:
    unit = text[-span_len:]
    start_index = len(text) - span_len
    repeat_count = 1

    while start_index - span_len >= 0 and text[start_index - span_len:start_index] == unit:
        repeat_count += 1
        start_index -= span_len
    return repeat_count, start_index


def _source_tail_has_repeat_evidence(
    source_atomic_units: tuple[str, ...],
    source_packed_chunks: tuple[str, ...],
    *,
    min_repeat_count: int,
) -> bool:
    return _sequence_has_repeated_suffix(source_atomic_units, min_repeat_count=min_repeat_count) or _sequence_has_repeated_suffix(
        source_packed_chunks,
        min_repeat_count=min_repeat_count,
    )


def _sequence_has_repeated_suffix(sequence: tuple[str, ...], *, min_repeat_count: int) -> bool:
    if not sequence or len(sequence) < min_repeat_count:
        return False

    max_span = len(sequence) // min_repeat_count
    for span_len in range(1, max_span + 1):
        unit = sequence[-span_len:]
        repeat_count = 1
        start_index = len(sequence) - span_len
        while start_index - span_len >= 0 and sequence[start_index - span_len:start_index] == unit:
            repeat_count += 1
            start_index -= span_len
        if repeat_count >= min_repeat_count:
            return True
    return False


__all__ = [
    "EN_CHUNK_BUDGET",
    "EN_FALLBACK_BUCKET_TOKENS",
    "MAX_ATOMIC_UNITS_PER_CHUNK",
    "SpeechMtChunkingInspection",
    "TAIL_REPEAT_MIN_NORMALIZED_LENGTH",
    "ZH_CHUNK_BUDGET",
    "ZH_FALLBACK_BUCKET_CHARS",
    "assemble_speech_mt_output",
    "guard_repeated_tail_translation",
    "inspect_speech_mt_chunking",
]
