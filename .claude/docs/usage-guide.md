# 多 Agent 协作框架使用指南

本文档通过真实的软件开发场景，演示如何使用 DewuGoJin 的多 Agent 协作框架。

---

## 目录

1. [快速参考](#快速参考)
2. [场景 1：新功能开发（完整生命周期）](#场景-1新功能开发)
3. [场景 2：Bug 修复](#场景-2bug-修复)
4. [场景 3：API 设计（跨域协作）](#场景-3api-设计跨域协作)
5. [场景 4：代码审查](#场景-4代码审查)
6. [场景 5：安全审计](#场景-5安全审计)
7. [场景 6：Sprint 规划与任务分解](#场景-6sprint-规划与任务分解)
8. [场景 7：发布前检查](#场景-7发布前检查)
9. [场景 8：紧急 Hotfix](#场景-8紧急-hotfix)
10. [场景 9：重构](#场景-9重构)
11. [场景 10：新人入场探索代码](#场景-10新人入场探索代码)
12. [反模式与常见错误](#反模式与常见错误)

---

## 快速参考

### Agent 一览

| Agent | Model | 何时调用 | 示例 Prompt 开头 |
|-------|-------|----------|------------------|
| `tech-lead` | opus | 架构决策、跨域协调、技术选型 | "设计 XX 系统的架构..." |
| `frontend-lead` | sonnet | React 组件、Zustand 状态、UI 实现 | "实现 XX 页面组件..." |
| `backend-lead` | sonnet | FastAPI 端点、数据库模型、服务层 | "实现 XX API 端点..." |
| `automation-developer` | sonnet | Playwright 自动化、FFmpeg 视频处理 | "编写 XX 自动化脚本..." |
| `qa-lead` | sonnet | 测试策略、Bug 分类、发布质量 | "为 XX 功能制定测试计划..." |
| `security-expert` | sonnet | 安全审计、漏洞扫描、加密审查 | "审计 XX 模块的安全性..." |
| `devops-engineer` | sonnet | CI/CD、构建配置、部署脚本 | "配置 XX 的 CI 流水线..." |

### Skill 一览

| Skill | 调用方式 | 用途 |
|-------|----------|------|
| `/sprint-plan` | `/sprint-plan new` | 创建新 Sprint |
| `/task-breakdown` | `/task-breakdown AI剪辑功能` | 将功能分解为任务 |
| `/code-review` | `/code-review backend/api/account.py` | 代码审查 |
| `/security-scan` | `/security-scan full backend/` | 安全扫描 |
| `/architecture-review` | `/architecture-review 登录系统` | 架构审查 |
| `/bug-report` | `/bug-report 登录超时` | 记录缺陷 |
| `/release-checklist` | `/release-checklist v1.0` | 发布前检查 |

### Handoff 模板（委托 Agent 时使用）

```
## Handoff
**From**: [你/上级 Agent]
**To**: [目标 Agent]
**Task**: [一句话总结]

### Context
[2-5 句：为什么要做这件事，已有哪些决策]

### Constraints
- [约束条件]

### Input Artifacts
- [需要先读的文件]

### Expected Output
- [具体交付物]
```

---

## 场景 1：新功能开发

> **示例**：开发"AI 视频剪辑"功能

### Phase 1：需求分析与任务分解

```
你：/task-breakdown AI视频剪辑功能
```

Skill 自动输出任务清单，包含前后端拆分、负责人分配、依赖关系。

### Phase 2：架构设计

委托 tech-lead 做架构决策：

```
你：请 tech-lead 设计 AI 视频剪辑功能的架构

## Handoff
**From**: User
**To**: tech-lead
**Task**: 设计 AI 视频剪辑功能的系统架构

### Context
需要实现用户上传视频 → AI 检测高光片段 → 自动剪辑 → 导出的完整流程。
涉及 FFmpeg 视频处理、前端剪辑 UI、后端 API。

### Constraints
- 必须使用现有的 FFmpeg 工具链
- 前端使用 Ant Design 组件库
- 视频处理必须异步（不能阻塞 API）

### Expected Output
- 系统架构图（组件划分）
- API 契约定义（端点列表 + 请求/响应格式）
- ADR 文档
```

tech-lead 产出架构方案后，你审批。

### Phase 3：并行实现

架构确定后，**同时**委托前后端：

```
你：请 backend-lead 和 frontend-lead 并行实现

（启动 backend-lead Agent）
## Handoff
**From**: User
**To**: backend-lead
**Task**: 实现 AI 剪辑 API 端点

### Context
tech-lead 已定义 API 契约（见 design/ai-clip-api.md）。
需要实现 POST /api/clips/analyze 和 GET /api/clips/{id}/status。

### Constraints
- 使用 Pydantic schema 验证
- FFmpeg 调用委托给 automation-developer
- 视频处理使用后台任务

### Input Artifacts
- design/ai-clip-api.md

### Expected Output
- backend/api/clip.py（路由）
- backend/services/clip_service.py（业务逻辑）
- backend/schemas/clip.py（Pydantic schema）

（同时启动 frontend-lead Agent）
## Handoff
**From**: User
**To**: frontend-lead
**Task**: 实现 AI 剪辑前端页面

### Context
tech-lead 已定义 API 契约（见 design/ai-clip-api.md）。
需要实现剪辑配置页和结果预览页。

### Constraints
- 使用 Ant Design 组件
- 状态管理用 Zustand
- 类型定义必须与后端 schema 一致

### Input Artifacts
- design/ai-clip-api.md

### Expected Output
- frontend/src/pages/ClipPage.tsx
- frontend/src/stores/clipStore.ts
- frontend/src/services/clipApi.ts
```

### Phase 4：Sync Gate（集成检查）

两个 Agent 都完成后，**你作为协调者检查**：

```
你：两个 Agent 都完成了，我来做集成检查：
1. frontend 的 API 调用类型是否匹配 backend 的 response schema？
2. 有没有命名冲突？
3. 错误处理是否对齐？

请 tech-lead 做架构级 review。
```

### Phase 5：测试与审查

```
你：/code-review backend/api/clip.py
你：/code-review frontend/src/pages/ClipPage.tsx
你：/security-scan quick backend/services/clip_service.py
```

---

## 场景 2：Bug 修复

> **示例**：用户报告"登录后 Cookie 过期不刷新"

### Step 1：记录 Bug

```
你：/bug-report 登录后 Cookie 过期不自动刷新，用户需要手动重新登录
```

### Step 2：定位问题

直接委托 backend-lead 调查（单域问题不需要 tech-lead）：

```
你：请 backend-lead 调查 Cookie 刷新问题

## Handoff
**From**: User
**To**: backend-lead
**Task**: 诊断并修复 Cookie 过期不刷新的问题

### Context
用户报告登录约 30 分钟后 Cookie 过期，但系统未自动续期。
预计问题在 backend/services/auth_service.py 或 backend/utils/crypto.py。

### Constraints
- 不能降低安全标准（Cookie 加密必须保留 AES-256-GCM）
- 修复后需要 security-expert 审查

### Expected Output
- 根因分析
- 修复代码
- 说明影响范围
```

### Step 3：安全审查

修复完成后：

```
你：请 security-expert 审查 Cookie 刷新的修复

## Handoff
**From**: User
**To**: security-expert
**Task**: 审查 Cookie 自动续期的安全性

### Context
backend-lead 修改了 auth_service.py 中的 Cookie 续期逻辑。
需要确认没有引入会话固定攻击或 Cookie 降级风险。

### Input Artifacts
- backend/services/auth_service.py（已修改）

### Expected Output
- 安全审查报告（通过/需修改）
```

---

## 场景 3：API 设计（跨域协作）

> **示例**：新增"账号批量导入" API

这是典型的跨域场景 —— 需要前后端同时参与。

### Step 1：tech-lead 定义契约

```
你：请 tech-lead 设计账号批量导入的 API 契约

## Handoff
**From**: User
**To**: tech-lead
**Task**: 设计批量导入账号的 API 契约

### Context
需要支持从 CSV/Excel 批量导入得物账号。涉及文件上传、
解析验证、批量创建、进度反馈。

### Constraints
- 单次最多导入 100 个账号
- 必须验证每行数据格式
- 需要返回逐行的成功/失败结果

### Expected Output
- API 端点定义（URL、Method、Request/Response Schema）
- 前后端共享的 TypeScript/Python 类型定义
- 错误码定义
```

### Step 2：前后端同步实现

tech-lead 输出契约后，前后端按契约各自实现（同场景 1 的 Phase 3）。

### Step 3：如果出现分歧

比如 frontend-lead 认为应该用 WebSocket 推送进度，backend-lead 认为轮询就够了：

```
你：前后端对进度反馈方案有分歧，请 tech-lead 裁定

## Handoff
**From**: User
**To**: tech-lead
**Task**: 裁定批量导入进度反馈的技术方案

### Context
- frontend-lead 建议：WebSocket 实时推送（用户体验好）
- backend-lead 建议：客户端轮询 GET /api/import/{id}/status（实现简单）
- 当前系统没有 WebSocket 基础设施

### Expected Output
- 选择方案 + 理由（ADR 格式）
```

---

## 场景 4：代码审查

### 单文件审查

```
你：/code-review backend/api/account.py
```

Skill 自动检测为 Python 模式，只运行 mypy + loguru 检查。

### 目录级审查

```
你：/code-review frontend/src/pages/
```

Skill 自动检测为 TypeScript 模式，运行 typecheck + any 检查。

### 委托 Agent 做深度审查

```
你：请 tech-lead 做架构级 review

## Handoff
**From**: User
**To**: tech-lead
**Task**: 架构级审查 clip 模块

### Context
clip 模块刚完成第一版实现，需要检查：
- 组件边界是否清晰
- API 设计是否符合 REST 规范
- 是否有循环依赖

### Input Artifacts
- backend/api/clip.py
- backend/services/clip_service.py
- frontend/src/pages/ClipPage.tsx

### Expected Output
- 架构审查报告（使用 /architecture-review skill）
```

---

## 场景 5：安全审计

### 快速扫描（日常开发）

```
你：/security-scan quick
```

只检查硬编码密钥、日志泄露、SQL 注入模式。约 30 秒完成。

### 针对性扫描

```
你：/security-scan full backend/services/
```

只扫描后端服务层，跳过前端检查。

### 依赖漏洞扫描

```
你：/security-scan dependencies
```

运行 pip-audit + npm audit。

### 深度安全审计（发布前）

```
你：请 security-expert 做发布前安全审计

## Handoff
**From**: User
**To**: security-expert
**Task**: v1.0 发布前全面安全审计

### Context
即将发布 v1.0，需要对以下高风险区域做深度审计：
- 账号登录（Cookie 加密、会话管理）
- 文件上传（路径遍历、大小限制）
- API 权限（越权访问）

### Constraints
- CRITICAL/HIGH 问题必须在发布前修复
- 审计范围：backend/ 全部 + frontend/src/services/

### Expected Output
- 完整安全扫描报告
- 风险评级（CRITICAL/HIGH/MEDIUM/LOW）
- 修复建议和优先级
```

---

## 场景 6：Sprint 规划与任务分解

### 创建新 Sprint

```
你：/sprint-plan new
```

Skill 引导你定义 Sprint 目标、周期、容量，自动生成任务分配表。

### 查看 Sprint 状态

```
你：/sprint-plan status
```

### 功能分解为任务

```
你：/task-breakdown 账号批量管理功能
```

输出结构化的任务列表，含 ID、负责人、估时、依赖关系：

```
FE-BATCH-01: 批量导入 UI 组件（Frontend Lead, 1d）
BE-BATCH-01: 批量导入 API（Backend Lead, 1.5d, 依赖 FE-BATCH-01 的类型定义）
BE-BATCH-02: CSV 解析服务（Backend Lead, 0.5d）
TEST-BATCH-01: 批量导入测试用例（QA Lead, 1d, 依赖 BE-BATCH-01）
```

---

## 场景 7：发布前检查

```
你：/release-checklist v1.0
```

Skill 自动检查：
- 功能完整性
- 代码质量（typecheck、lint）
- 安全扫描（CRITICAL/HIGH 必须为 0）
- 测试覆盖率（单元 80%+、API 100%、前端 70%+）
- 文档完整性
- 部署准备

任何阻塞条件未通过都会标红，给出明确的修复指引。

---

## 场景 8：紧急 Hotfix

> **示例**：生产环境登录功能完全不可用

紧急场景下**跳过层级**，直接委托实现：

```
你：请 backend-lead 紧急修复登录功能

## Handoff
**From**: User
**To**: backend-lead
**Task**: 紧急修复生产环境登录不可用问题

### Context
生产环境从今天 14:00 开始所有用户无法登录。
错误日志显示 "InvalidToken" 异常。
怀疑是今天早上的 crypto.py 更新引入的回归。

### Constraints
- 这是 S1 紧急修复，跳过常规审查流程
- 修复后仍需 security-expert 事后审查
- 尽量最小化变更范围

### Input Artifacts
- backend/utils/crypto.py（今天的变更）
- 生产环境错误日志

### Expected Output
- 修复补丁
- 根因分析
- 回归测试建议
```

修复后补审查：

```
你：/code-review backend/utils/crypto.py
你：/security-scan quick backend/utils/
```

---

## 场景 9：重构

> **示例**：将账号服务从同步改为异步

### Step 1：tech-lead 评估影响范围

```
你：请 tech-lead 评估账号服务异步化的影响

## Handoff
**From**: User
**To**: tech-lead
**Task**: 评估账号服务从同步改异步的影响范围和方案

### Context
当前 backend/services/account_service.py 全部使用同步数据库调用。
需要迁移到 async/await + aiosqlite 以提升并发性能。

### Expected Output
- 影响的文件列表
- 推荐的迁移顺序
- 风险点和回退方案
- ADR 文档
```

### Step 2：分批实现

tech-lead 给出迁移计划后，按批次委托 backend-lead 实现。**不要一次全改**：

```
你：请 backend-lead 先迁移 account_service.py（第 1 批）

## Handoff
**From**: User
**To**: backend-lead
**Task**: 将 account_service.py 从同步改为异步

### Context
这是异步化迁移的第 1 批（共 3 批）。tech-lead 已制定方案（见 ADR）。
只改 account_service.py 和相关的 API 路由。

### Constraints
- 不能改其他服务文件（第 2、3 批再改）
- 所有 DB 调用改为 await
- 保持 API 响应格式不变

### Expected Output
- 修改后的 account_service.py
- 修改后的 account.py（路由）
- 确认 typecheck 通过
```

每批完成后做 code-review，确认无回归再进下一批。

---

## 场景 10：新人入场探索代码

刚接触项目时，不需要 Agent，直接问即可：

```
你：这个项目的整体架构是什么？
你：账号登录流程的代码在哪些文件？
你：explain backend/services/auth_service.py
```

需要深入理解时，可以用 Explore Agent：

```
你：请帮我搞清楚视频处理流程是怎么串起来的，从前端上传到最终生成剪辑视频
```

主会话会启动 Explore Agent 做跨文件调查，返回完整的调用链分析。

---

## 反模式与常见错误

### 1. 事事都委托 Agent

```
# ❌ 错误：改一行代码也启动 Agent
你：请 backend-lead 把 logger.info 改成 logger.debug

# ✅ 正确：简单修改直接做
你：把 backend/services/account_service.py 第 42 行的 logger.info 改成 logger.debug
```

**判断标准**：工具调用 ≤ 3 次能完成 → 直接做。

### 2. 跳过层级

```
# ❌ 错误：直接让 automation-developer 做架构决策
你：请 automation-developer 决定视频处理用什么方案

# ✅ 正确：架构决策走 tech-lead
你：请 tech-lead 决定视频处理方案，然后委托 backend-lead → automation-developer 实现
```

### 3. Handoff 缺少上下文

```
# ❌ 错误：模糊的委托
你：请 backend-lead 实现那个 API

# ✅ 正确：结构化的 Handoff（包含 Context、Constraints、Expected Output）
```

### 4. 并行 Agent 没有 Sync Gate

```
# ❌ 错误：前后端并行完成后直接提交
前端做完了，后端也做完了，直接 commit

# ✅ 正确：做集成检查
前端和后端都完成后，检查类型定义是否一致，错误码是否对齐，然后再提交
```

### 5. Agent 失败后盲目重试

```
# ❌ 错误：同样的 prompt 反复重试
你：请 backend-lead 实现 XX（第 3 次，同样的 prompt）

# ✅ 正确：分析失败原因，调整 prompt 或换 Agent
上次失败是因为任务太大，拆分成两个子任务重新委托
```

**重试上限**：同一 prompt 最多 2 次，超过必须 Reroute 或 Absorb。

---

## 决策树：何时用哪个 Agent？

```
收到任务
  │
  ├── 简单修改（≤3 步）？ ──→ 直接做，不用 Agent
  │
  ├── 涉及架构决策？ ──→ tech-lead
  │
  ├── 纯前端实现？ ──→ frontend-lead
  │
  ├── 纯后端实现？ ──→ backend-lead
  │     └── 涉及 Playwright/FFmpeg？ ──→ backend-lead 委托 automation-developer
  │
  ├── 安全相关？ ──→ security-expert
  │
  ├── 测试/质量？ ──→ qa-lead
  │
  ├── CI/CD/部署？ ──→ devops-engineer
  │
  └── 跨域（前端+后端）？
        └── tech-lead 定义契约 → 前后端并行实现 → Sync Gate
```

---

*版本: 1.0*
*适用于: DewuGoJin Multi-Agent Framework v2.0*
*位置: .claude/docs/usage-guide.md*
