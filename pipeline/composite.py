"""组合管线 — FR-03: MT+TTS, FR-04: ASR+MT"""

# 1. Standard library
import logging
import time

# 2. Local
from audio import record, play, AudioError
from models.asr import ASREngine, ASRError
from models.mt import MTEngine, TranslationError
from models.tts import TTSEngine, TTSError
from pipeline._utils import make_output_path

logger = logging.getLogger(__name__)


def run_mt_tts(text: str, source_lang: str, target_lang: str, config: dict) -> dict:
    """FR-03: 文本 → MT 翻译 → TTS 合成 → 播放。

    Args:
        text: 待翻译文本。
        source_lang: 源语言代码，"zh" 或 "en"。
        target_lang: 目标语言代码，"zh" 或 "en"。
        config: 应用配置字典（来自 default.yaml）。

    Returns:
        {"source_text": str, "translated_text": str, "audio_path": str} 成功时；
        部分结果 + "error" 键 失败时。
    """
    tts_cfg = config["models"]["tts"]
    audio_cfg = config["audio"]
    storage_cfg = config["storage"]

    mt_engine = MTEngine()
    tts_engine = TTSEngine(
        zh_model_path=tts_cfg["zh_model_path"],
        en_model_path=tts_cfg["en_model_path"],
    )

    output_path = make_output_path(storage_cfg, "mt_tts")

    result: dict = {"source_text": text, "translated_text": None, "audio_path": None}
    start = time.monotonic()

    try:
        translated = mt_engine.translate(text, source_lang, target_lang)
        result["translated_text"] = translated
    except TranslationError as e:
        elapsed = time.monotonic() - start
        logger.error(
            "run_mt_tts MT失败: %s→%s, elapsed=%.2fs, error=%s",
            source_lang, target_lang, elapsed, str(e),
        )
        result["error"] = str(e)
        return result

    try:
        tts_engine.synthesize(translated, target_lang, output_path)
        play(wav_path=output_path, device=audio_cfg["device"])
        result["audio_path"] = output_path
        elapsed = time.monotonic() - start
        logger.info(
            "run_mt_tts 完成: %s→%s, elapsed=%.2fs, path=%s",
            source_lang, target_lang, elapsed, output_path,
        )
    except (TTSError, AudioError) as e:
        elapsed = time.monotonic() - start
        logger.error(
            "run_mt_tts TTS/播放失败: %s→%s, elapsed=%.2fs, error=%s",
            source_lang, target_lang, elapsed, str(e),
        )
        result["error"] = str(e)

    return result


def run_asr_mt(source_lang: str, target_lang: str, config: dict) -> dict:
    """FR-04: 录音 → ASR 识别 → MT 翻译 → TTS 合成 → 播放。

    Args:
        source_lang: 源语言代码，"zh" 或 "en"。
        target_lang: 目标语言代码，"zh" 或 "en"。
        config: 应用配置字典（来自 default.yaml）。

    Returns:
        {"source_text": str, "translated_text": str, "audio_path": str} 成功时；
        部分结果 + "error" 键 失败时。
    """
    asr_cfg = config["models"]["asr"]
    mt_cfg = config["models"]["mt"]
    tts_cfg = config["models"]["tts"]
    audio_cfg = config["audio"]
    storage_cfg = config["storage"]

    asr_engine = ASREngine(
        zh_model_path=asr_cfg["zh_model_path"],
        en_model_path=asr_cfg["en_model_path"],
    )
    mt_engine = MTEngine()
    tts_engine = TTSEngine(
        zh_model_path=tts_cfg["zh_model_path"],
        en_model_path=tts_cfg["en_model_path"],
    )

    audio_path = make_output_path(storage_cfg, "asr_mt")
    output_path = make_output_path(storage_cfg, "asr_mt_tts")

    result: dict = {"source_text": None, "translated_text": None, "audio_path": None}
    start = time.monotonic()

    try:
        recorded_path = record(
            output_path=audio_path,
            device=audio_cfg["device"],
            max_duration=audio_cfg["max_record_duration"],
        )
        result["audio_path"] = recorded_path
    except AudioError as e:
        elapsed = time.monotonic() - start
        logger.error(
            "run_asr_mt 录音失败: %s→%s, elapsed=%.2fs, error=%s",
            source_lang, target_lang, elapsed, str(e),
        )
        result["error"] = str(e)
        return result

    try:
        source_text = asr_engine.recognize(recorded_path, source_lang)
        result["source_text"] = source_text
    except ASRError as e:
        elapsed = time.monotonic() - start
        logger.error(
            "run_asr_mt ASR失败: %s→%s, elapsed=%.2fs, error=%s",
            source_lang, target_lang, elapsed, str(e),
        )
        result["error"] = str(e)
        return result

    try:
        translated = mt_engine.translate(source_text, source_lang, target_lang)
        result["translated_text"] = translated
    except TranslationError as e:
        elapsed = time.monotonic() - start
        logger.error(
            "run_asr_mt MT失败: %s→%s, elapsed=%.2fs, error=%s",
            source_lang, target_lang, elapsed, str(e),
        )
        result["error"] = str(e)
        return result

    try:
        tts_engine.synthesize(translated, target_lang, output_path)
        play(wav_path=output_path, device=audio_cfg["device"])
        result["audio_path"] = output_path
        elapsed = time.monotonic() - start
        logger.info(
            "run_asr_mt 完成: %s→%s, elapsed=%.2fs, path=%s",
            source_lang, target_lang, elapsed, output_path,
        )
    except (TTSError, AudioError) as e:
        elapsed = time.monotonic() - start
        logger.error(
            "run_asr_mt TTS/播放失败: %s→%s, elapsed=%.2fs, error=%s",
            source_lang, target_lang, elapsed, str(e),
        )
        result["error"] = str(e)

    return result
