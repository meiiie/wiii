/**
 * SourceCitation — clickable source badges.
 * Sprint 107: Badges now open SourcesPanel with the selected source.
 * Sprint 211: Badge color overhaul — accent-based, bordered, refined hover.
 * Sprint 233: Compact list layout, 3 visible by default, "+N" expandable.
 */
import { useState } from "react";
import type { SourceInfo } from "@/api/types";
import { useUIStore } from "@/stores/ui-store";

const MAX_VISIBLE = 3;

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
    <div className="source-citation">
      <div className="source-citation__header">
        Nguồn tham khảo
      </div>
      <div className="source-citation__list">
        {visibleSources.map((source, i) => (
          <button
            key={i}
            onClick={() => handleClick(i)}
            className="source-citation__item"
            title={source.title}
          >
            <span className="source-citation__index">[{i + 1}]</span>
            <span className="source-citation__title">{source.title}</span>
            {source.page_number && (
              <span className="source-citation__page">
                tr. {source.page_number}
              </span>
            )}
          </button>
        ))}
      </div>
      {!showAll && hiddenCount > 0 && (
        <button
          onClick={() => setShowAll(true)}
          className="source-citation__expand"
          aria-label={`Xem thêm ${hiddenCount} nguồn`}
        >
          +{hiddenCount} thêm...
        </button>
      )}
      {showAll && sources.length > MAX_VISIBLE && (
        <button
          onClick={() => setShowAll(false)}
          className="source-citation__expand"
          aria-label="Thu gọn danh sách nguồn"
        >
          Thu gọn
        </button>
      )}
    </div>
  );
}
