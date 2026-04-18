"""音频播放模块 — subprocess 调用 aplay，支持阻塞/非阻塞模式"""

# 1. Standard library
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_APLAY_TIMEOUT = 300  # seconds — generous upper bound for 180s recordings


class AudioPlaybackError(Exception):
    """Raised when audio playback fails."""


def play(
    wav_path: str,
    device: str = "default",
    blocking: bool = True,
) -> Optional[subprocess.Popen]:  # type: ignore[type-arg]
    """播放WAV文件.

    Args:
        wav_path: WAV文件路径.
        device: ALSA设备名，默认 "default".
        blocking: True 阻塞直到播放完成；False 立即返回 Popen 对象.

    Returns:
        blocking=True 时返回 None；blocking=False 时返回 Popen 对象供调用方管理.

    Raises:
        AudioPlaybackError: 文件不存在或 aplay 返回非零退出码（仅阻塞模式）.
    """
    path = Path(wav_path)
    if not path.exists():
        logger.error("播放文件不存在: path=%s", wav_path)
        raise AudioPlaybackError(f"文件不存在: {wav_path}")

    cmd = ["aplay", "-D", device, str(path)]
    logger.info("开始播放: path=%s, device=%s, blocking=%s", wav_path, device, blocking)

    try:
        if blocking:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=_APLAY_TIMEOUT,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace").strip()
                logger.error(
                    "aplay 返回错误: returncode=%d, stderr=%s",
                    result.returncode,
                    stderr,
                )
                raise AudioPlaybackError(
                    f"aplay 失败 (returncode={result.returncode}): {stderr}"
                )
            logger.info("播放完成: path=%s", wav_path)
            return None
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("非阻塞播放已启动: pid=%d, path=%s", proc.pid, wav_path)
            return proc

    except subprocess.TimeoutExpired as e:
        logger.error("aplay 超时: path=%s, timeout=%ds", wav_path, _APLAY_TIMEOUT)
        raise AudioPlaybackError(f"播放超时: {wav_path}") from e
    except FileNotFoundError as e:
        logger.error("aplay 未找到，请确认已安装 alsa-utils")
        raise AudioPlaybackError("aplay 命令不存在") from e
