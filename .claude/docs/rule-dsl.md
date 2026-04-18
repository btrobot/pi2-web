# Rule DSL Specification

Domain-Specific Language for defining coding standards, design rules, and quality gates.

> **⚠️ Critical Note**: Rules are not just style guides. They define **enforceable constraints** with specific examples, severity levels, and remediation guidance. Each rule must be actionable and verifiable.

## Overview

Rules define enforceable standards that agents must follow. Each rule is defined in a Markdown file with YAML Frontmatter, containing specific constraints, examples, and quality criteria.

## File Structure

```
rules/
└── {rule-name}.md    # kebab-case, one file per rule
```

## Frontmatter Schema

```yaml
---
paths:                     # REQUIRED: Files this rule applies to
  - "{glob-pattern}"
  - "{glob-pattern}"
---

# {Rule Display Name}

[Rule statement 1]
[Rule statement 2]
[Rule statement N]

## Examples

**Correct**:

```language
[Correct code example]
```

**Incorrect**:

```language
[Incorrect code example]
```
```

## Field Specifications

### paths (REQUIRED)

- **Format**: YAML list of glob patterns
- **Purpose**: Define scope of files this rule applies to
- **Examples**:
  ```yaml
  paths:
    - "src/gameplay/**"
    - "src/gameplay/**/*.{gd,gdscript}"
  ```

### Rule Statement Format

Rules use imperative language:

| Prefix | Meaning |
|--------|---------|
| MUST | Absolute requirement |
| MUST NOT | Absolute prohibition |
| SHOULD | Strong recommendation |
| SHOULD NOT | Strong discouragement |
| MAY | Permitted |

## Body Structure

### 1. Rule Statements

```markdown
# {Rule Title}

- Rule statement 1
- Rule statement 2
- Rule statement N
```

### 2. Examples Section

```markdown
## Examples

**Correct**:

```language
// Correct example with explanation
```

**Incorrect**:

```language
// Incorrect example with violation marked
```
```

### 3. Extended Documentation (Optional)

```markdown
## Rationale

Why this rule exists and what problems it prevents.

## Exceptions

When this rule can be legitimately bypassed.

## Related Rules

- `{rule-name}` — [How it relates]
```

---

## Rule Types

### Type 1: Code Rules

```markdown
---
paths:
  - "src/gameplay/**"
---

# Gameplay Code Rules

- ALL gameplay values MUST come from external config/data files
- Use delta time for ALL time-dependent calculations
- NO direct references to UI code — use events/signals
- Every gameplay system must implement a clear interface
- State machines must have explicit transition tables
- Write unit tests for all gameplay logic

## Examples

**Correct**:
```gdscript
var damage: float = config.get_value("combat", "base_damage", 10.0)
```

**Incorrect**:
```gdscript
var damage: float = 25.0   # VIOLATION: hardcoded
```
```

### Type 2: Design Document Rules

```markdown
---
paths:
  - "design/gdd/**"
---

# Design Document Rules

- Every design document MUST contain these 8 sections: Overview, Player Fantasy, Detailed Rules, Formulas, Edge Cases, Dependencies, Tuning Knobs, Acceptance Criteria
- Formulas must include variable definitions, expected value ranges, and example calculations
- Edge cases must explicitly state what happens, not just "handle gracefully"
- Dependencies must be bidirectional
- Acceptance criteria must be testable
- No hand-waving: "the system should feel good" is NOT a valid specification
```

### Type 3: Process Rules

```markdown
---
paths:
  - "production/**"
---

# Sprint Planning Rules

- Tasks MUST be small enough to complete in 1-3 days
- Tasks with dependencies MUST list those dependencies explicitly
- Tasks MUST NOT be assigned to multiple agents
- Buffer 20% capacity for unexpected work and bug fixes
- Critical path tasks MUST be identified and highlighted
```

### Type 4: Quality Rules

```markdown
---
paths:
  - "src/**/*.test.{ts,js}"
---

# Test Standards

- Test names MUST describe the expected behavior
- Tests MUST NOT have side effects (order-independent)
- Tests MUST clean up any resources they create
- Coverage MUST be measured and reported
```

---

## Severity Levels

### Strict (Blocking)

```markdown
# Critical Rule

- MUST NOT be violated
- Violations block commit/push
- Examples must be provided
```

### Standard (Warning)

```markdown
# Recommended Rule

- SHOULD be followed
- Violations produce warnings
- Still allow commit/push
```

### Advisory (Suggestion)

```markdown
# Best Practice

- MAY be followed
- No enforcement
- Learning resource
```

---

## Example Patterns

### Pattern 1: Data-Driven Rule

```markdown
# Data-Driven Design

- Gameplay values MUST come from external data files
- Configuration MUST NOT be hardcoded
- Data files MUST define default values and safe ranges

## Examples

**Correct**:
```gdscript
var damage: float = config.get_value("combat", "base_damage", 10.0)
```

**Incorrect**:
```gdscript
var damage: float = 25.0   # VIOLATION
```
```

### Pattern 2: Interface Rule

```markdown
# Interface Segregation

- Systems MUST expose clear, minimal interfaces
- Systems MUST NOT expose internal implementation details
- Dependencies MUST use interface references, not concrete types

## Examples

**Correct**:
```gdscript
interface IDamageable
    func take_damage(amount: float) -> void
    func get_health() -> float
```

**Incorrect**:
```gdscript
# Direct reference to Player class
var player: Player
player.health_component.take_damage()
```
```

### Pattern 3: Documentation Rule

```markdown
# Design Document Completeness

Design documents MUST include:

- **Overview** — One-paragraph summary
- **Player Fantasy** — Intended player feeling
- **Detailed Rules** — Complete mechanical specification
- **Formulas** — All math with variables defined
- **Edge Cases** — Boundary and error conditions
- **Dependencies** — Related systems (bidirectional)
- **Tuning Knobs** — Adjustable parameters with ranges
- **Acceptance Criteria** — Testable success conditions

## Examples

**Incomplete** (missing sections):
```markdown
# Combat System

This system handles combat.
```

**Complete**:
```markdown
# Combat System

## Overview
Handles all combat interactions between player and enemies.

## Player Fantasy
Fighting feels impactful and responsive, rewarding skillful play.

## Detailed Rules
[P完整规则]
...
```
```

---

## Cross-Reference Pattern

```markdown
## Related Rules

- `test-standards.md` — How to test code written under this rule
- `ui-code.md` — Interface rules for UI systems
- `data-files.md` — How to structure data files
```

---

## Full Example: Complete Rule File

```markdown
---
paths:
  - "src/gameplay/**"
  - "src/gameplay/**/*.gd"
---

# Gameplay Code Rules

Core rules for all gameplay-related code in the src/gameplay directory.

## Data-Driven Design

- ALL gameplay values MUST come from external config/data files, NEVER hardcoded
- Config access MUST provide default values for all parameters
- Safe ranges MUST be defined for all tunable values

## Time Independence

- Use delta time for ALL time-dependent calculations
- Frame-rate independent logic is non-negotiable
- Animation and physics MUST be separate concerns

## System Communication

- NO direct references to UI code from gameplay systems
- Use events/signals for all cross-system communication
- UI systems MUST subscribe to gameplay events, not poll state

## Interface Design

- Every gameplay system MUST implement a clear, documented interface
- State machines MUST have explicit transition tables
- State transitions MUST be documented with trigger conditions

## Testing

- Write unit tests for all gameplay logic
- Logic MUST be separable from presentation for testing
- Mock interfaces for external dependencies

## Documentation

- Document which design doc each feature implements
- Link code sections to specific game rules
- Document all assumptions about player behavior

## Examples

**Correct** (data-driven, time-independent):
```gdscript
var damage: float = config.get_value("combat", "base_damage", 10.0)
var speed: float = stats_resource.movement_speed * delta
```

**Incorrect** (hardcoded, frame-dependent):
```gdscript
var damage: float = 25.0   # VIOLATION: hardcoded gameplay value
var speed: float = 5.0      # VIOLATION: not from config, not using delta
```

## Rationale

These rules ensure:
- Designers can tune gameplay without programmer intervention
- Game runs consistently across different frame rates
- Systems remain loosely coupled for maintainability
- Quality is measurable through testing

## Related Rules

- `test-standards.md` — Testing requirements
- `data-files.md` — Data file structure
- `ui-code.md` — UI interface patterns
```

---

## Validation Rules

### MUST

- Frontmatter must be valid YAML
- `paths` must be a non-empty list
- At least one rule statement
- Examples for strict rules
- Correct/incorrect labeled clearly

### MUST NOT

- Duplicate rule file names
- Use vague language ("try to", "maybe")
- Have empty rule statements
- Mix different rule types in same file

### SHOULD

- Provide rationale for each rule
- Document exceptions
- Cross-reference related rules
- Include anti-patterns

---

## Rule Organization

### By Domain

```
rules/
├── code/
│   ├── gameplay-code.md
│   ├── ui-code.md
│   ├── network-code.md
│   └── shader-code.md
├── design/
│   ├── design-docs.md
│   └── narrative.md
└── process/
    ├── sprint-planning.md
    └── code-review.md
```

### By Engine

```
rules/
├── godot/
│   ├── godot-code.md
│   └── godot-assets.md
├── unity/
│   └── csharp-patterns.md
└── unreal/
    └── cpp-standards.md
```

---

## Meta-Framework Rules

The meta-framework includes rules for itself:

- `meta-framework-rules` — Rules for framework files

See `.claude/rules/` for full set.
