"""音频模块统一接口 — 导出 record(), play(), AudioError"""

# 1. Standard library
import logging
import threading
from typing import Optional

# 2. Local
from audio.capture import AudioCapture, AudioCaptureError
from audio.playback import play as _play, AudioPlaybackError

logger = logging.getLogger(__name__)


class AudioError(Exception):
    """音频模块统一异常，封装 capture/playback 底层错误."""


def record(
    output_path: str,
    device: str = "default",
    stop_flag: Optional[threading.Event] = None,
    max_duration: int = 180,
) -> str:
    """录音并保存为WAV文件.

    Args:
        output_path: 输出WAV文件路径.
        device: ALSA设备名，从配置传入，默认 "default".
        stop_flag: 外部停止信号，置位后提前结束录音.
        max_duration: 最大录音时长（秒），上限180秒.

    Returns:
        保存的WAV文件绝对路径.

    Raises:
        AudioError: 录音失败时.
    """
    try:
        with AudioCapture(device=device) as mic:
            return mic.record(
                output_path=output_path,
                stop_flag=stop_flag,
                max_duration=max_duration,
            )
    except AudioCaptureError as e:
        logger.error("录音失败: error=%s", str(e))
        raise AudioError(str(e)) from e


def play(
    wav_path: str,
    device: str = "default",
    blocking: bool = True,
) -> None:
    """播放WAV文件.

    Args:
        wav_path: WAV文件路径.
        device: ALSA设备名，从配置传入，默认 "default".
        blocking: True 阻塞直到播放完成；False 立即返回.

    Raises:
        AudioError: 播放失败时.
    """
    try:
        _play(wav_path=wav_path, device=device, blocking=blocking)
    except AudioPlaybackError as e:
        logger.error("播放失败: error=%s", str(e))
        raise AudioError(str(e)) from e


__all__ = ["record", "play", "AudioError"]
