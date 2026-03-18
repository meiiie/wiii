/**
 * CodeStudioCard — inline code streaming widget in chat (Claude Artifacts pattern).
 *
 * During streaming: shows code writing real-time in a scrollable area + spinner
 * After complete: collapsed card with title + "Mở Code Studio" button
 */
import { memo, useRef, useEffect } from "react";
import { Code2, Loader2, ExternalLink } from "lucide-react";
import { useCodeStudioStore } from "@/stores/code-studio-store";
import { useUIStore } from "@/stores/ui-store";

interface CodeStudioCardProps {
  sessionId: string;
}

export const CodeStudioCard = memo(function CodeStudioCard({
  sessionId,
}: CodeStudioCardProps) {
  const session = useCodeStudioStore((s) => s.sessions[sessionId]);
  const setActiveSession = useCodeStudioStore((s) => s.setActiveSession);
  const openCodeStudio = useUIStore((s) => s.openCodeStudio);
  const codeEndRef = useRef<HTMLDivElement>(null);

  const isStreaming = session?.status === "streaming";
  const lineCount = session?.code?.split("\n").length ?? 0;
  const codeLength = session?.code?.length ?? 0;

  useEffect(() => {
    if (!isStreaming) return;
    const rafId = requestAnimationFrame(() => {
      codeEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    });
    return () => cancelAnimationFrame(rafId);
  }, [isStreaming, codeLength]);

  if (!session) return null;

  const handleOpen = () => {
    setActiveSession(sessionId);
    openCodeStudio();
  };

  return (
    <article
      className="code-studio-card group/code-studio rounded-xl border border-border/60 overflow-hidden"
      data-status={isStreaming ? "streaming" : "complete"}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-surface-secondary/30 transition-colors"
        onClick={handleOpen}
      >
        <div className="w-7 h-7 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center shrink-0">
          <Code2 size={14} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-text truncate">
            {session.title}
          </div>
          <div className="text-[10px] text-text-tertiary">
            {isStreaming ? (
              <span className="text-[var(--accent)]">{lineCount} dòng · đang viết...</span>
            ) : (
              <span>{lineCount} dòng · {session.language}</span>
            )}
          </div>
        </div>
        {isStreaming ? (
          <Loader2 size={16} className="animate-spin text-[var(--accent)] shrink-0" />
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); handleOpen(); }}
            className="flex items-center gap-1 px-2 py-1 rounded-md bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors text-[11px] font-medium shrink-0"
          >
            <ExternalLink size={11} />
            Mở
          </button>
        )}
      </div>

      {/* Streaming code area — full inline view like Claude Artifacts */}
      {isStreaming && session.code && (
        <div className="border-t border-border/40">
          <div className="max-h-[320px] overflow-y-auto bg-[#0f172a] text-[#e2e8f0]">
            <pre className="p-3 text-[11px] leading-relaxed font-mono whitespace-pre-wrap break-all m-0">
              <code>{session.code}</code>
              <span className="inline-block w-[2px] h-[14px] bg-[var(--accent)] animate-pulse ml-0.5 align-middle" />
              <div ref={codeEndRef} />
            </pre>
          </div>
          {/* Bottom status bar */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1e293b] text-[10px] text-[#94a3b8] border-t border-[#334155]">
            <Loader2 size={10} className="animate-spin text-[var(--accent)]" />
            <span>{lineCount} dòng · {codeLength.toLocaleString()} bytes</span>
          </div>
        </div>
      )}
    </article>
  );
});
