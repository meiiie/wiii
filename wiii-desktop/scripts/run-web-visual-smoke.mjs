import { existsSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");

const candidates = [
  process.env.WIII_PLAYWRIGHT_PYTHON,
  path.join(repoRoot, "maritime-ai-service", ".venv", "Scripts", "python.exe"),
  path.join(repoRoot, "maritime-ai-service", ".venv", "bin", "python"),
  "python",
].filter(Boolean);

const python = candidates.find((candidate) => candidate === "python" || existsSync(candidate));

if (!python) {
  console.error("Could not find a Python executable for web_visual_smoke.py");
  process.exit(1);
}

const smokeScript = path.join(__dirname, "web_visual_smoke.py");
const result = spawnSync(python, [smokeScript, ...process.argv.slice(2)], {
  stdio: "inherit",
  cwd: repoRoot,
  env: {
    ...process.env,
    PYTHONUTF8: "1",
  },
});

if (typeof result.status === "number") {
  process.exit(result.status);
}

process.exit(1);
