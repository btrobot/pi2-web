---
name: architecture-review
description: "架构审查 - 审查技术架构决策"
argument-hint: "[系统名称]"
user-invocable: true
allowed-tools: Read, Write, Glob, Grep
---

# Architecture Review Skill

架构审查工作流，审查和批准技术架构决策。

## 触发方式

```
/architecture-review
/architecture-review AI剪辑系统
```

## 架构审查清单

### 1. 正确性

| 检查项 | 说明 |
|--------|------|
| 解决实际问题 | 架构是否真正解决问题 |
| 边界情况 | 是否处理了边界情况 |
| 数据一致性 | 数据流是否一致 |

### 2. 简单性

| 检查项 | 说明 |
|--------|------|
| 最简方案 | 是否是能做到的最简方案 |
| 过度设计 | 是否有不必要的复杂性 |
| 可删除性 | 设计是否便于删除/修改 |

### 3. 性能

| 检查项 | 说明 |
|--------|------|
| 延迟 | API 响应时间 |
| 吞吐量 | 并发处理能力 |
| 资源 | 内存、CPU、磁盘使用 |

### 4. 可维护性

| 检查项 | 说明 |
|--------|------|
| 可理解性 | 6 个月后能否理解 |
| 可测试性 | 能否有效测试 |
| 可修改性 | 修改是否容易出错 |

### 5. 安全性

| 检查项 | 说明 |
|--------|------|
| 数据保护 | 敏感数据是否加密 |
| 访问控制 | 是否有适当的权限控制 |
| 输入验证 | 所有输入是否验证 |

## 执行步骤

### Step 1: 收集架构文档

1. 读取 Tech Lead 提交的架构设计
2. 检查相关 ADR（Architecture Decision Records）
3. 理解设计背景和问题

### Step 2: 审查清单检查

按上述清单逐项检查。

### Step 3: 提出问题

```markdown
## 架构审查: [系统名称]

### 问题

#### Q1: [问题描述]
**位置**: [文件/模块]
**关注点**: 性能/安全/可维护性

[详细说明问题]

**建议**: [解决方案]
```

### Step 4: 做出决定

三种结论：

| 结论 | 说明 |
|------|------|
| ✅ Approved | 可以开始实现 |
| ⚠️ Approved with Changes | 需要小幅修改 |
| ❌ Rejected | 需要重新设计 |

### Step 5: 文档化决策

更新 ADR：

```markdown
## ADR-[N]: [标题]

**状态**: Accepted

**日期**: YYYY-MM-DD

**审查者**: Tech Lead

**审查意见**:
[审查决定和理由]
```

## 示例：AI 剪辑架构审查

```markdown
## 架构审查: AI 剪辑系统

**提交者**: Backend Lead
**日期**: 2024-01-15
**审查者**: Tech Lead

---

### 架构提案

### 系统结构
```
┌─────────────┐
│  前端        │ ← 用户交互
└──────┬──────┘
       │ HTTP
┌──────▼──────┐
│  AI Clip   │ ← AI 剪辑 API
│   Service   │
└──────┬──────┘
       │ subprocess
┌──────▼──────┐
│   FFmpeg    │ ← 视频处理
└─────────────┘
```

### 审查结果

#### ✅ 通过项

1. **使用 FFmpeg 子进程**
   - 简单直接
   - 易于调试
   - 无额外依赖

2. **异步实现**
   - 不阻塞 FastAPI
   - 支持并发

#### ⚠️ 需要改进

##### Q1: 高光检测算法硬编码

**问题**: 当前高光检测是简单的时间分段，逻辑写死在代码中。

**风险**:
- 未来难以优化
- 难以添加新的检测算法

**建议**:
```python
# 提取为策略模式
class HighlightDetector(Protocol):
    async def detect(self, video_path: str) -> List[ClipSegment]: ...

class SimpleDetector(HighlightDetector):
    ...

class AIDetector(HighlightDetector):
    ...

# 配置选择
detector = HighlightDetectors[config.detector_type]()
```

**决定**: Approved with Changes - 实现时使用策略模式

---

### 最终决定

✅ **Approved with Changes**

需要在实现时：
1. 提取高光检测为策略模式
2. 添加检测参数配置

---
```

## 输出

更新 `production/session-state/active.md`：

```markdown
## 决策日志

### [日期] AI 剪辑架构审查
- **状态**: Approved with Changes
- **决定**: 使用策略模式实现高光检测
- **行动**: Tech Lead 监督实现
```
