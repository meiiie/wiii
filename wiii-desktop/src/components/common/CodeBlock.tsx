import { useState, useCallback } from "react";
import { Copy, Check, Play, Maximize2, Loader2 } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import {
  RUNNABLE_LANGUAGES,
  PREVIEWABLE_LANGUAGES,
  getLanguageDisplayName,
} from "@/lib/code-languages";
import type { ArtifactData } from "@/api/types";
import { ShikiMinimalHighlighter } from "./ShikiMinimalHighlighter";

// Re-export for backward compat (tests import from here)
export { LANGUAGE_LABELS } from "@/lib/code-languages";

/* ---------------------------------------------------------------------------
 * Constants
 * --------------------------------------------------------------------------- */
/** Shiki dual-theme — CSS vars handle light↔dark toggle (globals.css) */
const SHIKI_THEMES = { light: "github-light", dark: "github-dark" } as const;

/** Streaming throttle (ms) — prevents flicker during token streaming */
const SHIKI_DELAY = 150;

/** Minimum lines before showing line numbers */
const MIN_LINES_FOR_LINE_NUMBERS = 5;

/** Minimum lines before showing Sandbox/Run action buttons */
const MIN_LINES_FOR_ACTIONS = 2;

/* ---------------------------------------------------------------------------
 * Helpers
 * --------------------------------------------------------------------------- */

/** Generate a stable artifact ID from code content (for sandbox panel). */
function codeArtifactId(code: string): string {
  let hash = 0;
  for (let i = 0; i < Math.min(code.length, 200); i++) {
    hash = ((hash << 5) - hash + code.charCodeAt(i)) | 0;
  }
  return `code-${Math.abs(hash).toString(36)}`;
}

/* ---------------------------------------------------------------------------
 * Component
 * --------------------------------------------------------------------------- */
interface CodeBlockProps {
  code: string;
  language: string;
}

export function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const langLower = language.toLowerCase();
  const isRunnable = RUNNABLE_LANGUAGES.has(langLower);
  const isPreviewable = PREVIEWABLE_LANGUAGES.has(langLower);
  const lineCount = code.split("\n").length;
  const showActions = lineCount >= MIN_LINES_FOR_ACTIONS;
  const showLineNumbers = lineCount >= MIN_LINES_FOR_LINE_NUMBERS;
  const displayName = getLanguageDisplayName(language);

  /* -- Handlers ----------------------------------------------------------- */

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  const handleExpand = useCallback(() => {
    const artifactId = codeArtifactId(code);
    const artifact: ArtifactData = {
      artifact_type: isPreviewable ? "html" : "code",
      artifact_id: artifactId,
      title: language ? `${language.toUpperCase()} Code` : "Code",
      content: code,
      language: language || "",
      metadata: {},
    };
    useUIStore.getState().openArtifact(artifactId, artifact);
  }, [code, language, isPreviewable]);

  const handleRun = useCallback(async () => {
    if (!isRunnable || running) return;
    setRunning(true);
    setOutput(null);
    setError(null);
    try {
      const { getPyodideRuntime } = await import("@/lib/pyodide-runtime");
      const runtime = getPyodideRuntime();
      await runtime.initialize();
      const result = await runtime.execute(code);
      setOutput(result.stdout || null);
      setError(result.stderr || null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setRunning(false);
    }
  }, [code, isRunnable, running]);

  /* -- Render ------------------------------------------------------------- */

  return (
    <div className="relative group/code rounded-lg overflow-hidden bg-white/50 dark:bg-white/5 border border-[var(--border)] my-2">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-4 py-2 bg-border/30 text-text-secondary text-xs">
        <span
          className="rounded-md bg-surface-tertiary/80 px-2 py-0.5 font-medium font-mono text-text-secondary"
          aria-label={`Ngôn ngữ: ${displayName}`}
        >
          {displayName}
        </span>
        <span className="flex-1" />

        {showActions && isRunnable && (
          <button
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 disabled:opacity-50 transition-colors"
            title="Chạy code Python"
            aria-label="Chạy code Python"
          >
            {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            <span>Chạy</span>
          </button>
        )}

        {showActions && (
          <button
            onClick={handleExpand}
            className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-border/50 transition-colors"
            title="Mở trong sandbox"
            aria-label="Mở trong sandbox"
          >
            <Maximize2 size={12} />
            <span>Sandbox</span>
          </button>
        )}

        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-text transition-colors"
          title="Sao chép mã"
          aria-label={copied ? "Đã sao chép" : "Sao chép mã"}
        >
          {copied ? (
            <>
              <Check size={14} />
              <span>Đã sao chép!</span>
            </>
          ) : (
            <>
              <Copy size={14} />
              <span>Sao chép</span>
            </>
          )}
        </button>
      </div>

      {/* Code content — Shiki highlighted */}
      <div className="p-4 overflow-x-auto [&_.shiki]:!bg-transparent">
        <ShikiMinimalHighlighter
          language={langLower || "text"}
          theme={SHIKI_THEMES}
          delay={SHIKI_DELAY}
          showLineNumbers={showLineNumbers}
          showLanguage={false}
          addDefaultStyles={false}
        >
          {code}
        </ShikiMinimalHighlighter>
      </div>

      {/* Inline output — Python run results */}
      {output && (
        <div className="border-t border-border/50 px-4 py-2">
          <div className="text-[10px] text-text-tertiary font-medium mb-1 uppercase tracking-wider">stdout</div>
          <pre className="text-xs font-mono text-green-600 dark:text-green-400 whitespace-pre-wrap max-h-[200px] overflow-auto">
            {output}
          </pre>
        </div>
      )}
      {error && (
        <div className="border-t border-border/50 px-4 py-2">
          <div className="text-[10px] text-red-500 font-medium mb-1 uppercase tracking-wider">stderr</div>
          <pre className="text-xs font-mono text-red-600 dark:text-red-400 whitespace-pre-wrap max-h-[150px] overflow-auto">
            {error}
          </pre>
        </div>
      )}
    </div>
  );
}
