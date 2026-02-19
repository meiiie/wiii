/**
 * Face expression configuration — Sprint 129: SVG Face on Blob.
 * Sprint 130: Added blush + eyeShape (happy ^_^ eyes) for VTuber expressiveness.
 * Sprint 142: Staggered transitions, momentum lerp — "Có Hồn" enhancement.
 * Maps each AvatarState to facial feature parameters.
 */
import type { AvatarState } from "./types";

/** Facial expression parameters for a single state */
export interface FaceExpression {
  /** Eye openness: 0 (closed) → 1 (normal) → 1.3 (wide) */
  eyeOpenness: number;
  /** Pupil size multiplier: 0.6 (small) → 1.0 (normal) → 1.2 (dilated) */
  pupilSize: number;
  /** Pupil horizontal offset: -1 (left) → 0 (center) → 1 (right) */
  pupilOffsetX: number;
  /** Pupil vertical offset: -1 (up) → 0 (center) → 1 (down) */
  pupilOffsetY: number;
  /** Mouth curvature: -1 (frown) → 0 (neutral) → 1 (smile) */
  mouthCurve: number;
  /** Mouth openness: 0 (closed) → 1 (fully open) */
  mouthOpenness: number;
  /** Mouth width multiplier: 0.5 (narrow) → 1.0 (normal) → 1.5 (wide) */
  mouthWidth: number;
  /** Brow vertical: -1 (angry/lowered) → 0 (neutral) → 1 (surprised/raised) */
  browRaise: number;
  /** Brow tilt: -1 (inner furrow) → 0 (flat) → 1 (outer raise) */
  browTilt: number;
  /** Blinks per minute (natural average ~15) */
  blinkRate: number;
  /** Sprint 130: Blush intensity: 0 (none) → 1 (full pink cheeks) */
  blush: number;
  /** Sprint 130: Happy eye shape: 0 (normal ellipse) → 1 (^_^ arc) */
  eyeShape: number;
  /** Sprint 131 Phase 2: Mouth shape: 0=default, 1=cat ω, 2=dot ·, 3=wavy ～ */
  mouthShape: number;
}

/** Interpolate all face expression parameters */
export function lerpFaceExpression(
  from: FaceExpression,
  to: FaceExpression,
  t: number,
): FaceExpression {
  const lerp = (a: number, b: number) => a + (b - a) * t;
  return {
    eyeOpenness: lerp(from.eyeOpenness, to.eyeOpenness),
    pupilSize: lerp(from.pupilSize, to.pupilSize),
    pupilOffsetX: lerp(from.pupilOffsetX, to.pupilOffsetX),
    pupilOffsetY: lerp(from.pupilOffsetY, to.pupilOffsetY),
    mouthCurve: lerp(from.mouthCurve, to.mouthCurve),
    mouthOpenness: lerp(from.mouthOpenness, to.mouthOpenness),
    mouthWidth: lerp(from.mouthWidth, to.mouthWidth),
    browRaise: lerp(from.browRaise, to.browRaise),
    browTilt: lerp(from.browTilt, to.browTilt),
    blinkRate: lerp(from.blinkRate, to.blinkRate),
    blush: lerp(from.blush, to.blush),
    eyeShape: lerp(from.eyeShape, to.eyeShape),
    mouthShape: lerp(from.mouthShape, to.mouthShape),
  };
}

// ─── Sprint 142: Staggered Feature Transitions ──────────────────
// Per-feature timing offsets (ms) for natural sequential activation:
// brows react FIRST (surprise reflex) → eyes follow → mouth lags → blush is autonomic
export const FEATURE_STAGGER: Record<keyof FaceExpression, number> = {
  browRaise: 0,        // brows react first (surprise reflex)
  browTilt: 0,
  eyeOpenness: 30,     // eyes follow brows
  pupilSize: 30,
  pupilOffsetX: 40,    // gaze shifts slightly later
  pupilOffsetY: 40,
  mouthCurve: 70,      // mouth is slower (muscle group lag)
  mouthOpenness: 70,
  mouthWidth: 70,
  mouthShape: 70,
  blush: 120,          // blush is autonomic — slowest
  eyeShape: 100,       // happy-eyes crossfade
  blinkRate: 0,        // immediate (not visual)
};

/** Cubic ease-out: decelerates toward end */
export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/** Cubic ease-in: accelerates from start */
export function easeInCubic(t: number): number {
  return t * t * t;
}

/**
 * Sprint 142 Phase 3: Lerp that dwells at zero when crossing sign boundary.
 * Prevents jarring instant flips (e.g. concerned→excited mouth curve).
 * Uses split-ease: easeOut to zero, then easeIn from zero.
 */
export function momentumLerp(from: number, to: number, t: number): number {
  if (from * to < 0) { // sign differs → crosses zero
    const zeroT = Math.abs(from) / (Math.abs(from) + Math.abs(to));
    if (t < zeroT) {
      return from * (1 - easeOutCubic(t / zeroT));
    } else {
      return to * easeInCubic((t - zeroT) / (1 - zeroT));
    }
  }
  return from + (to - from) * t;
}

/**
 * Sprint 143b: Anticipation ease — pulls back slightly before moving forward (Disney Principle #6).
 * @param t - Progress 0→1
 * @param pullback - Max pullback amount (default 0.1)
 */
export function anticipateEase(t: number, pullback: number = 0.1): number {
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  if (t < 0.15) {
    // Pull back phase (0→-pullback over first 15%)
    return -pullback * Math.sin((t / 0.15) * Math.PI * 0.5);
  }
  // Main motion (15%→100%)
  const mainT = (t - 0.15) / 0.85;
  return -pullback * Math.cos(mainT * Math.PI * 0.5) + mainT;
}

/** Keys that use momentum lerp when crossing zero (signed params only) */
const MOMENTUM_KEYS: Set<keyof FaceExpression> = new Set([
  "mouthCurve", "browRaise", "browTilt",
]);

/**
 * Sprint 142: Lerp with per-feature stagger timing.
 * Each facial feature starts its transition at a different offset,
 * creating natural sequential activation (brows→eyes→mouth→blush).
 *
 * @param from - Starting face expression
 * @param to - Target face expression
 * @param elapsedMs - Milliseconds since transition started
 * @param durationMs - Total transition duration per feature (default 400ms)
 */
export function staggeredLerpFace(
  from: FaceExpression, to: FaceExpression,
  elapsedMs: number, durationMs: number = 400,
): FaceExpression {
  const result = {} as FaceExpression;
  const keys = Object.keys(FEATURE_STAGGER) as (keyof FaceExpression)[];
  for (const key of keys) {
    const delay = FEATURE_STAGGER[key];
    const localElapsed = Math.max(0, elapsedMs - delay);
    const rawT = Math.min(localElapsed / durationMs, 1);
    // Sprint 143b: Apply anticipation ease for brows/eyes (Disney Principle #6)
    let t: number;
    if (key === "browRaise" || key === "eyeOpenness") {
      t = anticipateEase(rawT, 0.08);
    } else {
      // Apply easeInOutCubic per-feature
      t = rawT < 0.5 ? 4 * rawT * rawT * rawT : 1 - Math.pow(-2 * rawT + 2, 3) / 2;
    }
    if (MOMENTUM_KEYS.has(key)) {
      (result[key] as number) = momentumLerp(from[key] as number, to[key] as number, t);
    } else {
      (result[key] as number) = (from[key] as number) + ((to[key] as number) - (from[key] as number)) * t;
    }
  }
  return result;
}

/**
 * Face expression presets for each avatar state.
 *
 * idle: calm, slight smile, natural blink rate
 * listening: attentive, pupils up toward user, raised brows
 * thinking: concentrated, pupils up-right, slight furrow
 * speaking: animated, mouth oscillates (overridden in rAF), normal blink
 * complete: happy smile, relaxed, blush + happy eyes
 * error: wide-eyed, small pupils, worried furrow
 */
export const FACE_EXPRESSIONS: Record<AvatarState, FaceExpression> = {
  idle: {
    eyeOpenness: 1.0,
    pupilSize: 1.0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,
    mouthCurve: 0.15,
    mouthOpenness: 0,
    mouthWidth: 0.9,
    browRaise: 0,
    browTilt: 0,
    blinkRate: 15,
    blush: 0.15,
    eyeShape: 0.05,
    mouthShape: 1, // cat ω — kawaii idle
  },
  listening: {
    eyeOpenness: 1.1,
    pupilSize: 1.1,
    pupilOffsetX: 0,
    pupilOffsetY: -0.2,
    mouthCurve: 0.1,
    mouthOpenness: 0,
    mouthWidth: 1.0,
    browRaise: 0.2,
    browTilt: 0,
    blinkRate: 12,
    blush: 0.1,
    eyeShape: 0,
    mouthShape: 0, // default slight smile
  },
  thinking: {
    eyeOpenness: 0.9,
    pupilSize: 0.9,
    pupilOffsetX: 0.3,
    pupilOffsetY: -0.3,
    mouthCurve: 0,
    mouthOpenness: 0,
    mouthWidth: 0.8,
    browRaise: -0.3,
    browTilt: 0.2,
    blinkRate: 8,
    blush: 0,
    eyeShape: 0,
    mouthShape: 2, // dot · — contemplative
  },
  speaking: {
    eyeOpenness: 1.05,
    pupilSize: 1.05,
    pupilOffsetX: 0,
    pupilOffsetY: 0.1,        // looking slightly toward user (VTuber convention)
    mouthCurve: 0.2,
    mouthOpenness: 0.3,
    mouthWidth: 1.1,
    browRaise: 0.15,           // engaged brow lift
    browTilt: 0,
    blinkRate: 18,
    blush: 0.15,
    eyeShape: 0.05,            // hint of warmth while speaking
    mouthShape: 0, // default, animated by noise
  },
  complete: {
    eyeOpenness: 1.0,
    pupilSize: 1.0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,
    mouthCurve: 0.5,
    mouthOpenness: 0,
    mouthWidth: 1.2,
    browRaise: 0.1,
    browTilt: 0,
    blinkRate: 15,
    blush: 0.6,
    eyeShape: 0.85,
    mouthShape: 0, // default big smile
  },
  error: {
    eyeOpenness: 1.2,
    pupilSize: 0.8,
    pupilOffsetX: 0,
    pupilOffsetY: 0,
    mouthCurve: -0.4,
    mouthOpenness: 0.15,
    mouthWidth: 0.9,
    browRaise: -0.5,
    browTilt: -0.3,
    blinkRate: 20,
    blush: 0,
    eyeShape: 0,
    mouthShape: 3, // wavy ～ — nervous
  },
};
