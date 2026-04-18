#!/usr/bin/env python3
"""循环播放测试 — 下载音乐并通过 seeed2micvoicec 循环播放

用法: venv/bin/python scripts/test_playback_loop.py
按 Ctrl+C 停止
"""

import subprocess
import signal
import sys
from pathlib import Path

DEVICE = "plughw:2,0"
MP3_PATH = Path(__file__).resolve().parent.parent / "data" / "test_music.mp3"
WAV_PATH = Path(__file__).resolve().parent.parent / "data" / "test_music.wav"


def convert_to_wav() -> None:
    """将 mp3 转为 16kHz 16-bit mono WAV（匹配硬件）"""
    if WAV_PATH.exists():
        print(f"[转换] WAV 已存在: {WAV_PATH}")
        return
    print(f"[转换] MP3 → WAV ...")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(MP3_PATH),
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
            str(WAV_PATH),
        ],
        capture_output=True,
        timeout=60,
        check=True,
    )
    print(f"[转换] 完成: {WAV_PATH}")


def play_loop() -> None:
    """循环播放直到 Ctrl+C"""
    loop = 0
    while True:
        loop += 1
        print(f"[播放] 第 {loop} 轮 ...")
        result = subprocess.run(
            ["aplay", "-D", DEVICE, str(WAV_PATH)],
            capture_output=True,
            timeout=600,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            print(f"[错误] aplay 失败: {stderr}")
            sys.exit(1)


def main() -> None:
    signal.signal(signal.SIGINT, lambda *_: (print("\n[停止] 用户中断"), sys.exit(0)))

    if not MP3_PATH.exists():
        print(f"[错误] 音乐文件不存在: {MP3_PATH}")
        sys.exit(1)

    convert_to_wav()
    print(f"[播放] 设备: {DEVICE}, 按 Ctrl+C 停止")
    play_loop()


if __name__ == "__main__":
    main()
