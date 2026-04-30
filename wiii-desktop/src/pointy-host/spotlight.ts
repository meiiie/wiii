/**
 * Wiii Pointy — spotlight overlay with tooltip.
 *
 * Dims the page (radial-gradient hole around the target) and shows a small
 * Vietnamese-first tooltip near the element. Pure DOM, no Driver.js dep.
 */

const OVERLAY_ID = "wiii-pointy-overlay";
const TARGET_RING_ID = "wiii-pointy-target-ring";
const TOOLTIP_ID = "wiii-pointy-tooltip";
const BRAND_ORANGE = "#F97316";
const BRAND_CREAM = "#FAF5EE";
const PADDING = 8;

let overlayEl: HTMLDivElement | null = null;
let targetRingEl: HTMLDivElement | null = null;
let tooltipEl: HTMLDivElement | null = null;
let activeTimer: ReturnType<typeof setTimeout> | null = null;

function createOverlay(): HTMLDivElement {
  const el = document.createElement("div");
  el.id = OVERLAY_ID;
  el.setAttribute("data-wiii-pointy", "overlay");
  el.setAttribute("aria-hidden", "true");
  Object.assign(el.style, {
    position: "fixed",
    inset: "0",
    zIndex: "2147483645",
    pointerEvents: "none",
    background: "transparent",
    transition: "background 250ms ease-out",
  });
  return el;
}

function createTargetRing(): HTMLDivElement {
  const el = document.createElement("div");
  el.id = TARGET_RING_ID;
  el.setAttribute("data-wiii-pointy", "target-ring");
  el.setAttribute("aria-hidden", "true");
  Object.assign(el.style, {
    position: "fixed",
    zIndex: "2147483646",
    pointerEvents: "none",
    border: `3px solid ${BRAND_ORANGE}`,
    borderRadius: "14px",
    boxShadow: "0 0 0 7px rgba(249,115,22,0.18), 0 0 28px rgba(249,115,22,0.46)",
    opacity: "0",
    transform: "scale(0.96)",
    transition: "opacity 180ms ease-out, transform 180ms ease-out",
  });
  return el;
}

function createTooltip(): HTMLDivElement {
  const el = document.createElement("div");
  el.id = TOOLTIP_ID;
  el.setAttribute("data-wiii-pointy", "tooltip");
  el.setAttribute("role", "status");
  el.setAttribute("aria-live", "polite");
  Object.assign(el.style, {
    position: "fixed",
    zIndex: "2147483647",
    pointerEvents: "none",
    background: BRAND_CREAM,
    color: "#1F2937",
    border: `2px solid ${BRAND_ORANGE}`,
    borderRadius: "12px",
    padding: "8px 12px",
    fontFamily: "system-ui, -apple-system, sans-serif",
    fontSize: "14px",
    fontWeight: "500",
    maxWidth: "280px",
    boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
    opacity: "0",
    transform: "translateY(4px)",
    transition: "opacity 180ms ease-out, transform 180ms ease-out",
  });
  return el;
}

function ensureElements(): { overlay: HTMLDivElement; targetRing: HTMLDivElement; tooltip: HTMLDivElement } {
  if (!overlayEl || !overlayEl.isConnected) {
    overlayEl = createOverlay();
    document.body.appendChild(overlayEl);
  }
  if (!targetRingEl || !targetRingEl.isConnected) {
    targetRingEl = createTargetRing();
    document.body.appendChild(targetRingEl);
  }
  if (!tooltipEl || !tooltipEl.isConnected) {
    tooltipEl = createTooltip();
    document.body.appendChild(tooltipEl);
  }
  return { overlay: overlayEl, targetRing: targetRingEl, tooltip: tooltipEl };
}

/** Position tooltip below the target by default; flip above if it would overflow. */
export function computeTooltipPosition(
  targetRect: DOMRect,
  tooltipRect: { width: number; height: number },
  viewport: { width: number; height: number },
): { left: number; top: number } {
  const desiredLeft = Math.max(
    8,
    Math.min(
      targetRect.left + targetRect.width / 2 - tooltipRect.width / 2,
      viewport.width - tooltipRect.width - 8,
    ),
  );
  const wantsBelow = targetRect.bottom + tooltipRect.height + 12 <= viewport.height;
  const top = wantsBelow
    ? targetRect.bottom + 12
    : Math.max(8, targetRect.top - tooltipRect.height - 12);
  return { left: desiredLeft, top };
}

export interface SpotlightOptions {
  message?: string;
  duration_ms?: number;
  onClose?: () => void;
}

export function showSpotlight(target: Element, opts: SpotlightOptions = {}): void {
  const { overlay, targetRing, tooltip } = ensureElements();
  const rect = target.getBoundingClientRect();

  // Radial dim with a hole punched around the target.
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const r = Math.max(rect.width, rect.height) / 2 + PADDING;
  overlay.style.background = `radial-gradient(circle at ${cx}px ${cy}px, transparent 0px, transparent ${r}px, rgba(15,23,42,0.45) ${r + 24}px)`;

  const ringPad = Math.max(6, Math.min(14, Math.max(rect.width, rect.height) * 0.08));
  Object.assign(targetRing.style, {
    left: `${Math.max(4, rect.left - ringPad)}px`,
    top: `${Math.max(4, rect.top - ringPad)}px`,
    width: `${rect.width + ringPad * 2}px`,
    height: `${rect.height + ringPad * 2}px`,
    borderRadius: `${Math.min(18, Math.max(10, ringPad + 8))}px`,
    opacity: "1",
    transform: "scale(1)",
  });

  if (opts.message) {
    tooltip.textContent = opts.message;
    tooltip.style.opacity = "0";
    tooltip.style.transform = "translateY(4px)";
    // Force layout so we can measure.
    const tRect = tooltip.getBoundingClientRect();
    const viewport = {
      width: window.innerWidth || document.documentElement.clientWidth,
      height: window.innerHeight || document.documentElement.clientHeight,
    };
    const { left, top } = computeTooltipPosition(rect, tRect, viewport);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
    requestAnimationFrame(() => {
      tooltip.style.opacity = "1";
      tooltip.style.transform = "translateY(0)";
    });
  } else {
    tooltip.style.opacity = "0";
  }

  if (activeTimer) {
    clearTimeout(activeTimer);
    activeTimer = null;
  }
  const ms = Math.max(1500, Math.min(opts.duration_ms ?? 7000, 20000));
  activeTimer = setTimeout(() => {
    hideSpotlight();
    opts.onClose?.();
  }, ms);
}

export function hideSpotlight(): void {
  if (activeTimer) {
    clearTimeout(activeTimer);
    activeTimer = null;
  }
  if (overlayEl) overlayEl.style.background = "transparent";
  if (targetRingEl) {
    targetRingEl.style.opacity = "0";
    targetRingEl.style.transform = "scale(0.98)";
  }
  if (tooltipEl) {
    tooltipEl.style.opacity = "0";
    tooltipEl.style.transform = "translateY(4px)";
  }
}

export function destroySpotlight(): void {
  if (activeTimer) {
    clearTimeout(activeTimer);
    activeTimer = null;
  }
  for (const el of [overlayEl, targetRingEl, tooltipEl]) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }
  overlayEl = null;
  targetRingEl = null;
  tooltipEl = null;
}

export const _testing = {
  OVERLAY_ID,
  TARGET_RING_ID,
  TOOLTIP_ID,
  getOverlay: () => overlayEl,
  getTargetRing: () => targetRingEl,
  getTooltip: () => tooltipEl,
};
