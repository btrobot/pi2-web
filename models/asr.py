"""Vosk ASR engine wrapper for zh/en offline speech recognition."""

# 1. Standard library
import json
import logging
import time
import wave

# 2. Third-party
import vosk

logger = logging.getLogger(__name__)


class ASRError(Exception):
    """Raised when ASR recognition fails."""


class ASREngine:
    """Lazy-loading Vosk ASR engine supporting Chinese and English."""

    def __init__(self, zh_model_path: str, en_model_path: str) -> None:
        self._zh_model_path = zh_model_path
        self._en_model_path = en_model_path
        self._models: dict[str, vosk.Model] = {}

    def _load_model(self, lang: str) -> vosk.Model:
        if lang in self._models:
            return self._models[lang]

        if lang == "zh":
            path = self._zh_model_path
        elif lang == "en":
            path = self._en_model_path
        else:
            raise ASRError("不支持的语言: %s (支持 zh / en)" % lang)

        logger.info("加载 ASR 模型: lang=%s, path=%s", lang, path)
        try:
            model = vosk.Model(path)
        except Exception as e:
            logger.error("ASR 模型加载失败: lang=%s, path=%s, error=%s", lang, path, str(e))
            raise ASRError("无法加载模型: %s" % path) from e

        self._models[lang] = model
        logger.info("ASR 模型加载完成: lang=%s", lang)
        return model

    def recognize(self, audio_path: str, lang: str = "zh") -> str:
        """识别 16kHz Mono WAV 文件，返回识别文本。

        Args:
            audio_path: WAV 文件路径。
            lang: 语言代码，"zh" 或 "en"。

        Returns:
            识别出的文本字符串。

        Raises:
            ASRError: 文件读取失败或识别出错时抛出。
        """
        model = self._load_model(lang)

        try:
            with wave.open(audio_path, "rb") as wf:
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
                    raise ASRError(
                        "音频格式不符: 需要 16kHz Mono 16-bit WAV, 实际 channels=%d rate=%d width=%d"
                        % (wf.getnchannels(), wf.getframerate(), wf.getsampwidth())
                    )

                rec = vosk.KaldiRecognizer(model, wf.getframerate())
                rec.SetWords(True)

                start = time.monotonic()
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    rec.AcceptWaveform(data)

                result = json.loads(rec.FinalResult())
                text: str = result.get("text", "")
                elapsed = time.monotonic() - start

                logger.info(
                    "ASR 识别完成: lang=%s, duration=%.2fs, text_len=%d",
                    lang, elapsed, len(text),
                )
                return text

        except ASRError:
            raise
        except (FileNotFoundError, wave.Error) as e:
            logger.error("无法打开音频文件: path=%s, error=%s", audio_path, str(e))
            raise ASRError("无法打开音频文件: %s" % audio_path) from e
        except Exception as e:
            logger.error("ASR 识别失败: path=%s, lang=%s, error=%s", audio_path, lang, str(e))
            raise ASRError("识别失败: %s" % audio_path) from e
