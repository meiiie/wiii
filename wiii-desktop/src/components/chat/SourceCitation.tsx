/**
 * SourceCitation — clickable source badges.
 * Sprint 107: Badges now open SourcesPanel with the selected source.
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
      <div className="text-xs text-text-tertiary font-medium">Nguon tham khao:</div>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source, i) => (
          <button
            key={i}
            onClick={() => handleClick(i)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-[var(--source-badge)] text-[var(--source-text)] text-xs cursor-pointer hover:opacity-80 transition-opacity"
            title={source.content?.slice(0, 200)}
          >
            <span className="font-semibold">[{i + 1}]</span>
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
