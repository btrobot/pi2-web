"""单模块管线 — FR-01: TTS, FR-02: ASR"""

# 1. Standard library
import logging
import time

# 2. Local
from audio import record, play, AudioError
from models.asr import ASREngine, ASRError
from models.tts import TTSEngine, TTSError
from pipeline._utils import make_output_path

logger = logging.getLogger(__name__)


def run_tts(text: str, lang: str, config: dict) -> dict:
    """FR-01: 文本 → TTS 合成 → 播放。

    Args:
        text: 待合成文本。
        lang: 语言代码，"zh" 或 "en"。
        config: 应用配置字典（来自 default.yaml）。

    Returns:
        {"text": str, "audio_path": str} 成功时；
        {"text": str, "audio_path": None, "error": str} 失败时。
    """
    tts_cfg = config["models"]["tts"]
    audio_cfg = config["audio"]
    storage_cfg = config["storage"]

    engine = TTSEngine(
        zh_model_path=tts_cfg["zh_model_path"],
        en_model_path=tts_cfg["en_model_path"],
    )

    output_path = make_output_path(storage_cfg, "tts")

    start = time.monotonic()
    try:
        engine.synthesize(text, lang, output_path)
        play(wav_path=output_path, device=audio_cfg["device"])
        elapsed = time.monotonic() - start
        logger.info("run_tts 完成: lang=%s, elapsed=%.2fs, path=%s", lang, elapsed, output_path)
        return {"text": text, "audio_path": output_path}
    except (TTSError, AudioError) as e:
        elapsed = time.monotonic() - start
        logger.error("run_tts 失败: lang=%s, elapsed=%.2fs, error=%s", lang, elapsed, str(e))
        return {"text": text, "audio_path": None, "error": str(e)}


def run_asr(lang: str, config: dict) -> dict:
    """FR-02: 录音 → ASR 识别 → 返回文本。

    Args:
        lang: 语言代码，"zh" 或 "en"。
        config: 应用配置字典（来自 default.yaml）。

    Returns:
        {"text": str, "audio_path": str} 成功时；
        {"text": "", "audio_path": str|None, "error": str} 失败时。
    """
    asr_cfg = config["models"]["asr"]
    audio_cfg = config["audio"]
    storage_cfg = config["storage"]

    engine = ASREngine(
        zh_model_path=asr_cfg["zh_model_path"],
        en_model_path=asr_cfg["en_model_path"],
    )

    audio_path = make_output_path(storage_cfg, "asr")

    start = time.monotonic()
    recorded_path = None
    try:
        recorded_path = record(
            output_path=audio_path,
            device=audio_cfg["device"],
            max_duration=audio_cfg["max_record_duration"],
        )
        text = engine.recognize(recorded_path, lang)
        elapsed = time.monotonic() - start
        logger.info("run_asr 完成: lang=%s, elapsed=%.2fs, text_len=%d", lang, elapsed, len(text))
        return {"text": text, "audio_path": recorded_path}
    except AudioError as e:
        elapsed = time.monotonic() - start
        logger.error("run_asr 录音失败: lang=%s, elapsed=%.2fs, error=%s", lang, elapsed, str(e))
        return {"text": "", "audio_path": recorded_path, "error": str(e)}
    except ASRError as e:
        elapsed = time.monotonic() - start
        logger.error("run_asr 识别失败: lang=%s, elapsed=%.2fs, error=%s", lang, elapsed, str(e))
        return {"text": "", "audio_path": recorded_path, "error": str(e)}
