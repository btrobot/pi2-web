// Session end hook for pi5-offline-translator
import { existsSync, readFileSync, appendFileSync, writeFileSync, mkdirSync, unlinkSync, renameSync } from "fs";
import { join } from "path";
import { findProjectRoot, header, warn, ok, info, git } from "./utils.ts";

// Find project root using git repo location
const scriptPath = join(import.meta.dir!, "session-end.ts");
const projectRoot = findProjectRoot(scriptPath);
process.chdir(projectRoot);

header("Pi5 Offline Translator - Session Ending");

const timestamp = new Date().toISOString().replace(/[:.]/g, "-").substring(0, 19);
const stateFile = join(projectRoot, "production", "session-state", "active.md");
const sessionLogDir = join(projectRoot, "production", "session-logs");

// Ensure session log directory exists
if (!existsSync(sessionLogDir)) {
  mkdirSync(sessionLogDir, { recursive: true });
}

// ============================================
// Archive Active Session State
// ============================================

if (existsSync(stateFile)) {
  const stateContent = readFileSync(stateFile, "utf-8");
  if (stateContent && stateContent.trim()) {
    const archiveEntry = `\n## Archived Session State: ${timestamp}\n${stateContent}\n---\n\n`;

    appendFileSync(
      join(sessionLogDir, "session-log.md"),
      archiveEntry,
      "utf-8"
    );
    info("Session state archived to session-log.md");
  }
}

// ============================================
// Record Git Activity
// ============================================

console.log();

// Get recent commits from this session (last 8 hours)
const recentCommits = git(["log", "--oneline", "--since='8 hours ago'"]);
const uncommitted = git(["diff", "--name-only"]);

if (recentCommits || uncommitted) {
  const logEntry = `## Session End: ${timestamp}\n`;

  let entry = logEntry;

  if (recentCommits && recentCommits.trim()) {
    entry += "### Commits\n";
    entry += recentCommits.split("\n").map((l) => `  ${l}`).join("\n") + "\n";
  }

  if (uncommitted && uncommitted.trim()) {
    entry += "### Uncommitted Changes\n";
    entry += uncommitted.split("\n").map((f) => `  ${f}`).join("\n") + "\n";
  }

  entry += "---\n\n";
  appendFileSync(join(sessionLogDir, "session-log.md"), entry, "utf-8");
}

// ============================================
// Archive Agent Audit Log
// ============================================

const auditLogFile = join(sessionLogDir, "agent-audit.jsonl");
if (existsSync(auditLogFile)) {
  const auditContent = readFileSync(auditLogFile, "utf-8");
  if (auditContent && auditContent.trim()) {
    // Rename current log to timestamped archive
    const archiveName = `agent-audit-${timestamp}.jsonl`;
    renameSync(auditLogFile, join(sessionLogDir, archiveName));
    info(`Agent audit log archived to ${archiveName}`);
  }
}

// ============================================
// Check for Uncommitted Changes
// ============================================

const changes = git(["status", "--short"]);
if (changes && changes.trim()) {
  console.log();
  warn("Uncommitted changes detected:");
  console.log(changes);
}

// ============================================
// Cleanup Active State
// ============================================

if (existsSync(stateFile)) {
  // Delete active.md to clean up
  unlinkSync(stateFile);
  info("Active session state cleaned up");
}

// ============================================
// Show Next Steps
// ============================================

console.log();
header("Next Steps");
console.log("  1. Ensure all changes are committed before next session");
console.log("  2. Run /code-review to review code");
console.log("  3. Run /bug-report for any issues found");
console.log("  4. Check session-logs/session-log.md for history");
console.log();

ok("Session cleanup complete");
