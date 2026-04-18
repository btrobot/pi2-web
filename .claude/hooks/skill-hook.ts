// Skill hook for pi5-offline-translator
// Automatically updates active.md when skills are invoked via the Skill tool

import { existsSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { findProjectRoot } from './utils.ts';

const input = await Bun.stdin.text();

const scriptPath = join(import.meta.dir!, 'skill-hook.ts');
const projectRoot = findProjectRoot(scriptPath);
const stateFile = join(projectRoot, 'production', 'session-state', 'active.md');

// Only proceed if active.md exists
if (!existsSync(stateFile)) {
  process.exit(0);
}

// Parse Skill tool input
// Skill tool sends: { "tool_name": "Skill", "input": { "skill": "code-review", "args": "..." } }
let skillName = '';
let skillArgs = '';
try {
  const data = JSON.parse(input);
  // Handle Skill tool format
  skillName = data.input?.skill || data.skill || '';
  skillArgs = data.input?.args || data.args || '';
  // Fallback: try legacy /command format from input string
  if (!skillName) {
    const raw = data.input?.command || data.input || data.command || '';
    if (typeof raw === 'string') {
      const match = raw.match(/^\/([\w-]+)(?:\s+(.+))?/);
      if (match) {
        skillName = match[1];
        skillArgs = match[2] || '';
      }
    }
  }
} catch {
  process.exit(0);
}

// Only track known project skills
const knownSkills = ['code-review', 'architecture-review', 'sprint-plan', 'task-breakdown', 'bug-report', 'release-checklist'];
if (!knownSkills.includes(skillName)) {
  process.exit(0);
}

// Read current active.md and normalize line endings
const rawContent = readFileSync(stateFile, 'utf-8');
const content = rawContent.replace(/\r\n/g, '\n');

// Build skill invocation entry
const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
const skillEntry = `| ${skillName} | ${timestamp} | running | - |`;

let updated = content;

// Replace placeholder row or append after last data row in Agent Invocations table
const placeholderRe = /\| \(No [^)]+\) \|[^\n]*\n/;
const placeholderMatch = content.match(placeholderRe);

if (placeholderMatch) {
  updated = content.replace(placeholderMatch[0], skillEntry + '\n');
} else {
  // Append after the last row in the Agent Invocations table
  // Find the table by looking for rows between "## Agent Invocations" and the next "##"
  const tableSection = content.match(/## Agent Invocations\n\n\|[^\n]+\n\|[^\n]+\n((?:\|[^\n]+\n)*)/);
  if (tableSection && tableSection[1]) {
    const lastRow = tableSection[1].trimEnd();
    updated = content.replace(lastRow, lastRow + '\n' + skillEntry);
  }
}

if (updated !== content) {
  writeFileSync(stateFile, updated, 'utf-8');
}
