"""TTS engine wrapper using Piper first and espeak-ng as a fallback."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSError(Exception):
    """Raised when text-to-speech synthesis or playback fails."""


class TTSEngine:
    """Synthesize zh/en speech to WAV output files."""

    def __init__(self, zh_model_path: str, en_model_path: str) -> None:
        self._zh_model_path = zh_model_path
        self._en_model_path = en_model_path
        self._piper_available: bool | None = None
        self._piper_command: str | None = None

    def synthesize(self, text: str, lang: str, output_path: str) -> str:
        """Synthesize speech to a WAV file."""
        model_path = self._resolve_model(lang)
        start = time.monotonic()

        try:
            if self._is_piper_available():
                self._run_piper(text, model_path, output_path)
            else:
                logger.warning("piper CLI is unavailable; falling back to espeak-ng")
                self._run_espeak(text, lang, output_path)
        except TTSError:
            raise
        except Exception as exc:
            logger.error("TTS synthesis failed: lang=%s, error=%s", lang, str(exc))
            raise TTSError(f"synthesis failed: {exc}") from exc

        elapsed = time.monotonic() - start
        logger.info("TTS synthesis complete: lang=%s, duration=%.2fs, output=%s", lang, elapsed, output_path)
        return output_path

    def speak(self, text: str, lang: str) -> None:
        """Synthesize speech and play it through aplay."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self.synthesize(text, lang, tmp_path)
            self._play(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _resolve_model(self, lang: str) -> str:
        if lang == "zh":
            raw = self._zh_model_path
        elif lang == "en":
            raw = self._en_model_path
        else:
            raise ValueError(f"unsupported language: {lang!r}; only 'zh' and 'en' are supported")

        path = Path(raw)
        if path.is_dir():
            onnx_files = list(path.glob("*.onnx"))
            if not onnx_files:
                raise TTSError(f"no .onnx model found in directory: {raw}")
            return str(onnx_files[0])

        return raw

    def _resolve_piper_command(self) -> str | None:
        """Resolve piper from the active venv/bin before falling back to PATH."""
        if self._piper_command is not None:
            return self._piper_command

        executable_name = "piper.exe" if os.name == "nt" else "piper"
        interpreter_dir = Path(sys.executable).resolve().parent
        local_candidate = interpreter_dir / executable_name
        if local_candidate.exists():
            self._piper_command = str(local_candidate)
            return self._piper_command

        self._piper_command = shutil.which("piper")
        return self._piper_command

    def _is_piper_available(self) -> bool:
        if self._piper_available is None:
            self._piper_available = self._resolve_piper_command() is not None
        return self._piper_available

    def _run_piper(self, text: str, model_path: str, output_path: str) -> None:
        piper_command = self._resolve_piper_command()
        if piper_command is None:
            raise TTSError("piper command not found")

        cmd = [piper_command, "--model", model_path, "--output_file", output_path]
        try:
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            raise TTSError("piper synthesis timed out (60s)") from exc
        except FileNotFoundError as exc:
            raise TTSError("piper command not found") from exc

        if result.returncode != 0:
            logger.error("piper returned non-zero: code=%d, stderr=%s", result.returncode, result.stderr)
            raise TTSError(f"piper exited with code {result.returncode}: {result.stderr.strip()}")

    def _run_espeak(self, text: str, lang: str, output_path: str) -> None:
        espeak_lang = "zh" if lang == "zh" else "en"
        cmd = ["espeak-ng", "-v", espeak_lang, "-w", output_path, text]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            raise TTSError("espeak-ng synthesis timed out (60s)") from exc
        except FileNotFoundError as exc:
            raise TTSError("espeak-ng command not found") from exc

        if result.returncode != 0:
            logger.error("espeak-ng returned non-zero: code=%d, stderr=%s", result.returncode, result.stderr)
            raise TTSError(f"espeak-ng exited with code {result.returncode}: {result.stderr.strip()}")

    def _play(self, wav_path: str) -> None:
        cmd = ["aplay", wav_path]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise TTSError("aplay playback timed out (120s)") from exc
        except FileNotFoundError as exc:
            raise TTSError("aplay command not found") from exc

        if result.returncode != 0:
            logger.error("aplay returned non-zero: code=%d, stderr=%s", result.returncode, result.stderr)
            raise TTSError(f"aplay exited with code {result.returncode}: {result.stderr.strip()}")
