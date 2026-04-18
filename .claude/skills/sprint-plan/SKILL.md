---
name: sprint-plan
description: "Sprint 规划 - 创建和管理 Sprint 计划"
argument-hint: "[操作: new|status]"
user-invocable: true
allowed-tools: Read, Write, Glob, Grep
---

# Sprint Plan Skill

Sprint 规划工作流，用于创建和管理开发 Sprint。

## 触发方式

```
/sprint-plan
/sprint-plan new
/sprint-plan status
```

## Sprint 结构

```markdown
## Sprint [N] - [名称]
**周期**: YYYY-MM-DD ~ YYYY-MM-DD (2 周)

### 目标
- [目标 1]
- [目标 2]

### 任务
| ID | 任务 | 负责人 | 估计 | 依赖 | 状态 |
|----|------|--------|------|------|------|

### 容量
- 总估计: X 人天
- 缓冲: 20%
- 实际可用: X 人天

### 风险
| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
```

## 执行步骤

### Step 1: 理解上下文

1. 读取当前 `production/session-state/active.md`
2. 检查上一 Sprint 的完成情况
3. 了解下一里程碑的需求

### Step 2: 收集任务

从以下来源收集任务：
- 里程碑需求
- 未完成的任务
- 技术债务
- Bug 修复

### Step 3: 分解任务

每个任务必须：
- 可以在 1-3 天完成
- 有明确的验收标准
- 明确负责人
- 列出依赖关系

### Step 4: 评估容量

```
总开发时间 = 10 工作日
缓冲 20% = 2 天
可用容量 = 8 天
```

### Step 5: 分配任务

根据技能匹配分配任务：

| 任务类型 | 负责人 |
|----------|--------|
| UI 组件 | Frontend Lead |
| API 开发 | Backend Lead |
| 自动化 | Automation Developer (via Backend Lead) |
| 测试 | QA Lead |
| 基础设施 | DevOps Engineer |

## 示例 Sprint

```markdown
## Sprint 5 - AI 剪辑功能
**周期**: 2024-01-15 ~ 2024-01-26

### 目标
- 完成视频高光检测
- 完成智能剪辑功能
- 前端 AI 剪辑界面

### 任务
| ID | 任务 | 负责人 | 估计 | 依赖 | 状态 |
|----|------|--------|------|------|------|
| SP5-01 | FFmpeg 高光检测算法 | Automation Developer | 2d | - | [ ] |
| SP5-02 | 高光检测 API | Backend Lead | 1d | SP5-01 | [ ] |
| SP5-03 | AI 剪辑组件 | Frontend Lead | 2d | SP5-02 | [ ] |
| SP5-04 | 完整剪辑流程测试 | QA Lead | 1d | SP5-01 | [ ] |
| SP5-05 | 部署配置更新 | DevOps Engineer | 0.5d | - | [ ] |

### 容量
- 总估计: 6.5 人天
- 缓冲: 20%
- 实际可用: 8 人天 ✓

### 风险
| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| FFmpeg 依赖问题 | 低 | 中 | 备用方案：使用云转码 |
```

## 输出

更新 `production/session-state/active.md`：

```markdown
<!-- STATUS -->
Epic: AI 剪辑功能
Feature: 高光检测
Task: Sprint 5 规划
Owner: Tech Lead
<!-- /STATUS -->

## 当前 Sprint

### Sprint 5 (2024-01-15 ~ 2024-01-26)
[见上述 Sprint 定义]

## 进行中的任务
[任务列表]

## 最近完成
[完成的任务]
```

## 质量检查

在完成 Sprint 规划前，验证以下条件：

- [ ] Sprint 周期合理（推荐 2 周）
- [ ] 任务可分解到 1-3 天完成
- [ ] 所有任务有明确负责人
- [ ] 依赖关系已识别并记录
- [ ] 缓冲容量为 20%
- [ ] 风险已识别并有缓解策略
- [ ] 容量计算正确

## 下一步

Sprint 规划完成后：

1. **进度跟踪**: 运行 `/sprint-plan status` 查看 Sprint 进度
2. **任务分解**: 使用 `/task-breakdown` 分解复杂任务
3. **代码审查**: 调用 `/code-review` 审查关键代码
4. **安全扫描**: 对敏感功能运行 `/security-scan`
5. **架构审查**: 复杂功能调用 `/architecture-review`
