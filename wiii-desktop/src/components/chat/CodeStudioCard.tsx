/**
 * CodeStudioCard — compact inline card in the chat rail during/after code generation.
 *
 * During streaming: progress bar + line count + "Dang tao..."
 * After complete: title + "Mo Code Studio" button
 */
import { memo } from "react";
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

  if (!session) return null;

  const isStreaming = session.status === "streaming";
  const lineCount = session.code.split("\n").length;
  const progress =
    isStreaming && session.totalBytes > 0
      ? Math.round((session.code.length / session.totalBytes) * 100)
      : 100;

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
          <div className="flex items-center gap-1.5 text-[var(--accent)]">
            <Loader2 size={14} className="animate-spin" />
            <span className="text-[10px]">{lineCount} dong</span>
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
    </article>
  );
});
