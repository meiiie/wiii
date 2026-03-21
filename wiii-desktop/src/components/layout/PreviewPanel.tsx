/**
 * PreviewPanel — slide-in side panel showing expanded preview content.
 * Sprint 166: Follows SourcesPanel pattern.
 * Fixed right panel, Escape to close, expanded preview with full data.
 */
import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X, Eye, ExternalLink } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useChatStore } from "@/stores/chat-store";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { LazyImage } from "@/components/chat/PreviewCard";
import { slideInRight } from "@/lib/animations";
import type { PreviewItemData } from "@/api/types";

/** Shared content for both inline and overlay modes */
function PreviewPanelContent({
  previews,
  selected,
  selectedPreviewId,
  closePreview,
}: {
  previews: PreviewItemData[];
  selected: PreviewItemData | null;
  selectedPreviewId: string | null;
  closePreview: () => void;
}) {
  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0 preview-panel-shell__header">
        <div className="flex items-center gap-2">
          <Eye size={16} className="text-[var(--accent)]" />
          <span className="font-medium text-sm text-text">
            Xem trước
          </span>
          <span className="text-xs text-text-tertiary">
            ({previews.length})
          </span>
        </div>
        <button
          onClick={closePreview}
          className="p-1.5 rounded-md hover:bg-surface-tertiary text-text-secondary transition-colors"
          aria-label="Đóng panel xem trước"
        >
          <X size={16} />
        </button>
      </div>

      {/* Selected preview detail */}
      {selected ? (
        <ExpandedPreview item={selected} />
      ) : (
        <div className="flex flex-col items-center justify-center flex-1 text-text-tertiary text-sm p-4">
          <Eye size={32} className="mb-2 opacity-40" />
          <p>Chọn một thẻ xem trước để xem chi tiết.</p>
        </div>
      )}

      {/* Preview list */}
      {previews.length > 1 && (
        <div className="border-t border-border p-2 max-h-[35vh] overflow-y-auto">
          <div className="text-xs text-text-tertiary px-2 py-1 mb-1">
            Tất cả xem trước
          </div>
          <div className="space-y-1">
            {previews.map((p) => (
              <PreviewListItem
                key={p.preview_id}
                item={p}
                isSelected={selectedPreviewId === p.preview_id}
                onSelect={() => useUIStore.getState().openPreview(p.preview_id)}
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
}

export function PreviewPanel({ inline }: { inline?: boolean }) {
  const { previewPanelOpen, selectedPreviewId, closePreview } = useUIStore();
  const panelRef = useRef<HTMLDivElement>(null);

  // Get all previews from the last assistant message
  const previews = useChatStore((s) => {
    const conv = s.activeConversation();
    if (!conv) return [];
    for (let i = conv.messages.length - 1; i >= 0; i--) {
      const msg = conv.messages[i];
      if (msg.role === "assistant" && msg.previews && msg.previews.length > 0) {
        return msg.previews;
      }
    }
    // Also check streaming previews
    if (s.streamingPreviews.length > 0) return s.streamingPreviews;
    return [];
  });

  // Close on Escape
  useEffect(() => {
    if (!previewPanelOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closePreview();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [previewPanelOpen, closePreview]);

  const selected = selectedPreviewId
    ? previews.find((p) => p.preview_id === selectedPreviewId) ?? null
    : null;

  if (!previewPanelOpen) return null;

  const contentProps = { previews, selected, selectedPreviewId, closePreview };

  // Sprint 233: Inline mode — render directly inside resizable split panel
  if (inline) {
    return (
      <div ref={panelRef} className="h-full flex flex-col preview-panel-shell" role="complementary" aria-label="Xem trước nội dung">
        <PreviewPanelContent {...contentProps} />
      </div>
    );
  }

  // Mobile / overlay fallback — original fixed positioning
  return (
    <AnimatePresence>
      {previewPanelOpen && (
        <motion.div
          ref={panelRef}
          variants={slideInRight}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="fixed right-0 top-11 bottom-0 w-[420px] max-w-[90vw] border-l border-border shadow-xl z-40 flex flex-col preview-panel-shell"
          role="complementary"
          aria-label="Xem trước nội dung"
        >
          <PreviewPanelContent {...contentProps} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Expanded view of the selected preview */
function ExpandedPreview({ item }: { item: PreviewItemData }) {
  const isProduct = item.preview_type === "product";

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Large image */}
      {item.image_url && (
        <div className="rounded-lg overflow-hidden bg-surface-secondary">
          <LazyImage src={item.image_url} alt={item.title} />
        </div>
      )}

      {/* Title + type badge */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-[var(--accent)]/10 text-[var(--accent)]">
            {item.preview_type}
          </span>
          {item.citation_index != null && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[var(--source-badge)] text-[var(--source-text)]">
              [{item.citation_index}]
            </span>
          )}
          {isProduct && item.metadata?.platform != null && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-surface-secondary text-text-tertiary uppercase tracking-wider">
              {String(item.metadata.platform)}
            </span>
          )}
        </div>
        <h3 className="text-base font-semibold text-text leading-snug">
          {item.title}
        </h3>
      </div>

      {/* Product-specific: prominent price */}
      {isProduct && (item.metadata?.price != null || item.metadata?.extracted_price != null) && (
        <div className="text-xl font-bold text-[var(--accent)]">
          {String(item.metadata.extracted_price || item.metadata.price)}
        </div>
      )}

      {/* Snippet / description */}
      {item.snippet && (
        <div className="text-sm font-serif text-text-secondary leading-relaxed">
          <MarkdownRenderer content={item.snippet} />
        </div>
      )}

      {/* Product metadata grid */}
      {isProduct && item.metadata && (
        <div className="grid grid-cols-2 gap-2 text-sm">
          {item.metadata.seller != null && (
            <div>
              <span className="text-text-tertiary block text-xs">Người bán</span>
              <span className="text-text font-medium">{String(item.metadata.seller)}</span>
            </div>
          )}
          {item.metadata.rating != null && (
            <div>
              <span className="text-text-tertiary block text-xs">Đánh giá</span>
              <span className="text-text font-medium">{String(item.metadata.rating)} / 5 ★</span>
            </div>
          )}
          {item.metadata.sold_count != null && (
            <div>
              <span className="text-text-tertiary block text-xs">Đã bán</span>
              <span className="text-text font-medium">{String(item.metadata.sold_count)}</span>
            </div>
          )}
          {item.metadata.location != null && String(item.metadata.location) !== "" && (
            <div>
              <span className="text-text-tertiary block text-xs">Vị trí</span>
              <span className="text-text font-medium">{String(item.metadata.location)}</span>
            </div>
          )}
          {item.metadata.delivery != null && String(item.metadata.delivery) !== "" && (
            <div className="col-span-2">
              <span className="text-text-tertiary block text-xs">Giao hàng</span>
              <span className="text-text font-medium">{String(item.metadata.delivery)}</span>
            </div>
          )}
        </div>
      )}

      {/* Non-product metadata (original generic display) */}
      {!isProduct && item.metadata && Object.keys(item.metadata).length > 0 && (
        <div className="space-y-1.5">
          {item.metadata.price != null && (
            <div className="text-sm">
              <span className="text-text-tertiary">Giá: </span>
              <span className="font-semibold text-[var(--accent)]">
                {String(item.metadata.price)}
              </span>
            </div>
          )}
          {item.metadata.rating != null && (
            <div className="text-sm">
              <span className="text-text-tertiary">Đánh giá: </span>
              <span className="text-text">{String(item.metadata.rating)} / 5</span>
            </div>
          )}
          {item.metadata.platform != null && (
            <div className="text-sm">
              <span className="text-text-tertiary">Nền tảng: </span>
              <span className="text-text">{String(item.metadata.platform)}</span>
            </div>
          )}
          {item.metadata.relevance_score != null && (
            <div className="text-sm">
              <span className="text-text-tertiary">Độ liên quan: </span>
              <span className="text-text">{(Number(item.metadata.relevance_score) * 100).toFixed(0)}%</span>
            </div>
          )}
          {item.metadata.page_number != null && (
            <div className="text-sm">
              <span className="text-text-tertiary">Trang: </span>
              <span className="text-text">{String(item.metadata.page_number)}</span>
            </div>
          )}
        </div>
      )}

      {/* URL link — validate scheme to prevent javascript:/data: injection */}
      {item.url && /^https?:\/\//i.test(item.url) && (
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className={`inline-flex items-center gap-1.5 text-sm text-white
            ${isProduct ? "bg-[var(--accent)] hover:bg-[var(--accent)]/90 px-4 py-2 rounded-lg font-medium" : "text-[var(--accent)] hover:underline"}`}
        >
          <ExternalLink size={14} />
          {isProduct ? "Mở trên sàn" : "Mở liên kết gốc"}
        </a>
      )}
    </div>
  );
}

/** Compact list item for the preview list at the bottom */
function PreviewListItem({
  item,
  isSelected,
  onSelect,
}: {
  item: PreviewItemData;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
        isSelected
          ? "bg-[var(--accent)]/10 border border-[var(--accent)]/30"
          : "hover:bg-surface-tertiary border border-transparent"
      }`}
    >
      <div className="flex items-start gap-2">
        <span className="text-[10px] uppercase tracking-wider font-semibold px-1 py-0.5 rounded bg-surface-secondary text-text-tertiary shrink-0 mt-0.5">
          {item.preview_type}
        </span>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-text truncate">{item.title}</div>
          {item.snippet && !isSelected && (
            <div className="text-xs text-text-secondary mt-0.5 line-clamp-1">
              {item.snippet.slice(0, 100)}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
