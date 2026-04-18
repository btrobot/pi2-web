---
name: release-checklist
description: "发布检查清单 - 发布前的质量验证"
argument-hint: "[版本号]"
user-invocable: true
allowed-tools: Read, Write, Glob, Grep, Bash
---

# Release Checklist Skill

发布检查清单，发布前的质量验证。

## 触发方式

```
/release-checklist
/release-checklist v1.0.0
/release-checklist 1.2.3
```

## 发布前检查

### 1. 功能完整性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 所有计划功能已实现 | ☐ | |
| 功能测试通过 | ☐ | |
| E2E 测试通过 | ☐ | |
| 手动测试完成 | ☐ | |

### 2. 代码质量

| 检查项 | 状态 | 说明 |
|--------|------|------|
| TypeScript 类型检查通过 | ☐ | `npm run typecheck` |
| Python 类型检查通过 | ☐ | `mypy .` |
| ESLint 检查通过 | ☐ | `npm run lint` |
| 无 `any` 类型 | ☐ | `grep -rn "any" frontend/` |
| 无硬编码密钥 | ☐ | `grep -rn "password\s*=" backend/` |

### 3. 安全检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 安全扫描通过 | ☐ | `/security-scan` |
| 无高危漏洞 | ☐ | |
| 敏感数据已加密 | ☐ | |
| 无 secrets 泄露 | ☐ | |

### 4. 测试覆盖

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 单元测试覆盖率 >= 80% | ☐ | |
| API 端点测试 100% | ☐ | |
| 前端组件测试 >= 70% | ☐ | |

### 5. 文档

| 检查项 | 状态 | 说明 |
|--------|------|------|
| CHANGELOG 已更新 | ☐ | |
| API 文档已更新 | ☐ | |
| 部署文档已更新 | ☐ | |
| 破坏性变更已说明 | ☐ | |

### 6. 部署准备

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 数据库迁移脚本准备好 | ☐ | |
| 环境变量配置正确 | ☐ | |
| 回滚方案已测试 | ☐ | |
| 监控告警已配置 | ☐ | |

## 执行步骤

### Step 1: 确认发布范围

```bash
# 查看自上次发布以来的变更
git log v1.0.0..HEAD --oneline
```

### Step 2: 运行检查

按顺序执行检查项：

```bash
# 1. 代码检查
cd frontend && npm run typecheck && npm run lint
cd ../backend && mypy .

# 2. 安全扫描
/security-scan

# 3. 测试
cd frontend && npm run test
cd ../backend && pytest

# 4. 构建
cd frontend && npm run build
```

### Step 3: 生成报告

```markdown
## 发布检查报告 - v1.0.0

**发布日期**: YYYY-MM-DD
**检查人**: [姓名]

### 检查结果

| 类别 | 通过 | 失败 | 跳过 |
|------|------|------|------|
| 功能 | 12 | 0 | 0 |
| 代码质量 | 8 | 0 | 0 |
| 安全 | 5 | 0 | 0 |
| 测试 | 10 | 0 | 0 |
| 文档 | 4 | 0 | 0 |
| 部署 | 3 | 0 | 0 |

### 发现的 Blockers
无

### 发现的 Warning
- [Warning 描述]

### 签署
- [ ] Tech Lead 批准
- [ ] QA Lead 批准
- [ ] 安全确认

### 结论
✅ 可以发布 / ❌ 阻塞发布
```

## 阻塞发布条件

以下任一条件满足则阻塞发布：

| 严重性 | 条件 |
|--------|------|
| S1 | 任何 S1 级别 Bug 未修复 |
| S2 | 超过 3 个 S2 级别 Bug 未修复 |
| 安全 | 任何高危安全漏洞 |
| 测试 | 测试覆盖率低于目标 |
| 质量 | TypeScript/ESLint 检查失败 |

## 发布后跟踪

```markdown
## 发布跟踪 - v1.0.0

**发布时间**: YYYY-MM-DD HH:mm
**部署环境**: [环境]

### 监控指标
- 错误率: [X%]
- 响应时间: [Xms]
- 活跃用户: [X]

### 问题报告
- [Issue 链接]

### 回滚记录
无 / [原因]
```

## 输出

更新 `production/session-state/active.md` 发布检查结果。
