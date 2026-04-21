"""配置加载模块 — 从 default.yaml 加载，支持环境变量覆盖"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "default.yaml"

# 环境变量前缀 → yaml 路径映射
# 格式: "ENV_VAR_NAME": ("section", "key")
_ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "PI5_AUDIO_DEVICE": ("audio", "device"),
    "PI5_AUDIO_PLAYBACK_DEVICE": ("audio", "playback_device"),
    "PI5_AUDIO_RECORD_DEVICE": ("audio", "record_device"),
    "PI5_AUDIO_SAMPLE_RATE": ("audio", "sample_rate"),
    "PI5_AUDIO_MAX_RECORD_DURATION": ("audio", "max_record_duration"),
    "PI5_API_HOST": ("api", "host"),
    "PI5_API_PORT": ("api", "port"),
    "PI5_LOG_LEVEL": ("logging", "level"),
    "PI5_STORAGE_HISTORY_DIR": ("storage", "history_dir"),
    "PI5_STORAGE_RECORDINGS_DIR": ("storage", "recordings_dir"),
    "PI5_STORAGE_MAX_HISTORY": ("storage", "max_history"),
    "PI5_STORAGE_MAX_RECORDINGS": ("storage", "max_recordings"),
}

_config: dict[str, Any] | None = None


def _cast_value(original: Any, raw: str) -> Any:
    """将环境变量字符串转换为与原始值相同的类型。"""
    if isinstance(original, bool):
        return raw.lower() in ("1", "true", "yes")
    if isinstance(original, int):
        return int(raw)
    if isinstance(original, float):
        return float(raw)
    return raw


def _apply_env_overrides(config: dict[str, Any]) -> None:
    """将已设置的环境变量覆盖到配置字典中（原地修改）。"""
    for env_key, (section, key) in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_key)
        if raw is None:
            continue
        try:
            original = config[section][key]
            config[section][key] = _cast_value(original, raw)
            logger.debug(
                "配置覆盖: %s.%s = %s (来自 %s)", section, key, config[section][key], env_key
            )
        except KeyError:
            logger.warning("环境变量 %s 对应的配置路径 %s.%s 不存在，已跳过", env_key, section, key)
        except (ValueError, TypeError) as e:
            logger.warning("环境变量 %s 值 %r 类型转换失败，已跳过: %s", env_key, raw, e)


def _load() -> dict[str, Any]:
    """从 default.yaml 加载配置并应用环境变量覆盖。"""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"配置文件不存在: {_CONFIG_PATH}")

    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"配置文件格式错误，期望 mapping，得到 {type(config).__name__}")

    _apply_env_overrides(config)
    logger.info("配置加载完成: %s", _CONFIG_PATH)
    return config


def get_config() -> dict[str, Any]:
    """返回全局配置字典（单例，首次调用时加载）。

    Returns:
        包含 audio / models / storage / api / logging 各节的配置字典。

    Raises:
        FileNotFoundError: 配置文件不存在。
        ValueError: 配置文件格式错误。
    """
    global _config
    if _config is None:
        _config = _load()
    return _config


def reload_config() -> dict[str, Any]:
    """强制重新加载配置（测试或热重载场景使用）。

    Returns:
        重新加载后的配置字典。
    """
    global _config
    _config = None
    return get_config()
