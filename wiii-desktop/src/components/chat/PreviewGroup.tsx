/**
 * PreviewGroup — Horizontal scrollable carousel of PreviewCards.
 * Sprint 166: Initial grid layout.
 * Sprint 200: Upgraded to horizontal snap-scroll carousel with nav arrows.
 *
 * Product previews → horizontal carousel (220px cards).
 * Document/web previews → original 2-col grid.
 * Keyboard: ArrowLeft/Right to navigate, Enter to open panel.
 */
import { useRef, useCallback, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
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
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Determine if this is a product carousel (all items are product type)
  const isProductCarousel =
    block.items.length > 0 &&
    block.items.every((item) => item.preview_type === "product");

  // Track scroll state for arrow visibility
  const updateScrollState = useCallback(() => {
    const el = containerRef.current;
    if (!el || !isProductCarousel) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, [isProductCarousel]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !isProductCarousel) return;
    updateScrollState();
    el.addEventListener("scroll", updateScrollState, { passive: true });
    // Also update on resize
    const ro = new ResizeObserver(updateScrollState);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", updateScrollState);
      ro.disconnect();
    };
  }, [isProductCarousel, updateScrollState, block.items.length]);

  const scrollBy = useCallback(
    (direction: "left" | "right") => {
      const el = containerRef.current;
      if (!el) return;
      const scrollAmount = 240; // ~1 card width + gap
      el.scrollBy({
        left: direction === "right" ? scrollAmount : -scrollAmount,
        behavior: "smooth",
      });
    },
    [],
  );

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

  // Product carousel layout
  if (isProductCarousel) {
    return (
      <div className="relative group/carousel my-2">
        {/* Scroll container */}
        <div
          ref={containerRef}
          className="flex gap-3 overflow-x-auto snap-x snap-mandatory scroll-smooth
            pb-2 -mx-1 px-1 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent"
          role="region"
          aria-roledescription="carousel"
          aria-label="Kết quả tìm kiếm sản phẩm"
          onKeyDown={handleKeyDown}
        >
          {block.items.map((item, idx) => (
            <div
              key={item.preview_id}
              role="group"
              aria-roledescription="slide"
              aria-label={`Sản phẩm ${idx + 1} trên ${block.items.length}`}
              className="snap-start flex-shrink-0 w-[220px]"
            >
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

        {/* Left arrow */}
        {canScrollLeft && (
          <button
            onClick={() => scrollBy("left")}
            className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1
              w-8 h-8 rounded-full bg-[var(--surface,#fff)] border border-[var(--border,#e5e5e0)]
              shadow-md flex items-center justify-center
              opacity-0 group-hover/carousel:opacity-100 transition-opacity z-10
              hover:bg-[var(--surface-hover,#fafaf5)]"
            aria-label="Cuộn sang trái"
          >
            <ChevronLeft size={16} className="text-[var(--text-secondary,#6b6b6b)]" />
          </button>
        )}

        {/* Right arrow */}
        {canScrollRight && (
          <button
            onClick={() => scrollBy("right")}
            className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1
              w-8 h-8 rounded-full bg-[var(--surface,#fff)] border border-[var(--border,#e5e5e0)]
              shadow-md flex items-center justify-center
              opacity-0 group-hover/carousel:opacity-100 transition-opacity z-10
              hover:bg-[var(--surface-hover,#fafaf5)]"
            aria-label="Cuộn sang phải"
          >
            <ChevronRight size={16} className="text-[var(--text-secondary,#6b6b6b)]" />
          </button>
        )}
      </div>
    );
  }

  // Default grid layout for document/web previews
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
