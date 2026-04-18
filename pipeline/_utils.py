"""管线内部工具函数"""

# 1. Standard library
import time
from pathlib import Path


def make_output_path(storage_cfg: dict, prefix: str) -> str:
    """创建录音输出目录并返回带时间戳的文件路径。

    Args:
        storage_cfg: config["storage"] 子字典。
        prefix: 文件名前缀，如 "tts", "asr", "mt_tts", "asr_mt"。

    Returns:
        完整的 WAV 输出路径字符串。
    """
    recordings_dir = Path(storage_cfg["recordings_dir"])
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return str(recordings_dir / f"{prefix}_{int(time.time())}.wav")
