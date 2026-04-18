// Pre-commit validation hook for pi5-offline-translator
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { findProjectRoot, info, warn, getStagedFiles, isGitRepo } from "./utils.ts";

// Find project root
const scriptPath = join(import.meta.dir!, "pre-commit.ts");
const projectRoot = findProjectRoot(scriptPath);
process.chdir(projectRoot);

info("Running pre-commit checks...");

// Check if in git repository
if (!isGitRepo()) {
  info("Not a git repository, skipping checks");
  process.exit(0);
}

// Get staged files
const files = getStagedFiles();
if (files.length === 0) {
  info("No staged files");
  process.exit(0);
}

info(`Checking ${files.length} file(s):`);
files.forEach((f) => console.log(`  - ${f}`));
console.log();

let warningCount = 0;

// Sensitive data patterns
const sensitivePatterns = [
  /password\s*=\s*["'][^"']+["']/i,
  /api_key\s*=\s*["'][^"']+["']/i,
  /secret\s*=\s*["'][^"']+["']/i,
  /sk-[a-zA-Z0-9]{20,}/,
  /cookie.*=\s*["'][^"']+["']/i,
];

// Check each file
for (const file of files) {
  const fullPath = join(projectRoot, file);
  if (!existsSync(fullPath)) continue;

  const content = readFileSync(fullPath, "utf-8");
  if (!content) continue;

  // Check sensitive data
  for (const pattern of sensitivePatterns) {
    if (pattern.test(content)) {
      warn(`May contain sensitive data: ${file}`);
      warningCount++;
      break;
    }
  }

  // Check Python for print statements
  if (file.match(/\.py$/)) {
    const lines = content.split("\n");
    const printUsages: number[] = [];
    lines.forEach((line, i) => {
      if (/^\s*print\s*\(/.test(line)) {
        printUsages.push(i + 1);
      }
    });
    if (printUsages.length > 0) {
      warn(`Python uses print: ${file}`);
      warn("  Please use logging module instead");
      warningCount++;
    }
  }
}

console.log();

if (warningCount > 0) {
  warn(`Found ${warningCount} warning(s)`);
  warn("Please review and confirm before committing");
} else {
  info("All checks passed");
}

process.exit(0);
