---
name: task-breakdown
description: "任务分解 - 将功能分解为可执行的开发任务"
argument-hint: "[功能名称或描述]"
user-invocable: true
allowed-tools: Read, Write, Glob, Grep
---

# Task Breakdown Skill

任务分解工作流，将功能需求分解为可执行的开发任务。

## 触发方式

```
/task-breakdown
/task-breakdown AI 剪辑
/task-breakdown 多账号管理
```

## 执行步骤

### Step 1: 理解功能

1. 阅读功能需求文档
2. 识别核心用例
3. 识别用户交互流程

### Step 2: 识别参与者

确定需要哪些域参与：

| 功能类型 | 参与者 |
|----------|--------|
| UI 为主 | Frontend Lead |
| API 为主 | Backend Lead |
| 自动化 | Backend Lead, Automation Developer |
| 端到端 | 所有 Lead |

### Step 3: 分解任务

按层次分解：

```
功能
 └── Epic
      └── Feature
           └── User Story
                └── Task (开发任务)
```

### Step 4: 定义任务

每个任务包含：

```markdown
### [ID] 任务名称

**描述**: [具体做什么]

**验收标准**:
- [ ] 标准 1
- [ ] 标准 2

**估计**: Xd

**负责人**: [Agent]

**依赖**:
- [依赖任务 ID]

**类型**: frontend | backend | both

**测试需求**:
- [ ] 单元测试
- [ ] 集成测试
- [ ] E2E 测试
```

## 示例：AI 剪辑功能分解

```markdown
# AI 剪辑功能任务分解

## 功能概述
用户选择视频，系统自动检测高光片段，用户确认后剪辑生成最终视频。

## 任务分解

### 前端任务

#### FE-AICLIP-01: AI 剪辑页面布局

**描述**: 创建 AI 剪辑主页面布局

**验收标准**:
- [ ] 左侧：视频信息展示 + 高光片段列表
- [ ] 右侧：剪辑选项 + 操作按钮
- [ ] 响应式布局

**估计**: 1d
**负责人**: Frontend Lead
**类型**: frontend

---

#### FE-AICLIP-02: 高光片段列表组件

**描述**: 显示检测到的高光片段，支持删除、调整

**验收标准**:
- [ ] 显示开始/结束时间
- [ ] 显示时长
- [ ] 支持拖拽调整
- [ ] 支持删除片段
- [ ] 显示总时长

**依赖**: FE-AICLIP-01, BE-AICLIP-02
**估计**: 1d
**负责人**: Frontend Lead
**类型**: frontend

---

### 后端任务

#### BE-AICLIP-01: 视频信息 API

**描述**: 实现获取视频信息的 API

**验收标准**:
- [ ] GET /api/ai/video-info
- [ ] 返回时长、分辨率、帧率等信息
- [ ] 输入验证

**估计**: 0.5d
**负责人**: Backend Lead
**类型**: backend

---

#### BE-AICLIP-02: 高光检测 API

**描述**: 实现高光片段检测 API

**验收标准**:
- [ ] GET /api/ai/detect-highlights
- [ ] 返回高光片段列表
- [ ] 支持自定义检测参数

**依赖**: -
**估计**: 2d
**负责人**: Automation Developer
**类型**: backend

---

#### BE-AICLIP-03: 智能剪辑 API

**描述**: 实现基于片段的视频剪辑 API

**验收标准**:
- [ ] POST /api/ai/smart-clip
- [ ] 支持多片段合并
- [ ] 返回输出路径

**依赖**: BE-AICLIP-02
**估计**: 1d
**负责人**: Automation Developer
**类型**: backend

---

### 集成任务

#### INT-AICLIP-01: API 类型定义

**描述**: Frontend 和 Backend 协调 API 类型

**验收标准**:
- [ ] 定义请求/响应 TypeScript 类型
- [ ] 定义 Pydantic Schema
- [ ] 双方确认

**依赖**: BE-AICLIP-01, BE-AICLIP-02
**估计**: 0.5d
**负责人**: Frontend Lead + Backend Lead
**类型**: both

---

### 测试任务

#### TEST-AICLIP-01: AI 剪辑测试

**描述**: 编写 AI 剪辑功能测试

**验收标准**:
- [ ] 单元测试覆盖率 > 80%
- [ ] API 集成测试
- [ ] E2E 完整流程测试

**依赖**: BE-AICLIP-01, BE-AICLIP-02, BE-AICLIP-03
**估计**: 1d
**负责人**: QA Lead
**类型**: both

---

## 任务汇总

| ID | 任务 | 负责人 | 估计 | 依赖 | 类型 |
|----|------|--------|------|------|------|
| FE-AICLIP-01 | AI 剪辑页面布局 | UI Dev | 1d | - | FE |
| FE-AICLIP-02 | 高光片段列表 | UI Dev | 1d | FE-01, BE-02 | FE |
| BE-AICLIP-01 | 视频信息 API | API Dev | 0.5d | - | BE |
| BE-AICLIP-02 | 高光检测 API | Auto Dev | 2d | - | BE |
| BE-AICLIP-03 | 智能剪辑 API | Auto Dev | 1d | BE-02 | BE |
| INT-AICLIP-01 | API 类型定义 | Lead | 0.5d | BE-01, BE-02 | both |
| TEST-AICLIP-01 | AI 剪辑测试 | Test Eng | 1d | BE-01~03 | both |

**总计**: 7d
**缓冲后**: 8.5d (~9d)
```

## 输出

更新 `production/session-state/active.md` 任务分解结果。
