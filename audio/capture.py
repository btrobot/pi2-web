"""音频采集模块 — pyalsaaudio, 16kHz/16bit/Mono, 最大180秒, 输出WAV"""

# 1. Standard library
import logging
import threading
import wave
from pathlib import Path
from typing import Optional

# 2. Third-party
import alsaaudio

logger = logging.getLogger(__name__)

# Constants matching config/default.yaml
_SAMPLE_RATE = 16000
_CHANNELS = 1
_FORMAT = alsaaudio.PCM_FORMAT_S16_LE
_PERIOD_SIZE = 1024  # frames per read
_MAX_DURATION = 180  # seconds


class AudioCaptureError(Exception):
    """Raised when audio capture fails."""


class AudioCapture:
    """Thread-safe audio capture using pyalsaaudio.

    Usage:
        with AudioCapture(device="default") as mic:
            wav_path = mic.record(output_path="out.wav")
    """

    def __init__(self, device: str = "default") -> None:
        self._device = device
        self._pcm: Optional[alsaaudio.PCM] = None

    def __enter__(self) -> "AudioCapture":
        try:
            self._pcm = alsaaudio.PCM(
                type=alsaaudio.PCM_CAPTURE,
                mode=alsaaudio.PCM_NORMAL,
                device=self._device,
                channels=_CHANNELS,
                rate=_SAMPLE_RATE,
                format=_FORMAT,
                periodsize=_PERIOD_SIZE,
            )
        except alsaaudio.ALSAAudioError as e:
            logger.error("无法打开音频设备: device=%s, error=%s", self._device, str(e))
            raise AudioCaptureError(f"无法打开音频设备: {self._device}") from e
        logger.info("音频设备已打开: device=%s, rate=%d", self._device, _SAMPLE_RATE)
        return self

    def __exit__(self, *_: object) -> None:
        if self._pcm is not None:
            self._pcm.close()
            self._pcm = None
            logger.info("音频设备已关闭: device=%s", self._device)

    def record(
        self,
        output_path: str,
        stop_flag: Optional[threading.Event] = None,
        max_duration: int = _MAX_DURATION,
    ) -> str:
        """录音并保存为WAV文件.

        Args:
            output_path: 输出WAV文件路径.
            stop_flag: 外部停止信号，置位后停止录音.
            max_duration: 最大录音时长（秒），上限180秒.

        Returns:
            保存的WAV文件绝对路径.

        Raises:
            AudioCaptureError: 录音或写文件失败时.
        """
        if self._pcm is None:
            raise AudioCaptureError("AudioCapture 未通过 with 语句初始化")

        max_duration = min(max_duration, _MAX_DURATION)
        max_frames = _SAMPLE_RATE * max_duration
        frames_captured = 0
        chunks: list[bytes] = []

        logger.info(
            "开始录音: output=%s, max_duration=%ds", output_path, max_duration
        )

        try:
            while frames_captured < max_frames:
                if stop_flag is not None and stop_flag.is_set():
                    logger.info("收到停止信号，结束录音")
                    break

                length, data = self._pcm.read()
                if length < 0:
                    logger.warning("PCM 读取错误: length=%d，跳过", length)
                    continue
                if length == 0:
                    continue

                chunks.append(data)
                frames_captured += length

        except alsaaudio.ALSAAudioError as e:
            logger.error("录音过程中发生错误: error=%s", str(e))
            raise AudioCaptureError("录音失败") from e

        duration = frames_captured / _SAMPLE_RATE
        logger.info("录音完成: frames=%d, duration=%.1fs", frames_captured, duration)

        return _save_wav(chunks, output_path)


def _save_wav(chunks: list[bytes], output_path: str) -> str:
    """将PCM数据块写入WAV文件."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(_CHANNELS)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(_SAMPLE_RATE)
            wf.writeframes(b"".join(chunks))
    except OSError as e:
        logger.error("WAV文件写入失败: path=%s, error=%s", output_path, str(e))
        raise AudioCaptureError(f"WAV文件写入失败: {output_path}") from e

    logger.info("WAV文件已保存: path=%s", output_path)
    return str(path.resolve())
