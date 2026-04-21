"""Inspect the active MT runtime wiring for a language pair.

Usage examples:
  python scripts/check_mt_runtime.py --source en --target zh
  python scripts/check_mt_runtime.py --source zh --target en --translate "你好，世界"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.mt import (  # noqa: E402
    MTEngine,
    _iter_package_translations,
    _requires_external_sentence_tokenizer,
    configure_argos_environment,
)


def _load_config() -> dict:
    config_path = PROJECT_ROOT / "config" / "default.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"<unavailable: {exc}>"


def _describe_wrappers(translation: object) -> Iterable[str]:
    current = translation
    depth = 0
    while current is not None:
        yield f"wrapper[{depth}]: {type(current).__name__}"
        current = getattr(current, "underlying", None)
        depth += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Pi2 MT runtime wiring")
    parser.add_argument("--source", required=True, choices=["zh", "en"])
    parser.add_argument("--target", required=True, choices=["zh", "en"])
    parser.add_argument("--translate", help="Optional text to translate after inspection")
    args = parser.parse_args()

    config = _load_config()
    package_dir = config.get("models", {}).get("mt", {}).get("package_path")
    resolved_package_dir = configure_argos_environment(package_dir)

    print("project_root:", PROJECT_ROOT)
    print("git_head:", _git_head())
    print("models.mt:", Path(sys.modules["models.mt"].__file__).resolve())
    print("argos_package_dir:", resolved_package_dir)
    print("requires_external_sentence_tokenizer(en, zh):", _requires_external_sentence_tokenizer("en", "zh"))
    print("requires_external_sentence_tokenizer(zh, en):", _requires_external_sentence_tokenizer("zh", "en"))
    print("requested_pair:", f"{args.source}->{args.target}")
    print("pair_requires_external_sentence_tokenizer:", _requires_external_sentence_tokenizer(args.source, args.target))

    engine = MTEngine()
    engine._ensure_loaded(args.source, args.target)
    translation = engine._translations[(args.source, args.target)]

    for line in _describe_wrappers(translation):
        print(line)

    package_translations = list(_iter_package_translations(translation))
    print("package_translation_count:", len(package_translations))
    for index, package_translation in enumerate(package_translations):
        pkg = getattr(package_translation, "pkg", None)
        sentencizer = getattr(package_translation, "sentencizer", None)
        print(f"package_translation[{index}].type:", type(package_translation).__name__)
        print(f"package_translation[{index}].package_path:", getattr(pkg, 'package_path', None))
        print(f"package_translation[{index}].packaged_sbd_path:", getattr(pkg, 'packaged_sbd_path', None))
        print(f"package_translation[{index}].sentencizer:", type(sentencizer).__name__ if sentencizer else None)

    if args.translate:
        print("translation_input:", args.translate)
        print("translation_output:", engine.translate(args.translate, args.source, args.target))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
