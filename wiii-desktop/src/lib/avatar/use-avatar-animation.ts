/**
 * Avatar animation hook — Sprint 115: Living Avatar Foundation.
 * Sprint 119: Reduced motion support (WCAG 2.2), smooth color transitions.
 * Sprint 129: SVG Face animation (eyes, mouth, eyebrows, blink).
 *
 * Manages: rAF loop, state interpolation, IntersectionObserver visibility,
 * direct DOM updates for SVG path (bypasses React at 60fps), canvas DPI,
 * face expression interpolation, blink controller, speaking mouth oscillation.
 */
import { useRef, useEffect, useCallback, useState } from "react";
import type { AvatarState, Particle } from "./types";
import type { StateVisuals } from "./types";
import { STATE_CONFIG, getSizeTier, getBlobResolution } from "./state-config";
import { generateBlobPath } from "./blob-geometry";
import { spawnParticle, updateParticles, renderParticles } from "./particle-system";
import { FACE_EXPRESSIONS, lerpFaceExpression } from "./face-config";
import type { FaceExpression } from "./face-config";
import { getFaceDimensions, generateMouthPath } from "./face-geometry";
import { BlinkController } from "./blink-controller";
import { getNoiseGenerator } from "./noise-engine";

/** Global per-instance seed counter */
let _seedCounter = 0;

/** Reset seed counter (for testing) */
export function _resetSeedCounter(): void {
  _seedCounter = 0;
}

/** Cubic ease-in-out for smooth state transitions */
function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/** Linearly interpolate between two values */
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Interpolate between two hex color strings (e.g. "#f97316" → "#22c55e") */
export function lerpHexColor(from: string, to: string, t: number): string {
  if (from === to || t >= 1) return to;
  if (t <= 0) return from;
  const f = parseInt(from.slice(1), 16);
  const t2 = parseInt(to.slice(1), 16);
  if (isNaN(f) || isNaN(t2)) return to;
  const r = Math.round(lerp((f >> 16) & 0xff, (t2 >> 16) & 0xff, t));
  const g = Math.round(lerp((f >> 8) & 0xff, (t2 >> 8) & 0xff, t));
  const b = Math.round(lerp(f & 0xff, t2 & 0xff, t));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

/** Interpolate all visual parameters between two states */
function lerpVisuals(from: StateVisuals, to: StateVisuals, t: number): StateVisuals {
  const e = easeInOutCubic(t);
  return {
    noiseAmplitude: lerp(from.noiseAmplitude, to.noiseAmplitude, e),
    noiseFrequency: lerp(from.noiseFrequency, to.noiseFrequency, e),
    timeSpeed: lerp(from.timeSpeed, to.timeSpeed, e),
    glowIntensity: lerp(from.glowIntensity, to.glowIntensity, e),
    glowColor: lerpHexColor(from.glowColor, to.glowColor, e),
    blobColor: to.blobColor,  // CSS variable — can't interpolate in JS
    scale: lerp(from.scale, to.scale, e),
    indicatorColor: lerpHexColor(from.indicatorColor, to.indicatorColor, e),
    indicatorVisible: to.indicatorVisible,
    particleCount: Math.round(lerp(from.particleCount, to.particleCount, e)),
    particleColor: lerpHexColor(from.particleColor, to.particleColor, e),
    particleOrbitSpeed: lerp(from.particleOrbitSpeed, to.particleOrbitSpeed, e),
    particleDriftSpeed: lerp(from.particleDriftSpeed, to.particleDriftSpeed, e),
    tinyBorderRadius: to.tinyBorderRadius,
  };
}

export interface AnimationResult {
  svgRef: React.RefObject<SVGSVGElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  pathRef: React.RefObject<SVGPathElement | null>;
  /** Sprint 129: Face element refs for direct DOM manipulation */
  faceGroupRef: React.RefObject<SVGGElement | null>;
  leftEyeRef: React.RefObject<SVGGElement | null>;
  rightEyeRef: React.RefObject<SVGGElement | null>;
  leftBrowRef: React.RefObject<SVGLineElement | null>;
  rightBrowRef: React.RefObject<SVGLineElement | null>;
  mouthRef: React.RefObject<SVGPathElement | null>;
  glowOpacity: number;
  glowColor: string;
  blobColor: string;
  scale: number;
  indicatorColor: string;
  indicatorVisible: boolean;
}

export function useAvatarAnimation(
  state: AvatarState,
  size: number,
): AnimationResult {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pathRef = useRef<SVGPathElement | null>(null);

  // Sprint 129: Face element refs
  const faceGroupRef = useRef<SVGGElement | null>(null);
  const leftEyeRef = useRef<SVGGElement | null>(null);
  const rightEyeRef = useRef<SVGGElement | null>(null);
  const leftBrowRef = useRef<SVGLineElement | null>(null);
  const rightBrowRef = useRef<SVGLineElement | null>(null);
  const mouthRef = useRef<SVGPathElement | null>(null);

  // Sprint 129: Blink controller + face expression tracking
  const blinkCtrlRef = useRef(new BlinkController(FACE_EXPRESSIONS[state]?.blinkRate ?? 15));
  const fromFaceRef = useRef<FaceExpression>(FACE_EXPRESSIONS[state] || FACE_EXPRESSIONS.idle);
  const toFaceRef = useRef<FaceExpression>(FACE_EXPRESSIONS[state] || FACE_EXPRESSIONS.idle);

  // Per-instance seed (assigned once on mount)
  const seedRef = useRef<number>(0);

  // Animation state
  const timeRef = useRef(0);
  const rafRef = useRef<number>(0);
  const lastFrameRef = useRef(0);
  const visibleRef = useRef(true);
  const particlesRef = useRef<Particle[]>([]);

  // State transition tracking
  const prevStateRef = useRef(state);
  const transitionRef = useRef(1); // 1 = fully transitioned
  const fromVisualsRef = useRef(STATE_CONFIG[state] || STATE_CONFIG.idle);
  const toVisualsRef = useRef(STATE_CONFIG[state] || STATE_CONFIG.idle);

  // Derived values for React rendering (glow, color, scale)
  const [renderState, setRenderState] = useState(() => {
    const v = STATE_CONFIG[state] || STATE_CONFIG.idle;
    return {
      glowOpacity: v.glowIntensity,
      glowColor: v.glowColor,
      blobColor: v.blobColor,
      scale: v.scale,
      indicatorColor: v.indicatorColor,
      indicatorVisible: v.indicatorVisible,
    };
  });

  const tier = getSizeTier(size);
  const resolution = getBlobResolution(tier);

  // Sprint 119: Detect prefers-reduced-motion (WCAG 2.2)
  const prefersReducedMotionRef = useRef(false);
  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    prefersReducedMotionRef.current = mql.matches;
    const handler = (e: MediaQueryListEvent) => {
      prefersReducedMotionRef.current = e.matches;
    };
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  // Assign unique seed on mount
  useEffect(() => {
    seedRef.current = _seedCounter++;
  }, []);

  // Detect state changes and start transition
  useEffect(() => {
    if (state !== prevStateRef.current) {
      // Snapshot current interpolated visuals as the "from" state
      const t = easeInOutCubic(Math.min(transitionRef.current, 1));
      fromVisualsRef.current = lerpVisuals(
        fromVisualsRef.current,
        toVisualsRef.current,
        t,
      );
      toVisualsRef.current = STATE_CONFIG[state] || STATE_CONFIG.idle;

      // Sprint 129: Also transition face expression
      fromFaceRef.current = lerpFaceExpression(
        fromFaceRef.current,
        toFaceRef.current,
        easeInOutCubic(t),
      );
      toFaceRef.current = FACE_EXPRESSIONS[state] || FACE_EXPRESSIONS.idle;
      blinkCtrlRef.current.setRate(toFaceRef.current.blinkRate);
      blinkCtrlRef.current.triggerBlink(); // Blink on state change for natural feel

      transitionRef.current = 0;
      prevStateRef.current = state;
    }
  }, [state]);

  // rAF animation loop
  const animate = useCallback(
    (timestamp: number) => {
      // Sprint 119: Skip ALL animation when user prefers reduced motion
      if (prefersReducedMotionRef.current) {
        rafRef.current = requestAnimationFrame(animate);
        return;
      }

      if (!visibleRef.current) {
        rafRef.current = requestAnimationFrame(animate);
        return;
      }

      // Delta time with cap (max 100ms to prevent jumps after tab switch)
      const dt = lastFrameRef.current
        ? Math.min((timestamp - lastFrameRef.current) / 1000, 0.1)
        : 0.016;
      lastFrameRef.current = timestamp;

      // Advance state transition (0.4s duration)
      if (transitionRef.current < 1) {
        transitionRef.current = Math.min(transitionRef.current + dt / 0.4, 1);
      }

      const visuals = lerpVisuals(
        fromVisualsRef.current,
        toVisualsRef.current,
        transitionRef.current,
      );

      // Advance animation time
      timeRef.current += dt * visuals.timeSpeed;

      const cx = size / 2;
      const cy = size / 2;
      const blobRadius = (size / 2) * 0.82;

      // Update SVG blob path via direct DOM (bypasses React reconciliation)
      if (tier !== "tiny" && pathRef.current && resolution > 0) {
        const d = generateBlobPath(
          cx, cy, blobRadius, resolution,
          timeRef.current, visuals.noiseFrequency,
          visuals.noiseAmplitude, seedRef.current,
        );
        pathRef.current.setAttribute("d", d);
      }

      // Update canvas particles (large tier only)
      if (tier === "large" && canvasRef.current) {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          const dpr = window.devicePixelRatio || 1;
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.save();
          ctx.scale(dpr, dpr);

          // Spawn particles to meet target count
          while (particlesRef.current.length < visuals.particleCount) {
            particlesRef.current.push(spawnParticle(cx, cy, blobRadius));
          }

          // Update and render
          particlesRef.current = updateParticles(
            particlesRef.current, cx, cy, dt,
            visuals.particleOrbitSpeed, visuals.particleDriftSpeed,
          );
          renderParticles(ctx, particlesRef.current, visuals.particleColor);

          ctx.restore();
        }
      }

      // Sprint 129: Update face features via direct DOM (large tier only)
      if (tier === "large" && faceGroupRef.current) {
        const faceT = easeInOutCubic(Math.min(transitionRef.current, 1));
        const face = lerpFaceExpression(fromFaceRef.current, toFaceRef.current, faceT);
        const dims = getFaceDimensions(blobRadius);

        // Blink
        const blinkScale = blinkCtrlRef.current.advance(dt);
        const eyeScaleY = face.eyeOpenness * blinkScale;

        // Idle pupil drift via noise
        const noise3D = getNoiseGenerator();
        const noiseTime = timeRef.current;
        const seed = seedRef.current;
        const driftX = noise3D(noiseTime * 0.4, seed + 100, 0) * dims.pupilMaxOffset;
        const driftY = noise3D(noiseTime * 0.4, 0, seed + 100) * dims.pupilMaxOffset;
        const pupilDx = face.pupilOffsetX * dims.pupilMaxOffset + driftX;
        const pupilDy = face.pupilOffsetY * dims.pupilMaxOffset + driftY;

        // Face micro-motion (swim with blob)
        const microX = noise3D(noiseTime * 0.5, seed + 200, 0) * blobRadius * 0.02;
        const microY = noise3D(noiseTime * 0.5, 0, seed + 200) * blobRadius * 0.02;
        faceGroupRef.current.setAttribute("transform",
          `translate(${(cx + microX).toFixed(1)}, ${(cy + microY).toFixed(1)})`);

        // Eyes — GPU-accelerated transforms
        if (leftEyeRef.current) {
          leftEyeRef.current.setAttribute("transform",
            `translate(${pupilDx.toFixed(2)}, ${pupilDy.toFixed(2)}) scale(1, ${eyeScaleY.toFixed(3)})`);
        }
        if (rightEyeRef.current) {
          rightEyeRef.current.setAttribute("transform",
            `translate(${pupilDx.toFixed(2)}, ${pupilDy.toFixed(2)}) scale(1, ${eyeScaleY.toFixed(3)})`);
        }

        // Eyebrows — GPU-accelerated transforms
        const browRaiseY = face.browRaise * -dims.eyeRy * 0.5;
        if (leftBrowRef.current) {
          const tiltAngle = face.browTilt * 12;
          leftBrowRef.current.setAttribute("transform",
            `translate(0, ${browRaiseY.toFixed(2)}) rotate(${(-tiltAngle).toFixed(1)})`);
        }
        if (rightBrowRef.current) {
          const tiltAngle = face.browTilt * 12;
          rightBrowRef.current.setAttribute("transform",
            `translate(0, ${browRaiseY.toFixed(2)}) rotate(${tiltAngle.toFixed(1)})`);
        }

        // Mouth — speaking state uses noise-driven oscillation
        let mouthOpenness = face.mouthOpenness;
        let mouthCurve = face.mouthCurve;
        if (state === "speaking") {
          const speakNoise = noise3D(noiseTime * 4, seed + 300, 0);
          mouthOpenness = Math.max(0, speakNoise * 0.4 + 0.25);
          const widthNoise = noise3D(noiseTime * 2, seed + 400, 0);
          mouthCurve = 0.15 + widthNoise * 0.1;
        }
        if (mouthRef.current) {
          const mouthPath = generateMouthPath(0, dims.mouthY, {
            curve: mouthCurve,
            openness: mouthOpenness,
            width: face.mouthWidth,
          }, dims.mouthBaseWidth);
          mouthRef.current.setAttribute("d", mouthPath);
        }
      }

      // Update React state (throttled — only when values change meaningfully)
      setRenderState((prev) => {
        const changed =
          Math.abs(prev.glowOpacity - visuals.glowIntensity) > 0.005 ||
          prev.glowColor !== visuals.glowColor ||
          prev.blobColor !== visuals.blobColor ||
          Math.abs(prev.scale - visuals.scale) > 0.002 ||
          prev.indicatorColor !== visuals.indicatorColor ||
          prev.indicatorVisible !== visuals.indicatorVisible;
        if (!changed) return prev;
        return {
          glowOpacity: visuals.glowIntensity,
          glowColor: visuals.glowColor,
          blobColor: visuals.blobColor,
          scale: visuals.scale,
          indicatorColor: visuals.indicatorColor,
          indicatorVisible: visuals.indicatorVisible,
        };
      });

      rafRef.current = requestAnimationFrame(animate);
    },
    [size, tier, resolution],
  );

  // Start/stop rAF loop + IntersectionObserver
  useEffect(() => {
    // Tiny tier: no animation loop needed (CSS-only)
    if (tier === "tiny") return;

    // Setup canvas DPI for large tier
    if (tier === "large" && canvasRef.current) {
      const canvas = canvasRef.current;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = size * dpr;
      canvas.height = size * dpr;
      canvas.style.width = `${size}px`;
      canvas.style.height = `${size}px`;
    }

    // Start rAF
    rafRef.current = requestAnimationFrame(animate);

    // IntersectionObserver to pause when off-screen
    const observer = new IntersectionObserver(
      ([entry]) => {
        visibleRef.current = entry.isIntersecting;
      },
      { threshold: 0.1 },
    );

    const el = svgRef.current;
    if (el) observer.observe(el);

    return () => {
      cancelAnimationFrame(rafRef.current);
      observer.disconnect();
    };
  }, [tier, size, animate]);

  return {
    svgRef,
    canvasRef,
    pathRef,
    faceGroupRef,
    leftEyeRef,
    rightEyeRef,
    leftBrowRef,
    rightBrowRef,
    mouthRef,
    ...renderState,
  };
}
