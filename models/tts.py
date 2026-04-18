"""TTS 语音合成引擎封装 — piper-tts (fallback: espeak-ng)"""

# 1. Standard library
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TTSError(Exception):
    """TTS 合成失败时抛出"""


class TTSEngine:
    """封装 piper-tts CLI，按需加载模型，支持 espeak-ng fallback。

    输出规格: 16kHz, 16-bit, Mono WAV
    """

    def __init__(self, zh_model_path: str, en_model_path: str) -> None:
        """初始化引擎，不立即加载模型。

        Args:
            zh_model_path: 中文 piper .onnx 模型目录或文件路径
            en_model_path: 英文 piper .onnx 模型目录或文件路径
        """
        self._zh_model_path = zh_model_path
        self._en_model_path = en_model_path
        self._piper_available: Optional[bool] = None  # lazy-checked

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize(self, text: str, lang: str, output_path: str) -> str:
        """合成语音并保存为 WAV 文件。

        Args:
            text: 待合成文本
            lang: 语言代码，"zh" 或 "en"
            output_path: 输出 WAV 文件路径

        Returns:
            保存成功的文件路径（与 output_path 相同）

        Raises:
            TTSError: 合成失败
            ValueError: lang 不支持
        """
        model_path = self._resolve_model(lang)
        start = time.monotonic()

        try:
            if self._is_piper_available():
                self._run_piper(text, model_path, output_path)
            else:
                logger.warning("piper CLI 不可用，使用 espeak-ng fallback")
                self._run_espeak(text, lang, output_path)
        except TTSError:
            raise
        except Exception as e:
            logger.error("TTS 合成失败: lang=%s, error=%s", lang, str(e))
            raise TTSError(f"合成失败: {e}") from e

        elapsed = time.monotonic() - start
        logger.info("TTS 合成完成: lang=%s, duration=%.2fs, output=%s", lang, elapsed, output_path)
        return output_path

    def speak(self, text: str, lang: str) -> None:
        """合成语音并通过 aplay 直接播放。

        Args:
            text: 待合成文本
            lang: 语言代码，"zh" 或 "en"

        Raises:
            TTSError: 合成或播放失败
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self.synthesize(text, lang, tmp_path)
            self._play(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_model(self, lang: str) -> str:
        """返回对应语言的模型路径，并验证其存在。"""
        if lang == "zh":
            raw = self._zh_model_path
        elif lang == "en":
            raw = self._en_model_path
        else:
            raise ValueError(f"不支持的语言: {lang!r}，仅支持 'zh' / 'en'")

        # 如果路径是目录，查找其中第一个 .onnx 文件
        p = Path(raw)
        if p.is_dir():
            onnx_files = list(p.glob("*.onnx"))
            if not onnx_files:
                raise TTSError(f"模型目录中未找到 .onnx 文件: {raw}")
            return str(onnx_files[0])

        return raw

    def _is_piper_available(self) -> bool:
        """检查 piper CLI 是否可用（结果缓存）。"""
        if self._piper_available is None:
            self._piper_available = shutil.which("piper") is not None
        return self._piper_available

    def _run_piper(self, text: str, model_path: str, output_path: str) -> None:
        """调用 piper CLI 合成语音。"""
        cmd = ["piper", "--model", model_path, "--output_file", output_path]
        try:
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired as e:
            raise TTSError("piper 合成超时 (60s)") from e
        except FileNotFoundError as e:
            raise TTSError("piper 命令未找到") from e

        if result.returncode != 0:
            logger.error("piper 返回非零: code=%d, stderr=%s", result.returncode, result.stderr)
            raise TTSError(f"piper 退出码 {result.returncode}: {result.stderr.strip()}")

    def _run_espeak(self, text: str, lang: str, output_path: str) -> None:
        """调用 espeak-ng 合成语音（fallback）。"""
        espeak_lang = "zh" if lang == "zh" else "en"
        cmd = ["espeak-ng", "-v", espeak_lang, "-w", output_path, text]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired as e:
            raise TTSError("espeak-ng 合成超时 (60s)") from e
        except FileNotFoundError as e:
            raise TTSError("espeak-ng 命令未找到") from e

        if result.returncode != 0:
            logger.error("espeak-ng 返回非零: code=%d, stderr=%s", result.returncode, result.stderr)
            raise TTSError(f"espeak-ng 退出码 {result.returncode}: {result.stderr.strip()}")

    def _play(self, wav_path: str) -> None:
        """通过 aplay 播放 WAV 文件。"""
        cmd = ["aplay", wav_path]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as e:
            raise TTSError("aplay 播放超时 (120s)") from e
        except FileNotFoundError as e:
            raise TTSError("aplay 命令未找到") from e

        if result.returncode != 0:
            logger.error("aplay 返回非零: code=%d, stderr=%s", result.returncode, result.stderr)
            raise TTSError(f"aplay 退出码 {result.returncode}: {result.stderr.strip()}")
