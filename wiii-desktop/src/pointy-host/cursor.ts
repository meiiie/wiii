/**
 * Wiii Pointy — animated cursor overlay.
 *
 * Renders a Browser-Use-like collaborator cursor with a compact Wiii badge.
 * Pure DOM + Web Animations API; no React, no framework.
 */

const CURSOR_ID = "wiii-pointy-cursor";
const CURSOR_WIDTH = 124;
const CURSOR_HEIGHT = 62;
const CURSOR_TIP_X = 5;
const CURSOR_TIP_Y = 4;
const CURSOR_SIZE = CURSOR_WIDTH;
const BRAND_ORANGE = "#F97316";
const POINTER_BLACK = "#111827";
const LIVE_GREEN = "#22C55E";

let cursorEl: SVGSVGElement | null = null;
export interface CursorPoint {
  x: number;
  y: number;
}

let lastPos: CursorPoint | null = null;
let activeAnimation: Animation | null = null;

function createCursor(): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("id", CURSOR_ID);
  svg.setAttribute("width", String(CURSOR_WIDTH));
  svg.setAttribute("height", String(CURSOR_HEIGHT));
  svg.setAttribute("viewBox", `0 0 ${CURSOR_WIDTH} ${CURSOR_HEIGHT}`);
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("data-wiii-pointy", "cursor");
  svg.setAttribute("data-wiii-pointy-scope", "iframe");

  const css = svg.style;
  css.position = "fixed";
  css.left = "0px";
  css.top = "0px";
  css.zIndex = "2147483646";
  css.pointerEvents = "none";
  css.transformOrigin = `${CURSOR_TIP_X}px ${CURSOR_TIP_Y}px`;
  css.filter = "drop-shadow(0 12px 26px rgba(15,23,42,0.26))";
  css.opacity = "0";
  css.transition = "opacity 200ms ease-out";
  css.overflow = "visible";
  css.willChange = "transform, opacity";

  svg.innerHTML = `
    <style>
      #${CURSOR_ID} .wiii-pointy-live-ring {
        transform-origin: 105px 43px;
        animation: wiii-pointy-live-pulse 1.25s ease-out infinite;
      }
      #${CURSOR_ID}[data-wiii-pointy-state="moving"] .wiii-pointy-badge {
        filter: drop-shadow(0 0 10px rgba(249,115,22,0.28));
      }
      @keyframes wiii-pointy-live-pulse {
        0% { opacity: 0.52; transform: scale(0.72); }
        100% { opacity: 0; transform: scale(1.8); }
      }
    </style>
    <path d="M5 4 L5 35 L15 25 L22 44 L31 40 L24 23 L40 23 Z" fill="${POINTER_BLACK}" stroke="white" stroke-width="2.6" stroke-linejoin="round"/>
    <g class="wiii-pointy-badge">
      <rect x="36" y="9" width="82" height="38" rx="19" fill="rgba(255,255,255,0.96)" stroke="rgba(17,24,39,0.12)" stroke-width="1"/>
      <circle cx="55" cy="28" r="11" fill="${BRAND_ORANGE}"/>
      <text x="55" y="32" text-anchor="middle" font-family="Aptos Rounded,Nunito Sans,Segoe UI,sans-serif" font-size="11" font-weight="900" fill="white">W</text>
      <text class="wiii-pointy-label" x="83" y="32" text-anchor="middle" font-family="Aptos Rounded,Nunito Sans,Segoe UI,sans-serif" font-size="14" font-weight="850" fill="${POINTER_BLACK}">Wiii</text>
      <circle class="wiii-pointy-live-ring" cx="105" cy="43" r="5" fill="${LIVE_GREEN}"/>
      <circle cx="105" cy="43" r="4" fill="${LIVE_GREEN}" stroke="white" stroke-width="1.8"/>
    </g>
  `;
  return svg;
}

function ensureCursor(): SVGSVGElement {
  if (cursorEl && cursorEl.isConnected) return cursorEl;
  cursorEl = createCursor();
  document.body.appendChild(cursorEl);
  return cursorEl;
}

function setCursorLabel(cursor: SVGSVGElement, label?: string): void {
  const clean = String(label || "Wiii").trim().slice(0, 18) || "Wiii";
  const labelNode = cursor.querySelector(".wiii-pointy-label");
  if (labelNode) labelNode.textContent = clean;
  cursor.setAttribute("aria-label", clean);
}

/**
 * Compute the screen point the cursor should land on for a given element.
 * Lands slightly above-right of the element center to look like it's
 * "pointing" at the button rather than covering it.
 */
export function computeTargetPoint(rect: DOMRect): CursorPoint {
  return {
    x: rect.left + rect.width / 2 - CURSOR_TIP_X,
    y: rect.top + rect.height / 2 - CURSOR_TIP_Y,
  };
}

/** Compute starting point if cursor has no last position (off-screen right edge). */
export function computeOriginPoint(): CursorPoint {
  const w = typeof window !== "undefined" ? window.innerWidth : 1024;
  const h = typeof window !== "undefined" ? window.innerHeight : 768;
  return { x: w - CURSOR_SIZE, y: h / 2 };
}

function clampTransformPoint(point: CursorPoint): CursorPoint {
  if (typeof window === "undefined") return point;
  const maxX = Math.max(0, window.innerWidth - CURSOR_WIDTH);
  const maxY = Math.max(0, window.innerHeight - CURSOR_HEIGHT);
  return {
    x: Math.max(0, Math.min(point.x, maxX)),
    y: Math.max(0, Math.min(point.y, maxY)),
  };
}

function computeArcPoint(
  start: CursorPoint,
  target: CursorPoint,
): CursorPoint {
  const dx = target.x - start.x;
  const dy = target.y - start.y;
  const distance = Math.hypot(dx, dy);
  return {
    x: start.x + dx * 0.56,
    y: start.y + dy * 0.48 - Math.min(distance * 0.18, 72),
  };
}

export interface MoveCursorOptions {
  duration_ms?: number;
  label?: string;
  onComplete?: () => void;
}

function moveCursorToTransformPoint(
  rawTarget: CursorPoint,
  opts: MoveCursorOptions = {},
): Animation | null {
  const cursor = ensureCursor();
  setCursorLabel(cursor, opts.label);
  const target = clampTransformPoint(rawTarget);
  const start = lastPos ?? computeOriginPoint();
  lastPos = target;

  activeAnimation?.cancel();
  activeAnimation = null;
  cursor.style.opacity = "1";
  cursor.setAttribute("data-wiii-pointy-state", "moving");
  const duration = Math.max(220, Math.min(opts.duration_ms ?? 620, 1400));
  const finalTransform = `translate(${target.x}px, ${target.y}px) scale(1)`;
  const arc = computeArcPoint(start, target);

  if (typeof cursor.animate !== "function") {
    cursor.style.transform = finalTransform;
    cursor.setAttribute("data-wiii-pointy-state", "pointing");
    opts.onComplete?.();
    return null;
  }

  const animation = cursor.animate(
    [
      { transform: `translate(${start.x}px, ${start.y}px) scale(0.92) rotate(-2deg)` },
      { transform: `translate(${arc.x}px, ${arc.y}px) scale(1.08) rotate(-7deg)`, offset: 0.58 },
      { transform: `translate(${target.x}px, ${target.y}px) scale(1.02) rotate(1deg)`, offset: 0.86 },
      { transform: finalTransform },
    ],
    {
      duration,
      easing: "cubic-bezier(0.22, 1, 0.36, 1)",
      fill: "forwards",
    },
  );
  activeAnimation = animation;
  animation.onfinish = () => {
    cursor.style.transform = finalTransform;
    cursor.setAttribute("data-wiii-pointy-state", "pointing");
    activeAnimation = null;
    opts.onComplete?.();
  };
  return animation;
}

/** Move cursor so its pointer tip lands on a viewport coordinate. */
export function moveCursorToPoint(
  point: CursorPoint,
  opts: MoveCursorOptions = {},
): Animation | null {
  return moveCursorToTransformPoint(
    {
      x: point.x - CURSOR_TIP_X,
      y: point.y - CURSOR_TIP_Y,
    },
    opts,
  );
}

/** Move cursor to a target rect with spring-ish easing. */
export function moveCursorToRect(rect: DOMRect, opts: MoveCursorOptions = {}): Animation | null {
  return moveCursorToTransformPoint(computeTargetPoint(rect), opts);
}

/** Hide the cursor (does not remove it from DOM, just fades out). */
export function hideCursor(): void {
  if (cursorEl) cursorEl.style.opacity = "0";
}

/** Remove the cursor element entirely (for cleanup / tests). */
export function destroyCursor(): void {
  if (activeAnimation) {
    activeAnimation.onfinish = null;
    activeAnimation.oncancel = null;
    activeAnimation.cancel();
    activeAnimation = null;
  }
  if (cursorEl && cursorEl.parentNode) {
    cursorEl.parentNode.removeChild(cursorEl);
  }
  cursorEl = null;
  lastPos = null;
}

export const _testing = {
  CURSOR_ID,
  CURSOR_SIZE,
  getCursor: () => cursorEl,
  setLastPos: (p: CursorPoint | null) => {
    lastPos = p;
  },
};
