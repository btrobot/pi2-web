---
paths:
  - "**/*"
---

# Commit Rules

Git 提交规范，适用于所有提交。

## Commit Format

Commits MUST follow this format:

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

## Commit Types

- `feat` — 新功能
- `fix` — Bug 修复
- `docs` — 文档更新
- `style` — 代码格式
- `refactor` — 重构
- `test` — 测试相关
- `chore` — 构建/工具相关

## Rules

### Message Format

- commit messages MUST use lowercase type prefixes
- commit messages MUST include a scope in parentheses when applicable
- commit messages SHOULD be concise (under 72 characters)
- commit messages MUST describe what changed, not why

### Scope Usage

- scope MUST match the affected module or directory
- common scopes: `audio`, `asr`, `mt`, `tts`, `pipeline`, `storage`, `api`, `hardware`, `config`
- scope SHOULD NOT be omitted for feature work

### Body Format

- body MUST separate subject from body with a blank line
- body lines MUST NOT exceed 72 characters
- body SHOULD explain the motivation and contrast with previous behavior

### When to Commit

- commits MUST represent a complete, working change
- commits SHOULD be atomic (one logical change per commit)
- commits MUST NOT include generated files or build artifacts

## Examples

**Correct**:

```bash
feat(asr): add Vosk Chinese model integration

Load vosk-model-small-cn and wrap recognize API.
Support 16kHz mono WAV input.
```

```bash
fix(audio): prevent recording timeout on long sessions

Add 3-minute hard limit to audio capture.
Gracefully stop and save partial recording.
```

```bash
docs: update model download instructions
```

**Incorrect**:

```bash
# VIOLATION: no scope
git commit -m "fix: bug"

# VIOLATION: vague message
git commit -m "update stuff"

# VIOLATION: multiple changes
git commit -m "feat: add login and fix styling and update docs"

# VIOLATION: committing build artifacts
git commit -m "feat: add new page" --include dist/*
```

## Prohibited Patterns

- MUST NOT commit with empty or default messages
- MUST NOT commit directly to main/master branches
- MUST NOT include sensitive data in commit messages
- MUST NOT commit untracked files without reviewing them

## Rationale

These rules ensure:
- Clear, searchable commit history
- Easy rollback to specific changes
- Meaningful release notes
- Traceability between commits and issues

## Related Rules

- `coordination-rules.md` — Collaboration guidelines
- `code-review-rules.md` — Review process before commits
- `python-coding-rules.md` — Code standards
