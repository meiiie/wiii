/**
 * PreviewGroup — Horizontal scrollable container of PreviewCards.
 * Sprint 166: Renders items[] from PreviewBlockData.
 * Grid: 1-col on narrow, 2-col on wide viewports.
 * Keyboard: ArrowLeft/Right to navigate, Enter to open panel.
 */
import { useRef, useCallback } from "react";
import type { PreviewBlockData } from "@/api/types";
import { useUIStore } from "@/stores/ui-store";
import { PreviewCard } from "./PreviewCard";

interface PreviewGroupProps {
  block: PreviewBlockData;
  onPreviewClick?: (previewId: string) => void;
}

export function PreviewGroup({ block, onPreviewClick }: PreviewGroupProps) {
  const openPreview = useUIStore((s) => s.openPreview);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const container = containerRef.current;
      if (!container) return;

      const cards = container.querySelectorAll<HTMLElement>("button");
      const focused = document.activeElement;
      const idx = Array.from(cards).indexOf(focused as HTMLElement);

      if (e.key === "ArrowRight" && idx < cards.length - 1) {
        e.preventDefault();
        cards[idx + 1]?.focus();
      } else if (e.key === "ArrowLeft" && idx > 0) {
        e.preventDefault();
        cards[idx - 1]?.focus();
      }
    },
    [],
  );

  if (!block.items || block.items.length === 0) return null;

  return (
    <div
      ref={containerRef}
      className="grid grid-cols-1 sm:grid-cols-2 gap-2 my-2"
      role="list"
      aria-label="Nội dung xem trước"
      onKeyDown={handleKeyDown}
    >
      {block.items.map((item) => (
        <div key={item.preview_id} role="listitem">
          <PreviewCard
            item={item}
            onClick={() => {
              onPreviewClick?.(item.preview_id);
              openPreview(item.preview_id);
            }}
          />
        </div>
      ))}
    </div>
  );
}
