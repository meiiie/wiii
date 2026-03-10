/**
 * PreviewCard — Base card for rich preview items.
 * Sprint 166: Delegates to specialized renderers via PreviewCardRenderer.
 * Keeps LazyImage helper for external use.
 */
import { useRef, useEffect, useState } from "react";
import type { PreviewItemData } from "@/api/types";
import { PreviewCardRenderer } from "./previews";

interface PreviewCardProps {
  item: PreviewItemData;
  onClick?: () => void;
}

/** Lazy-load image via IntersectionObserver. */
export function LazyImage({ src, alt }: { src: string; alt: string }) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const el = imgRef.current;
    if (!el) return;
    setLoaded(false);
    setError(false);
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
      <div className="w-16 h-16 rounded-md flex-shrink-0 bg-surface-tertiary flex items-center justify-center text-text-quaternary text-xs">
        ?
      </div>
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

export function PreviewCard({ item, onClick }: PreviewCardProps) {
  return <PreviewCardRenderer item={item} onClick={onClick} />;
}
