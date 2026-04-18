// Session start hook for pi5-offline-translator
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { join } from "path";
import { findProjectRoot, info, ok, warn, header, git } from "./utils.ts";

const scriptPath = join(import.meta.dir!, "session-start.ts");
const projectRoot = findProjectRoot(scriptPath);
process.chdir(projectRoot);

header("Pi5 Offline Translator - Session Started");

// ============================================
// Project Structure Check
// ============================================

info("Checking project structure...");

const expectedDirs = ["models", "audio", "pipeline", "api", "storage", "hardware", "config", "tests"];
for (const dir of expectedDirs) {
  if (existsSync(join(projectRoot, dir))) {
    ok(`${dir}/: Found`);
  }
}

// ============================================
// Prerequisites Check
// ============================================

console.log();
info("Checking prerequisites...");

// Python
const pythonVersion = Bun.which("python") || Bun.which("python3");
if (pythonVersion) {
  const cmd = Bun.which("python") ? "python" : "python3";
  const output = Bun.spawnSync({ cmd: [cmd, "--version"], stdout: "pipe" });
  ok(`Python: ${output.stdout.toString().trim()}`);
} else {
  warn("Python: Not installed");
}

// ============================================
// Session State Recovery
// ============================================

console.log();
const stateDir = join(projectRoot, "production", "session-state");
const stateFile = join(stateDir, "active.md");
const templateFile = join(stateDir, "active.md.template");

if (existsSync(stateFile)) {
  header("ACTIVE SESSION STATE DETECTED", "yellow");
  console.log("A previous session left state at: production/session-state/active.md");
  console.log("Read this file to recover context and continue where you left off.");
  console.log();

  const content = readFileSync(stateFile, "utf-8");
  if (content) {
    console.log("Quick summary:");
    const lines = content.split("\n");
    lines.slice(0, 20).forEach((line) => console.log(`  ${line}`));
    if (lines.length > 20) {
      console.log(`  ... (${lines.length} total lines)`);
    }
  }
} else {
  info("No active session state found");
  console.log();

  if (!existsSync(stateDir)) {
    mkdirSync(stateDir, { recursive: true });
  }

  if (existsSync(templateFile)) {
    const template = readFileSync(templateFile, "utf-8");
    const timestamp = new Date().toISOString().replace("T", " ").substring(0, 19);
    const newState = template.replace(/\{timestamp\}/g, timestamp);
    writeFileSync(stateFile, newState, "utf-8");
    ok("Created new session state from template");
  } else {
    warn("Template not found: production/session-state/active.md.template");
  }
}

// ============================================
// Memory System Check
// ============================================

console.log();
const memoryDir = join(projectRoot, ".claude", "memory");
if (existsSync(memoryDir)) {
  header("Memory System");
  const memoryFiles = ["PROJECT.md", "PATTERNS.md", "DECISIONS.md"];
  for (const file of memoryFiles) {
    if (existsSync(join(memoryDir, file))) {
      ok(`${file}: Loaded`);
    }
  }
}

// ============================================
// Recent Git Activity
// ============================================

console.log();
info("Recent commits:");
const recentCommits = git(["log", "--oneline", "-5"]);
if (recentCommits) {
  recentCommits.split("\n").forEach((line) => console.log(`  ${line}`));
}

// ============================================
// Available Skills
// ============================================

console.log();
header("Available Skills");
console.log("  /sprint-plan          - Sprint planning");
console.log("  /task-breakdown       - Task breakdown");
console.log("  /architecture-review  - Architecture review");
console.log("  /code-review          - Code review");
console.log("  /bug-report           - Bug report");
console.log("  /release-checklist    - Release checklist");
console.log();

ok("Session initialized");
