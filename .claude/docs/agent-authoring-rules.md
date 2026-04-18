# Agent 编写规范

基于 Claude-Code-Game-Studios 的 Agent DSL 最佳实践，总结适合 DewuGoJin 项目的 Agent 编写规范。

---

## 1. Agent 类型与配置

### 1.1 三层架构

| 层级 | Model | maxTurns | 角色 | 特点 |
|------|-------|----------|------|------|
| **Tier 1** | opus | 30-40 | tech-lead | 战略决策，可 WebSearch |
| **Tier 2** | sonnet | 20-25 | Lead 类 | 战术协调，有 delegation |
| **Tier 3** | sonnet | 15-20 | Developer 类 | 专注执行，被调用 |

### 1.2 Frontmatter 配置模板

```yaml
---
name: {agent-name}              # kebab-case
description: "Invoked for ..."  # 英文，一句话
tools: [Read, Glob, Grep, Write, Edit, Bash]  # 根据需要
model: {sonnet|opus}           # 通常 sonnet
maxTurns: 20                   # 15-25
skills: [{skill-name}]         # 可选
---
```

### 1.3 Tools 配置原则

| Agent 类型 | Tools |
|-----------|-------|
| 纯设计/咨询 | Read, Glob, Grep, Write, Edit |
| 需要执行命令 | + Bash |
| 需要调用子 Agent | + Task |
| 战略层 | + WebSearch |

---

## 2. 文档结构

每个 Agent 定义包含以下章节（按顺序）：

### 2.1 必需章节

```markdown
# [Agent Display Name]

[一句话角色描述]

**You are a [collaborative type], not [autonomous type]. [Approval context].**

## Organization

[组织架构图]

## Standard Workflow (Optional)

[工作流 - 如需自定义，见第3节。否则依赖模板默认工作流]

## Core Responsibilities

1. **Responsibility 1**: [描述]
2. **Responsibility 2**: [描述]
...

## Can Do

- [权限 1]
- [权限 2]

## Must NOT Do

- [禁止 1]
- [禁止 2]

## Collaboration

### Reports To
[上级]

### Coordinates With
- [平级 1]
- [平级 2]
```

### 2.2 可选章节（按需添加）

```markdown
## Decision Points          # 需要做选择时
## Escalation              # 需要升级时
## Special Handling        # 特殊处理协议
## Directory Scope         # 可修改的文件范围
## Quality Standards        # 质量标准
## Code Patterns           # 代码模式/模板
## [Domain] Standards       # 领域特定标准
```

---

## 3. 工作流模板

### 3.1 Implementation Workflow（实现型）

适用于：Lead、Developer、Specialist

```markdown
### Phase 1: Understand Context
1. Read design document
2. Identify requirements and constraints
3. Ask clarifying questions if needed

### Phase 2: Propose Approach
1. Present implementation plan
2. Explain design decisions
3. List affected files

### Phase 3: Get Approval
**Tools**: AskUserQuestion

### Phase 4: Implement
1. Write code
2. Add error handling
3. Follow coding standards

### Phase 5: Self-Review
1. Run type check
2. Verify no violations
3. Offer next steps
```

### 3.2 Advisor Workflow（咨询型）

适用于：Security Expert、QA Lead

```markdown
### Phase 1: Understand Scope
1. Review feature/change
2. Identify boundaries
3. List data flows

### Phase 2: Analysis
1. Present findings
2. Identify issues
3. Assess risk levels

### Phase 3: Recommendations
1. Propose fixes
2. Prioritize by severity
3. Set remediation timeline

### Phase 4: Verification
1. Verify fixes implemented
2. Re-scan/re-test
3. Document findings
```

---

## 4. 委托关系（Delegation Map）

### 4.1 格式

```markdown
## Collaboration

### Reports To
`tech-lead` — [原因]

### Coordinates With
- `backend-lead` — [协作内容]
- `frontend-lead` — [协作内容]

### Delegates To
- `automation-developer` for [具体任务]
```

### 4.2 术语规范

| 术语 | 含义 |
|------|------|
| Reports to | 向谁汇报 |
| Delegates to | 委托给谁执行 |
| Coordinates with | 平等协作 |

---

## 5. 职责定义模式

### 5.1 Core Responsibilities

- 使用动词开头
- 3-6 项为宜
- 每项包含：做什么 + 覆盖场景

```markdown
### Core Responsibilities

1. **API Design**: Design REST endpoints, define schemas, ensure security
2. **Service Layer**: Implement business logic, handle errors, manage transactions
3. **Database**: Design models, manage migrations, optimize queries
```

### 5.2 Must NOT Do

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

**核心问题**：每个 Agent 的定义应该只包含**差异化**内容。

### 6.1 应该包含

| 内容 | 说明 |
|------|------|
| Core Responsibilities | 这个 Agent 独特做什么 |
| Domain Standards | 领域特定的标准/模式 |
| Directory Scope | 可以修改的范围 |
| Can Do / Must NOT | 明确的边界 |

### 6.2 应该复用

| 内容 | 处理方式 |
|------|----------|
| Standard Workflow | 直接复用，不改内容 |
| Collaboration Map | 只写关系，不写协议 |
| Decision Points | 只写"何时问"，不重复模式 |
| Ambiguity Protocol | 统一一句话 |

### 6.3 示例：避免重复

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

## 7. 编写流程

### 7.1 步骤

1. **确定类型**：是实现型还是咨询型？
2. **配置 Frontmatter**：name, description, tools, model, maxTurns
3. **编写 Role Statement**：一句话定位
4. **选择工作流模板**：直接复用
5. **定义核心职责**：3-6 项
6. **定义边界**：Can Do / Must NOT Do
7. **配置协作关系**：Reports to / Coordinates with / Delegates to
8. **按需添加章节**：只添加需要的

### 7.2 验证清单

- [ ] description 使用英文，双引号
- [ ] name 使用 kebab-case
- [ ] model 与 Agent 类型匹配
- [ ] Standard Workflow 步骤完整（如自定义）
- [ ] Core Responsibilities 3-6 项
- [ ] Must NOT Do 非空
- [ ] Collaboration 至少一个关系
- [ ] Agent 名称使用 backticks
- [ ] 无循环依赖

---

## 8. 我们的 Agent 配置

| Agent | 类型 | Model | 工作流 |
|-------|------|-------|--------|
| tech-lead | 战略 | **opus** | Advisor |
| frontend-lead | 战术 | sonnet | Implementation |
| backend-lead | 战术 | sonnet | Implementation |
| automation-developer | 专家 | sonnet | Implementation |
| qa-lead | 战术 | sonnet | Advisor |
| security-expert | 专家 | sonnet | Advisor |
| devops-engineer | 专家 | sonnet | Implementation |

---

## 9. 模板文件

参考 `.claude/agents/templates/` 下的模板：

```
templates/
├── implementer-template.md   # 实现型模板
└── advisor-template.md       # 咨询型模板
```

---

*版本: 1.0*
*基于: Claude-Code-Game-Studios Agent DSL*
