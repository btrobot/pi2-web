// Agent stop audit hook for pi5-offline-translator
// Logs agent completion with outcome summary
import { appendFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { findProjectRoot } from "./utils.ts";

const scriptPath = join(import.meta.dir!, "log-agent-stop.ts");
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
  // Unparseable input
}

const lastMessage = typeof data.last_assistant_message === "string"
  ? data.last_assistant_message
  : "";

const entry = {
  timestamp: new Date().toISOString(),
  event: "SubagentStop",
  session_id: data.session_id || "unknown",
  agent_id: data.agent_id || "unknown",
  agent_type: data.agent_type || data.agent_name || data.name || "unknown",
  summary: lastMessage.substring(0, 200) || null,
};

appendFileSync(auditLogFile, JSON.stringify(entry) + "\n", "utf-8");
