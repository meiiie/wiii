import { useState, useCallback, useEffect, useMemo, useRef, useId } from "react";
import { Copy, Check, Play, Maximize2, Loader2, WrapText } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { RUNNABLE_LANGUAGES, PREVIEWABLE_LANGUAGES, getLanguageDisplayName } from "@/lib/code-languages";
import type { ArtifactData } from "@/api/types";
import { ShikiMinimalHighlighter } from "./ShikiMinimalHighlighter";

export { LANGUAGE_LABELS } from "@/lib/code-languages";

const SHIKI_THEMES = { light: "github-light", dark: "github-dark" } as const;
const SHIKI_DELAY = 150;
const HIGHLIGHT_CHARACTER_LIMIT = 100_000;
const HIGHLIGHT_LINE_LIMIT = 1_000;
const COLLAPSE_LINE_LIMIT = 200;
const PREVIEW_LINE_COUNT = 80;

function codeArtifactId(code: string): string {
  let hash = 0;
  for (let i = 0; i < Math.min(code.length, 200); i++) {
    hash = ((hash << 5) - hash + code.charCodeAt(i)) | 0;
  }
  return `code-${Math.abs(hash).toString(36)}`;
}

interface CodeBlockProps {
  code: string;
  language: string;
  streaming?: boolean;
}

export function CodeBlock({ code, language, streaming = false }: CodeBlockProps) {
  const [copyState, setCopyState] = useState<"idle" | "pending" | "success" | "error">("idle");
  const [wrap, setWrap] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const copyRequestRef = useRef(0);
  const copyPendingRef = useRef(false);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const codeRef = useRef(code);
  codeRef.current = code;
  const feedbackId = useId();
  const viewportId = useId();
  const langLower = language.toLowerCase();
  const isRunnable = RUNNABLE_LANGUAGES.has(langLower);
  const isPreviewable = PREVIEWABLE_LANGUAGES.has(langLower);
  const lines = useMemo(() => code.split("\n"), [code]);
  const lineCount = lines.length;
  const showActions = lineCount >= 2;
  const displayName = getLanguageDisplayName(language);
  const collapsed = lineCount > COLLAPSE_LINE_LIMIT && !expanded;
  const displayedCode = collapsed ? lines.slice(0, PREVIEW_LINE_COUNT).join("\n") : code;
  const largeCode = code.length > HIGHLIGHT_CHARACTER_LIMIT || lineCount > HIGHLIGHT_LINE_LIMIT;
  const highlight = !streaming && !largeCode;
  const copyLabel = copyState === "pending" ? "Đang sao chép" : copyState === "success" ? "Đã sao chép" : "Sao chép mã";
  const feedback = copyState === "error"
    ? "Chưa sao chép được. Chọn mã và sao chép thủ công, hoặc thử lại."
    : copyState === "success" ? "Đã sao chép toàn bộ mã."
      : copyState === "pending" ? "Đang sao chép mã…" : "";

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      copyRequestRef.current += 1;
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  useEffect(() => {
    copyRequestRef.current += 1;
    copyPendingRef.current = false;
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    setCopyState("idle");
  }, [code]);

  const handleCopy = useCallback(async () => {
    if (copyPendingRef.current) return;
    copyPendingRef.current = true;
    const request = ++copyRequestRef.current;
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    setCopyState("pending");
    const current = () => mountedRef.current && request === copyRequestRef.current && code === codeRef.current;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(code);
      if (current()) {
        setCopyState("success");
        copyTimerRef.current = setTimeout(() => {
          if (current()) setCopyState("idle");
        }, 2000);
      }
    } catch {
      if (current()) setCopyState("error");
    } finally {
      if (request === copyRequestRef.current) copyPendingRef.current = false;
    }
  }, [code]);

  const handleExpand = useCallback(() => {
    const artifactId = codeArtifactId(code);
    const artifact: ArtifactData = {
      artifact_type: isPreviewable ? "html" : "code", artifact_id: artifactId,
      title: language ? `${language.toUpperCase()} Code` : "Code", content: code,
      language: language || "", metadata: {},
    };
    useUIStore.getState().openArtifact(artifactId, artifact);
  }, [code, language, isPreviewable]);

  const handleRun = useCallback(async () => {
    if (!isRunnable || running) return;
    setRunning(true); setOutput(null); setError(null);
    try {
      const { getPyodideRuntime } = await import("@/lib/pyodide-runtime");
      const runtime = getPyodideRuntime();
      await runtime.initialize();
      const result = await runtime.execute(code);
      setOutput(result.stdout || null); setError(result.stderr || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally { setRunning(false); }
  }, [code, isRunnable, running]);

  return (
    <div className="wiii-code-block relative my-2 min-w-0 max-w-full overflow-hidden rounded-lg border border-[var(--border)] bg-white/50 dark:bg-white/5" data-wrap={wrap} data-testid="code-block">
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1.5 bg-border/30 px-3 py-2 text-xs text-text-secondary">
        <span className="max-w-full truncate rounded-md bg-surface-tertiary/80 px-2 py-0.5 font-mono font-medium" aria-label={`Ngôn ngữ: ${displayName}`}>{displayName}</span>
        <span className="text-[10px] text-text-tertiary">{lineCount} dòng</span>
        <div className="ml-auto flex max-w-full flex-wrap items-center gap-1.5">
          {showActions && isRunnable && (
            <button type="button" onClick={handleRun} disabled={running} className="flex min-h-7 items-center gap-1 rounded px-2 hover:bg-border/50 disabled:opacity-50" title="Chạy code Python" aria-label="Chạy code Python">
              {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}<span>Chạy</span>
            </button>
          )}
          {showActions && (
            <button type="button" onClick={handleExpand} className="flex min-h-7 items-center gap-1 rounded px-2 hover:bg-border/50" title="Mở trong sandbox" aria-label="Mở trong sandbox"><Maximize2 size={12} /><span>Sandbox</span></button>
          )}
          <button type="button" onClick={() => setWrap(value => !value)} aria-label="Ngắt dòng mã" aria-pressed={wrap} aria-controls={viewportId} className="flex min-h-7 items-center gap-1 rounded px-2 hover:bg-border/50 aria-pressed:bg-border/50"><WrapText size={14} /><span>Ngắt dòng</span></button>
          <button type="button" onClick={handleCopy} disabled={copyState === "pending"} aria-busy={copyState === "pending"} aria-label={copyLabel} aria-describedby={feedback ? feedbackId : undefined} className="flex min-h-7 items-center gap-1 rounded px-2 hover:bg-border/50 disabled:opacity-60" title="Sao chép toàn bộ mã">
            {copyState === "pending" ? <Loader2 size={14} className="animate-spin" /> : copyState === "success" ? <Check size={14} /> : <Copy size={14} />}<span>{copyState === "idle" || copyState === "error" ? "Sao chép" : copyLabel}</span>
          </button>
        </div>
      </div>
      {feedback && <p id={feedbackId} role="status" aria-live="polite" className={copyState === "error" ? "border-t border-[var(--border)] px-3 py-2 text-xs text-text-secondary" : "sr-only"}>{feedback}</p>}
      {streaming && <p className="px-3 pt-2 text-[11px] text-text-tertiary">Đang nhận mã…</p>}
      {largeCode && <p className="px-3 pt-2 text-[11px] text-text-tertiary">Mã lớn · hiển thị văn bản để cuộn mượt. Sao chép vẫn lấy toàn bộ mã.</p>}
      <div id={viewportId} className="wiii-code-block__viewport p-3 [&_.shiki]:!bg-transparent" role="region" aria-label={`Mã ${displayName}, ${lineCount} dòng`} tabIndex={0}>
        {highlight ? (
          <ShikiMinimalHighlighter language={langLower || "text"} theme={SHIKI_THEMES} delay={SHIKI_DELAY} showLineNumbers={lineCount >= 5 && !wrap} showLanguage={false} addDefaultStyles={false}>{displayedCode}</ShikiMinimalHighlighter>
        ) : <pre><code>{displayedCode}</code></pre>}
      </div>
      {lineCount > COLLAPSE_LINE_LIMIT && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] px-3 py-2 text-xs text-text-secondary">
          <span>{collapsed ? `${PREVIEW_LINE_COUNT} / ${lineCount} dòng` : `${lineCount} dòng`}</span>
          <button type="button" aria-expanded={!collapsed} aria-controls={viewportId} onClick={() => setExpanded(value => !value)} className="min-h-7 rounded px-2 hover:bg-border/50">{collapsed ? "Xem toàn bộ mã" : "Thu gọn mã"}</button>
        </div>
      )}
      {output && <div className="border-t border-border/50 px-4 py-2"><div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-text-tertiary">stdout</div><pre className="max-h-[200px] overflow-auto whitespace-pre-wrap font-mono text-xs text-green-600 dark:text-green-400">{output}</pre></div>}
      {error && <div className="border-t border-border/50 px-4 py-2"><div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-red-500">stderr</div><pre className="max-h-[150px] overflow-auto whitespace-pre-wrap font-mono text-xs text-red-600 dark:text-red-400">{error}</pre></div>}
    </div>
  );
}
