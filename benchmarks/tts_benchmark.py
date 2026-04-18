"""TTS 基准测试脚本 — 评估 piper-tts 中英文合成延迟与输出有效性。

运行方式:
    python benchmarks/tts_benchmark.py
"""

# 1. Standard library
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

# 2. Third-party
import yaml

# 3. Local application
sys.path.insert(0, str(Path(__file__).parent.parent))
from models.tts import TTSEngine, TTSError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Test cases: (text, lang)
# ---------------------------------------------------------------------------
TEST_CASES: list[tuple[str, str]] = [
    ("你好，世界！", "zh"),
    ("今天天气很好。", "zh"),
    ("我想去北京旅游。", "zh"),
    ("请帮我翻译这句话。", "zh"),
    ("离线翻译系统非常实用。", "zh"),
    ("Hello, world!", "en"),
    ("The weather is nice today.", "en"),
    ("I would like to visit Beijing.", "en"),
    ("Please translate this sentence.", "en"),
    ("Offline translation systems are very practical.", "en"),
]

LATENCY_TARGET_S = 3.0
MIN_WAV_SIZE_BYTES = 1  # output must be non-empty


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "default.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_benchmark() -> None:
    config = _load_config()
    tts_cfg = config["models"]["tts"]
    engine = TTSEngine(
        zh_model_path=tts_cfg["zh_model_path"],
        en_model_path=tts_cfg["en_model_path"],
    )

    results: list[dict] = []
    latencies: list[float] = []

    logger.info("=== TTS 基准测试开始 (共 %d 条) ===", len(TEST_CASES))

    with tempfile.TemporaryDirectory() as tmp_dir:
        for idx, (text, lang) in enumerate(TEST_CASES, start=1):
            output_path = str(Path(tmp_dir) / f"tts_bench_{idx}.wav")
            start = time.monotonic()
            returned_path: Optional[str] = None
            error: Optional[str] = None
            file_size: int = 0

            try:
                returned_path = engine.synthesize(text, lang, output_path)
                latency = time.monotonic() - start
                wav = Path(returned_path)
                file_size = wav.stat().st_size if wav.exists() else 0
            except (TTSError, ValueError) as e:
                latency = time.monotonic() - start
                error = str(e)
                logger.error("合成失败 [%d]: lang=%s, error=%s", idx, lang, error)

            latencies.append(latency)
            passed_latency = latency < LATENCY_TARGET_S
            passed_file = file_size > MIN_WAV_SIZE_BYTES and error is None
            passed = passed_latency and passed_file

            results.append(
                {
                    "id": idx,
                    "lang": lang,
                    "text": text,
                    "latency_s": latency,
                    "latency_ok": passed_latency,
                    "file_size": file_size,
                    "file_ok": passed_file,
                    "error": error,
                }
            )

            status = "OK" if passed else "FAIL"
            logger.info(
                "[%d/%d] %s lang=%s latency=%.3fs size=%dB text=%r",
                idx,
                len(TEST_CASES),
                status,
                lang,
                latency,
                file_size,
                text,
            )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    latency_pass_count = sum(1 for r in results if r["latency_ok"])
    file_pass_count = sum(1 for r in results if r["file_ok"])
    error_count = sum(1 for r in results if r["error"])

    print("\n" + "=" * 70)
    print("TTS 基准测试报告")
    print("=" * 70)
    print(f"{'#':<4} {'Lang':<5} {'Latency(s)':<12} {'<3s?':<6} {'Size(B)':<10} {'File OK':<8} {'Text'}")
    print("-" * 70)
    for r in results:
        lat_flag = "PASS" if r["latency_ok"] else "FAIL"
        file_flag = "PASS" if r["file_ok"] else "FAIL"
        detail = r["text"] if not r["error"] else f"ERROR: {r['error']}"
        print(
            f"{r['id']:<4} {r['lang']:<5} {r['latency_s']:<12.3f} {lat_flag:<6} "
            f"{r['file_size']:<10} {file_flag:<8} {detail}"
        )
    print("-" * 70)
    print(f"平均延迟:       {avg_latency:.3f}s  (目标 < {LATENCY_TARGET_S}s)")
    print(f"延迟达标:       {latency_pass_count}/{len(TEST_CASES)}")
    print(f"文件有效:       {file_pass_count}/{len(TEST_CASES)}")
    print(f"合成错误:       {error_count}/{len(TEST_CASES)}")
    overall = (
        "PASS"
        if latency_pass_count == len(TEST_CASES) and file_pass_count == len(TEST_CASES)
        else "FAIL"
    )
    print(f"整体结果:       {overall}")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
