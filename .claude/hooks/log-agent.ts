// Agent audit hook for pi5-offline-translator
// Logs agent start/stop events as structured JSONL for audit trail
import { appendFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { findProjectRoot } from "./utils.ts";

const scriptPath = join(import.meta.dir!, "log-agent.ts");
const projectRoot = findProjectRoot(scriptPath);

const sessionLogDir = join(projectRoot, "production", "session-logs");
const auditLogFile = join(sessionLogDir, "agent-audit.jsonl");

if (!existsSync(sessionLogDir)) {
  mkdirSync(sessionLogDir, { recursive: true });
}

const input = await Bun.stdin.text();

let data: Record<string, unknown> = {};
try {
  data = JSON.parse(input);
} catch {
  // Unparseable input, log minimal entry
}

const entry = {
  timestamp: new Date().toISOString(),
  event: "SubagentStart",
  session_id: data.session_id || "unknown",
  agent_id: data.agent_id || "unknown",
  agent_type: data.agent_type || data.agent_name || data.name || "unknown",
};

appendFileSync(auditLogFile, JSON.stringify(entry) + "\n", "utf-8");
