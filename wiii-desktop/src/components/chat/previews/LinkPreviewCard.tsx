/**
 * LinkPreviewCard — URL with OG metadata preview.
 * Sprint 166: Large og_image, title, og_description snippet, domain.
 */
import { Link } from "lucide-react";
import type { PreviewItemData } from "@/api/types";

interface Props {
  item: PreviewItemData;
  onClick?: () => void;
}

/** Extract domain from URL. */
function extractDomain(url?: string): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function LinkPreviewCard({ item, onClick }: Props) {
  const domain = extractDomain(item.url);
  const ogDescription = (item.metadata?.og_description as string) ?? item.snippet;
  const hasImage = !!item.image_url;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col rounded-lg border border-[var(--border,#e5e5e0)] overflow-hidden
        bg-[var(--surface,#ffffff)] hover:bg-[var(--surface-hover,#fafaf5)]
        transition-colors text-left w-full group
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
      aria-label={`Liên kết: ${item.title}`}
    >
      {/* OG image — large, top-aligned */}
      {hasImage && (
        <div className="w-full h-36 bg-[var(--surface-secondary,#f5f5f0)] overflow-hidden">
          <img
            src={item.image_url!}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        </div>
      )}

      {/* Text content */}
      <div className="p-3 flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link size={14} className="text-[var(--text-tertiary,#999)] flex-shrink-0" />
          <h4 className="text-sm font-medium text-[var(--text-primary,#1a1a1a)] line-clamp-1">
            {item.title}
          </h4>
        </div>

        {ogDescription && (
          <p className="text-xs text-[var(--text-secondary,#6b6b6b)] mt-1 line-clamp-2">
            {ogDescription}
          </p>
        )}

        {domain && (
          <p className="text-[11px] text-[var(--text-tertiary,#999)] mt-1.5 truncate">
            {domain}
          </p>
        )}
      </div>
    </button>
  );
}
