"""CLI 交互菜单 — 6 种模式 (FR-01~06)

NOTE: print() is intentional in this module — CLI user-facing output, not logging.
Diagnostic/debug output uses logger. This is an approved exemption from python-coding-rules.
"""

# 1. Standard library
import logging

# 2. Local
from pipeline import run_pipeline

logger = logging.getLogger(__name__)

_MENU = """
========================================
  Pi5 离线双语语音交互系统
========================================
  1. TTS 中文朗读        (FR-01)
  2. TTS 英文朗读        (FR-02)
  3. ASR 中文识别        (FR-03)
  4. ASR 英文识别        (FR-04)
  5. 中文输入 → 翻译+朗读 (FR-05)
  6. 语音输入 → 翻译+朗读 (FR-06)
  0. 退出
========================================
"""


def _prompt_text(label: str) -> str:
    return input(f"{label}: ").strip()


def _run_tts(config: dict, lang: str) -> None:
    text = _prompt_text("请输入文本")
    if not text:
        print("文本不能为空")
        return
    result = run_pipeline(mode=f"tts_{lang}_{lang}", config=config, input_text=text)
    if result.get("error"):
        print(f"错误: {result['error']}")
    else:
        print(f"朗读完成 | 音频: {result.get('output_audio_path', '-')}")


def _run_asr(config: dict, lang: str) -> None:
    print("开始录音，按 Ctrl+C 停止...")
    result = run_pipeline(mode=f"asr_{lang}_{lang}", config=config)
    if result.get("error"):
        print(f"错误: {result['error']}")
    else:
        print(f"识别结果: {result.get('output_text', '')}")


def _run_mt_tts(config: dict) -> None:
    text = _prompt_text("请输入中文文本")
    if not text:
        print("文本不能为空")
        return
    result = run_pipeline(
        mode="mt_tts_zh_en",
        config=config,
        input_text=text,
    )
    if result.get("error"):
        print(f"错误: {result['error']}")
    else:
        print(f"翻译结果: {result.get('output_text', '')}")
        print(f"音频: {result.get('output_audio_path', '-')}")


def _run_asr_mt(config: dict) -> None:
    print("开始录音，按 Ctrl+C 停止...")
    result = run_pipeline(
        mode="asr_mt_tts_zh_en",
        config=config,
    )
    if result.get("error"):
        print(f"错误: {result['error']}")
    else:
        print(f"识别: {result.get('source_text', '')}")
        print(f"翻译: {result.get('output_text', '')}")
        print(f"音频: {result.get('output_audio_path', '-')}")


def run_cli(config: dict) -> None:
    """启动 CLI 交互菜单。

    Args:
        config: 应用配置字典（来自 default.yaml）。
    """
    logger.info("CLI 启动")
    while True:
        print(_MENU)
        choice = input("请选择 [0-6]: ").strip()

        try:
            if choice == "0":
                print("退出")
                logger.info("CLI 正常退出")
                break
            elif choice == "1":
                _run_tts(config, lang="zh")
            elif choice == "2":
                _run_tts(config, lang="en")
            elif choice == "3":
                _run_asr(config, lang="zh")
            elif choice == "4":
                _run_asr(config, lang="en")
            elif choice == "5":
                _run_mt_tts(config)
            elif choice == "6":
                _run_asr_mt(config)
            else:
                print("无效选项，请输入 0-6")
        except KeyboardInterrupt:
            print("\n操作已取消")
            logger.info("CLI 操作被用户中断")
        except Exception as e:
            logger.error("CLI 执行失败: choice=%s, error=%s", choice, str(e))
            print(f"执行失败: {e}")
