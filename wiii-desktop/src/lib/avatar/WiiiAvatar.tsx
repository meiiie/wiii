/**
 * WiiiAvatar — living organic blob avatar for Wiii's visual identity.
 * Sprint 115: Living Avatar System Foundation.
 * Sprint 119: Aria labels (a11y), reduced-motion-aware rendering.
 *
 * 3-tier rendering:
 *   Tiny  (<=20px) — CSS-only motion.div (backward compat with Sprint 111)
 *   Medium (22-36px) — SVG noise-deformed blob + glow filter
 *   Large  (>=40px) — Canvas particles + SVG blob + glow + indicator
 */
import { memo, useRef, useEffect } from "react";
import { motion } from "motion/react";
import type { AvatarState, WiiiAvatarProps } from "./types";
import { getSizeTier, STATE_CONFIG } from "./state-config";
import { useAvatarAnimation } from "./use-avatar-animation";
import "./avatar.css";

export type { AvatarState } from "./types";

/** Aria labels for screen readers — Vietnamese state descriptions */
export const STATE_LABELS: Record<AvatarState, string> = {
  idle: "Wiii",
  listening: "Wiii — đang lắng nghe",
  thinking: "Wiii — đang suy nghĩ",
  speaking: "Wiii — đang trả lời",
  complete: "Wiii — đã hoàn thành",
  error: "Wiii — gặp lỗi",
};

/** Global instance counter for unique SVG filter IDs */
let _instanceCounter = 0;

function WiiiAvatarInner({ state = "idle", size = 24, className = "" }: WiiiAvatarProps) {
  const tier = getSizeTier(size);
  const fontSize = Math.round(size * 0.42);
  const config = STATE_CONFIG[state] || STATE_CONFIG.idle;

  // Unique filter ID per instance (stable across renders)
  const instanceIdRef = useRef(0);
  useEffect(() => {
    instanceIdRef.current = ++_instanceCounter;
  }, []);
  const filterId = `wiii-glow-${instanceIdRef.current}`;

  // Animation hook (rAF skipped for tiny tier internally)
  const {
    svgRef,
    canvasRef,
    pathRef,
    glowOpacity,
    glowColor: _glowColor,
    blobColor,
    scale,
    indicatorColor,
    indicatorVisible,
  } = useAvatarAnimation(state, size);

  const ariaLabel = STATE_LABELS[state] || "Wiii";

  // ─── Tiny Tier: CSS-only (matches Sprint 111 behavior) ─────────────
  if (tier === "tiny") {
    return (
      <motion.div
        role="img"
        aria-label={ariaLabel}
        className={`wiii-avatar wiii-avatar-tiny relative shrink-0 ${className}`}
        style={{ width: size, height: size }}
      >
        <motion.div
          className="w-full h-full flex items-center justify-center text-white font-bold overflow-hidden"
          style={{
            fontSize: Math.round(size * 0.46),
            background: config.blobColor,
            borderRadius: config.tinyBorderRadius,
            boxShadow: `0 0 ${Math.round(size * 0.5)}px ${config.glowColor}${Math.round(config.glowIntensity * 255).toString(16).padStart(2, "0")}`,
          }}
          animate={
            state === "thinking"
              ? { scale: [1, 1.06, 1] }
              : state === "idle"
                ? { scale: [1, 1.03, 1] }
                : { scale: [1.08, 1] }
          }
          transition={
            state === "thinking"
              ? { duration: 1.2, repeat: Infinity, ease: "easeInOut" }
              : state === "idle"
                ? { duration: 3, repeat: Infinity, ease: "easeInOut" }
                : { duration: 0.4, ease: "easeOut" }
          }
        >
          W
        </motion.div>
      </motion.div>
    );
  }

  // ─── Medium/Large Tier: SVG Blob + optional Canvas particles ───────
  const halfSize = size / 2;
  const glowStdDev = Math.max(1, Math.round(size * 0.08));
  const indicatorSize = Math.max(3, Math.round(size * 0.14));

  // Initial circle path (replaced by noise-deformed path via rAF)
  const initRadius = halfSize * 0.82;
  const initialPath = `M ${halfSize} ${halfSize - initRadius} A ${initRadius} ${initRadius} 0 1 1 ${halfSize} ${halfSize + initRadius} A ${initRadius} ${initRadius} 0 1 1 ${halfSize} ${halfSize - initRadius} Z`;

  return (
    <motion.div
      role="img"
      aria-label={ariaLabel}
      className={`wiii-avatar relative shrink-0 ${className}`}
      style={{ width: size, height: size }}
      animate={{ scale }}
      transition={{ duration: 0.3, ease: "easeOut" }}
    >
      {/* Canvas layer — particles behind blob (large tier only) */}
      {tier === "large" && (
        <canvas
          ref={canvasRef as React.Ref<HTMLCanvasElement>}
          className="absolute inset-0 wiii-avatar-canvas"
          style={{ width: size, height: size }}
        />
      )}

      {/* SVG layer — blob shape + glow filter + "W" text */}
      <svg
        ref={svgRef as React.Ref<SVGSVGElement>}
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        className="absolute inset-0 wiii-avatar-svg"
        aria-hidden="true"
      >
        <defs>
          <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur
              in="SourceGraphic"
              stdDeviation={glowStdDev}
              result="blur"
            />
            <feColorMatrix
              in="blur"
              type="matrix"
              values={`1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 ${(glowOpacity * 3).toFixed(2)} 0`}
              result="glow"
            />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Blob path — updated at 60fps via direct DOM ref */}
        <path
          ref={pathRef as React.Ref<SVGPathElement>}
          fill={blobColor}
          filter={glowOpacity > 0.05 ? `url(#${filterId})` : undefined}
          d={initialPath}
        />

        {/* "W" character */}
        <text
          x={halfSize}
          y={halfSize}
          textAnchor="middle"
          dominantBaseline="central"
          fill="white"
          fontWeight="bold"
          fontSize={fontSize}
          style={{ pointerEvents: "none" }}
        >
          W
        </text>
      </svg>

      {/* Online indicator dot */}
      {indicatorVisible && (
        <motion.div
          className="absolute rounded-full"
          style={{
            width: indicatorSize,
            height: indicatorSize,
            bottom: 0,
            right: 0,
            background: indicatorColor,
          }}
          animate={
            state === "thinking"
              ? { scale: [1, 1.3, 1], opacity: [0.8, 1, 0.8] }
              : { scale: [1, 1.2, 1] }
          }
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
    </motion.div>
  );
}

export const WiiiAvatar = memo(WiiiAvatarInner);
