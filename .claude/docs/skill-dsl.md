# Skill DSL Specification

Domain-Specific Language for defining Claude Code skills/workflows.

> **⚠️ Critical Note**: Skills are not simple command handlers. They define **structured multi-phase workflows** with decision points, output templates, quality gates, and cross-references to other skills, agents, and documents.

## Overview

Skills are triggered workflows that orchestrate multiple agents to accomplish specific tasks. Each skill is defined in a Markdown file with YAML Frontmatter, containing detailed phases, templates, and quality checks.

## File Structure

```
skills/
└── {skill-name}/
    └── SKILL.md    # Skill definition (in subdirectory)
```

## Frontmatter Schema

```yaml
---
name: {skill-id}              # REQUIRED: kebab-case identifier
description: "{text}"          # REQUIRED: What this skill does
argument-hint: "{hint}"        # OPTIONAL: Expected arguments
user-invocable: {bool}        # REQUIRED: Can users trigger directly
allowed-tools: {tools}         # REQUIRED: comma-separated list
---
```

## Field Specifications

### name (REQUIRED)

- **Format**: kebab-case
- **Pattern**: `^[a-z][a-z0-9-]*$`
- **Length**: 3-50 characters
- **Examples**: `brainstorm`, `design-review`, `code-review`, `sprint-plan`

### description (REQUIRED)

- **Format**: String
- **Length**: 20-200 characters
- **Content**: Detailed description of what the skill does
- **Style**: Include methodology or framework references

### argument-hint (OPTIONAL)

- **Format**: String describing expected arguments
- **Pattern**: `[argument-name]` for optional, `<argument-name>` for required
- **Examples**: 
  - `[path-to-design-doc]` - optional path
  - `<feature-name>` - required name
  - `[genre or theme hint, or 'open' for fully open brainstorm]`

### user-invocable (REQUIRED)

- **Type**: Boolean
- **Default**: `false`
- **Usage**: `true` for skills users can invoke directly via `/command`

### allowed-tools (REQUIRED)

- **Format**: Comma-separated list (no brackets, no quotes)
- **Purpose**: Explicitly whitelist tools for this skill
- **Usage**: Restrict tools to prevent misuse
- **Examples**:
  - `allowed-tools: Read, Glob, Grep, Write, WebSearch, AskUserQuestion`
  - `allowed-tools: Read, Glob, Grep` (read-only skills)

## Body Structure

### 1. Context Detection (Recommended)

For skills that behave differently based on the target domain (e.g., Python vs TypeScript), add a `## Context Detection` section immediately after the trigger examples. This section SHOULD:

- Detect domain from the file path argument (extension or directory prefix)
- Fall back to `active.md` Active Task component if no argument is given
- Set a domain label that controls which checklists and static checks are executed

```markdown
## Context Detection

**IMPORTANT**: Before starting, determine scope from the argument:

1. If the argument contains a file path:
   - Path starts with `backend/` or ends with `.py` → **Python mode**
   - Path starts with `frontend/` or ends with `.ts`/`.tsx` → **TypeScript mode**
2. If no argument: check `active.md` for context, or use both modes
```

This avoids running irrelevant checks (e.g., `npm run typecheck` when reviewing a Python file) and produces focused, actionable reports.

### 2. Invocation Handler

```markdown
When this skill is invoked:

1. **Parse arguments** — [What to do with inputs]
2. **Check prerequisites** — [What to verify exists]
3. **Read context** — [What documents to load]
4. **Begin workflow** — [Start first phase]
```

### 2. Phase Definition

```markdown
---

### Phase N: {Phase Name}

[Detailed description of this phase]

**Goal**: [What this phase accomplishes]

#### Steps

1. [Step description]
2. [Step description]

#### Decision Point (optional)

- [Option A] → [Outcome]
- [Option B] → [Outcome]
```

### 3. Quality Checks

```markdown
### Quality Checks

Review against these standards:

- [ ] [Check item 1]
- [ ] [Check item 2]
- [ ] [Check item 3]
```

### 4. Output Format

```markdown
### Output Format

Generate output using this template:

```
## [Output Title]

### Section 1
[Content]

### Section 2
[Content]
```
```

### 5. Next Steps

```markdown
### Next Steps

Suggest these actions after completion:
1. [Next action 1]
2. [Next action 2]
```

---

## Phase Patterns

### Pattern 1: Discovery Phase

```markdown
### Phase 1: Discovery

Start by gathering context:

**Questions to ask**:
- [Question 1]
- [Question 2]
- [Question 3]

**Documents to read**:
- [Document 1]
- [Document 2]

**Synthesize** the answers into [output format].
```

### Pattern 2: Analysis Phase

```markdown
### Phase 2: Analysis

**Goal**: Evaluate [target] against [criteria]

**Checklist**:
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

**Output**: Structured analysis document
```

### Pattern 3: Design Phase

```markdown
### Phase 3: Design

**Goal**: Create [deliverable]

**Approach**:
1. [Design step 1]
2. [Design step 2]
3. [Design step 3]

**Template**: [Reference to template file]
```

### Pattern 4: Review Phase

```markdown
### Phase 4: Review

**Goal**: Validate [deliverable]

**Review Criteria**:
- Completeness: [X/8 sections present]
- Consistency: [Check internal consistency]
- Implementability: [Check if implementable]

**Verdict Options**:
- APPROVED
- NEEDS REVISION
- MAJOR REVISION NEEDED
```

---

## Decision Points

Decision points use `AskUserQuestion` for user input:

```markdown
### Decision Point: [Topic]

Present options and capture decision:

1. **Option A**: [Description]
   - Pros: [Advantage 1]
   - Cons: [Disadvantage 1]
   
2. **Option B**: [Description]
   - Pros: [Advantage 1]
   - Cons: [Disadvantage 1]

**Recommended**: Option A

Use `AskUserQuestion` with concise labels:
- [A - Option A] — [Brief reason]
- [B - Option B] — [Brief reason]
```

---

## Quality Gates

### Completeness Checklists

```markdown
### Completeness Checklist

- [ ] Has Overview section
- [ ] Has Player Fantasy section
- [ ] Has Detailed Rules section
- [ ] Has Formulas section
- [ ] Has Edge Cases section
- [ ] Has Dependencies section
- [ ] Has Tuning Knobs section
- [ ] Has Acceptance Criteria section
```

### Consistency Checks

```markdown
### Consistency Checks

**Internal Consistency**:
- Do formulas produce values that match described behavior?
- Do edge cases contradict main rules?
- Are definitions consistent throughout?

**Cross-System Consistency**:
- Does this conflict with existing mechanics?
- Does this create unintended interactions?
- Is this consistent with pillars?
```

---

## Output Templates

### Template Reference Pattern

```markdown
### Template Usage

Generate output using the template at:
`.claude/docs/templates/{template-name}.md`
```

### Inline Template

```markdown
### Output Template

```
## [Deliverable Title]

### Section Name
Content here

### Another Section
More content
```
```

---

## Cross-References

### To Other Skills

```markdown
### Related Skills

- `/{skill-name}` — [Description]
- `/{another-skill}` — [Description]

### Workflow Sequence
[Skill A] → [Skill B] → [Skill C]
```

### To Agents

```markdown
### Involves

- `{agent-name}` — [Role in this skill]
- `{another-agent}` — [Role in this skill]
```

### To Documents

```markdown
### Reads

- `design/gdd/{document}.md` — [Purpose]
- `production/session-state/{file}.md` — [Purpose]

### Writes

- `design/gdd/{document}.md` — [Purpose]
```

---

## Full Example: Design Review Skill

```markdown
---
name: design-review
description: "Reviews a game design document for completeness, internal consistency, implementability, and adherence to project design standards. Run this before handing a design document to programmers."
argument-hint: "[path-to-design-doc]"
user-invocable: true
allowed-tools: Read, Glob, Grep
---

When this skill is invoked:

1. **Parse the argument** for the design document path
2. **Read the target design document** in full
3. **Read the master CLAUDE.md** for project context
4. **Read related design documents** referenced by target
5. **Evaluate against Design Document Standard checklist**
6. **Check for internal consistency**
7. **Check for implementability**
8. **Output the review** with verdict
9. **Suggest next steps**

---

### Phase 1: Document Analysis

**Goal**: Understand the design document

**Steps**:
1. Read the target document completely
2. Identify all referenced systems
3. List dependencies
4. Note any ambiguous sections

### Phase 2: Completeness Check

**Goal**: Verify all required sections exist

**Completeness Checklist**:
- [ ] Overview section (one-paragraph summary)
- [ ] Player Fantasy section (intended feeling)
- [ ] Detailed Rules section (unambiguous mechanics)
- [ ] Formulas section (all math defined)
- [ ] Edge Cases section (unusual situations)
- [ ] Dependencies section (other systems)
- [ ] Tuning Knobs section (configurable values)
- [ ] Acceptance Criteria section (testable conditions)

### Phase 3: Consistency Review

**Goal**: Find contradictions and conflicts

**Internal Consistency**:
- Do formulas match described behavior?
- Do edge cases contradict main rules?
- Are dependencies bidirectional?

**Cross-System Consistency**:
- Conflicts with existing mechanics?
- Unintended interactions?
- Consistent with pillars?

### Phase 4: Implementability Check

**Goal**: Ensure rules are precise enough to implement

**Checkpoints**:
- Rules are unambiguous?
- No "hand-wave" sections?
- Performance implications considered?

### Phase 5: Review Output

**Goal**: Generate structured review

**Output Format**:
```
## Design Review: [Document Title]

### Completeness: [X/8 sections present]
[List missing sections]

### Consistency Issues
[List contradictions]

### Implementability Concerns
[List vague sections]

### Balance Concerns
[List balance risks]

### Recommendations
[Prioritized improvements]

### Verdict: [APPROVED / NEEDS REVISION / MAJOR REVISION NEEDED]
```

### Next Steps

1. If `game-concept.md`: Run `/map-systems` next
2. If system GDD: Update systems index status
3. If NEEDS REVISION: Run `/design-system` to fix
```

---

## Validation Rules

### MUST

- Frontmatter must be valid YAML
- `name` must be unique
- `trigger` must start with `/`
- `allowed-tools` must be non-empty
- At least one phase defined
- Each phase must have steps
- Output format must be defined
- Next steps should be suggested

### MUST NOT

- Duplicate skill names
- Duplicate trigger commands
- Reference non-existent agents
- Skip completeness checks for design skills
- Omit output templates for document-producing skills

### SHOULD

- Include decision points for user choices
- Reference related skills and documents
- Provide checklists for review skills
- Define quality gates
- Suggest next steps in workflow sequence

---

## Skill Categories

### Discovery Skills
- `brainstorm` — Ideation and concept generation
- `prototype` — Quick validation of mechanics
- `playtest-report` — Feedback collection

### Design Skills
- `design-system` — Detailed specification writing
- `design-review` — Quality assurance of specs
- `map-systems` — System decomposition

### Production Skills
- `sprint-plan` — Sprint planning
- `release-checklist` — Release preparation
- `hotfix` — Emergency fixes

### Review Skills
- `code-review` — Code quality checks
- `balance-check` — Game balance analysis
- `asset-audit` — Asset pipeline validation

---

## Meta-Framework Skills

The meta-framework includes one core skill:

1. `framework-forge` — Generates complete multi-agent frameworks

See `.claude/skills/framework-forge/SKILL.md` for full definition.
