/**
 * CodeArtifact — code display + execution.
 * Sprint 167: "Không Gian Sáng Tạo"
 *
 * Features:
 * - Syntax-highlighted code via MarkdownRenderer
 * - "Chạy" (Run) button for Python code (via Pyodide Web Worker)
 * - stdout/stderr/chart output display
 */
import { useState, useCallback } from "react";
import { Play, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import type { ArtifactData } from "@/api/types";

interface Props {
  artifact: ArtifactData;
  mode: "card" | "panel";
}

const EXECUTABLE_LANGUAGES = new Set(["python", "py", "python3"]);

export default function CodeArtifact({ artifact, mode }: Props) {
  const [output, setOutput] = useState<string>(artifact.metadata?.output || "");
  const [error, setError] = useState<string>(artifact.metadata?.error || "");
  const [images, setImages] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "running" | "success" | "error">(
    artifact.metadata?.execution_status === "success" ? "success" :
    artifact.metadata?.execution_status === "error" ? "error" : "idle"
  );
  const [statusMessage, setStatusMessage] = useState("");

  const isExecutable = EXECUTABLE_LANGUAGES.has(artifact.language?.toLowerCase() || "");

  const handleRun = useCallback(async () => {
    if (!isExecutable) return;

    setStatus("loading");
    setStatusMessage("Đang tải Pyodide...");
    setOutput("");
    setError("");
    setImages([]);

    try {
      const { getPyodideRuntime } = await import("@/lib/pyodide-runtime");
      const runtime = getPyodideRuntime();
      await runtime.initialize((msg) => setStatusMessage(msg));

      setStatus("running");
      setStatusMessage("Đang chạy Python...");

      const result = await runtime.execute(artifact.content);

      setOutput(result.stdout);
      setError(result.stderr);
      setImages(result.images);
      setStatus(result.exitCode === 0 ? "success" : "error");
      setStatusMessage(
        result.exitCode === 0
          ? `Hoàn thành (${result.executionTime}ms)`
          : "Lỗi thực thi"
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setStatus("error");
      // M-5: Timeout-specific UI feedback
      setStatusMessage(
        msg.includes("timeout") || msg.includes("Timeout") || msg.includes("quá lâu")
          ? "Quá thời gian (60s). Thử code ngắn hơn."
          : msg.includes("Cancelled")
          ? "Đã huỷ"
          : "Lỗi thực thi"
      );
    }
  }, [artifact.content, isExecutable]);

  const codeBlock = `\`\`\`${artifact.language || ""}\n${artifact.content}\n\`\`\``;

  if (mode === "card") {
    return (
      <div className="text-sm">
        <MarkdownRenderer content={codeBlock} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Code display */}
      <div className="text-sm">
        <MarkdownRenderer content={codeBlock} />
      </div>

      {/* Run button (Python only) */}
      {isExecutable && (
        <div className="flex items-center gap-2">
          <button
            onClick={handleRun}
            disabled={status === "loading" || status === "running"}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {status === "loading" || status === "running" ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            Chạy
          </button>
          {statusMessage && (
            <span className="text-xs text-text-tertiary flex items-center gap-1">
              {status === "success" && <CheckCircle2 size={12} className="text-green-500" />}
              {status === "error" && <XCircle size={12} className="text-red-500" />}
              {statusMessage}
            </span>
          )}
        </div>
      )}

      {/* Output */}
      {output && (
        <div>
          <div className="text-[10px] text-text-tertiary font-medium mb-1 uppercase tracking-wider">stdout</div>
          <pre className="bg-surface-secondary rounded-lg p-3 text-xs font-mono text-text-secondary overflow-auto max-h-[300px] whitespace-pre-wrap">
            {output}
          </pre>
        </div>
      )}

      {/* Error */}
      {error && (
        <div>
          <div className="text-[10px] text-red-500 font-medium mb-1 uppercase tracking-wider">stderr</div>
          <pre className="bg-red-50 dark:bg-red-950/30 rounded-lg p-3 text-xs font-mono text-red-600 dark:text-red-400 overflow-auto max-h-[200px] whitespace-pre-wrap">
            {error}
          </pre>
        </div>
      )}

      {/* Chart images */}
      {images.map((img, idx) => (
        <div key={idx}>
          <div className="text-[10px] text-text-tertiary font-medium mb-1 uppercase tracking-wider">
            Chart {images.length > 1 ? idx + 1 : ""}
          </div>
          <img
            src={`data:image/png;base64,${img}`}
            alt={`Chart output ${idx + 1}`}
            className="rounded-lg max-w-full bg-white"
          />
        </div>
      ))}
    </div>
  );
}
