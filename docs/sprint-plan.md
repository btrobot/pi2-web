# Pi5 离线双语语音交互系统 - Sprint 计划

> 版本: 1.0.0 | 日期: 2026-04-07
> 基于: `docs/task-breakdown.md` v1.0.0
> 状态: 待审批

---

## Sprint 概览

| Sprint | 名称 | 目标 | 周期 |
|--------|------|------|------|
| Sprint 1 | 地基 | 项目骨架 + USB 音频 + 模型封装 | 第 1 周 |
| Sprint 2 | 核心管线 | 4 条管线跑通 + 存储模块 | 第 2 周 |
| Sprint 3 | 接口与交互 | API 导出 + CLI + Web UI | 第 3 周 |
| Sprint 4 | 验收 | 系统集成测试 + 性能调优 + 缺陷修复 | 第 4 周 |

---

## Sprint 1: 地基

> 目标: 所有底层模块独立可用，为管线集成做好准备

### 任务分配

| 任务 | 负责 | 依赖 | 复杂度 |
|------|------|------|--------|
| T-INF-01 项目骨架 | Python Developer | 无 | S |
| T-APP-01 配置管理 | Python Developer | T-INF-01 | S |
| T-QA-01 测试框架 | QA Lead | T-INF-01 | S |
| T-INF-03 环境安装脚本 | Embedded Engineer | T-INF-01 | M |
| T-INF-02 模型下载脚本 | ML Engineer | T-INF-01 | M |
| T-HW-01 USB 音频配置 | Embedded Engineer | T-INF-03 | S |
| T-HW-02 音频采集 | Embedded Engineer | T-HW-01 | M |
| T-HW-03 音频播放 | Embedded Engineer | T-HW-01 | S |
| T-HW-04 音频统一接口 | Embedded Engineer | T-HW-02, T-HW-03 | S |
| T-ASR-01 Vosk 封装 | ML Engineer | T-INF-02 | M |
| T-MT-01 Argos 封装 | ML Engineer | T-INF-02 | M |
| T-TTS-01 piper-tts 封装 | ML Engineer | T-INF-02 | M |

### 并行执行计划

```
第 1 天:
  Python Developer  → T-INF-01 (骨架)
  
第 1-2 天 (T-INF-01 完成后并行启动):
  Python Developer  → T-APP-01 (配置)
  QA Lead           → T-QA-01 (测试框架)
  Embedded Engineer → T-INF-03 (环境脚本) → T-HW-01 (USB 音频配置, 快速完成)
  ML Engineer       → T-INF-02 (模型下载)

第 2-4 天 (各自前置完成后):
  Embedded Engineer → T-HW-02 + T-HW-03 → T-HW-04 (音频链路全通)
  ML Engineer       → T-ASR-01, T-MT-01, T-TTS-01 (三个模型封装可并行)
```

### 里程碑 M1: 底层模块就绪

验收标准:
- [ ] USB 麦克风通过 `arecord -l` 可见
- [ ] `audio.record()` 可录制 WAV 文件，`audio.play()` 可播放
- [ ] `asr.recognize()` 可识别中英文音频并返回文本
- [ ] `mt.translate()` 可完成中英互译
- [ ] `tts.synthesize()` 可生成中英文语音 WAV
- [ ] 所有模型总内存占用 < 2GB (通过 `htop` 验证)

---

## Sprint 2: 核心管线

> 目标: 4 条翻译管线端到端跑通，存储模块完成，基准测试通过

### 任务分配

| 任务 | 负责 | 依赖 | 复杂度 |
|------|------|------|--------|
| T-STR-01 历史记录管理 | Python Developer | T-INF-01 | M |
| T-STR-02 录音文件管理 | Python Developer | T-INF-01 | M |
| T-STR-03 存储统一接口 | Python Developer | T-STR-01, T-STR-02 | S |
| T-PIP-01 单模块管线 | Python Developer | T-ASR-01, T-TTS-01, T-HW-04 | M |
| T-PIP-02 组合管线 | Python Developer | T-PIP-01, T-MT-01 | M |
| T-PIP-03 管线统一入口 | Python Developer | T-PIP-01, T-PIP-02 | S |
| T-ASR-02 ASR 基准测试 | QA Lead | T-ASR-01, T-HW-02 | M |
| T-MT-02 MT 基准测试 | QA Lead | T-MT-01 | M |
| T-TTS-02 TTS 基准测试 | QA Lead | T-TTS-01 | S |
| T-QA-02 存储单元测试 | QA Lead | T-STR-03, T-QA-01 | M |

### 并行执行计划

```
第 1-2 天 (Sprint 2 开始即并行):
  Python Developer  → T-STR-01 + T-STR-02 → T-STR-03
  QA Lead           → T-ASR-02, T-MT-02, T-TTS-02 (三个基准测试并行)

第 3-4 天:
  Python Developer  → T-PIP-01 → T-PIP-02 → T-PIP-03
  QA Lead           → T-QA-02 (存储测试)

第 5 天:
  集成验证: Tech Lead 协调管线 + 存储联调
```

### 里程碑 M2: 核心功能可用

验收标准:
- [ ] FR-01: 输入中文文本，3 秒内开始播放中文语音
- [ ] FR-02: 录制英文语音，5 秒内返回识别文本，准确率 >= 80%
- [ ] FR-03: 输入中文文本，8 秒内播放英文语音
- [ ] FR-04: 录制英文语音，8 秒内返回中文翻译
- [ ] 历史记录自动保存，FIFO 淘汰正确 (第 6 条添加后仅剩 5 条)
- [ ] 录音 FIFO 淘汰正确
- [ ] ASR 基准: 准确率 >= 80%, 延迟 < 5s
- [ ] MT 基准: 延迟 < 3s
- [ ] TTS 基准: 延迟 < 3s

### 风险检查点

Sprint 2 结束时评估以下风险，如触发则启动缓解措施:

| 风险 | 触发条件 | 缓解措施 |
|------|---------|---------|
| ASR 准确率不足 | 中文或英文 < 80% | 切换 Whisper-tiny 备选方案 |
| 端到端延迟超标 | FR-03/04 > 8s | 模型预加载优化；评估更小模型 |
| 内存超限 | 模型总占用 > 2GB | 按需加载/卸载模型 (不同时驻留) |

---

## Sprint 3: 接口与交互

> 目标: 导出 API 完成，CLI 和 Web UI 可用，接口测试通过

### 任务分配

| 任务 | 负责 | 依赖 | 复杂度 |
|------|------|------|--------|
| T-API-01 Flask 应用 | Python Developer | T-INF-01 | S |
| T-API-02 历史记录接口 | Python Developer | T-STR-01, T-API-01 | M |
| T-API-03 录音导出接口 | Python Developer | T-STR-02, T-API-01 | M |
| T-APP-02 命令行入口 | Python Developer | T-PIP-03, T-STR-03, T-APP-01 | M |
| T-APP-03 简单 Web UI | Python Developer | T-API-02, T-API-03, T-PIP-03 | L |
| T-QA-03 API 接口测试 | QA Lead | T-API-02, T-API-03, T-QA-01 | M |
| T-QA-04 管线集成测试 | QA Lead | T-PIP-03, T-QA-01 | L |

### 并行执行计划

```
第 1-2 天:
  Python Developer  → T-API-01 → T-API-02 + T-API-03 (并行)
  QA Lead           → T-QA-04 (管线集成测试，使用预录音频)

第 3-4 天:
  Python Developer  → T-APP-02 (CLI)
  QA Lead           → T-QA-03 (API 测试)

第 5 天:
  Python Developer  → T-APP-03 (Web UI)
  QA Lead           → 补充测试用例，回归测试
```

### 里程碑 M3: 用户可交互

验收标准:
- [ ] CLI 菜单可选择 6 种功能模式，各模式正常工作
- [ ] Web UI 可通过局域网浏览器访问 (http://<pi-ip>:5000)
- [ ] `GET /api/health` 返回正确状态
- [ ] `GET /api/history` 返回历史记录 JSON
- [ ] `GET /api/history/export` 下载 ZIP 文件完整
- [ ] `GET /api/recordings` 返回录音列表 JSON
- [ ] `GET /api/recordings/export` 下载 ZIP 文件完整
- [ ] 7 个 API 端点测试全部通过
- [ ] 管线集成测试通过 (FR-01 ~ FR-04 端到端)

---

## Sprint 4: 验收

> 目标: Pi5 实机系统测试通过，性能达标，缺陷清零

### 任务分配

| 任务 | 负责 | 依赖 | 复杂度 |
|------|------|------|--------|
| T-QA-05 系统集成测试 | QA Lead | T-APP-02, T-APP-03 | L |
| T-HW-05 ReSpeaker 适配 (可选) | Embedded Engineer | T-HW-04 | L |
| 缺陷修复 | 对应 Agent | T-QA-05 发现的问题 | 视情况 |
| 性能调优 | ML Engineer + Embedded Engineer | T-QA-05 性能数据 | 视情况 |

### 执行计划

```
第 1-2 天:
  QA Lead → T-QA-05 系统集成测试 (Pi5 实机)
  - 全功能验证
  - 1 小时连续运行稳定性测试
  - 内存/CPU 监控
  - 局域网导出测试

第 3-4 天:
  根据 T-QA-05 结果:
  - ML Engineer → 模型性能调优 (如延迟超标)
  - Embedded Engineer → 音频问题修复 (如驱动不稳定)
  - Python Developer → 应用层缺陷修复
  - QA Lead → 回归测试

第 5 天:
  QA Lead → 最终验收测试
  Tech Lead → 验收报告
```

### 里程碑 M4: 系统交付

验收标准:
- [ ] 全部 6 项功能需求 (FR-01 ~ FR-06) 通过验收
- [ ] NFR-01: 断网环境下所有功能正常
- [ ] NFR-02: TTS < 3s, ASR < 5s, MT < 3s, 端到端 < 8s
- [ ] NFR-03: 模型内存 < 2GB, 系统总内存 < 4GB, 磁盘 < 2GB
- [ ] NFR-04: 连续运行 1 小时无崩溃
- [ ] NFR-05: 配置外部化，日志完整
- [ ] 零 P0/P1 缺陷
- [ ] 系统启动时间 < 30 秒

---

## Agent 工作量分布

| Agent | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 | 总任务 |
|-------|----------|----------|----------|----------|--------|
| Embedded Engineer | 5 任务 | - | - | T-HW-05 + 按需修复 | 6 |
| ML Engineer | 4 任务 | - | - | 按需调优 | 4 |
| Python Developer | 2 任务 | 6 任务 | 5 任务 | 按需修复 | 13 |
| QA Lead | 1 任务 | 4 任务 | 2 任务 | 1 任务 | 8 |

说明:
- Embedded Engineer 和 ML Engineer 的工作集中在 Sprint 1，Sprint 2 起进入支持角色
- Python Developer 是主力，贯穿 Sprint 1-3
- QA Lead 从 Sprint 2 开始持续介入，Sprint 4 主导验收

---

## 关键路径

```
T-INF-01 → T-INF-03 → T-HW-01 (USB, S) → T-HW-02 → T-HW-04 → T-PIP-01 → T-PIP-02 → T-PIP-03 → T-APP-02 → T-QA-05
                                                                       ↑
T-INF-01 → T-INF-02 → T-ASR-01 ───────────────────────────────────────┘
                     → T-MT-01 ────────────────────────────────→ T-PIP-02
                     → T-TTS-01 ───────────────────────────────→ T-PIP-01
```

关键路径上的瓶颈:
1. T-HW-01 已降级为 USB 音频配置 (S)，不再是瓶颈
2. T-PIP-02 (组合管线) — 依赖所有模型模块和音频模块，是实际瓶颈
3. T-QA-05 (系统测试) — 必须在 Pi5 实机上执行

缓解: USB 麦克风先行，ReSpeaker 驱动 (T-HW-05) 后置为可选优化任务，不阻塞主流程。Sprint 1 中 Embedded Engineer 和 ML Engineer 完全并行推进。
