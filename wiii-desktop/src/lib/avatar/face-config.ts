/**
 * Face expression configuration — Sprint 129: SVG Face on Blob.
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
  };
}

/**
 * Face expression presets for each avatar state.
 *
 * idle: calm, slight smile, natural blink rate
 * listening: attentive, pupils up toward user, raised brows
 * thinking: concentrated, pupils up-right, slight furrow
 * speaking: animated, mouth oscillates (overridden in rAF), normal blink
 * complete: happy smile, relaxed
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
    mouthWidth: 1.0,
    browRaise: 0,
    browTilt: 0,
    blinkRate: 15,
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
  },
  speaking: {
    eyeOpenness: 1.0,
    pupilSize: 1.0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,
    mouthCurve: 0.2,
    mouthOpenness: 0.3,
    mouthWidth: 1.1,
    browRaise: 0.1,
    browTilt: 0,
    blinkRate: 18,
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
  },
};
