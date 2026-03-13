/**
 * SourceCitation — clickable source badges.
 * Sprint 107: Badges now open SourcesPanel with the selected source.
 * Sprint 211: Badge color overhaul — accent-based, bordered, refined hover.
 */
import { useState } from "react";
import type { SourceInfo } from "@/api/types";
import { useUIStore } from "@/stores/ui-store";

const MAX_VISIBLE = 5;

interface SourceCitationProps {
  sources: SourceInfo[];
}

export function SourceCitation({ sources }: SourceCitationProps) {
  const { selectSource, sourcesPanelOpen, toggleSourcesPanel } = useUIStore();
  const [showAll, setShowAll] = useState(false);

  if (!sources || sources.length === 0) return null;

  const handleClick = (index: number) => {
    selectSource(index);
    if (!sourcesPanelOpen) {
      toggleSourcesPanel();
    }
  };

  const visibleSources = showAll ? sources : sources.slice(0, MAX_VISIBLE);
  const hiddenCount = sources.length - MAX_VISIBLE;

  return (
    <div className="mt-3 space-y-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
        Nguồn tham khảo
      </div>
      <div className="flex flex-wrap gap-1.5">
        {visibleSources.map((source, i) => (
          <button
            key={i}
            onClick={() => handleClick(i)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-[var(--accent)]/8 text-[var(--accent)] border border-[var(--accent)]/15 text-xs cursor-pointer hover:bg-[var(--accent)]/15 hover:border-[var(--accent)]/30 transition-colors"
            title={source.title}
          >
            <span className="font-semibold">{i + 1}</span>
            <span className="truncate max-w-[200px]" title={source.title}>{source.title}</span>
            {source.page_number && (
              <span className="text-[10px] opacity-70">
                (tr. {source.page_number})
              </span>
            )}
          </button>
        ))}
        {!showAll && hiddenCount > 0 && (
          <button
            onClick={() => setShowAll(true)}
            className="inline-flex items-center px-2 py-1 rounded-md bg-[var(--surface-tertiary)] text-text-tertiary border border-[var(--border)] text-xs hover:text-text-secondary hover:bg-[var(--surface-secondary)] transition-colors"
            aria-label={`Xem thêm ${hiddenCount} nguồn`}
          >
            +{hiddenCount}
          </button>
        )}
        {showAll && sources.length > MAX_VISIBLE && (
          <button
            onClick={() => setShowAll(false)}
            className="inline-flex items-center px-2 py-1 rounded-md bg-[var(--surface-tertiary)] text-text-tertiary border border-[var(--border)] text-xs hover:text-text-secondary hover:bg-[var(--surface-secondary)] transition-colors"
            aria-label="Thu gọn danh sách nguồn"
          >
            Thu gọn
          </button>
        )}
      </div>
    </div>
  );
}
