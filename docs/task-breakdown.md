# Pi5 离线双语语音交互系统 - 任务分解

> 版本: 1.0.0 | 日期: 2026-04-07
> 基于: `docs/requirements-spec.md` v1.0.0
> 状态: 待审批

---

## 任务编号规则

`T-{模块缩写}-{序号}`

| 缩写 | 模块 |
|------|------|
| HW | 硬件/音频 (hardware/, audio/) |
| ASR | 语音识别 (models/asr.py) |
| MT | 机器翻译 (models/mt.py) |
| TTS | 语音合成 (models/tts.py) |
| PIP | 管线 (pipeline/) |
| STR | 存储 (storage/) |
| API | 导出接口 (api/) |
| APP | 应用主控 (app/, main.py, config/) |
| INF | 基础设施 (scripts/, config/) |
| QA | 测试/验证 (tests/, benchmarks/) |

## 复杂度定义

| 等级 | 预估工作量 | 说明 |
|------|-----------|------|
| S | < 1 小时 | 简单配置、小文件 |
| M | 1-3 小时 | 单模块实现 |
| L | 3-6 小时 | 复杂模块或跨模块集成 |

---

## 模块 1: 基础设施

### T-INF-01: 项目骨架和目录结构初始化

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | S |
| 依赖 | 无 |
| 产出 | 完整目录结构、`__init__.py`、`.gitignore`、`requirements.txt` |

- 按 CLAUDE.md 定义的目录结构创建所有目录和空模块文件
- 创建 `requirements.txt` (vosk, argostranslate, piper-tts, pyalsaaudio, flask)
- 创建 `config/default.yaml` 配置模板 (模型路径、音频参数、存储路径、Flask 端口)

### T-INF-02: 模型下载脚本

| 属性 | 值 |
|------|-----|
| 负责 | ML Engineer |
| 复杂度 | M |
| 依赖 | T-INF-01 |
| 产出 | `scripts/download_models.sh` |

- 编写脚本下载 Vosk 中英模型、Argos 中英语言对、piper-tts 中英语音包
- 下载到 `models/data/` 目录
- 包含校验逻辑 (文件存在则跳过)
- 输出模型文件大小和总占用

### T-INF-03: 环境安装脚本

| 属性 | 值 |
|------|-----|
| 负责 | Embedded Engineer |
| 复杂度 | M |
| 依赖 | T-INF-01 |
| 产出 | `scripts/setup_env.sh` |

- 安装系统级依赖 (espeak-ng, libasound2-dev, python3-dev 等)
- 安装 Python 依赖
- 配置 ALSA 默认声卡
- 加载 ReSpeaker 设备树覆盖

---

## 模块 2: 硬件/音频层

### T-HW-01: USB 麦克风音频配置

| 属性 | 值 |
|------|-----|
| 负责 | Embedded Engineer |
| 复杂度 | S |
| 依赖 | T-INF-03 |
| 产出 | `hardware/asound.conf`、验证脚本 |

- 配置 ALSA 使用 USB 麦克风作为默认输入设备
- 编写 `hardware/asound.conf` (默认声卡、采样率、通道)
- 验证 `arecord -l` 和 `aplay -l` 可见设备
- 录制 5 秒测试音频并回放验证

### T-HW-02: 音频采集模块

| 属性 | 值 |
|------|-----|
| 负责 | Embedded Engineer |
| 复杂度 | M |
| 依赖 | T-HW-01 |
| 产出 | `audio/capture.py` |

- 使用 pyalsaaudio 实现麦克风录音
- 参数: 16kHz, 16-bit, Mono
- 设备名通过配置文件指定（便于后续切换 ReSpeaker）
- 支持指定最大时长 (默认 180 秒)
- 支持手动停止 (线程安全的 stop flag)
- 输出 WAV 文件到指定路径
- 异常处理: 设备不可用时抛出明确错误

### T-HW-03: 音频播放模块

| 属性 | 值 |
|------|-----|
| 负责 | Embedded Engineer |
| 复杂度 | S |
| 依赖 | T-HW-01 |
| 产出 | `audio/playback.py` |

- 使用 subprocess 调用 `aplay` 播放 WAV 文件
- 支持阻塞和非阻塞模式
- 异常处理: 文件不存在、设备忙

### T-HW-04: 音频模块统一接口

| 属性 | 值 |
|------|-----|
| 负责 | Embedded Engineer |
| 复杂度 | S |
| 依赖 | T-HW-02, T-HW-03 |
| 产出 | `audio/__init__.py` |

- 导出 `record(max_duration, output_path)` 和 `play(audio_path)` 两个公共函数
- 类型注解完整
- 统一异常类型 `AudioError`

### T-HW-05: ReSpeaker HAT V2 驱动适配 (可选优化)

| 属性 | 值 |
|------|-----|
| 负责 | Embedded Engineer |
| 复杂度 | L |
| 依赖 | T-HW-04 |
| 产出 | `hardware/setup_respeaker.sh` |

- 编译安装 seeed-2mic-voicecard 驱动
- 配置 `/boot/config.txt` 加载 dtoverlay
- 更新 ALSA 配置切换到 ReSpeaker 声卡
- 验证音频采集/播放模块无需代码改动即可工作（仅改配置）
- 此任务不阻塞主流程，可在 Sprint 3/4 执行

---

## 模块 3: ASR (语音识别)

### T-ASR-01: Vosk ASR 引擎封装

| 属性 | 值 |
|------|-----|
| 负责 | ML Engineer |
| 复杂度 | M |
| 依赖 | T-INF-02 |
| 产出 | `models/asr.py` |

- 加载 Vosk 中文模型 (vosk-model-small-cn) 和英文模型 (vosk-model-small-en)
- 接口: `recognize(audio_path: str, lang: str) -> str`
- 支持 16kHz Mono WAV 输入
- 模型按需加载 (首次调用时加载，后续复用)
- 异常: `ASRError`
- 记录识别耗时日志

### T-ASR-02: ASR 准确率基准测试

| 属性 | 值 |
|------|-----|
| 负责 | QA Lead |
| 复杂度 | M |
| 依赖 | T-ASR-01, T-HW-02 |
| 产出 | `benchmarks/asr_benchmark.py` |

- 准备中英文测试音频样本 (5-10 句)
- 测量识别准确率 (目标 >= 80%)
- 测量单句识别延迟 (目标 < 5 秒)
- 输出基准报告

---

## 模块 4: MT (机器翻译)

### T-MT-01: Argos Translate 引擎封装

| 属性 | 值 |
|------|-----|
| 负责 | ML Engineer |
| 复杂度 | M |
| 依赖 | T-INF-02 |
| 产出 | `models/mt.py` |

- 加载 Argos 中英/英中翻译模型
- 接口: `translate(text: str, source_lang: str, target_lang: str) -> str`
- 模型按需加载
- 异常: `TranslationError`
- 记录翻译耗时日志

### T-MT-02: MT 翻译质量基准测试

| 属性 | 值 |
|------|-----|
| 负责 | QA Lead |
| 复杂度 | M |
| 依赖 | T-MT-01 |
| 产出 | `benchmarks/mt_benchmark.py` |

- 准备中英文测试句对 (10-20 句日常用语)
- 测量翻译延迟 (目标 < 3 秒)
- 人工评估翻译质量 (语义正确性)
- 输出基准报告

---

## 模块 5: TTS (语音合成)

### T-TTS-01: piper-tts 引擎封装

| 属性 | 值 |
|------|-----|
| 负责 | ML Engineer |
| 复杂度 | M |
| 依赖 | T-INF-02 |
| 产出 | `models/tts.py` |

- 加载 piper-tts 中文和英文语音包
- 接口: `synthesize(text: str, lang: str, output_path: str) -> str`
- 输出 16kHz, 16-bit, Mono WAV
- 模型按需加载
- 异常: `TTSError`
- 记录合成耗时日志

### T-TTS-02: TTS 语音质量基准测试

| 属性 | 值 |
|------|-----|
| 负责 | QA Lead |
| 复杂度 | S |
| 依赖 | T-TTS-01 |
| 产出 | `benchmarks/tts_benchmark.py` |

- 测试中英文各 5 句
- 测量合成延迟 (目标 < 3 秒)
- 人工评估语音自然度
- 输出基准报告

---

## 模块 6: Pipeline (处理管线)

### T-PIP-01: 单模块管线 (FR-01, FR-02)

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | M |
| 依赖 | T-ASR-01, T-TTS-01, T-HW-04 |
| 产出 | `pipeline/single.py` |

- FR-01 管线: 文本 -> TTS -> 播放
- FR-02 管线: 录音 -> ASR -> 返回文本
- 每个管线函数接收输入，返回结果，自动保存历史记录
- 统一错误处理和日志

### T-PIP-02: 组合管线 (FR-03, FR-04)

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | M |
| 依赖 | T-PIP-01, T-MT-01 |
| 产出 | `pipeline/composite.py` |

- FR-03 管线: 文本 -> MT -> TTS -> 播放
- FR-04 管线: 录音 -> ASR -> MT -> 返回文本
- 端到端延迟监控 (目标 < 8 秒)
- 中间步骤失败时返回已完成部分 + 错误信息

### T-PIP-03: 管线统一入口

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | S |
| 依赖 | T-PIP-01, T-PIP-02 |
| 产出 | `pipeline/__init__.py` |

- 导出统一调度函数 `run_pipeline(mode: str, **kwargs)`
- mode 枚举: `tts`, `asr`, `mt_tts`, `asr_mt`
- 自动调用对应管线并保存历史记录

---

## 模块 7: Storage (存储管理)

### T-STR-01: 历史记录管理

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | M |
| 依赖 | T-INF-01 |
| 产出 | `storage/history.py` |

- 实现 `data/history/metadata.json` 的 CRUD
- FIFO 淘汰: 超过 5 条时删除最早记录及其音频文件
- 接口: `add_record()`, `list_records()`, `get_record(id)`, `export_all()`
- 文件命名: 递增编号
- 元数据与音频文件一致性保证

### T-STR-02: 录音文件管理

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | M |
| 依赖 | T-INF-01 |
| 产出 | `storage/recordings.py` |

- 实现 `data/recordings/metadata.json` 的 CRUD
- FIFO 淘汰: 超过 5 个时删除最早录音
- 接口: `save_recording()`, `list_recordings()`, `get_recording(id)`, `export_all()`
- 记录文件大小和时长

### T-STR-03: 存储模块统一接口

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | S |
| 依赖 | T-STR-01, T-STR-02 |
| 产出 | `storage/__init__.py` |

- 导出 HistoryManager 和 RecordingManager
- 初始化时创建 data/ 目录结构
- 磁盘空间检查 (< 500MB 运行时数据)

---

## 模块 8: API (Flask 导出接口)

### T-API-01: Flask 应用和健康检查

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | S |
| 依赖 | T-INF-01 |
| 产出 | `api/app.py` |

- 创建 Flask app 实例
- `GET /api/health` 返回系统状态 (模型加载状态、磁盘空间、运行时长)
- 绑定 `0.0.0.0` 局域网可访问
- 无认证 (局域网信任)

### T-API-02: 历史记录导出接口

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | M |
| 依赖 | T-STR-01, T-API-01 |
| 产出 | `api/history_routes.py` |

- `GET /api/history` — 返回历史记录列表 JSON
- `GET /api/history/<id>/audio` — 下载指定音频文件
- `GET /api/history/export` — 打包下载所有历史记录 (ZIP: 音频 + metadata)
- 输入验证: id 范围检查
- 错误处理: 404 记录不存在

### T-API-03: 录音导出接口

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | M |
| 依赖 | T-STR-02, T-API-01 |
| 产出 | `api/recording_routes.py` |

- `GET /api/recordings` — 返回录音列表 JSON
- `GET /api/recordings/<id>/audio` — 下载指定录音文件
- `GET /api/recordings/export` — 打包下载所有录音 (ZIP)
- 输入验证和错误处理同上

---

## 模块 9: 应用主控

### T-APP-01: 配置管理模块

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | S |
| 依赖 | T-INF-01 |
| 产出 | `config/settings.py` |

- 从 `config/default.yaml` 加载配置
- 配置项: 模型路径、音频参数、存储路径、Flask 端口、日志级别
- 提供全局 `get_config()` 函数

### T-APP-02: 命令行交互入口

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | M |
| 依赖 | T-PIP-03, T-STR-03, T-APP-01 |
| 产出 | `main.py`, `app/cli.py` |

- 命令行菜单: 选择功能模式 (FR-01 ~ FR-06)
- FR-01: 输入文本 -> TTS 播放
- FR-02: 开始录音 -> ASR 识别 -> 显示文本
- FR-03: 输入文本 -> MT + TTS 播放
- FR-04: 开始录音 -> ASR + MT -> 显示翻译
- FR-05: 查看/导出历史记录
- FR-06: 纯录音模式
- 启动时加载模型，显示加载进度

### T-APP-03: 简单 Web UI

| 属性 | 值 |
|------|-----|
| 负责 | Python Developer |
| 复杂度 | L |
| 依赖 | T-API-02, T-API-03, T-PIP-03 |
| 产出 | `api/templates/index.html`, `api/static/` |

- 单页面 HTML + JS (无前端框架)
- 功能按钮: 4 种翻译模式 + 录音
- 历史记录列表和下载
- 录音列表和下载
- 系统状态显示
- 响应式布局，支持手机浏览器访问

---

## 模块 10: 测试与验证

### T-QA-01: 单元测试框架搭建

| 属性 | 值 |
|------|-----|
| 负责 | QA Lead |
| 复杂度 | S |
| 依赖 | T-INF-01 |
| 产出 | `tests/conftest.py`, `tests/__init__.py` |

- pytest 配置
- 通用 fixture: 临时音频文件、临时存储目录、mock 配置
- 测试数据目录 `tests/data/`

### T-QA-02: 存储模块单元测试

| 属性 | 值 |
|------|-----|
| 负责 | QA Lead |
| 复杂度 | M |
| 依赖 | T-STR-03, T-QA-01 |
| 产出 | `tests/test_storage.py` |

- 历史记录 CRUD 测试
- FIFO 淘汰测试 (第 6 条记录添加后验证最早记录被删除)
- 录音管理 CRUD 测试
- 录音 FIFO 淘汰测试
- 元数据与文件一致性测试

### T-QA-03: API 接口测试

| 属性 | 值 |
|------|-----|
| 负责 | QA Lead |
| 复杂度 | M |
| 依赖 | T-API-02, T-API-03, T-QA-01 |
| 产出 | `tests/test_api.py` |

- Flask test client 测试所有 7 个端点
- 正常响应和错误响应
- ZIP 导出文件完整性
- 并发请求测试

### T-QA-04: 管线集成测试

| 属性 | 值 |
|------|-----|
| 负责 | QA Lead |
| 复杂度 | L |
| 依赖 | T-PIP-03, T-QA-01 |
| 产出 | `tests/test_pipeline.py` |

- FR-01 ~ FR-04 端到端测试 (使用预录音频)
- 延迟测量 (各管线是否满足 NFR-02)
- 错误传播测试 (ASR 失败时管线行为)
- 历史记录自动保存验证

### T-QA-05: 系统集成测试 (Pi5 实机)

| 属性 | 值 |
|------|-----|
| 负责 | QA Lead |
| 复杂度 | L |
| 依赖 | T-APP-02, T-APP-03 |
| 产出 | `tests/test_system.py`, 测试报告 |

- Pi5 实机上运行全部功能
- 连续运行 1 小时稳定性测试 (NFR-04)
- 内存占用监控 (目标 < 4GB)
- 模型总内存 < 2GB 验证
- CPU 空闲时 < 10% 验证
- 导出接口局域网访问测试

---

## 依赖关系总览

```
T-INF-01 (项目骨架)
  ├── T-INF-02 (模型下载) ──> T-ASR-01, T-MT-01, T-TTS-01
  ├── T-INF-03 (环境安装) ──> T-HW-01 (USB 音频配置)
  ├── T-STR-01, T-STR-02 (存储)
  ├── T-API-01 (Flask)
  ├── T-APP-01 (配置)
  └── T-QA-01 (测试框架)

T-HW-01 (USB 音频配置, S)
  ├── T-HW-02 (采集) ─┐
  └── T-HW-03 (播放) ─┴── T-HW-04 (音频接口) ──> T-HW-05 (ReSpeaker 适配, 可选)

T-ASR-01 ─┐
T-TTS-01 ─┼── T-PIP-01 (单模块管线)
T-HW-04 ──┘       │
T-MT-01 ───────────┴── T-PIP-02 (组合管线) ──> T-PIP-03 (管线入口)

T-STR-01 ──> T-STR-03 ──> T-API-02
T-STR-02 ──> T-STR-03 ──> T-API-03

T-PIP-03 + T-STR-03 + T-APP-01 ──> T-APP-02 (CLI)
T-API-02 + T-API-03 + T-PIP-03 ──> T-APP-03 (Web UI)

T-APP-02 + T-APP-03 ──> T-QA-05 (系统测试)
```

---

## 任务统计

| 负责 Agent | 任务数 | S | M | L |
|-----------|--------|---|---|---|
| Embedded Engineer | 6 | 3 | 2 | 1 |
| ML Engineer | 4 | 0 | 4 | 0 |
| Python Developer | 12 | 4 | 7 | 1 |
| QA Lead | 7 | 1 | 4 | 2 |
| **合计** | **29** | **8** | **17** | **4** |
