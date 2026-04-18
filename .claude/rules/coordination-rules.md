---
paths:
  - "production/**"
  - ".claude/**"
---

# Coordination Rules

Pi5 离线翻译系统多 Agent 协作规则。

> This is a **Process Rule** covering collaboration between agents.

## Agent Hierarchy

```
用户 (Product Owner)
  └── Tech Lead (opus)
        ├── Embedded Engineer (sonnet) — 硬件/音频/驱动
        ├── ML Engineer (sonnet) — ASR/MT/TTS 模型
        ├── Python Developer (sonnet) — 应用逻辑/API/存储
        └── QA Lead (sonnet) — 测试/验证
```

## Vertical Delegation

### Rules

- User MUST assign tasks to Tech Lead for complex/cross-domain work
- Tech Lead MUST assign tasks to Domain Specialists
- Complex decisions MUST escalate through hierarchy
- Results MUST report back through hierarchy

### Prohibited

- Specialists MUST NOT accept tasks directly from users (except simple tasks)
- Specialists MUST NOT make cross-domain decisions
- Specialists MUST NOT skip Tech Lead and report to User directly

## Horizontal Collaboration

### Collaboration Matrix

| Agent | Collaborates With | Topics |
|-------|------------------|--------|
| Embedded Engineer | ML Engineer | 音频格式 (采样率、位深、通道数) |
| Embedded Engineer | Python Developer | 音频采集/播放 API 接口 |
| ML Engineer | Python Developer | ASR/MT/TTS 模块接口 |
| ML Engineer | QA Lead | 模型准确率测试标准 |
| Python Developer | QA Lead | 功能测试用例 |
| Embedded Engineer | QA Lead | 硬件测试流程 |

### Rules

- Agents MAY discuss and propose suggestions
- Agents MUST NOT make decisions for other domains
- Collaboration results SHOULD be documented

## Conflict Resolution

### Escalation Path

| Conflict Type | Escalate To | Description |
|--------------|-------------|-------------|
| System architecture | Tech Lead | 模块划分、接口设计 |
| Model selection | Tech Lead | ASR/MT/TTS 方案选择 |
| Hardware compatibility | Tech Lead | 驱动兼容性、替代方案 |
| Feature design | User | 需求不明确 |
| Performance vs quality | Tech Lead | 模型大小 vs 准确率 |
| Resource conflicts | User | Agent 冲突 |
| No consensus | Tech Lead | 水平协商失败 |

### Escalation Format

```markdown
## Escalation Report

### Conflict
[Clear description of conflict]

### Views
- **Agent A**: [View and reasoning]
- **Agent B**: [View and reasoning]

### Impact
- [Impact on project]

### Suggestion
[Proposed solution]

### Request
[What leadership should do]
```

## Agent Handoff Protocol

When delegating work from one agent to another, the caller MUST provide a structured handoff.

### Handoff Format

```markdown
## Handoff

**From**: [caller agent name]
**To**: [target agent name]
**Task**: [one-line summary]

### Context
[2-5 sentences: why this task exists, what has been decided]

### Constraints
- [constraint 1]
- [constraint 2]

### Input Artifacts
- [file or decision the receiving agent should read first]

### Expected Output
- [concrete deliverable]
- [quality bar]
```

### Rules

- Handoffs MUST flow through the hierarchy
- The `Context` section MUST NOT exceed 500 words
- The `Constraints` section MUST include cross-domain boundaries if applicable

### Parallel Handoff Sync Gate

When multiple agents are delegated in parallel:

1. Main session launches agents with individual handoff prompts
2. Each agent completes and returns results
3. Main session (or Tech Lead) performs **integration check**:
   - Are the outputs compatible? (e.g., audio format matches ASR input requirements)
   - Any conflicts between parallel decisions?
   - Update `active.md` with combined results
4. Only after sync gate passes → proceed to next phase

### Handoff Failure

#### Failure Detection

| Failure Type | Detection | Example |
|-------------|-----------|---------|
| **Timeout** | Agent hits maxTurns | Complex model integration exceeds 25 turns |
| **Wrong output** | Deliverable mismatch | Asked for ASR module, got only research notes |
| **Scope violation** | Modifies wrong files | ML Engineer edits audio capture code |
| **Quality failure** | Output fails tests | Model doesn't load on Pi5 |
| **Blocked** | Missing dependency | Needs audio format spec not yet defined |

#### Recovery Flow

1. Diagnose root cause: unclear prompt? wrong agent? environment issue?
2. Options (in order of preference):
   - **Refine**: adjust handoff prompt and re-delegate to same agent
   - **Reroute**: delegate to a different agent
   - **Absorb**: main session handles directly
3. **Retry limit**: MUST NOT retry same agent with same prompt more than 2 times
4. Record failure in `active.md`

## Change Propagation

### Trigger Conditions

Changes affecting multiple domains MUST trigger propagation:

- 音频格式变更 (采样率、位深)
- 模块接口变更 (ASR/MT/TTS API)
- 模型文件路径变更
- 系统配置变更

### Propagation Flow

```
1. Change initiated → Notify Tech Lead
2. Tech Lead assesses impact → Identify affected agents
3. Tech Lead coordinates → Confirm change plan
4. Implementation → Complete schedule
5. Tracking → Confirm completion
```

### Change Notification Template

```markdown
## Change Notification

### Change Description
[What changed]

### Impact Scope
- [ ] Embedded Engineer
- [ ] ML Engineer
- [ ] Python Developer
- [ ] QA Lead

### Timeline
- Plan confirmed: [Date]
- Implementation: [Date]
- Testing passed: [Date]
```

## Cross-Domain Changes

### Default Prohibitions

| Prohibition | Description |
|------------|-------------|
| Embedded Engineer → Models | Cannot modify ASR/MT/TTS model code |
| ML Engineer → Hardware | Cannot modify audio capture/ALSA config |
| Python Developer → Models | Cannot modify model inference code |
| Python Developer → Hardware | Cannot modify driver/ALSA code |
| QA Lead → Implementation | Can only modify test files |

### Authorization Process

1. Request authorization from domain specialist
2. Explain reason and scope
3. Receive written confirmation
4. Document authorization source

## Decision Rules

### Decision Types

| Type | Decision Maker | Description |
|------|---------------|-------------|
| Product | User | 功能范围、优先级 |
| System architecture | Tech Lead | 模块划分、接口设计 |
| Hardware | Embedded Engineer | 驱动配置、音频设备 |
| Model selection | ML Engineer (+ Tech Lead approval) | ASR/MT/TTS 方案 |
| Application logic | Python Developer | API 设计、存储方案 |
| Testing | QA Lead | 测试标准、覆盖率 |

### Decision Flow

```
1. Question → Understand the problem
2. Options → Propose 2-3 options
3. Analysis → Analyze trade-offs
4. Decision → Decision maker chooses
5. Document → Log to session state
```

## State Management

### Session State File

Location: `production/session-state/active.md`

### Update Triggers

| Trigger | Content |
|---------|---------|
| Sprint start | Sprint goals, task assignments |
| Task start | Current task, owner |
| Task completion | Mark done, record results |
| Decision made | Log to decision log |
| Risk identified | Record risk and mitigation |

## Validation Rules

### Before Committing

- [ ] Changes reviewed by relevant specialist
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] Session state updated
- [ ] No blocking issues from other domains

### Violation Handling

| Violation | Action |
|-----------|--------|
| Skip hierarchy | Tech Lead corrects |
| Cross-domain change | Rollback and re-coordinate |
| Not documented | Require documentation |
| Conflict not escalated | Tech Lead intervenes |

## Related Rules

- `commit-rules.md` — Commit standards
- `code-review-rules.md` — Review checklist
- `python-coding-rules.md` — Python coding standards
