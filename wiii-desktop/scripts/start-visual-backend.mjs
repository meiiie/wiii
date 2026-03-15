import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const backendDir = path.join(repoRoot, "maritime-ai-service");

const pythonCandidates = [
  process.env.WIII_PLAYWRIGHT_PYTHON,
  path.join(backendDir, ".venv", "Scripts", "python.exe"),
  path.join(backendDir, ".venv", "bin", "python"),
  "python",
].filter(Boolean);

const python = pythonCandidates.find((candidate) => candidate === "python" || existsSync(candidate));

if (!python) {
  console.error("Could not find a Python executable for the visual backend.");
  process.exit(1);
}

const child = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "warning"],
  {
    cwd: backendDir,
    stdio: "inherit",
    env: {
      ...process.env,
      ENABLE_STRUCTURED_VISUALS: "true",
      PYTHONIOENCODING: "utf-8",
    },
  },
);

const forwardSignal = (signal) => {
  if (!child.killed) {
    child.kill(signal);
  }
};

process.on("SIGINT", () => forwardSignal("SIGINT"));
process.on("SIGTERM", () => forwardSignal("SIGTERM"));
process.on("exit", () => forwardSignal("SIGTERM"));

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
