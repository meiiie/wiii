/**
 * CodeStudioPanel — side panel for streaming code + live preview.
 *
 * Modeled on ArtifactPanel.tsx (same layout pattern).
 * Shows Code tab (streaming code display) and Preview tab (InlineVisualFrame).
 * Version bar for navigating between iterations.
 */
import { memo, useCallback, useState, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X, Copy, Check, Code2, Eye, Loader2, Download } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useCodeStudioStore } from "@/stores/code-studio-store";
import type { CodeStudioSession } from "@/stores/code-studio-store";
import { InlineVisualFrame } from "@/components/common/InlineVisualFrame";

type StudioTab = "code" | "preview";

export const CodeStudioPanel = memo(function CodeStudioPanel() {
  const { codeStudioPanelOpen, closeCodeStudio } = useUIStore();
  const activeSessionId = useCodeStudioStore((s) => s.activeSessionId);
  const sessions = useCodeStudioStore((s) => s.sessions);

  const session = activeSessionId ? sessions[activeSessionId] : null;

  if (!codeStudioPanelOpen || !session) return null;

  return (
    <AnimatePresence>
      <motion.div
        key="code-studio-panel"
        initial={{ x: "100%", opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: "100%", opacity: 0 }}
        transition={{ type: "spring", damping: 25, stiffness: 200 }}
        className="fixed right-0 top-[var(--titlebar-height,32px)] bottom-[var(--statusbar-height,24px)] w-[52vw] max-w-[860px] min-w-[420px] border-l border-border z-40 flex flex-col shadow-xl code-studio-panel"
      >
        <CodeStudioContent session={session} onClose={closeCodeStudio} />
      </motion.div>
    </AnimatePresence>
  );
});

const CodeStudioContent = memo(function CodeStudioContent({
  session,
  onClose,
}: {
  session: CodeStudioSession;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<StudioTab>("code");
  const switchVersion = useCodeStudioStore((s) => s.switchVersion);
  const isStreaming = session.status === "streaming";

  // Auto-switch to preview when code completes
  useEffect(() => {
    if (session.status === "complete") {
      setActiveTab("preview");
    }
  }, [session.status]);

  return (
    <>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border shrink-0 code-studio-panel__header">
        <div className="w-9 h-9 rounded-xl bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center shrink-0">
          <Code2 size={17} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-text truncate">{session.title}</div>
          <div className="flex items-center gap-2 mt-1 text-[11px] text-text-tertiary">
            <span className="uppercase tracking-[0.08em]">{session.language}</span>
            {isStreaming && (
              <span className="flex items-center gap-1 text-[var(--accent)]">
                <Loader2 size={10} className="animate-spin" />
                Dang tao...
              </span>
            )}
            {!isStreaming && (
              <span className="text-[var(--green)]">Da xong</span>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md hover:bg-surface-tertiary text-text-tertiary hover:text-text transition-colors"
          aria-label="Dong Code Studio"
        >
          <X size={16} />
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-border shrink-0">
        <TabButton
          icon={Code2}
          label="Code"
          active={activeTab === "code"}
          onClick={() => setActiveTab("code")}
        />
        <TabButton
          icon={Eye}
          label="Preview"
          active={activeTab === "preview"}
          onClick={() => setActiveTab("preview")}
          disabled={isStreaming}
        />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto min-h-0">
        {activeTab === "code" && <CodeTab session={session} />}
        {activeTab === "preview" && <PreviewTab session={session} />}
      </div>

      {/* Version bar */}
      {session.versions.length > 1 && (
        <div className="flex items-center gap-2 px-4 py-2 border-t border-border shrink-0 overflow-x-auto">
          {session.versions.map((v) => (
            <button
              key={v.version}
              onClick={() => switchVersion(session.sessionId, v.version)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                v.version === session.activeVersion
                  ? "bg-[var(--accent)] text-white"
                  : "bg-surface-tertiary text-text-secondary hover:bg-border"
              }`}
            >
              v{v.version}
            </button>
          ))}
        </div>
      )}
    </>
  );
});

function TabButton({
  icon: Icon,
  label,
  active,
  onClick,
  disabled,
}: {
  icon: typeof Code2;
  label: string;
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium transition-colors ${
        active
          ? "text-[var(--accent)]"
          : disabled
          ? "text-text-tertiary/40 cursor-not-allowed"
          : "text-text-tertiary hover:text-text-secondary"
      }`}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

function CodeTab({ session }: { session: CodeStudioSession }) {
  const [copied, setCopied] = useState(false);
  const codeEndRef = useRef<HTMLDivElement>(null);
  const isStreaming = session.status === "streaming";

  // Auto-scroll to bottom during streaming
  useEffect(() => {
    if (isStreaming && codeEndRef.current) {
      codeEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [session.code, isStreaming]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(session.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignore clipboard errors.
    }
  }, [session.code]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([session.code], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${session.title.replace(/\s+/g, "_").toLowerCase()}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }, [session.code, session.title]);

  const lineCount = session.code.split("\n").length;

  return (
    <div className="relative h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border/50 shrink-0">
        <span className="text-[10px] text-text-tertiary">
          {lineCount} dong · {session.code.length} bytes
          {isStreaming && session.totalBytes > 0 && (
            <> · {Math.round((session.code.length / session.totalBytes) * 100)}%</>
          )}
        </span>
        <div className="flex gap-1">
          <button
            onClick={handleCopy}
            disabled={isStreaming}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-surface-tertiary hover:bg-border text-text-secondary transition-colors disabled:opacity-40"
            title="Sao chep"
          >
            {copied ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
            {copied ? "Da chep" : "Copy"}
          </button>
          <button
            onClick={handleDownload}
            disabled={isStreaming}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-surface-tertiary hover:bg-border text-text-secondary transition-colors disabled:opacity-40"
            title="Tai xuong"
          >
            <Download size={12} />
          </button>
        </div>
      </div>

      {/* Code display */}
      <div className="flex-1 overflow-auto p-4 font-mono text-[13px] leading-relaxed code-studio-panel__code">
        <pre className="whitespace-pre-wrap break-words text-text-secondary">
          <code>{session.code}</code>
          {isStreaming && (
            <span className="code-studio-cursor" aria-hidden="true" />
          )}
        </pre>
        <div ref={codeEndRef} />
      </div>
    </div>
  );
}

function PreviewTab({ session }: { session: CodeStudioSession }) {
  if (session.status === "streaming") {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-tertiary py-16">
        <Loader2 size={32} className="mb-3 animate-spin opacity-50" />
        <p className="text-sm">Dang tao code, preview se hien sau khi hoan thanh.</p>
      </div>
    );
  }

  if (!session.code) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-tertiary py-16">
        <Eye size={32} className="mb-3 opacity-50" />
        <p className="text-sm">Khong co code de preview.</p>
      </div>
    );
  }

  return (
    <div className="h-full">
      <InlineVisualFrame
        html={session.code}
        title={session.title}
        sessionId={session.sessionId}
        className="w-full h-full"
      />
    </div>
  );
}
