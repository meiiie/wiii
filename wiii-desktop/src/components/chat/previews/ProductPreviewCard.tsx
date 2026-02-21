/**
 * ProductPreviewCard — Product search result preview.
 * Sprint 166: Image thumbnail, title, VND price, rating stars, seller, platform badge.
 */
import { useRef, useEffect, useState } from "react";
import { ShoppingBag, Star } from "lucide-react";
import type { PreviewItemData } from "@/api/types";

interface Props {
  item: PreviewItemData;
  onClick?: () => void;
}

/** Lazy-load product image. */
function ProductImage({ src, alt }: { src: string; alt: string }) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const el = imgRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.src = src;
          obs.disconnect();
        }
      },
      { threshold: 0.1 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [src]);

  if (error) {
    return (
      <span className="w-16 h-16 rounded-md bg-[var(--surface-secondary,#f5f5f0)] flex items-center justify-center flex-shrink-0">
        <ShoppingBag size={20} className="text-[var(--text-tertiary,#999)]" />
      </span>
    );
  }

  return (
    <img
      ref={imgRef}
      alt={alt}
      onLoad={() => setLoaded(true)}
      onError={() => setError(true)}
      className={`w-16 h-16 rounded-md object-cover flex-shrink-0 transition-opacity ${loaded ? "opacity-100" : "opacity-0"}`}
    />
  );
}

/** Format VND price with dot separators. */
function formatVND(price: unknown): string | null {
  if (price == null) return null;
  const num = typeof price === "number" ? price : Number(price);
  if (isNaN(num)) return String(price);
  return num.toLocaleString("vi-VN") + "đ";
}

export function ProductPreviewCard({ item, onClick }: Props) {
  const price = item.metadata?.price;
  const rating = item.metadata?.rating as number | undefined;
  const seller = item.metadata?.seller as string | undefined;
  const platform = item.metadata?.platform as string | undefined;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-start gap-3 p-3 rounded-lg border border-[var(--border,#e5e5e0)]
        bg-[var(--surface,#ffffff)] hover:bg-[var(--surface-hover,#fafaf5)]
        transition-colors text-left w-full group
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
      aria-label={`Sản phẩm: ${item.title}`}
    >
      {/* Thumbnail */}
      {item.image_url ? (
        <ProductImage src={item.image_url} alt={item.title} />
      ) : (
        <span className="w-16 h-16 rounded-md bg-[var(--surface-secondary,#f5f5f0)] flex items-center justify-center flex-shrink-0">
          <ShoppingBag size={20} className="text-[var(--accent,#c2662d)]" />
        </span>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-medium text-[var(--text-primary,#1a1a1a)] line-clamp-2">
          {item.title}
        </h4>

        {/* Price */}
        {price != null && (
          <p className="text-sm font-bold text-[var(--accent,#c2662d)] mt-1">
            {formatVND(price)}
          </p>
        )}

        {/* Rating + seller */}
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          {rating != null && (
            <span className="inline-flex items-center gap-0.5 text-xs text-[var(--text-secondary,#6b6b6b)]">
              <Star size={12} className="text-amber-400 fill-amber-400" />
              {Number(rating).toFixed(1)}
            </span>
          )}
          {seller && (
            <span className="text-xs text-[var(--text-tertiary,#999)] truncate">
              {seller}
            </span>
          )}
          {platform && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--surface-secondary,#f5f5f0)] text-[var(--text-tertiary,#999)] flex-shrink-0 uppercase tracking-wide">
              {platform}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
