/**
 * Pyodide Runtime — lazy-loaded Python execution in Web Worker.
 * Sprint 167: "Không Gian Sáng Tạo"
 * Sprint 167b: Security & quality hardening (H-1, H-5, M-6)
 *
 * Runs Python code via Pyodide (WASM) in a dedicated Web Worker.
 * Non-blocking UI — Python execution can take 10+ seconds.
 * Captures stdout, stderr, matplotlib figures, and pandas DataFrames.
 *
 * Lazy loading: Pyodide core (~7 MB gzip) is only loaded on first use.
 */

import type { ExecutionResult } from "@/api/types";
export type { ExecutionResult };

type WorkerMessage =
  | { type: "ready" }
  | { type: "result"; payload: ExecutionResult }
  | { type: "error"; payload: string }
  | { type: "status"; payload: string };

/** H-5: Pyodide CDN URL — can be overridden for self-hosted deployments */
const PYODIDE_CDN_BASE = "https://cdn.jsdelivr.net/pyodide/v0.27.0/full";

/** H-5: Init timeout — 30s for Pyodide download + install */
const INIT_TIMEOUT_MS = 30_000;

export class PyodideRuntime {
  private worker: Worker | null = null;
  private ready = false;
  private initializing = false;
  private pendingResolve: ((result: ExecutionResult) => void) | null = null;
  private pendingReject: ((error: Error) => void) | null = null;
  private onStatus?: (message: string) => void;

  async initialize(onStatus?: (msg: string) => void): Promise<void> {
    if (this.ready) return;
    if (this.initializing) {
      // Wait for existing initialization
      return new Promise<void>((resolve) => {
        const check = setInterval(() => {
          if (this.ready) {
            clearInterval(check);
            resolve();
          }
        }, 100);
      });
    }

    // H-5: Offline detection
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      throw new Error("Không có kết nối mạng. Pyodide cần tải từ CDN.");
    }

    this.initializing = true;
    this.onStatus = onStatus;

    return new Promise<void>((resolve, reject) => {
      // H-5: 30s init timeout
      const initTimeout = setTimeout(() => {
        this.initializing = false;
        this.worker?.terminate();
        this.worker = null;
        reject(new Error("Tải Pyodide quá lâu (>30s). Kiểm tra kết nối mạng."));
      }, INIT_TIMEOUT_MS);

      try {
        // Create inline worker with Pyodide loading code
        const workerCode = `
          let pyodide = null;

          async function initPyodide() {
            importScripts("${PYODIDE_CDN_BASE}/pyodide.js");
            pyodide = await loadPyodide({
              indexURL: "${PYODIDE_CDN_BASE}/",
            });
            // Pre-install common packages
            await pyodide.loadPackagesFromImports("import micropip");
            const micropip = pyodide.pyimport("micropip");
            await micropip.install(["numpy", "pandas"]);
            // Note: matplotlib installed on-demand in execute
            postMessage({ type: "ready" });
          }

          async function execute(code) {
            const start = performance.now();
            const stdout = [];
            const stderr = [];
            const images = [];

            // Redirect stdout/stderr
            pyodide.runPython(\`
import sys
from io import StringIO
_stdout = StringIO()
_stderr = StringIO()
sys.stdout = _stdout
sys.stderr = _stderr
\`);

            let exitCode = 0;
            try {
              // Check if matplotlib is needed
              if (code.includes("matplotlib") || code.includes("plt.")) {
                try {
                  await pyodide.loadPackagesFromImports("import matplotlib");
                  pyodide.runPython(\`
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
\`);
                } catch(e) {
                  // matplotlib load error — continue without it
                }
              }

              await pyodide.runPythonAsync(code);

              // Capture matplotlib figures
              try {
                const figCount = pyodide.runPython(\`
import matplotlib.pyplot as plt
len(plt.get_fignums())
\`);
                if (figCount > 0) {
                  const b64 = pyodide.runPython(\`
import io, base64
buf = io.BytesIO()
plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
plt.close('all')
buf.seek(0)
base64.b64encode(buf.read()).decode('utf-8')
\`);
                  images.push(b64);
                }
              } catch(e) {
                // No matplotlib — skip
              }
            } catch(err) {
              exitCode = 1;
              stderr.push(String(err));
            }

            // Capture stdout/stderr
            const out = pyodide.runPython("_stdout.getvalue()");
            const err = pyodide.runPython("_stderr.getvalue()");
            if (out) stdout.push(out);
            if (err) stderr.push(err);

            // Restore streams
            pyodide.runPython(\`
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
\`);

            const executionTime = Math.round(performance.now() - start);

            return {
              stdout: stdout.join("\\n"),
              stderr: stderr.join("\\n"),
              exitCode,
              images,
              tables: [],
              executionTime,
            };
          }

          self.onmessage = async function(e) {
            const { type, payload } = e.data;
            if (type === "init") {
              try {
                postMessage({ type: "status", payload: "Đang tải Pyodide..." });
                await initPyodide();
              } catch(err) {
                postMessage({ type: "error", payload: String(err) });
              }
            } else if (type === "execute") {
              try {
                postMessage({ type: "status", payload: "Đang chạy Python..." });
                const result = await execute(payload);
                postMessage({ type: "result", payload: result });
              } catch(err) {
                postMessage({ type: "error", payload: String(err) });
              }
            }
          };
        `;

        // M-6: Revoke worker blob URL immediately after Worker creation
        const blob = new Blob([workerCode], { type: "application/javascript" });
        const blobUrl = URL.createObjectURL(blob);
        this.worker = new Worker(blobUrl);
        URL.revokeObjectURL(blobUrl);

        this.worker.onmessage = (e: MessageEvent<WorkerMessage>) => {
          const msg = e.data;
          if (msg.type === "ready") {
            clearTimeout(initTimeout);
            this.ready = true;
            this.initializing = false;
            resolve();
          } else if (msg.type === "result") {
            this.pendingResolve?.(msg.payload);
            this.pendingResolve = null;
            this.pendingReject = null;
          } else if (msg.type === "error") {
            if (this.initializing) {
              clearTimeout(initTimeout);
              this.initializing = false;
              reject(new Error(msg.payload));
            }
            this.pendingReject?.(new Error(msg.payload));
            this.pendingResolve = null;
            this.pendingReject = null;
          } else if (msg.type === "status") {
            this.onStatus?.(msg.payload);
          }
        };

        this.worker.onerror = (err) => {
          clearTimeout(initTimeout);
          this.initializing = false;
          reject(new Error(`Worker error: ${err.message}`));
        };

        // Start initialization
        this.worker.postMessage({ type: "init" });
      } catch (err) {
        clearTimeout(initTimeout);
        this.initializing = false;
        reject(err);
      }
    });
  }

  async execute(code: string): Promise<ExecutionResult> {
    if (!this.ready || !this.worker) {
      await this.initialize();
    }

    // H-1: Reject any pending execution (concurrent safety)
    if (this.pendingReject) {
      this.pendingReject(new Error("Cancelled: new execution started"));
      this.pendingResolve = null;
      this.pendingReject = null;
    }

    return new Promise<ExecutionResult>((resolve, reject) => {
      this.pendingResolve = resolve;
      this.pendingReject = reject;

      // 60s timeout
      const timer = setTimeout(() => {
        this.pendingReject?.(new Error("Execution timeout (60s)"));
        this.pendingResolve = null;
        this.pendingReject = null;
      }, 60_000);

      const origResolve = this.pendingResolve;
      this.pendingResolve = (result) => {
        clearTimeout(timer);
        origResolve(result);
      };
      const origReject = this.pendingReject;
      this.pendingReject = (err) => {
        clearTimeout(timer);
        origReject(err);
      };

      this.worker!.postMessage({ type: "execute", payload: code });
    });
  }

  destroy(): void {
    this.worker?.terminate();
    this.worker = null;
    this.ready = false;
    this.initializing = false;
  }
}

// Singleton instance — shared across all artifact panels
let _instance: PyodideRuntime | null = null;

export function getPyodideRuntime(): PyodideRuntime {
  if (!_instance) {
    _instance = new PyodideRuntime();
  }
  return _instance;
}
