"""Pi5 offline bilingual speech interaction system entrypoint."""

# 1. Standard library
import argparse
import logging
import sys
from pathlib import Path

# 2. Third-party
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "config" / "default.yaml"


def _load_config() -> dict:
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError:
        logger.error("config file not found: path=%s", _CONFIG_PATH)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - entrypoint should exit on config failure
        logger.error("failed to load config: path=%s, error=%s", _CONFIG_PATH, str(exc))
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pi5 offline bilingual speech interaction system")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--server",
        action="store_true",
        help="explicitly start the Flask API server (default behavior)",
    )
    mode_group.add_argument(
        "--cli",
        action="store_true",
        help="start the minimal CLI debug path",
    )
    args = parser.parse_args()

    config = _load_config()

    if args.cli:
        logger.info("starting CLI debug mode")
        from app.cli import run_cli

        run_cli(config)
    else:
        logger.info("starting API server mode")
        from api.app import run_server

        run_server(config)


if __name__ == "__main__":
    main()
