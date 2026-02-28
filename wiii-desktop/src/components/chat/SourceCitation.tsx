/**
 * SourceCitation — clickable source badges.
 * Sprint 107: Badges now open SourcesPanel with the selected source.
 * Sprint 211: Badge color overhaul — accent-based, bordered, refined hover.
 */
import type { SourceInfo } from "@/api/types";
import { useUIStore } from "@/stores/ui-store";

interface SourceCitationProps {
  sources: SourceInfo[];
}

export function SourceCitation({ sources }: SourceCitationProps) {
  const { selectSource, sourcesPanelOpen, toggleSourcesPanel } = useUIStore();

  if (!sources || sources.length === 0) return null;

  const handleClick = (index: number) => {
    selectSource(index);
    if (!sourcesPanelOpen) {
      toggleSourcesPanel();
    }
  };

  return (
    <div className="mt-3 space-y-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
        Nguồn tham khảo
      </div>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source, i) => (
          <button
            key={i}
            onClick={() => handleClick(i)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-[var(--accent)]/8 text-[var(--accent)] border border-[var(--accent)]/15 text-xs cursor-pointer hover:bg-[var(--accent)]/15 hover:border-[var(--accent)]/30 transition-colors"
            title={source.content?.slice(0, 200)}
          >
            <span className="font-semibold">{i + 1}</span>
            <span className="truncate max-w-[200px]">{source.title}</span>
            {source.page_number && (
              <span className="text-[10px] opacity-70">
                (tr. {source.page_number})
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
