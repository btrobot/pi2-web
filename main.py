"""Pi5 离线双语语音交互系统 - 入口"""

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
        with _CONFIG_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("配置文件不存在: path=%s", _CONFIG_PATH)
        sys.exit(1)
    except Exception as e:
        logger.error("配置文件加载失败: path=%s, error=%s", _CONFIG_PATH, str(e))
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pi5 离线双语语音交互系统")
    parser.add_argument(
        "--server",
        action="store_true",
        help="启动 Flask API 服务器（默认启动 CLI）",
    )
    args = parser.parse_args()

    config = _load_config()

    if args.server:
        logger.info("启动 API 服务器模式")
        from api.app import run_server
        run_server(config)
    else:
        logger.info("启动 CLI 模式")
        from app.cli import run_cli
        run_cli(config)


if __name__ == "__main__":
    main()
