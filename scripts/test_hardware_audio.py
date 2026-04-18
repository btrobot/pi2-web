#!/usr/bin/env python3
"""硬件音频测试 — 使用 seeed2micvoicec 真实录音和播放

测试流程:
1. 录音 3 秒
2. 播放刚录制的音频
3. 打印结果摘要
"""

import sys
import threading
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audio.capture import AudioCapture
from audio.playback import play

DEVICE = "plughw:3,0"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "test_hw"
RECORD_SECONDS = 8


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = OUTPUT_DIR / "hw_test.wav"

    # --- 录音 ---
    print(f"[录音] 设备: {DEVICE}, 时长: {RECORD_SECONDS}s")
    print("[录音] 请对着麦克风说话...")

    stop = threading.Event()

    def _stop_after(seconds: float) -> None:
        time.sleep(seconds)
        stop.set()

    timer = threading.Thread(target=_stop_after, args=(RECORD_SECONDS,), daemon=True)
    timer.start()

    t0 = time.perf_counter()
    with AudioCapture(device=DEVICE) as mic:
        saved = mic.record(output_path=str(wav_path), stop_flag=stop, max_duration=RECORD_SECONDS)
    record_elapsed = time.perf_counter() - t0

    # 读取 WAV 信息
    with wave.open(saved, "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        frames = wf.getnframes()
        duration = frames / rate
        sample_width = wf.getsampwidth()

    print(f"[录音] 完成: {saved}")
    print(f"  采样率: {rate} Hz, 位深: {sample_width * 8}-bit, 声道: {channels}")
    print(f"  帧数: {frames}, 时长: {duration:.2f}s, 耗时: {record_elapsed:.2f}s")

    if duration < 0.5:
        print("[警告] 录音时长过短，可能麦克风未正常工作")

    # --- 播放 ---
    print(f"\n[播放] 设备: {DEVICE}")
    print("[播放] 正在回放录音...")

    t0 = time.perf_counter()
    play(wav_path=saved, device=DEVICE, blocking=True)
    play_elapsed = time.perf_counter() - t0

    print(f"[播放] 完成, 耗时: {play_elapsed:.2f}s")

    # --- 摘要 ---
    print("\n===== 测试结果 =====")
    print(f"录音: OK ({duration:.2f}s)")
    print(f"播放: OK ({play_elapsed:.2f}s)")
    print(f"文件: {saved} ({Path(saved).stat().st_size} bytes)")


if __name__ == "__main__":
    main()
