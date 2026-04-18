# Hook DSL Specification

Domain-Specific Language for defining quality gates and automation hooks.

> **Critical Note**: Hooks are executable scripts that define **structured validation pipelines** with input schemas, exit codes, error handling, and cross-platform compatibility.

## Runtime: Bun + TypeScript

This project uses **Bun** as the primary hook runtime with TypeScript.

### Why Bun?

| 特性 | Bun | PowerShell | Bash |
|------|-----|------------|------|
| 启动速度 | ~100x faster | 慢 | 基准 |
| TypeScript | 原生支持 | 需转换 | 需 ts-node |
| 跨平台 | ✅ | 仅 Windows | ✅ |
| 文件路径 | `import.meta.dir` | `$PSCommandPath` | `$BASH_SOURCE` |
| ANSI 颜色 | ✅ | 需终端支持 | ✅ |

### Prerequisites

```bash
# 安装 Bun
curl -fsSL https://bun.sh/install | bash

# Windows
powershell -c "irm bun.sh/install.ps1 | iex"
```

---

## File Structure

```
hooks/
├── utils.ts            # 共享工具函数
├── session-start.ts    # 会话开始
├── session-end.ts      # 会话结束
├── pre-commit.ts       # 提交前检查
├── log-agent.ts        # Agent 启动审计 (SubagentStart)
├── log-agent-stop.ts   # Agent 完成审计 (SubagentStop)
└── skill-hook.ts       # Skill 调用记录
```

### Settings Configuration

> **Important**: Ensure hooks run from the project root. The recommended pattern is `PROJECT_ROOT=$(git rev-parse --show-toplevel) && bun "$PROJECT_ROOT/.claude/hooks/xxx.ts"`.

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "command": "PROJECT_ROOT=$(git rev-parse --show-toplevel) && bun \"$PROJECT_ROOT/.claude/hooks/session-start.ts\"",
        "timeout": 15
      }]
    }],
    "Stop": [{
      "hooks": [{
        "command": "cd $PWD && bun .claude/hooks/session-end.ts",
        "timeout": 10
      }]
    }],
    "PreToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "command": "cd $PWD && bun .claude/hooks/pre-commit.ts",
        "timeout": 5
      }]
    }]
  }
}
```

---

## Hook Template

```typescript
// hook-name.ts: Brief description
import { join } from "path";
import { findProjectRoot, info, warn, header, ok } from "./utils.ts";

// 查找项目根目录（自动向上查找 .git）
const scriptPath = join(import.meta.dir!, "hook-name.ts");
const projectRoot = findProjectRoot(scriptPath);
process.chdir(projectRoot);

header("Hook Title");

// 执行业务逻辑
info("Message...");

ok("Complete");
process.exit(0);
```

---

## Utility Functions

共享工具在 `utils.ts` 中定义：

### 路径处理

```typescript
import { findProjectRoot } from "./utils.ts";

// 自动向上查找包含 .git 的目录作为项目根目录
const root = findProjectRoot(__filename);
process.chdir(root);
```

### 日志输出

```typescript
import { info, ok, warn, error, header } from "./utils.ts";

info("信息消息");           // [INFO] 消息 (蓝色)
ok("成功消息");            // [OK] 消息 (绿色)
warn("警告消息");          // [WARN] 消息 (黄色)
error("错误消息");         // [ERROR] 消息 (红色)
header("标题");            // ===== 标题 ===== (带空行)
```

### Git 操作

```typescript
import { git, isGitRepo, getStagedFiles, getUncommittedChanges } from "./utils.ts";

// 检查是否在 git 仓库
if (!isGitRepo()) {
  info("Not a git repository, skipping");
  process.exit(0);
}

// 获取暂存文件
const files = getStagedFiles();

// 获取未提交变更
const changes = getUncommittedChanges();
```

### 文件操作

```typescript
import { readFile } from "./utils.ts";

// 安全读取文件（失败返回 null）
const content = readFile("path/to/file");
```

---

## Hook Types

### Type 1: Session Hooks

```typescript
// session-start.ts
import { existsSync, join } from "path";
import { findProjectRoot, info, ok, warn, header, readFile } from "./utils.ts";

const projectRoot = findProjectRoot(join(import.meta.dir!, "session-start.ts"));
process.chdir(projectRoot);

header("Project - Session Started");

// 检查项目结构
if (existsSync(join(projectRoot, "frontend"))) {
  ok("Frontend: Found");
}

// 检查依赖
if (Bun.which("node")) {
  const v = Bun.spawnSync({ cmd: ["node", "--version"], stdout: "pipe" });
  ok(`Node.js: ${v.stdout}`);
}

ok("Session initialized");
process.exit(0);
```

### Type 2: PreToolUse Hooks

```typescript
// pre-tool.ts
// 检查工具调用是否允许

const input = await fetch(process.stdin).then(r => r.json());

const { tool_name, tool_input } = input;

if (tool_name === "Bash" && tool_input.command?.includes("rm -rf")) {
  error("Dangerous command blocked");
  process.exit(2);  // Block
}

process.exit(0);  // Allow
```

### Type 3: PreCommit Hooks

```typescript
// pre-commit.ts
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { findProjectRoot, info, warn, getStagedFiles, isGitRepo } from "./utils.ts";

const projectRoot = findProjectRoot(join(import.meta.dir!, "pre-commit.ts"));
process.chdir(projectRoot);

info("Running pre-commit checks...");

if (!isGitRepo()) {
  process.exit(0);
}

const files = getStagedFiles();
if (files.length === 0) {
  info("No staged files");
  process.exit(0);
}

// 检查敏感数据
const sensitivePatterns = [
  /password\s*=\s*["'][^"']+["']/i,
  /api_key\s*=\s*["'][^"']+["']/i,
  /sk-[a-zA-Z0-9]{20,}/,
];

let warningCount = 0;

for (const file of files) {
  const content = readFileSync(join(projectRoot, file), "utf-8");
  for (const pattern of sensitivePatterns) {
    if (pattern.test(content)) {
      warn(`Sensitive data detected: ${file}`);
      warningCount++;
      break;
    }
  }
}

if (warningCount > 0) {
  warn(`Found ${warningCount} warning(s)`);
}

process.exit(0);
```

---

## Exit Code Conventions

| Code | Meaning | Behavior |
|------|---------|----------|
| 0 | Success | Continue workflow |
| 1 | Warning | Continue with warning shown |
| 2 | Block | Block workflow, show error |

---

## Regex Patterns (Common Pitfalls)

### Problem: `\s*` Matches Newlines

```typescript
// 错误：\s 包括换行符，会跨行匹配
const bad = content.match(/Epic:\s*(.+)/);

// 正确：只匹配空格和 Tab
const good = content.match(/Epic:(?:[ \t]*)([^\n]*)/);
```

---

## Migration from PowerShell

### Before (PowerShell)

```powershell
#Requires -Version 5.1
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Join-Path $ScriptDir "..\.."
Set-Location $ProjectRoot

if (Test-Path "frontend") {
    Write-Host "[OK] Frontend found" -ForegroundColor Green
}
```

### After (Bun + TypeScript)

```typescript
import { existsSync, join } from "path";
import { findProjectRoot, ok } from "./utils.ts";

const projectRoot = findProjectRoot(join(import.meta.dir!, "session-start.ts"));
process.chdir(projectRoot);

if (existsSync(join(projectRoot, "frontend"))) {
  ok("Frontend: Found");
}
```

### Command Comparison

| PowerShell | Bun TypeScript |
|------------|----------------|
| `$MyInvocation.MyCommand.Path` | `import.meta.dir` |
| `Split-Path -Parent` | `dirname()` |
| `Join-Path` | `join()` |
| `Test-Path` | `existsSync()` |
| `Get-Content -Raw` | `readFileSync()` |
| `Write-Host` | `console.log()` |
| `exit 0` | `process.exit(0)` |

---

## Validation Checklist

### Script Validation

```bash
# 检查 TypeScript 语法
bun --bun tsc --noEmit hooks/your-hook.ts

# 直接运行测试
bun hooks/your-hook.ts
```

### Documentation Checklist

- [ ] TypeScript 类型定义
- [ ] 依赖说明（Bun 版本）
- [ ] Exit codes 文档化
- [ ] Error messages 清晰可操作

---

## Event Types

| Event | When | Common Use |
|-------|------|------------|
| SessionStart | 会话开始 | 加载上下文，显示状态 |
| SessionStop | 会话结束 | 保存状态，清理 |
| PreToolUse | 工具执行前 | 验证输入，阻止危险操作 |
| PostToolUse | 工具执行后 | 验证输出，记录指标 |
| PreCommit | git commit 前 | 运行检查，阻止不良提交 |

---

## Validation Rules

### MUST

- 使用 Bun + TypeScript 编写
- 使用 `findProjectRoot()` 确保工作目录正确
- 处理缺失依赖时优雅降级
- 清晰定义 exit codes

### MUST NOT

- 执行不受信任的代码
- 包含无限循环
- 产生过多输出
- 阻止合法操作

### SHOULD

- 提供类型定义
- 使用 `utils.ts` 中的共享函数
- 支持 ANSI 颜色输出
- 包含摘要输出

---

## Troubleshooting

### "Module not found" Error

**症状**:
```
error: Module not found ".claude/hooks/session-end.ts"
```

**原因**: Claude Code 可能在非项目根目录运行 hook，导致相对路径解析失败。

**解决**: 在 settings.json 中使用 `cd $PWD &&` 确保从项目根目录执行：

```json
{
  "hooks": {
    "Stop": [{
      "command": "cd $PWD && bun .claude/hooks/session-end.ts"
    }]
  }
}
```

### Hook 不生效

1. 检查 Bun 是否安装：`bun --version`
2. 检查 settings.json 格式是否正确
3. 测试单独运行：`bun .claude/hooks/session-start.ts`
4. 检查文件权限

### 颜色不显示

Windows PowerShell 5.1 不支持 ANSI 颜色。如需兼容，使用 Windows Terminal 或 PowerShell 7+。

