"""Pi5 offline bilingual speech interaction system entrypoint."""

# 1. Standard library
import argparse
import logging
import os
import sys
from pathlib import Path

# 2. Third-party
import yaml

from models.mt import configure_argos_environment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "config" / "default.yaml"
_PROJECT_ROOT = Path(__file__).resolve().parent


def _candidate_local_venv_pythons() -> tuple[Path, ...]:
    if os.name == "nt":
        return (
            _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
            _PROJECT_ROOT / "venv" / "Scripts" / "python.exe",
        )
    return (
        _PROJECT_ROOT / ".venv" / "bin" / "python",
        _PROJECT_ROOT / "venv" / "bin" / "python",
    )


def _running_inside_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _maybe_reexec_with_local_venv() -> None:
    if _running_inside_virtualenv():
        return

    current_executable = Path(sys.executable).resolve()
    for candidate in _candidate_local_venv_pythons():
        if not candidate.exists():
            continue

        resolved_candidate = candidate.resolve()
        if resolved_candidate == current_executable:
            return

        logger.info(
            "restarting with local virtual environment interpreter: current=%s, target=%s",
            current_executable,
            resolved_candidate,
        )
        os.execv(str(resolved_candidate), [str(resolved_candidate), str(_PROJECT_ROOT / "main.py"), *sys.argv[1:]])
        return


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
    configure_argos_environment(config.get("models", {}).get("mt", {}).get("package_path"))

    if args.cli:
        logger.info("starting CLI debug mode")
        from app.cli import run_cli

        run_cli(config)
    else:
        logger.info("starting API server mode")
        from api.app import run_server

        run_server(config)


if __name__ == "__main__":
    _maybe_reexec_with_local_venv()
    main()
