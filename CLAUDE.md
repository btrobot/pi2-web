# Pi5 Offline Translation System

Raspberry Pi 5 上的全离线双语语音交互系统。

## Project Overview

在 Pi5 上部署离线 ASR + MT + TTS 模型，实现中英双语语音交互，支持历史记录和录音导出。

## Six Core Features

1. A 文字 → A 语音 (TTS)
2. B 语音 → B 文字 (ASR)
3. A 文字 → B 语音 (MT + TTS)
4. B 语音 → A 文字 (ASR + MT)
5. 历史记录：最近 5 条，可导出
6. 录音：单次 3 分钟上限，最多 5 个文件，可导出

## Tech Stack

| Component | Tool | Notes |
|-----------|------|-------|
| ASR | Vosk (vosk>=0.3.45) | 离线语音识别，中英双模型 |
| MT | Argos Translate (argostranslate>=1.9.0) | 离线神经机器翻译 |
| TTS | piper-tts (>=1.2.0) | 离线语音合成 |
| Audio | pyalsaaudio (>=0.10.0) | ALSA 音频采集/播放 |
| Language | Python 3.11+ | 主开发语言 |
| API | Flask (>=3.0.0) | Web UI + REST 导出接口 |
| Config | PyYAML (>=6.0) | YAML 配置管理 |
| Testing | pytest (>=8.0.0) + pytest-cov | 单元/集成/系统测试 |
| Platform | Raspberry Pi 5 (ARM64, 8GB RAM) | 目标硬件 |

## Directory Structure

```
pi2-test/
├── main.py                  # 入口 (CLI 模式 / --server API 模式)
├── requirements.txt         # Python 依赖
├── pytest.ini               # 测试配置
├── config/
│   ├── default.yaml         # 主配置文件 (音频/模型路径/存储/API)
│   └── settings.py          # 配置加载/校验
├── models/                  # AI 模型封装
│   ├── asr.py               # Vosk 语音识别引擎
│   ├── mt.py                # Argos 机器翻译引擎
│   ├── tts.py               # Piper 语音合成引擎
│   └── data/                # 模型文件 (需通过 scripts/download_models.sh 下载)
├── audio/                   # 音频模块
│   ├── capture.py           # 麦克风采集
│   └── playback.py          # 音频播放
├── pipeline/                # 处理管线
│   ├── single.py            # 单语管线 (TTS / ASR)
│   ├── composite.py         # 复合管线 (ASR→MT→TTS / ASR→MT)
│   └── _utils.py            # 管线工具函数
├── api/                     # Flask Web 服务
│   ├── app.py               # Flask 应用 + 服务启动
│   ├── history_routes.py    # 历史记录 API
│   ├── recording_routes.py  # 录音文件 API
│   └── templates/
│       └── index.html       # Web UI 页面
├── app/
│   └── cli.py               # CLI 交互界面
├── storage/                 # 数据持久化
│   ├── history.py           # 历史记录管理 (最多 5 条)
│   └── recordings.py        # 录音文件管理 (最多 5 个)
├── hardware/
│   └── asound.conf          # ALSA 音频设备配置
├── scripts/
│   ├── setup_env.sh         # 环境安装脚本
│   └── download_models.sh   # 模型下载脚本
├── tests/
│   ├── conftest.py          # 测试 fixtures
│   ├── test_storage.py      # 存储模块测试
│   ├── test_pipeline.py     # 管线集成测试
│   ├── test_api.py          # API 接口测试
│   └── test_system.py       # 端到端系统测试
├── benchmarks/              # 性能基准测试
│   ├── asr_benchmark.py
│   ├── mt_benchmark.py
│   └── tts_benchmark.py
├── data/                    # 运行时数据
│   ├── history/             # 历史记录 JSON
│   └── recordings/          # 录音 WAV 文件
├── production/              # 生产环境状态
│   ├── session-state/
│   └── session-logs/
└── docs/                    # 项目文档
    ├── requirements-spec.md # 需求规格
    ├── task-breakdown.md    # 任务分解
    └── sprint-plan.md       # Sprint 计划
```

## Running

```bash
# CLI 模式
python main.py

# Web API 模式 (默认 0.0.0.0:5000)
python main.py --server

# 运行测试
pytest

# 环境安装
bash scripts/setup_env.sh
bash scripts/download_models.sh
```

## Key Constraints

- **全离线运行**：所有功能不依赖网络
- **Pi5 资源限制**：所有模型内存总占用 < 2GB
- **实时性**：单句处理延迟 < 5 秒
- **音频标准**：16kHz, 16-bit, Mono WAV
- **存储限制**：历史记录最多 5 条，录音最多 5 个文件

## Configuration

主配置文件 `config/default.yaml`，包含：
- `audio` — 设备名、采样率、录音时长上限 (180s)
- `models` — ASR/MT/TTS 模型文件路径
- `storage` — 历史记录和录音存储路径及上限
- `api` — Flask 服务地址和端口
- `logging` — 日志级别

## Development Rules

- Python coding: `.claude/rules/python-coding-rules.md`
- Code review: `.claude/rules/code-review-rules.md`
- Commit format: `.claude/rules/commit-rules.md`
- Agent coordination: `.claude/rules/coordination-rules.md`

## Quick Reference

- 技术选型报告: `deep-research-report.md`
- 需求规格: `docs/requirements-spec.md`
- Sprint 计划: `docs/sprint-plan.md`
- 任务分解: `docs/task-breakdown.md`
