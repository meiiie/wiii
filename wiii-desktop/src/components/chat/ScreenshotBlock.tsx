/**
 * ScreenshotBlock — browser screenshot with fullscreen overlay.
 * Sprint 153: "Mắt Thần" — visual transparency during Playwright search.
 * Sprint 154: Full images kept permanently (no stripping on finalize).
 */
import { useState } from "react";
import type { ScreenshotBlockData } from "@/api/types";

export function ScreenshotBlock({ block }: { block: ScreenshotBlockData }) {
  const [expanded, setExpanded] = useState(false);

  let hostname = "";
  try {
    hostname = new URL(block.url).hostname;
  } catch {
    hostname = block.url;
  }

  if (!block.image) {
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
          src={`data:image/jpeg;base64,${block.image}`}
          alt={block.label}
          className="screenshot-thumbnail"
        />
      </div>

      {expanded && (
        <div
          className="screenshot-overlay"
          onClick={() => setExpanded(false)}
          role="dialog"
          aria-label="Screenshot fullscreen"
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
              src={`data:image/jpeg;base64,${block.image}`}
              alt={block.label}
              className="screenshot-full"
            />
          </div>
        </div>
      )}
    </>
  );
}
