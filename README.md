# Pi5 离线双语语音交互系统

在 Raspberry Pi 5 上运行的全离线中英双语语音交互系统，支持语音识别、机器翻译、语音合成及历史记录导出。

---

## 功能列表

| # | 功能 | 说明 |
|---|------|------|
| FR-01 | 中文文字 → 中文语音 | TTS 合成并播放 |
| FR-02 | 英文语音 → 英文文字 | ASR 识别返回文本 |
| FR-03 | 中文文字 → 英文语音 | MT 翻译 + TTS 合成 |
| FR-04 | 英文语音 → 中文文字 | ASR 识别 + MT 翻译 |
| FR-05 | 历史记录管理 | 保留最近 5 条，支持导出 |
| FR-06 | 独立录音 | 单次上限 3 分钟，最多 5 个文件，支持导出 |

---

## 技术栈

| 模块 | 方案 | 备选 |
|------|------|------|
| ASR | Vosk | Whisper-tiny |
| MT | Argos Translate | - |
| TTS | piper-tts | eSpeak-ng |
| 音频采集 | pyalsaaudio + ReSpeaker 2-Mics HAT V2 | USB 麦克风 |
| Web 框架 | Flask | - |
| 开发语言 | Python 3.11+ | - |
| 平台 | Raspberry Pi 5 (ARM64, 8GB) | - |

---

## 快速开始

### 1. 安装环境

```bash
bash scripts/setup_env.sh
```

### 2. 下载模型

```bash
bash scripts/download_models.sh
```

### 3. 启动 CLI

```bash
python main.py
```

### 4. 启动 Web 服务

```bash
python main.py --server
```

Web 服务默认监听 `0.0.0.0:5000`，局域网内可访问。

---

## 项目结构

```
pi5-translator/
├── main.py              # 入口
├── config/
│   └── default.yaml     # 配置文件
├── models/              # ASR / MT / TTS 模块封装
│   └── data/            # 模型文件 (vosk / argos / piper)
├── audio/               # 音频采集与播放
├── pipeline/            # ASR → MT → TTS 处理链
├── api/                 # Flask 导出接口
├── storage/             # 历史记录与录音管理
├── data/
│   ├── history/         # 历史记录 (最多 5 条)
│   └── recordings/      # 录音文件 (最多 5 个)
├── scripts/             # 环境安装、模型下载脚本
└── tests/               # 测试
```

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 系统健康检查 |
| `/api/history` | GET | 历史记录列表 |
| `/api/history/<id>/audio` | GET | 下载指定历史音频 |
| `/api/history/export` | GET | 打包下载全部历史记录 (ZIP) |
| `/api/recordings` | GET | 录音文件列表 |
| `/api/recordings/<id>/audio` | GET | 下载指定录音文件 |
| `/api/recordings/export` | GET | 打包下载全部录音文件 (ZIP) |

---

## 配置说明

配置文件：`config/default.yaml`

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `audio.device` | `default` | ALSA 设备名，ReSpeaker 用 `plughw:2,0` |
| `audio.sample_rate` | `16000` | 采样率 (Hz) |
| `audio.max_record_duration` | `180` | 单次录音上限 (秒) |
| `models.asr.zh_model_path` | `models/data/vosk-model-small-cn-0.22` | 中文 ASR 模型路径 |
| `models.asr.en_model_path` | `models/data/vosk-model-small-en-us-0.15` | 英文 ASR 模型路径 |
| `models.mt.package_path` | `models/data/argos` | Argos 翻译模型目录 |
| `models.tts.zh_model_path` | `models/data/piper/zh_CN` | 中文 TTS 模型路径 |
| `models.tts.en_model_path` | `models/data/piper/en_US` | 英文 TTS 模型路径 |
| `storage.max_history` | `5` | 历史记录上限 |
| `storage.max_recordings` | `5` | 录音文件上限 |
| `api.host` | `0.0.0.0` | Web 服务监听地址 |
| `api.port` | `5000` | Web 服务端口 |

---

## 测试

```bash
pytest
```

---

## 许可证

[待定]
