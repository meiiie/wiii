/**
 * WebPreviewCard — Web search result preview.
 * Sprint 166: Google favicon, title, snippet, domain, date badge.
 */
import { Globe } from "lucide-react";
import type { PreviewItemData } from "@/api/types";

interface Props {
  item: PreviewItemData;
  onClick?: () => void;
}

/** Extract domain from URL, fallback to raw string. */
function extractDomain(url?: string): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function WebPreviewCard({ item, onClick }: Props) {
  const domain = extractDomain(item.url);
  const date = item.metadata?.date as string | undefined;
  const faviconUrl = domain
    ? `https://www.google.com/s2/favicons?domain=${domain}&sz=32`
    : null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-start gap-3 p-3 rounded-lg border border-[var(--border,#e5e5e0)]
        bg-[var(--surface,#ffffff)] hover:bg-[var(--surface-hover,#fafaf5)]
        transition-colors text-left w-full group
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
      aria-label={`Kết quả web: ${item.title}`}
    >
      {/* Favicon or globe icon */}
      <span className="w-8 h-8 rounded-md bg-[var(--surface-secondary,#f5f5f0)] flex items-center justify-center flex-shrink-0 overflow-hidden">
        {faviconUrl ? (
          <img
            src={faviconUrl}
            alt=""
            width={16}
            height={16}
            className="w-4 h-4"
            onError={(e) => {
              e.currentTarget.style.display = "none";
              e.currentTarget.parentElement?.classList.add("favicon-fallback");
            }}
          />
        ) : (
          <Globe size={16} className="text-[var(--text-tertiary,#999)]" />
        )}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-medium text-[var(--text-primary,#1a1a1a)] line-clamp-1 group-hover:text-[var(--accent,#c2662d)] transition-colors">
          {item.title}
        </h4>

        {item.snippet && (
          <p className="text-xs text-[var(--text-secondary,#6b6b6b)] mt-1 line-clamp-2">
            {item.snippet}
          </p>
        )}

        {/* Domain + date */}
        <div className="flex items-center gap-2 mt-1">
          {domain && (
            <span className="text-[11px] text-[var(--text-tertiary,#999)] truncate">
              {domain}
            </span>
          )}
          {date && (
            <span className="text-[10px] text-[var(--text-tertiary,#999)] flex-shrink-0">
              {date}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
