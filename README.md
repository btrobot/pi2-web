# Pi5 离线中英双语语音交互系统

一个运行在 **Raspberry Pi 5** 上的离线中英双语语音交互项目，提供 Web 控制台、Pi5 本地录音/播放、历史记录管理，以及中英之间的文本/语音转换能力。

## 项目能力

当前支持 6 类页面能力、12 个叶子模式：

- 同语文字 → 语音
  - `tts_zh_zh`
  - `tts_en_en`
- 同语语音 → 文字
  - `asr_zh_zh`
  - `asr_en_en`
- 跨语文字 → 语音
  - `mt_tts_zh_en`
  - `mt_tts_en_zh`
- 跨语语音 → 文字
  - `asr_mt_zh_en`
  - `asr_mt_en_zh`
- 跨语文字 → 文字
  - `mt_zh_en`
  - `mt_en_zh`
- 跨语语音 → 语音
  - `asr_mt_tts_zh_en`
  - `asr_mt_tts_en_zh`

另提供一套独立的 **Pi5 本地录音菜单**，用于保存和复用录音文件。

---

## 当前实现特性

- **完全离线运行**
  - ASR：Vosk
  - MT：Argos Translate
  - TTS：Piper / espeak-ng 兜底
- **Pi5 本地播放**
  - Web 页面只负责控制
  - 音频在 Pi5 侧通过 ALSA 播放
- **Pi5 本地录音**
  - Web 页面发起录音/停止
  - 录音文件保存在 Pi5 本地
- **历史记录归档**
  - 历史记录保留最新 **7 组**
  - 每组可能包含：`input_audio` / `output_audio` / `input_text` / `output_text`
  - 超出后按“组”自动删除最早记录
- **独立录音归档**
  - 录音菜单最多保留最新 **5** 组录音
- **浏览器控制台**
  - 可查看最近历史
  - 可下载历史工件
  - 可复用已有录音继续做语音类转换

---

## 目录结构

```text
api/                Flask 路由与页面模板
app/                模式注册、i18n、CLI
audio/              Pi5 录音/播放协调
config/             默认配置与环境变量覆盖
models/             ASR / MT / TTS 模型封装
pipeline/           各模式统一执行入口
scripts/            环境、模型、检查脚本
storage/            历史记录与录音存储管理
tests/              自动化测试
main.py             项目启动入口
```

---

## 环境要求

### 1）Windows 开发 / 测试

适合：
- UI/API 开发
- 单元测试 / 回归测试
- 不接 Pi5 音频硬件的日常开发

不适合：
- 真正的 ALSA 录音 / 播放验证

### 2）Linux / Raspberry Pi 运行

适合：
- 真机录音
- Pi5 本地播放
- 离线模型完整验证

建议环境：
- Raspberry Pi 5
- Raspberry Pi OS / Debian 系 Linux
- Python 3.11+
- 已安装 ALSA 相关依赖

---

## 安装

## Windows 开发环境

PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
pytest -q
```

或者：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_env.ps1
```

说明：
- `requirements-dev.txt` 不安装 Linux 专用的 `pyalsaaudio`
- 可用于绝大多数本地开发和测试

## Pi5 / Linux 运行环境

```bash
sudo apt update
sudo apt install -y build-essential python3-dev python3-venv python3-pip libasound2-dev espeak-ng ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-pi.txt
pytest -q
```

或者：

```bash
bash scripts/setup_env.sh
```

依赖文件说明：

- `requirements.txt`
  - 默认入口，目前指向开发依赖
- `requirements-dev.txt`
  - 跨平台开发 / 测试依赖
- `requirements-pi.txt`
  - Pi5 / Linux 运行依赖，包含 `pyalsaaudio`

---

## 模型准备

项目默认模型目录：

```text
models/data/
```

包括：
- Vosk 中文模型
- Vosk 英文模型
- Argos 中英翻译包
- Argos/Stanza 离线分句资源
- Piper 中文语音模型
- Piper 英文语音模型

### 下载离线模型

在有网络的 Linux 机器上执行：

```bash
bash scripts/download_models.sh
```

下载完成后，将整个 `models/data/` 拷贝到 Pi5。

### 检查 MT 运行时

```bash
python scripts/check_mt_runtime.py --source en --target zh
python scripts/check_mt_runtime.py --source zh --target en
```

这个脚本可用于检查：
- Argos 包是否正确安装
- 是否错误落回网络下载逻辑
- 当前语言对是否会使用外部分句器

---

## 启动

### 启动 Web 服务

```bash
python main.py
```

或：

```bash
python main.py --server
```

默认地址：

- `http://127.0.0.1:5000`
- 局域网访问地址由 `config/default.yaml` 中的 `api.host` / `api.port` 决定

### 启动 CLI 调试模式

```bash
python main.py --cli
```

---

## 配置

默认配置文件：

```text
config/default.yaml
```

重点配置项：

```yaml
audio:
  playback_device: "plughw:3,0"
  record_device: "plughw:3,0"
  max_record_duration: 180

storage:
  history_dir: "data/history"
  recordings_dir: "data/recordings"
  max_history: 7
  max_recordings: 5
```

支持环境变量覆盖，例如：

- `PI5_STORAGE_MAX_HISTORY`
- `PI5_STORAGE_MAX_RECORDINGS`
- `PI5_AUDIO_DEVICE`
- `PI5_AUDIO_PLAYBACK_DEVICE`
- `PI5_AUDIO_RECORD_DEVICE`
- `PI5_API_HOST`
- `PI5_API_PORT`

---

## 存储规则

### 历史记录

历史记录目录默认在：

```text
data/history/
```

当前结构包含：

- `record_XXX/`
  - 单组记录目录
  - 包含 `manifest.json` 和该组的工件文件
- `input_audio/`
- `output_audio/`
- `input_text/`
- `output_text/`
- `index.json`

规则：
- 只保留最新 **7 组**历史记录
- 删除按“组”进行，不按模式分别计数
- 超出上限时，最早的一整组会被删除
- 孤儿 `record_XXX` 目录也会在同步时自动收口清理

### 独立录音

录音目录默认在：

```text
data/recordings/
```

规则：
- 只保留最新 **5** 组录音
- 录音菜单与转译历史分开管理

---

## Web / API 概览

### 页面入口

- `GET /`
  - Web 控制台

### 基础接口

- `GET /api/bootstrap`
  - 前端初始化配置
- `GET /api/health`
  - 健康检查与启动自检结果

### 转换接口

- `POST /api/conversions/text`
  - 文字类模式转换
- `POST /api/conversions/speech`
  - 语音类模式转换

### 历史记录接口

- `GET /api/history/recent`
- `GET /api/history`
- `GET /api/history/<id>/artifacts/<artifact_kind>`
- `DELETE /api/history/<id>`
- `GET /api/history/export`

### 录音接口

- `GET /api/recordings`
- `POST /api/recordings`
- `GET /api/recordings/<id>/audio`
- `DELETE /api/recordings/<id>`
- `GET /api/recordings/export`

### Pi5 媒体控制接口

- `GET /api/pi5/media/state`
- `POST /api/pi5/media/stop`
- `GET /api/pi5/recordings/state`
- `POST /api/pi5/recordings/start`
- `POST /api/pi5/recordings/stop`

---

## 开发与测试

### 全量测试

```bash
pytest -q
```

### 常用定向测试

```bash
pytest tests/test_api.py -q
pytest tests/test_storage.py -q
pytest tests/test_pipeline.py -q
```

### 硬件相关脚本

```bash
python scripts/test_hardware_audio.py
python scripts/test_playback_loop.py
```

---

## 常见问题

### 1. Windows 上安装 `pyalsaaudio` 失败

这是预期行为。

请使用：

```bash
pip install -r requirements-dev.txt
```

不要在 Windows 开发环境中强装 Pi 运行依赖。

### 2. 跨语文字转语音报 `espeak-ng 命令未找到`

在 Pi5 / Linux 上安装：

```bash
sudo apt install -y espeak-ng
```

### 3. 第一次 MT 请求很慢，或者报缺离线资源

先执行：

```bash
bash scripts/download_models.sh
python scripts/check_mt_runtime.py --source zh --target en
python scripts/check_mt_runtime.py --source en --target zh
```

### 4. 浏览器页面能点，但没有声音

检查：
- 是否在 Pi5 本地播放，而不是浏览器播放
- ALSA 设备号是否正确
- `config/default.yaml` 中的 `playback_device` 是否匹配当前声卡
- `GET /api/pi5/media/state` 返回是否正常

---

## 当前约束

- 目前只支持 **中文 / 英文**
- Web 页面对语音模式是 **控制面**，不是浏览器本地音频处理面
- 真正的录音与播放以 **Pi5 本地设备** 为准
- 历史记录保留 **7 组**，录音保留 **5 组**

---

## 适合的使用方式

- 在 Windows 上开发前端、接口、存储逻辑和回归测试
- 在 Pi5 上做真实模型、录音、播放、端到端验证
- 把 `models/data/` 作为离线部署资产统一管理

---

## 许可证 / 说明

当前仓库未单独声明开源许可证；如需对外发布，请补充许可证、部署说明和模型来源说明。
