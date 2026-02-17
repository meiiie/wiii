/**
 * SourcesPanel — slide-in side panel showing full source content.
 * Sprint 107: Wired to useUIStore sourcesPanelOpen/selectedSourceIndex.
 *
 * Displays the list of sources from the last assistant message,
 * with the selected source expanded to show full content.
 */
import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X, FileText, ExternalLink } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useChatStore } from "@/stores/chat-store";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { slideInRight } from "@/lib/animations";
import type { SourceInfo } from "@/api/types";

export function SourcesPanel() {
  const { sourcesPanelOpen, selectedSourceIndex, toggleSourcesPanel, selectSource } =
    useUIStore();
  const panelRef = useRef<HTMLDivElement>(null);

  // Get sources from the last assistant message that has them
  const sources = useChatStore((s) => {
    const conv = s.activeConversation();
    if (!conv) return [];
    // Walk backwards to find the latest message with sources
    for (let i = conv.messages.length - 1; i >= 0; i--) {
      const msg = conv.messages[i];
      if (msg.role === "assistant" && msg.sources && msg.sources.length > 0) {
        return msg.sources;
      }
    }
    return [];
  });

  // Close on Escape
  useEffect(() => {
    if (!sourcesPanelOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") toggleSourcesPanel();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [sourcesPanelOpen, toggleSourcesPanel]);

  const selected =
    selectedSourceIndex !== null && sources[selectedSourceIndex]
      ? sources[selectedSourceIndex]
      : null;

  return (
    <AnimatePresence>
      {sourcesPanelOpen && (
        <motion.div
          ref={panelRef}
          variants={slideInRight}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="fixed right-0 top-0 bottom-0 w-[360px] max-w-[90vw] bg-surface border-l border-border shadow-xl z-40 flex flex-col"
          role="complementary"
          aria-label="Nguồn tham khảo"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-[var(--accent)]" />
              <span className="font-medium text-sm text-text">
                Nguồn tham khảo
              </span>
              <span className="text-xs text-text-tertiary">
                ({sources.length})
              </span>
            </div>
            <button
              onClick={toggleSourcesPanel}
              className="p-1.5 rounded-md hover:bg-surface-tertiary text-text-secondary transition-colors"
              aria-label="Đóng panel nguồn"
            >
              <X size={16} />
            </button>
          </div>

          {/* Source list */}
          <div className="flex-1 overflow-y-auto">
            {sources.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-text-tertiary text-sm">
                <FileText size={32} className="mb-2 opacity-40" />
                <p>Mình chưa tìm được nguồn cho câu hỏi này.</p>
              </div>
            ) : (
              <div className="p-2 space-y-1">
                {sources.map((source, i) => (
                  <SourceItem
                    key={i}
                    index={i}
                    source={source}
                    isSelected={selectedSourceIndex === i}
                    onSelect={() =>
                      selectSource(selectedSourceIndex === i ? null : i)
                    }
                  />
                ))}
              </div>
            )}
          </div>

          {/* Selected source detail */}
          <AnimatePresence>
            {selected && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1, transition: { duration: 0.2 } }}
                exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
                className="border-t border-border overflow-hidden"
              >
                <div className="p-4 max-h-[40vh] overflow-y-auto">
                  <div className="text-xs font-medium text-text-tertiary mb-2">
                    Nội dung trích dẫn:
                  </div>
                  <div className="text-sm font-serif text-text">
                    <MarkdownRenderer content={selected.content} />
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SourceItem({
  index,
  source,
  isSelected,
  onSelect,
}: {
  index: number;
  source: SourceInfo;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors ${
        isSelected
          ? "bg-[var(--accent)]/10 border border-[var(--accent)]/30"
          : "hover:bg-surface-tertiary border border-transparent"
      }`}
    >
      <div className="flex items-start gap-2">
        <span
          className={`inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold shrink-0 mt-0.5 ${
            isSelected
              ? "bg-[var(--accent)] text-white"
              : "bg-[var(--source-badge)] text-[var(--source-text)]"
          }`}
        >
          {index + 1}
        </span>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-text truncate">{source.title}</div>
          {source.page_number && (
            <div className="text-[11px] text-text-tertiary mt-0.5">
              Trang {source.page_number}
            </div>
          )}
          {source.content && !isSelected && (
            <div className="text-xs text-text-secondary mt-1 line-clamp-2">
              {source.content.slice(0, 150)}
              {source.content.length > 150 ? "..." : ""}
            </div>
          )}
        </div>
        {source.document_id && (
          <ExternalLink size={12} className="shrink-0 text-text-tertiary mt-1" />
        )}
      </div>
    </button>
  );
}
