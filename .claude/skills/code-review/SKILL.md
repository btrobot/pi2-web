---
name: code-review
description: "代码审查 - 审查代码质量和规范"
argument-hint: "[文件路径或 PR]"
user-invocable: true
allowed-tools: Read, Write, Glob, Grep, Bash
---

# Code Review Skill

代码审查工作流，审查代码质量和规范。

## 触发方式

```
/code-review
/code-review backend/api/account.py
/code-review frontend/src/pages/Account.tsx
```

## Context Detection

**IMPORTANT**: Before starting the review, determine the review scope from the argument:

1. If the argument contains a file path:
   - Path starts with `backend/` or file ends with `.py` → **Python mode**: use Backend checklist only, run `mypy`, grep for `print(`
   - Path starts with `frontend/` or file ends with `.ts`/`.tsx` → **TypeScript mode**: use Frontend checklist only, run `npm run typecheck`, grep for `any`
   - Other paths → use both checklists
2. If no argument is provided:
   - Check `active.md` for the current Active Task component
   - If component mentions frontend/backend, use the corresponding mode
   - Otherwise, use both checklists

Set the `**Domain**` field in the report header to: `Python` | `TypeScript` | `Full Stack`

## 审查清单

### 1. 功能正确性

| 检查项 | 说明 |
|--------|------|
| 逻辑正确 | 代码逻辑是否正确 |
| 边界情况 | 是否处理边界情况 |
| 错误处理 | 错误是否正确处理 |

### 2. 代码质量

| 检查项 | 说明 |
|--------|------|
| 命名规范 | 变量/函数命名清晰 |
| 函数长度 | 函数是否过长 (< 50 行) |
| 代码重复 | 是否有重复代码 |
| 注释质量 | 关键逻辑有注释 |

### 3. 技术规范

#### Frontend (TypeScript)

| 检查项 | 标准 |
|--------|------|
| 类型定义 | 禁止 `any` |
| 组件规范 | 函数式组件 + Hooks |
| 错误处理 | Promise catch / try-catch |

#### Backend (Python)

| 检查项 | 标准 |
|--------|------|
| 类型注解 | 公共函数必须有注解 |
| Pydantic | 使用 Schema 验证 |
| 日志 | 使用 loguru，不使用 print |

### 4. 安全

| 检查项 | 标准 |
|--------|------|
| 敏感数据 | 不明文存储/日志 |
| 输入验证 | 使用 Pydantic 验证 |
| SQL 注入 | 使用 ORM 参数化 |

## 执行步骤

### Step 1: 确定审查范围

Detect the domain from the argument (see Context Detection above). This determines which checklist and static checks to run.

### Step 2: 读取代码

读取需要审查的文件。If a directory is given, use Glob to find all source files in that directory.

### Step 3: 静态检查

Run the checks that match the detected domain:

**TypeScript mode** (frontend):
```bash
cd frontend && npm run typecheck
```
Then use Grep to search for `any` type usages in the target files.

**Python mode** (backend):
```bash
cd backend && mypy .
```
Then use Grep to search for `print(` calls in the target files.

**Full Stack mode**: run both sets of checks.

### Step 4: 生成审查报告

```markdown
## 代码审查报告

**文件**: [路径]
**审查者**: [Agent name, auto-detected from context]
**域**: [Python | TypeScript | Full Stack]
**日期**: YYYY-MM-DD

---

### 审查清单

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 逻辑正确 | ✅ | - |
| 边界情况 | ⚠️ | 缺少空数组检查 |
| 错误处理 | ✅ | - |
| 命名规范 | ✅ | - |
| 类型定义 | ❌ | 第 42 行使用 any |
| ... | | |

---

### 问题

#### 🔴 高: [问题标题]

**位置**: [文件:行号]

**问题**:
```[代码]
[有问题的代码]
```

**建议**:
```[代码]
[修复后的代码]
```

---

### 总结

| 等级 | 数量 |
|------|------|
| 🔴 高 | 1 |
| 🟡 中 | 2 |
| 🟢 低 | 3 |

**结论**: ❌ 需要修改 / ⚠️ 需要审查 / ✅ 可以合并
```

## 示例：API 审查

```markdown
## 代码审查报告

**文件**: backend/api/account.py
**审查者**: [Agent name, auto-detected from context]
**域**: Python
**日期**: 2024-01-15

---

### 审查清单

| 检查项 | 状态 |
|--------|------|
| 逻辑正确 | ✅ |
| Pydantic Schema | ✅ |
| 错误处理 | ⚠️ |
| 日志记录 | ✅ |
| 权限检查 | ❌ |

---

### 问题

#### 🔴 高: 缺少权限检查

**位置**: backend/api/account.py:56

**问题**:
```python
@router.delete("/{account_id}")
async def delete_account(account_id: int, db: AsyncSession):
    # 任何人都可以删除任何账号！
    await service.delete(db, account_id)
```

**风险**: 用户可以删除他人账号

**建议**:
```python
@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    db: AsyncSession,
    current_user: User = Depends(get_current_user),
):
    # 检查权限
    if current_user.id != account_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权操作")

    await service.delete(db, account_id)
```

---

#### 🟡 中: 错误日志缺少上下文

**位置**: backend/api/account.py:34

**问题**:
```python
except Exception as e:
    logger.error(f"删除失败")  # 缺少 account_id
```

**建议**:
```python
except Exception as e:
    logger.error(f"删除账号失败: account_id={account_id}, error={e}")
```

---

### 总结

- 🔴 高: 1 (必须修复)
- 🟡 中: 1 (建议修复)
- 🟢 低: 0

**结论**: ❌ 需要修改后重新审查
```

## 输出

审查完成后更新 `production/session-state/active.md`：

```markdown
## 决策日志

### [日期] 代码审查 - account.py
- **状态**: 需要修改
- **问题**: 缺少权限检查
- **行动**: Backend Lead 修复后重新提交
```
