"""MT 基准测试脚本 — 评估 Argos Translate 中英互译延迟。

运行方式:
    python benchmarks/mt_benchmark.py
"""

# 1. Standard library
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# 2. Third-party
import yaml

# 3. Local application
sys.path.insert(0, str(Path(__file__).parent.parent))
from models.mt import MTEngine, TranslationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Test cases: (source_text, source_lang, target_lang)
# ---------------------------------------------------------------------------
TEST_CASES: list[tuple[str, str, str]] = [
    ("你好，世界！", "zh", "en"),
    ("今天天气很好。", "zh", "en"),
    ("我想去北京旅游。", "zh", "en"),
    ("请帮我翻译这句话。", "zh", "en"),
    ("这是一个测试句子。", "zh", "en"),
    ("机器翻译技术发展很快。", "zh", "en"),
    ("离线翻译系统非常实用。", "zh", "en"),
    ("Hello, world!", "en", "zh"),
    ("The weather is nice today.", "en", "zh"),
    ("I would like to visit Beijing.", "en", "zh"),
    ("Please translate this sentence.", "en", "zh"),
    ("This is a benchmark test.", "en", "zh"),
    ("Machine translation is improving rapidly.", "en", "zh"),
    ("Offline translation systems are very practical.", "en", "zh"),
    ("How are you doing today?", "en", "zh"),
]

LATENCY_TARGET_S = 3.0


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "default.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_benchmark() -> None:
    _load_config()  # validate config is readable; MT uses installed packages
    engine = MTEngine()

    results: list[dict] = []
    latencies: list[float] = []

    logger.info("=== MT 基准测试开始 (共 %d 条) ===", len(TEST_CASES))

    for idx, (source, src_lang, tgt_lang) in enumerate(TEST_CASES, start=1):
        start = time.monotonic()
        translated: Optional[str] = None
        error: Optional[str] = None

        try:
            translated = engine.translate(source, src_lang, tgt_lang)
            latency = time.monotonic() - start
        except TranslationError as e:
            latency = time.monotonic() - start
            error = str(e)
            logger.error("翻译失败 [%d]: %s→%s, error=%s", idx, src_lang, tgt_lang, error)

        latencies.append(latency)
        passed_latency = latency < LATENCY_TARGET_S

        results.append(
            {
                "id": idx,
                "src_lang": src_lang,
                "tgt_lang": tgt_lang,
                "source": source,
                "translated": translated or "",
                "latency_s": latency,
                "latency_ok": passed_latency,
                "error": error,
            }
        )

        status = "OK" if passed_latency and error is None else "FAIL"
        logger.info(
            "[%d/%d] %s %s→%s latency=%.3fs result=%r",
            idx,
            len(TEST_CASES),
            status,
            src_lang,
            tgt_lang,
            latency,
            translated or error,
        )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    latency_pass_count = sum(1 for r in results if r["latency_ok"])
    error_count = sum(1 for r in results if r["error"])

    print("\n" + "=" * 72)
    print("MT 基准测试报告")
    print("=" * 72)
    print(f"{'#':<4} {'Pair':<8} {'Latency(s)':<12} {'<3s?':<6} {'Source → Translation'}")
    print("-" * 72)
    for r in results:
        flag = "PASS" if r["latency_ok"] else "FAIL"
        pair = f"{r['src_lang']}→{r['tgt_lang']}"
        if r["error"]:
            detail = f"ERROR: {r['error']}"
        else:
            detail = f"{r['source']!r} → {r['translated']!r}"
        print(f"{r['id']:<4} {pair:<8} {r['latency_s']:<12.3f} {flag:<6} {detail}")
    print("-" * 72)
    print(f"平均延迟:       {avg_latency:.3f}s  (目标 < {LATENCY_TARGET_S}s)")
    print(f"延迟达标:       {latency_pass_count}/{len(TEST_CASES)}")
    print(f"翻译错误:       {error_count}/{len(TEST_CASES)}")
    overall = "PASS" if latency_pass_count == len(TEST_CASES) and error_count == 0 else "FAIL"
    print(f"整体结果:       {overall}")
    print("=" * 72)


if __name__ == "__main__":
    run_benchmark()
