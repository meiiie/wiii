/**
 * CodeStudioCard — compact inline card in the chat rail during/after code generation.
 *
 * During streaming: progress bar + contextual phase message + code preview
 * After complete: title + "Mo Code Studio" button
 */
import { memo, useMemo } from "react";
import { Code2, Loader2, ExternalLink } from "lucide-react";
import { useCodeStudioStore } from "@/stores/code-studio-store";
import { useUIStore } from "@/stores/ui-store";

const LOADING_MESSAGES = [
  { threshold: 0, message: "Dang len ke hoach..." },
  { threshold: 15, message: "Dang thiet ke giao dien..." },
  { threshold: 35, message: "Dang viet logic xu ly..." },
  { threshold: 55, message: "Dang them controls tuong tac..." },
  { threshold: 75, message: "Dang kiem tra chat luong..." },
  { threshold: 90, message: "Sap xong roi..." },
];

function getLoadingMessage(progress: number): string {
  for (let i = LOADING_MESSAGES.length - 1; i >= 0; i--) {
    if (progress >= LOADING_MESSAGES[i].threshold) return LOADING_MESSAGES[i].message;
  }
  return LOADING_MESSAGES[0].message;
}

interface CodeStudioCardProps {
  sessionId: string;
}

export const CodeStudioCard = memo(function CodeStudioCard({
  sessionId,
}: CodeStudioCardProps) {
  const session = useCodeStudioStore((s) => s.sessions[sessionId]);
  const setActiveSession = useCodeStudioStore((s) => s.setActiveSession);
  const openCodeStudio = useUIStore((s) => s.openCodeStudio);

  if (!session) return null;

  const isStreaming = session.status === "streaming";
  const lineCount = session.code.split("\n").length;
  const progress =
    isStreaming && session.totalBytes > 0
      ? Math.round((session.code.length / session.totalBytes) * 100)
      : 100;

  const previewLines = useMemo(() => {
    if (!isStreaming || !session.code) return [];
    return session.code.split("\n").filter((l) => l.trim()).slice(-3);
  }, [isStreaming, session.code]);

  const handleOpen = () => {
    setActiveSession(sessionId);
    openCodeStudio();
  };

  return (
    <article
      className="code-studio-card group/code-studio"
      data-status={isStreaming ? "streaming" : "complete"}
    >
      <div className="flex items-center gap-3 px-3 py-2.5">
        <div className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center shrink-0">
          <Code2 size={15} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="text-[11px] text-text-tertiary uppercase tracking-wider">
            Code Studio
          </div>
          <div className="text-sm font-medium text-text truncate">
            {session.title}
          </div>
        </div>

        {isStreaming ? (
          <div className="text-right shrink-0">
            <div className="flex items-center gap-1.5 text-[var(--accent)]">
              <Loader2 size={14} className="animate-spin" />
              <span className="text-[11px]">{getLoadingMessage(progress)}</span>
            </div>
            <div className="text-[9px] text-text-tertiary mt-0.5">
              {lineCount} dong · {progress}%
            </div>
          </div>
        ) : (
          <button
            onClick={handleOpen}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors text-xs font-medium"
          >
            <ExternalLink size={12} />
            Mo
          </button>
        )}
      </div>

      {/* Progress bar during streaming */}
      {isStreaming && (
        <div className="px-3 pb-2">
          <div className="h-1 rounded-full bg-surface-tertiary overflow-hidden">
            <div
              className="h-full rounded-full bg-[var(--accent)] transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Code preview snippet during streaming */}
      {isStreaming && previewLines.length > 0 && (
        <div className="mx-3 mb-2 rounded bg-surface-tertiary/50 px-2 py-1.5 font-mono text-[10px] text-text-tertiary leading-tight overflow-hidden max-h-[3.6em]">
          {previewLines.map((line, i) => (
            <div key={i} className="truncate">{line}</div>
          ))}
        </div>
      )}
    </article>
  );
});
