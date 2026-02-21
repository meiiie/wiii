/**
 * DocumentPreviewCard — RAG source document preview.
 * Sprint 166: FileText icon, title, snippet, relevance bar, page badge, citation.
 */
import { FileText } from "lucide-react";
import type { PreviewItemData } from "@/api/types";

interface Props {
  item: PreviewItemData;
  onClick?: () => void;
}

export function DocumentPreviewCard({ item, onClick }: Props) {
  const relevance = (item.metadata?.relevance_score as number) ?? null;
  const pageNum = (item.metadata?.page_number as number) ?? item.metadata?.page as number ?? null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-start gap-3 p-3 rounded-lg border border-[var(--border,#e5e5e0)]
        bg-[var(--surface,#ffffff)] hover:bg-[var(--surface-hover,#fafaf5)]
        transition-colors text-left w-full group
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
      aria-label={`Nguồn tài liệu: ${item.title}`}
    >
      {/* Icon */}
      <span className="w-10 h-10 rounded-md bg-[var(--surface-secondary,#f5f5f0)] flex items-center justify-center flex-shrink-0">
        <FileText size={20} className="text-[var(--accent,#c2662d)]" />
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {item.citation_index != null && (
            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-[var(--accent,#c2662d)] text-white text-xs font-medium flex-shrink-0">
              {item.citation_index}
            </span>
          )}
          <h4 className="text-sm font-medium text-[var(--text-primary,#1a1a1a)] truncate">
            {item.title}
          </h4>
        </div>

        {item.snippet && (
          <p className="text-xs text-[var(--text-secondary,#6b6b6b)] mt-1 line-clamp-2">
            {item.snippet}
          </p>
        )}

        {/* Relevance bar + page badge */}
        <div className="flex items-center gap-2 mt-2">
          {relevance != null && (
            <div className="flex items-center gap-1.5 flex-1 min-w-0">
              <div className="flex-1 h-1.5 rounded-full bg-[var(--surface-secondary,#f5f5f0)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-[var(--accent,#c2662d)] transition-all"
                  style={{ width: `${Math.round(relevance * 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-[var(--text-tertiary,#999)] flex-shrink-0">
                {Math.round(relevance * 100)}%
              </span>
            </div>
          )}
          {pageNum != null && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--surface-secondary,#f5f5f0)] text-[var(--text-tertiary,#999)] flex-shrink-0">
              Tr. {pageNum}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
