"""统一管线入口 — run_pipeline() 自动路由并保存历史记录"""

# 1. Standard library
import logging
from typing import Any

# 2. Local
from pipeline.single import run_tts, run_asr
from pipeline.composite import run_mt_tts, run_asr_mt
from storage.history import HistoryManager

logger = logging.getLogger(__name__)

_VALID_MODES = {"tts", "asr", "mt_tts", "asr_mt"}

_history_cache: dict[str, HistoryManager] = {}


def run_pipeline(mode: str, config: dict, **kwargs: Any) -> dict:
    """统一管线入口，自动路由到对应管线并保存历史记录。

    Args:
        mode: 管线模式，"tts" | "asr" | "mt_tts" | "asr_mt"。
        config: 应用配置字典（来自 default.yaml）。
        **kwargs: 传递给对应管线函数的参数。

    Returns:
        对应管线函数的返回 dict，附加 "history_id" 键（保存成功时）。

    Raises:
        ValueError: mode 不在支持列表中。
    """
    if mode not in _VALID_MODES:
        raise ValueError("不支持的管线模式: %r，支持: %s" % (mode, ", ".join(sorted(_VALID_MODES))))

    logger.info("run_pipeline 开始: mode=%s", mode)

    if mode == "tts":
        result = run_tts(
            text=kwargs["text"],
            lang=kwargs["lang"],
            config=config,
        )
        _save_history(
            config=config,
            record_type="tts",
            source_lang=kwargs["lang"],
            target_lang=None,
            source_text=result.get("text", ""),
            target_text=None,
            audio_path=result.get("audio_path"),
            result=result,
        )

    elif mode == "asr":
        result = run_asr(
            lang=kwargs["lang"],
            config=config,
        )
        _save_history(
            config=config,
            record_type="asr",
            source_lang=kwargs["lang"],
            target_lang=None,
            source_text=result.get("text", ""),
            target_text=None,
            audio_path=result.get("audio_path"),
            result=result,
        )

    elif mode == "mt_tts":
        result = run_mt_tts(
            text=kwargs["text"],
            source_lang=kwargs["source_lang"],
            target_lang=kwargs["target_lang"],
            config=config,
        )
        _save_history(
            config=config,
            record_type="mt_tts",
            source_lang=kwargs["source_lang"],
            target_lang=kwargs["target_lang"],
            source_text=result.get("source_text", ""),
            target_text=result.get("translated_text"),
            audio_path=result.get("audio_path"),
            result=result,
        )

    else:  # asr_mt
        result = run_asr_mt(
            source_lang=kwargs["source_lang"],
            target_lang=kwargs["target_lang"],
            config=config,
        )
        _save_history(
            config=config,
            record_type="asr_mt",
            source_lang=kwargs["source_lang"],
            target_lang=kwargs["target_lang"],
            source_text=result.get("source_text") or "",
            target_text=result.get("translated_text"),
            audio_path=result.get("audio_path"),
            result=result,
        )

    logger.info("run_pipeline 完成: mode=%s, error=%s", mode, result.get("error"))
    return result


def _save_history(
    config: dict,
    record_type: str,
    source_lang: str,
    target_lang: str | None,
    source_text: str,
    target_text: str | None,
    audio_path: str | None,
    result: dict,
) -> None:
    """保存历史记录，失败时仅记录日志，不影响主流程。"""
    storage_cfg = config["storage"]
    cache_key = storage_cfg["history_dir"]
    try:
        if cache_key not in _history_cache:
            _history_cache[cache_key] = HistoryManager(
                history_dir=storage_cfg["history_dir"],
                max_records=storage_cfg["max_history"],
            )
        manager = _history_cache[cache_key]
        record = manager.add_record(
            record_type=record_type,
            source_lang=source_lang,
            target_lang=target_lang,
            source_text=source_text,
            target_text=target_text,
            audio_path=audio_path,
        )
        result["history_id"] = record["id"]
    except Exception as e:
        logger.error("历史记录保存失败: type=%s, error=%s", record_type, str(e))
