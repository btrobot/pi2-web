# Agent 核心设计理念

基于 Claude-Code-Game-Studios 最佳实践，总结的多 Agent 协作框架设计原则。

---

## 1. 分层架构

```
User (Product Owner)
  └── Tech Lead (opus)     ← 战略决策层
        ├── Frontend Lead    ← 战术协调层
        ├── Backend Lead
        │     └── Automation Developer
        ├── QA Lead
        ├── Security Expert
        └── DevOps Engineer
```

| 层级 | Model | 职责 |
|------|-------|------|
| **战略层** | opus | 技术决策、架构设计、跨域协调 |
| **战术层** | sonnet | 领域实现、团队协调、质量把控 |
| **执行层** | sonnet | 具体功能实现、测试执行 |

---

## 2. Agent 类型

| 类型 | Model | 特点 | 工作流 |
|------|-------|------|--------|
| **战略型** | opus | 决策，协调部门 | Advisor Workflow |
| **实现型** | sonnet | 代码实施 | Implementation Workflow |
| **咨询型** | sonnet | 审查、建议 | Advisor Workflow |

### 我们的 Agent 配置

| Agent | 类型 | Model | 工作流 |
|-------|------|-------|--------|
| tech-lead | 战略 | **opus** | Advisor |
| frontend-lead | 实现 | sonnet | Implementation |
| backend-lead | 实现 | sonnet | Implementation |
| automation-developer | 实现 | sonnet | Implementation |
| qa-lead | 咨询 | sonnet | Advisor |
| security-expert | 咨询 | sonnet | Advisor |
| devops-engineer | 实现 | sonnet | Implementation |

---

## 3. 核心协议

### Implementation Workflow（实现型）

适用于：Lead、Developer、Specialist

```
1. Understand Context    ← 理解上下文、设计文档
2. Propose Approach    ← 提议方案、列出选项
3. Get Approval       ← 获得批准（使用 AskUserQuestion）
4. Implement          ← 实施代码
5. Self-Review        ← 自我审查
6. Offer Next Steps   ← 提供下一步建议
```

### Advisor Workflow（咨询型）

适用于：Security Expert、QA Lead

```
1. Understand Scope     ← 理解范围、识别风险
2. Analysis           ← 分析问题、评估风险
3. Recommendations    ← 提出建议、优先级排序
4. Verification      ← 验证修复、文档记录
```

---

## 4. 委托关系

### 术语规范

| 术语 | 含义 | 示例 |
|------|------|------|
| Reports to | 向谁汇报 | tech-lead |
| Delegates to | 委托给谁 | automation-developer |
| Coordinates with | 平等协作 | frontend-lead |

### 关系图谱

```
Tech Lead
├── Frontend Lead
│     └── (直接实现)
├── Backend Lead
│     └── Automation Developer
├── QA Lead
│     └── (直接执行)
├── Security Expert
│     └── (独立运作)
└── DevOps Engineer
      └── (直接实现)
```

---

## 5. 职责定义原则

### Core Responsibilities

| 原则 | 说明 |
|------|------|
| 动词开头 | Design, Implement, Review... |
| 3-6项 | 不多不少，聚焦核心 |
| 覆盖场景 | 包含 happy path、edge cases、error handling |

```markdown
## Core Responsibilities

1. **API Design**: Design REST endpoints, define schemas, ensure security
2. **Service Layer**: Implement business logic, handle errors, manage transactions
3. **Database**: Design models, manage migrations, optimize queries
```

### Must NOT Do

- 明确边界
- 包含"应该委托给谁"

```markdown
## Must NOT Do

- Modify frontend code (delegate to frontend-lead)
- Skip Pydantic validation
- Log sensitive data
```

---

## 6. 差异化原则

### 应该包含

| 内容 | 说明 |
|------|------|
| Core Responsibilities | 这个 Agent 独特做什么 |
| Domain Standards | 领域特定的标准/模式 |
| Directory Scope | 可以修改的范围 |
| Quality Checklists | 质量检查项 |

### 应该复用

| 内容 | 处理方式 |
|------|----------|
| Standard Workflow | 直接复用模板，不改内容 |
| Collaboration Map | 只写关系，不写协议 |
| Decision Points | 只写"何时问"，不重复模式 |
| Ambiguity Protocol | 统一一句话，不重复 |

### 示例对比

```markdown
# ❌ 错误：每个 Agent 都写完整协议

## Decision Points
When presenting decisions, use `AskUserQuestion` with this pattern:
1. **Explain first** — Write full analysis...
2. **Capture the decision** — Call AskUserQuestion...

## Special Handling
### Ambiguity Protocol
If you encounter unclear requirements:
→ STOP implementation
→ Ask clarifying questions
→ Wait for clarification before proceeding
```

```markdown
# ✅ 正确：只写差异化部分

## When to Ask
Ask the user for decision when:
- Choosing between component structures
- Deciding state management approach

## Directory Scope
Only modify: `frontend/src/`
```

---

## 7. 验证清单

### Frontmatter

- [ ] `name` 使用 kebab-case，与文件名一致
- [ ] `description` 使用英文，双引号
- [ ] `model` 与 Agent 类型匹配
- [ ] `maxTurns` 设置合理（15-40）

### Body

- [ ] 第一段以 "You are the..." 开头
- [ ] Core Responsibilities 3-6 项
- [ ] Must NOT Do 非空
- [ ] Collaboration 至少一个关系
- [ ] Agent 名称使用 backticks: `agent-name`

### 一致性

- [ ] 无循环依赖
- [ ] 术语统一（Reports to / Delegates to / Coordinates with）
- [ ] 无重复的协议内容

---

## 8. 工具配置原则

| Agent 类型 | Tools |
|-----------|-------|
| 纯设计/咨询 | Read, Glob, Grep, Write, Edit |
| 需要执行命令 | + Bash |
| 需要调用子 Agent | + Task |
| 战略层 | + WebSearch |

---

## 9. 编写流程

```
1. 确定类型        ← 实现型还是咨询型？
2. 配置 Frontmatter  ← name, description, tools, model
3. 编写 Role Statement  ← 一句话定位
4. 选择工作流模板    ← 直接复用
5. 定义核心职责      ← 3-6 项
6. 定义边界        ← Can Do / Must NOT Do
7. 配置协作关系      ← Reports to / Coordinates with
8. 按需添加章节      ← 只添加需要的
```

---

## 10. 核心原则总结

| 原则 | 说明 |
|------|------|
| **简洁** | 只写必要的，避免冗余 |
| **聚焦** | 每个 Agent 有明确的职责边界 |
| **不重复** | 通用协议通过模板复用 |
| **可验证** | 有清晰的检查清单 |
| **可扩展** | 按需添加章节 |

---

*版本: 1.0*
*基于: Claude-Code-Game-Studios Agent DSL*
*位置: .claude/docs/agent-design-principles.md*
