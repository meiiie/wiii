/**
 * ArtifactPanel — side panel for expanded artifact view.
 * Sprint 167: "Không Gian Sáng Tạo"
 * Sprint 167b: H-3 (blob leak), H-4 (iframeRef), M-3 (CSS vars), M-7 (narrowed deps)
 *
 * Tabs: Code | Preview | Output
 * Follows PreviewPanel pattern but wider (50vw).
 * Renders sandboxed iframe for HTML artifacts, code display for code.
 */
import { memo, useMemo, useCallback, useState, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X, Copy, Check, Code2, Eye, Terminal, Play } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useChatStore } from "@/stores/chat-store";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { wrapInSandboxHtml, createSandboxUrl, listenFromSandbox, escapeHtml } from "@/lib/artifact-sandbox";
import type { ArtifactData } from "@/api/types";

const TAB_ITEMS = [
  { id: "code" as const, label: "Code", icon: Code2 },
  { id: "preview" as const, label: "Xem trước", icon: Eye },
  { id: "output" as const, label: "Kết quả", icon: Terminal },
];

export const ArtifactPanel = memo(function ArtifactPanel() {
  const { artifactPanelOpen, selectedArtifactId, artifactActiveTab, closeArtifact, setArtifactTab, _ephemeralArtifact } = useUIStore();

  // M-7: Narrow dependencies — extract only what we need
  const streamingArtifacts = useChatStore((s) => s.streamingArtifacts);
  const messages = useChatStore((s) => s.activeConversation()?.messages);
  const messageCount = messages?.length ?? 0;

  const artifact = useMemo<ArtifactData | null>(() => {
    if (!selectedArtifactId) return null;
    // Sprint 168: Check ephemeral artifact first (from CodeBlock "Sandbox" button)
    if (_ephemeralArtifact && _ephemeralArtifact.artifact_id === selectedArtifactId) {
      return _ephemeralArtifact;
    }
    // Check streaming
    const streaming = streamingArtifacts.find((a) => a.artifact_id === selectedArtifactId);
    if (streaming) return streaming;
    // Check finalized messages
    if (messages) {
      for (const msg of messages) {
        const found = msg.artifacts?.find((a) => a.artifact_id === selectedArtifactId);
        if (found) return found;
      }
    }
    return null;
  }, [selectedArtifactId, streamingArtifacts, messages, messageCount, _ephemeralArtifact]);

  if (!artifactPanelOpen || !artifact) return null;

  return (
    <AnimatePresence>
      <motion.div
        key="artifact-panel"
        initial={{ x: "100%", opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: "100%", opacity: 0 }}
        transition={{ type: "spring", damping: 25, stiffness: 200 }}
        className="fixed right-0 top-[var(--titlebar-height,32px)] bottom-[var(--statusbar-height,24px)] w-[50vw] max-w-[800px] min-w-[400px] bg-surface border-l border-border z-40 flex flex-col shadow-xl"
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
          <Code2 size={16} className="text-[var(--accent)]" />
          <span className="text-sm font-medium text-text truncate flex-1">
            {artifact.title}
          </span>
          {artifact.language && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-tertiary text-text-secondary font-mono">
              {artifact.language}
            </span>
          )}
          <button
            onClick={closeArtifact}
            className="p-1.5 rounded-md hover:bg-surface-tertiary text-text-tertiary hover:text-text transition-colors"
            aria-label="Đóng panel artifact"
          >
            <X size={16} />
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-border shrink-0">
          {TAB_ITEMS.map((tab) => {
            const TabIcon = tab.icon;
            const isActive = artifactActiveTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setArtifactTab(tab.id)}
                className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
                  isActive
                    ? "border-[var(--accent)] text-[var(--accent)]"
                    : "border-transparent text-text-tertiary hover:text-text-secondary"
                }`}
              >
                <TabIcon size={14} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-auto">
          {artifactActiveTab === "code" && <CodeTab artifact={artifact} />}
          {artifactActiveTab === "preview" && <PreviewTab artifact={artifact} />}
          {artifactActiveTab === "output" && <OutputTab artifact={artifact} />}
        </div>
      </motion.div>
    </AnimatePresence>
  );
});

// ===== Code Tab =====

function CodeTab({ artifact }: { artifact: ArtifactData }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(artifact.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Silent fail
    }
  }, [artifact.content]);

  const codeBlock = `\`\`\`${artifact.language || ""}\n${artifact.content}\n\`\`\``;

  return (
    <div className="relative">
      {/* Copy button */}
      <div className="absolute top-2 right-2 z-10 flex gap-1">
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-surface-tertiary hover:bg-border text-text-secondary transition-colors"
          title="Sao chép"
        >
          {copied ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
          {copied ? "Đã sao chép" : "Sao chép"}
        </button>
      </div>

      {/* Code rendering */}
      <div className="p-4 text-sm">
        <MarkdownRenderer content={codeBlock} />
      </div>
    </div>
  );
}

// ===== Preview Tab =====

function PreviewTab({ artifact }: { artifact: ArtifactData }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeHeight, setIframeHeight] = useState(400);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  // H-3: Create and track blob URL properly — revoke previous on change
  useEffect(() => {
    // Revoke previous
    if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
    // Create new
    const isHtml = artifact.artifact_type === "html" || artifact.artifact_type === "react";
    const content = isHtml ? artifact.content : `<pre><code>${escapeHtml(artifact.content)}</code></pre>`;
    const html = wrapInSandboxHtml(content, artifact.title);
    const url = createSandboxUrl(html);
    blobUrlRef.current = url;
    setBlobUrl(url);
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [artifact.artifact_type, artifact.content, artifact.title]);

  // H-4: Listen for resize messages — validate source via iframeRef
  useEffect(() => {
    const cleanup = listenFromSandbox((msg) => {
      if (msg.type === "resize" && typeof (msg.payload as { height?: number })?.height === "number") {
        setIframeHeight(Math.min((msg.payload as { height: number }).height, 800));
      }
    }, iframeRef);
    return cleanup;
  }, []);

  if (!blobUrl) return null;

  return (
    <div className="p-4">
      <iframe
        ref={iframeRef}
        src={blobUrl}
        sandbox="allow-scripts"
        style={{ width: "100%", height: `${iframeHeight}px`, border: "none", borderRadius: "8px" }}
        className="bg-white"
        title={artifact.title}
      />
    </div>
  );
}

// ===== Output Tab =====

function OutputTab({ artifact }: { artifact: ArtifactData }) {
  const output = artifact.metadata?.output;
  const error = artifact.metadata?.error;
  const imageUrl = artifact.metadata?.image_url;

  if (!output && !error && !imageUrl) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-tertiary py-16">
        <Play size={32} className="mb-3 opacity-50" />
        <p className="text-sm">Nhấn "Chạy" để xem kết quả</p>
        <p className="text-xs mt-1 opacity-70">Kết quả thực thi sẽ hiển thị ở đây</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      {/* stdout */}
      {output && (
        <div>
          <div className="text-[10px] text-text-tertiary font-medium mb-1 uppercase tracking-wider">stdout</div>
          <pre className="bg-surface-secondary rounded-lg p-3 text-xs font-mono text-text-secondary overflow-auto max-h-[300px] whitespace-pre-wrap">
            {output}
          </pre>
        </div>
      )}

      {/* stderr */}
      {error && (
        <div>
          <div className="text-[10px] text-red-500 font-medium mb-1 uppercase tracking-wider">stderr</div>
          <pre className="bg-red-50 dark:bg-red-950/30 rounded-lg p-3 text-xs font-mono text-red-600 dark:text-red-400 overflow-auto max-h-[200px] whitespace-pre-wrap">
            {error}
          </pre>
        </div>
      )}

      {/* Chart/Image output */}
      {imageUrl && (
        <div>
          <div className="text-[10px] text-text-tertiary font-medium mb-1 uppercase tracking-wider">Output</div>
          <img
            src={typeof imageUrl === "string" && imageUrl.startsWith("data:") ? imageUrl : `data:image/png;base64,${imageUrl}`}
            alt="Execution output"
            className="rounded-lg max-w-full"
          />
        </div>
      )}
    </div>
  );
}
