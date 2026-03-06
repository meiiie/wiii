/**
 * ProductPreviewCard — Product search result card.
 * Sprint 166: Initial list-style (64px thumb).
 * Sprint 200: Upgraded to full card style (220×150 image, prominent price).
 *
 * Layout:
 * ┌─────────────────────┐
 * │ [Platform]           │  ← badge overlay top-left
 * │   [Product Image]    │  ← 220×150px, object-fit: cover
 * ├─────────────────────┤
 * │ Product Title (2     │
 * │ lines max)           │
 * │ ★ 4.8  |  Đã bán 250│
 * │ ──────────────────── │
 * │ 1,500,000đ           │  ← Bold accent color
 * │ Giao trong 2 ngày    │  ← Delivery info (if available)
 * └─────────────────────┘
 */
import { useRef, useEffect, useState } from "react";
import { ShoppingBag, Star } from "lucide-react";
import type { PreviewItemData } from "@/api/types";

interface Props {
  item: PreviewItemData;
  onClick?: () => void;
}

/** Platform label mapping for display. */
const PLATFORM_LABELS: Record<string, string> = {
  google_shopping: "Google",
  shopee: "Shopee",
  tiktok_shop: "TikTok",
  lazada: "Lazada",
  facebook_marketplace: "Facebook",
  facebook_search: "Facebook",
  facebook_group: "FB Group",
  facebook_groups_auto: "FB Groups",
  all_web: "Web",
  instagram: "Instagram",
  websosanh: "WebSoSánh",
  international: "Quốc tế",
  dealer: "Đại lý",
  "1688": "1688",
  taobao: "Taobao",
  aliexpress: "AliExpress",
  amazon: "Amazon",
};

/** Lazy-load product image with full-width card style. */
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
      <div className="w-full h-[140px] bg-gradient-to-br from-[var(--surface-secondary,#f5f5f0)] to-[var(--surface-tertiary,#e8e8e3)] flex items-center justify-center">
        <ShoppingBag size={32} className="text-[var(--text-tertiary,#999)]" />
      </div>
    );
  }

  return (
    <img
      ref={imgRef}
      alt={alt}
      onLoad={() => setLoaded(true)}
      onError={() => setError(true)}
      className={`w-full h-[140px] object-cover transition-opacity ${loaded ? "opacity-100" : "opacity-0"}`}
    />
  );
}

/** Format VND price with dot separators. */
function formatVND(price: unknown): string | null {
  if (price == null || price === "") return null;
  const str = String(price);
  // Already formatted with đ
  if (str.includes("đ") || str.includes("₫")) return str;
  const num = Number(str.replace(/[.,\s]/g, ""));
  if (isNaN(num)) return str;
  return num.toLocaleString("vi-VN") + "đ";
}

export function ProductPreviewCard({ item, onClick }: Props) {
  const price = item.metadata?.price;
  const extractedPrice = item.metadata?.extracted_price;
  const rating = item.metadata?.rating as number | undefined;
  const seller = item.metadata?.seller as string | undefined;
  const platform = item.metadata?.platform as string | undefined;
  const soldCountRaw = item.metadata?.sold_count;
  const delivery = item.metadata?.delivery as string | undefined;
  const soldCount =
    typeof soldCountRaw === "string" || typeof soldCountRaw === "number"
      ? soldCountRaw
      : null;

  const displayPrice = formatVND(extractedPrice) || formatVND(price);
  const platformLabel = platform ? PLATFORM_LABELS[platform] || platform : undefined;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col rounded-lg border border-[var(--border,#e5e5e0)]
        bg-[var(--surface,#ffffff)] hover:bg-[var(--surface-hover,#fafaf5)]
        hover:shadow-md transition-all text-left w-[220px] overflow-hidden group
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
      aria-label={`Sản phẩm: ${item.title}`}
    >
      {/* Image section with platform badge overlay */}
      <div className="relative w-full">
        {item.image_url ? (
          <ProductImage src={item.image_url} alt={item.title} />
        ) : (
          <div className="w-full h-[140px] bg-gradient-to-br from-[var(--surface-secondary,#f5f5f0)] to-[var(--surface-tertiary,#e8e8e3)] flex items-center justify-center">
            <ShoppingBag size={32} className="text-[var(--accent,#c2662d)] opacity-60" />
          </div>
        )}
        {/* Platform badge */}
        {platformLabel && (
          <span className="absolute top-2 left-2 text-[10px] px-1.5 py-0.5 rounded
            bg-black/60 text-white font-medium backdrop-blur-sm">
            {platformLabel}
          </span>
        )}
      </div>

      {/* Content section */}
      <div className="p-3 flex-1 flex flex-col gap-1.5 min-h-0">
        {/* Title */}
        <h4 className="text-[13px] font-medium text-[var(--text-primary,#1a1a1a)] line-clamp-2 leading-snug">
          {item.title}
        </h4>

        {/* Rating + sold count */}
        <div className="flex items-center gap-2 flex-wrap">
          {rating != null && (
            <span className="inline-flex items-center gap-0.5 text-xs text-[var(--text-secondary,#6b6b6b)]">
              <Star size={11} className="text-amber-400 fill-amber-400" />
              {Number(rating).toFixed(1)}
            </span>
          )}
          {soldCount != null && (
            <span className="text-[11px] text-[var(--text-tertiary,#999)]">
              Đã bán {soldCount}
            </span>
          )}
          {seller && soldCount == null && (
            <span className="text-[11px] text-[var(--text-tertiary,#999)] truncate max-w-[120px]">
              {seller}
            </span>
          )}
        </div>

        {/* Price */}
        {displayPrice && (
          <p className="text-sm font-bold text-[var(--accent,#c2662d)] mt-auto">
            {displayPrice}
          </p>
        )}

        {/* Delivery info */}
        {delivery && (
          <p className="text-[11px] text-[var(--text-tertiary,#999)] truncate">
            {delivery}
          </p>
        )}
      </div>
    </button>
  );
}
