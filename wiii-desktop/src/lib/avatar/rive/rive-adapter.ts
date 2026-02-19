/**
 * Rive Adapter — Sprint 141: Pure functions mapping emotion engine → Rive inputs.
 *
 * This module is rendering-agnostic — no Rive SDK imports.
 * It converts FaceExpression, MoodType, SoulEmotionData, and AvatarState
 * into a flat Record<string, number> of Rive state machine input values.
 */
import type { FaceExpression } from "../face-config";
import type { AvatarState } from "../types";
import type { MoodType } from "../mood-theme";
import type { SoulEmotionData } from "../types";
import { FACE_EXPRESSIONS, lerpFaceExpression } from "../face-config";
import { applyMoodToExpression } from "../mood-theme";
import {
  RIVE_INPUTS,
  PARAM_RANGES,
  STATE_ENERGY,
  HAND_GESTURES,
  type RangeMapping,
} from "./rive-config";

// ── Range mapping ───────────────────────────────────────────────────

/** Map a value from source range to Rive range, clamped. */
export function mapToRive(value: number, mapping: RangeMapping): number {
  const { srcMin, srcMax, riveMin, riveMax } = mapping;
  const normalized = (value - srcMin) / (srcMax - srcMin);
  const clamped = Math.max(0, Math.min(1, normalized));
  return riveMin + clamped * (riveMax - riveMin);
}

/** Map a Rive value back to source range. */
export function mapFromRive(riveValue: number, mapping: RangeMapping): number {
  const { srcMin, srcMax, riveMin, riveMax } = mapping;
  const normalized = (riveValue - riveMin) / (riveMax - riveMin);
  const clamped = Math.max(0, Math.min(1, normalized));
  return srcMin + clamped * (srcMax - srcMin);
}

// ── FaceExpression → Rive inputs ────────────────────────────────────

/** Convert a resolved FaceExpression to Rive Number input values. */
export function faceExpressionToRive(face: FaceExpression): Record<string, number> {
  return {
    [RIVE_INPUTS.eyeOpenness]: mapToRive(face.eyeOpenness, PARAM_RANGES.eyeOpenness),
    [RIVE_INPUTS.pupilSize]: mapToRive(face.pupilSize, PARAM_RANGES.pupilSize),
    [RIVE_INPUTS.gazeX]: mapToRive(face.pupilOffsetX, PARAM_RANGES.gazeX),
    [RIVE_INPUTS.gazeY]: mapToRive(face.pupilOffsetY, PARAM_RANGES.gazeY),
    [RIVE_INPUTS.eyeShape]: mapToRive(face.eyeShape, PARAM_RANGES.eyeShape),
    [RIVE_INPUTS.mouthCurve]: mapToRive(face.mouthCurve, PARAM_RANGES.mouthCurve),
    [RIVE_INPUTS.mouthOpenness]: mapToRive(face.mouthOpenness, PARAM_RANGES.mouthOpenness),
    [RIVE_INPUTS.mouthWidth]: mapToRive(face.mouthWidth, PARAM_RANGES.mouthWidth),
    [RIVE_INPUTS.mouthShape]: mapToRive(face.mouthShape, PARAM_RANGES.mouthShape),
    [RIVE_INPUTS.browRaise]: mapToRive(face.browRaise, PARAM_RANGES.browRaise),
    [RIVE_INPUTS.browTilt]: mapToRive(face.browTilt, PARAM_RANGES.browTilt),
    [RIVE_INPUTS.blush]: mapToRive(face.blush, PARAM_RANGES.blush),
  };
}

// ── Full state resolution ───────────────────────────────────────────

export interface ResolvedAvatarState {
  /** All Rive Number input values (name → 0-100) */
  inputs: Record<string, number>;
  /** Whether mouth should oscillate (speaking state) */
  isSpeaking: boolean;
  /** Hand gesture value */
  handGesture: number;
}

/**
 * Resolve the complete avatar state from all input sources.
 *
 * Priority (highest wins):
 *  1. Soul emotion face overrides (partial, blended by intensity)
 *  2. Mood overlay (additive modifiers)
 *  3. State base expression
 *
 * @param state - Avatar lifecycle state
 * @param mood - Current emotional mood
 * @param soulEmotion - LLM-driven face override (nullable)
 * @returns Fully resolved Rive input values
 */
export function resolveAvatarState(
  state: AvatarState,
  mood: MoodType,
  soulEmotion: SoulEmotionData | null,
): ResolvedAvatarState {
  // 1. Base expression from state
  const baseFace = FACE_EXPRESSIONS[state] || FACE_EXPRESSIONS.idle;

  // 2. Apply mood overlay (additive blend)
  let face = applyMoodToExpression(baseFace, mood, 1.0);

  // 3. Apply soul emotion override (highest priority)
  if (soulEmotion && soulEmotion.intensity > 0 && soulEmotion.face) {
    // Build a target expression from soul data
    const soulTarget: FaceExpression = { ...face };
    for (const [key, value] of Object.entries(soulEmotion.face)) {
      if (key in soulTarget && typeof value === "number") {
        (soulTarget as unknown as Record<string, number>)[key] = value;
      }
    }
    // Blend toward soul target by intensity
    face = lerpFaceExpression(face, soulTarget, soulEmotion.intensity);

    // Soul mood overrides mood-based expression if present
    if (soulEmotion.mood && soulEmotion.mood !== "neutral") {
      face = applyMoodToExpression(face, soulEmotion.mood, soulEmotion.intensity * 0.5);
    }
  }

  // Convert to Rive inputs
  const inputs = faceExpressionToRive(face);

  // Add energy from state
  inputs[RIVE_INPUTS.energy] = STATE_ENERGY[state] ?? 30;

  // Determine hand gesture based on state
  let handGesture: number = HAND_GESTURES.rest;
  if (state === "complete") handGesture = HAND_GESTURES.wave;
  if (state === "thinking") handGesture = HAND_GESTURES.point; // chin rest
  if (state === "error") handGesture = HAND_GESTURES.coverMouth;
  inputs[RIVE_INPUTS.handGesture] = handGesture;

  return {
    inputs,
    isSpeaking: state === "speaking",
    handGesture,
  };
}

// ── Smooth interpolation helper ─────────────────────────────────────

/**
 * Smoothly interpolate between current and target input values.
 * Uses exponential decay for natural-feeling transitions.
 *
 * @param current - Current input values
 * @param target - Target input values
 * @param speed - Interpolation speed (0-1, higher = faster). Default 0.08
 * @returns New interpolated values
 */
export function lerpRiveInputs(
  current: Record<string, number>,
  target: Record<string, number>,
  speed: number = 0.08,
): Record<string, number> {
  const result: Record<string, number> = {};

  for (const key of Object.keys(target)) {
    const cur = current[key] ?? target[key];
    const tgt = target[key];
    const diff = tgt - cur;

    // Snap if close enough (avoid floating point noise)
    if (Math.abs(diff) < 0.1) {
      result[key] = tgt;
    } else {
      result[key] = cur + diff * speed;
    }
  }

  return result;
}
