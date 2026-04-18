"""Primitive pipeline operations with no storage or route coupling."""

from __future__ import annotations

from typing import Any

from pipeline._utils import make_output_path


def capture_audio(*, config: dict[str, Any], prefix: str) -> str:
    """Capture input audio to a timestamped WAV file."""

    from audio import record

    audio_cfg = config["audio"]
    output_path = make_output_path(config["storage"], prefix)
    return record(
        output_path=output_path,
        device=audio_cfg["device"],
        max_duration=audio_cfg["max_record_duration"],
    )


def recognize_audio(*, config: dict[str, Any], audio_path: str, lang: str) -> str:
    """Run ASR on an existing audio file."""

    from models.asr import ASREngine

    asr_cfg = config["models"]["asr"]
    engine = ASREngine(
        zh_model_path=asr_cfg["zh_model_path"],
        en_model_path=asr_cfg["en_model_path"],
    )
    return engine.recognize(audio_path, lang)


def translate_text(*, text: str, source_lang: str, target_lang: str) -> str:
    """Translate text for cross-language modes."""

    from models.mt import MTEngine

    engine = MTEngine()
    return engine.translate(text, source_lang, target_lang)


def synthesize_text(
    *,
    config: dict[str, Any],
    text: str,
    lang: str,
    prefix: str,
    playback: bool = True,
) -> str:
    """Synthesize speech to a timestamped WAV file and optionally play it."""

    from audio import play
    from models.tts import TTSEngine

    tts_cfg = config["models"]["tts"]
    audio_cfg = config["audio"]
    output_path = make_output_path(config["storage"], prefix)
    engine = TTSEngine(
        zh_model_path=tts_cfg["zh_model_path"],
        en_model_path=tts_cfg["en_model_path"],
    )
    engine.synthesize(text, lang, output_path)
    if playback:
        play(wav_path=output_path, device=audio_cfg["device"])
    return output_path

__all__ = ["capture_audio", "recognize_audio", "synthesize_text", "translate_text"]
