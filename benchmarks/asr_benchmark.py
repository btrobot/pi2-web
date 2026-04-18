"""ASR 基准测试脚本 — 评估 Vosk 中英文识别延迟与准确率。

运行方式:
    python benchmarks/asr_benchmark.py
"""

# 1. Standard library
import logging
import struct
import sys
import time
import wave
from pathlib import Path
from typing import Optional

# 2. Third-party
import yaml

# 3. Local application
sys.path.insert(0, str(Path(__file__).parent.parent))
from models.asr import ASREngine, ASRError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Test cases: (expected_text, lang)
# For real accuracy testing replace silence WAVs with actual recordings.
# ---------------------------------------------------------------------------
TEST_CASES: list[tuple[str, str]] = [
    ("你好世界", "zh"),
    ("今天天气怎么样", "zh"),
    ("我想去北京旅游", "zh"),
    ("请帮我翻译这句话", "zh"),
    ("这是一个测试句子", "zh"),
    ("hello world", "en"),
    ("how are you today", "en"),
    ("the weather is nice", "en"),
    ("please translate this sentence", "en"),
    ("this is a benchmark test", "en"),
]

LATENCY_TARGET_S = 5.0
SAMPLE_RATE = 16000
SILENCE_DURATION_S = 1  # short silence WAV for smoke-testing without real audio


def _generate_silence_wav(path: str, duration_s: int = SILENCE_DURATION_S) -> None:
    """生成指定时长的静音 WAV 文件 (16kHz, 16-bit, Mono)。"""
    num_frames = SAMPLE_RATE * duration_s
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack("<" + "h" * num_frames, *([0] * num_frames)))
    logger.info("生成静音 WAV: path=%s, duration=%ds", path, duration_s)


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "default.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_benchmark() -> None:
    config = _load_config()
    asr_cfg = config["models"]["asr"]
    engine = ASREngine(
        zh_model_path=asr_cfg["zh_model_path"],
        en_model_path=asr_cfg["en_model_path"],
    )

    tmp_wav = str(Path(__file__).parent / "_bench_silence.wav")
    _generate_silence_wav(tmp_wav)

    results: list[dict] = []
    latencies: list[float] = []

    logger.info("=== ASR 基准测试开始 (共 %d 条) ===", len(TEST_CASES))

    for idx, (expected, lang) in enumerate(TEST_CASES, start=1):
        start = time.monotonic()
        recognized: Optional[str] = None
        error: Optional[str] = None

        try:
            recognized = engine.recognize(tmp_wav, lang=lang)
            latency = time.monotonic() - start
        except ASRError as e:
            latency = time.monotonic() - start
            error = str(e)
            logger.error("识别失败 [%d]: lang=%s, error=%s", idx, lang, error)

        latencies.append(latency)
        passed_latency = latency < LATENCY_TARGET_S

        results.append(
            {
                "id": idx,
                "lang": lang,
                "expected": expected,
                "recognized": recognized or "",
                "latency_s": latency,
                "latency_ok": passed_latency,
                "error": error,
            }
        )

        status = "OK" if passed_latency and error is None else "FAIL"
        logger.info(
            "[%d/%d] %s lang=%s latency=%.3fs recognized=%r",
            idx,
            len(TEST_CASES),
            status,
            lang,
            latency,
            recognized or error,
        )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    latency_pass_count = sum(1 for r in results if r["latency_ok"])
    error_count = sum(1 for r in results if r["error"])

    print("\n" + "=" * 60)
    print("ASR 基准测试报告")
    print("=" * 60)
    print(f"{'#':<4} {'Lang':<5} {'Latency(s)':<12} {'<5s?':<6} {'Result / Error'}")
    print("-" * 60)
    for r in results:
        flag = "PASS" if r["latency_ok"] else "FAIL"
        detail = r["recognized"] if not r["error"] else f"ERROR: {r['error']}"
        print(f"{r['id']:<4} {r['lang']:<5} {r['latency_s']:<12.3f} {flag:<6} {detail}")
    print("-" * 60)
    print(f"平均延迟:       {avg_latency:.3f}s  (目标 < {LATENCY_TARGET_S}s)")
    print(f"延迟达标:       {latency_pass_count}/{len(TEST_CASES)}")
    print(f"识别错误:       {error_count}/{len(TEST_CASES)}")
    overall = "PASS" if latency_pass_count == len(TEST_CASES) and error_count == 0 else "FAIL"
    print(f"整体结果:       {overall}")
    print("=" * 60)

    # Cleanup temp file
    Path(tmp_wav).unlink(missing_ok=True)


if __name__ == "__main__":
    run_benchmark()
