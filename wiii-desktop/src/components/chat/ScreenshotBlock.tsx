/**
 * ScreenshotBlock — browser screenshot with fullscreen overlay.
 * Sprint 153: "Mắt Thần" — visual transparency during Playwright search.
 * Sprint 154: Full images kept permanently (no stripping on finalize).
 * Sprint 162b: Base64→Blob URL conversion for memory optimization.
 */
import { useState, useEffect, useRef, useMemo } from "react";
import type { ScreenshotBlockData } from "@/api/types";
import { base64ToBlobUrl, revokeBlobUrl } from "@/lib/blob-url";

export function ScreenshotBlock({ block }: { block: ScreenshotBlockData }) {
  const [expanded, setExpanded] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  // Convert base64 to Blob URL (memory-efficient, cached)
  const blobUrl = useMemo(() => {
    if (!block.image) return null;
    return base64ToBlobUrl(block.image, "image/jpeg");
  }, [block.image]);

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => {
      if (blobUrl) revokeBlobUrl(blobUrl);
    };
  }, [blobUrl]);

  // Escape key to close fullscreen overlay
  useEffect(() => {
    if (!expanded) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", handleKey);
    overlayRef.current?.focus();
    return () => window.removeEventListener("keydown", handleKey);
  }, [expanded]);

  let hostname = "";
  try {
    hostname = new URL(block.url).hostname;
  } catch {
    hostname = block.url;
  }

  if (!blobUrl) {
    // No image — placeholder (shouldn't happen with full image persistence)
    return (
      <div className="screenshot-block screenshot-placeholder">
        <div className="screenshot-header">
          <span className="screenshot-label">{block.label}</span>
          <span className="screenshot-url">{hostname}</span>
        </div>
        <div className="screenshot-thumbnail-placeholder">
          Ảnh chụp trình duyệt không khả dụng
        </div>
      </div>
    );
  }

  // Full image — clickable expand
  return (
    <>
      <div
        className="screenshot-block"
        onClick={() => setExpanded(true)}
        onKeyDown={(e) => e.key === "Enter" && setExpanded(true)}
        role="button"
        tabIndex={0}
      >
        <div className="screenshot-header">
          <span className="screenshot-label">{block.label}</span>
          <span className="screenshot-url">{hostname}</span>
        </div>
        <img
          src={blobUrl}
          alt={block.label}
          className="screenshot-thumbnail"
        />
      </div>

      {expanded && (
        <div
          ref={overlayRef}
          className="screenshot-overlay"
          onClick={() => setExpanded(false)}
          role="dialog"
          aria-label="Screenshot fullscreen"
          tabIndex={-1}
        >
          <div
            className="screenshot-overlay-content"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="screenshot-overlay-header">
              <span>{block.label}</span>
              <span className="screenshot-overlay-url">{block.url}</span>
              <button onClick={() => setExpanded(false)} aria-label="Đóng">
                ✕
              </button>
            </div>
            <img
              src={blobUrl}
              alt={block.label}
              className="screenshot-full"
            />
          </div>
        </div>
      )}
    </>
  );
}
