---
paths:
  - "**/*.py"
---

# Code Review Rules

适用于 Pi5 离线翻译系统所有 Python 代码。

## Review Process

- code MUST be reviewed before merging
- reviewers MUST check against these rules
- all feedback MUST be addressed or documented

## Mandatory Checks

### Type Safety

- [ ] All public functions have type annotations
- [ ] No untyped function parameters

### Error Handling

- [ ] All I/O operations have try-except
- [ ] Errors are logged with context
- [ ] No silent exception handling (`except: pass`)
- [ ] Subprocess calls have timeout

### Resource Management

- [ ] Audio devices use context managers
- [ ] File handles properly closed
- [ ] Recording enforces 3-minute limit
- [ ] Storage enforces 5-record/5-recording limit

### Code Quality

- [ ] Functions are small and focused (< 50 lines)
- [ ] No code duplication
- [ ] Proper naming conventions
- [ ] Comments explain "why" not "what"
- [ ] Uses `logging` module, not `print()`

## Severity Levels

### Blocking (MUST fix before merge)

- Missing type annotations on public functions
- Silent exception handling
- `print()` instead of logging
- Audio device / file handle leak
- Hardcoded file paths or device names
- Missing timeout on subprocess or I/O

### Warning (SHOULD fix)

- Code duplication
- Functions too long
- Missing error handling for edge cases
- Inconsistent naming

### Suggestion (MAY fix)

- Code style preferences
- Minor optimizations
- Documentation improvements

## Review Checklist

| Check | Severity |
|-------|----------|
| Type annotations on public functions | Blocking |
| No `except: pass` | Blocking |
| No `print()` statements | Blocking |
| Logging with `logging` module | Blocking |
| Context managers for resources | Blocking |
| Subprocess timeout | Blocking |
| Storage limits enforced | Blocking |
| Error handling for I/O | Warning |
| Docstrings on public functions | Suggestion |

## Review Example

```markdown
## Code Review: models/asr.py

### Issues Found

#### Blocking: Missing timeout on subprocess

**Location**: line 42

```python
result = subprocess.run(["ffmpeg", "-i", path, out])  # No timeout!
```

**Required Fix**:
```python
result = subprocess.run(["ffmpeg", "-i", path, out], timeout=60)
```

#### Warning: Long function

**Location**: line 15-80, `recognize()` is 65 lines.

Consider splitting audio loading and inference into separate functions.

---

**Verdict**: Changes Requested
**Blocking Issues**: 1
**Warnings**: 1
```

## Review Response Format

```markdown
## Code Review Response

### Reviewer: [Agent name]
### Date: YYYY-MM-DD
### Files Reviewed: [List]

### Summary
[Brief assessment]

### Blocking Issues
1. [Issue with location and fix]

### Warnings
1. [Warning with suggestion]

### Verdict
- Changes Requested / Approved with Comments / Approved

### Next Steps
[What author should do]
```

## Related Rules

- `python-coding-rules.md` — Python coding standards
- `commit-rules.md` — Commit message format
