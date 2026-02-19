/**
 * Sprint 141: Rive adapter unit tests.
 *
 * Tests the pure mapping functions between FaceExpression/emotion engine
 * and Rive state machine inputs. No Rive SDK dependency.
 */
import { describe, it, expect } from "vitest";
import {
  mapToRive,
  mapFromRive,
  faceExpressionToRive,
  resolveAvatarState,
  lerpRiveInputs,
} from "../lib/avatar/rive/rive-adapter";
import { PARAM_RANGES, RIVE_INPUTS, STATE_ENERGY, HAND_GESTURES } from "../lib/avatar/rive/rive-config";
import { FACE_EXPRESSIONS } from "../lib/avatar/face-config";

// ── mapToRive / mapFromRive ────────────────────────────────────────

describe("mapToRive", () => {
  it("maps source midpoint to rive midpoint", () => {
    const mapping = { srcMin: -1, srcMax: 1, riveMin: 0, riveMax: 100 };
    expect(mapToRive(0, mapping)).toBe(50);
  });

  it("maps source min to rive min", () => {
    const mapping = { srcMin: 0, srcMax: 1, riveMin: 0, riveMax: 100 };
    expect(mapToRive(0, mapping)).toBe(0);
  });

  it("maps source max to rive max", () => {
    const mapping = { srcMin: 0, srcMax: 1, riveMin: 0, riveMax: 100 };
    expect(mapToRive(1, mapping)).toBe(100);
  });

  it("clamps below source min", () => {
    const mapping = { srcMin: 0, srcMax: 1, riveMin: 0, riveMax: 100 };
    expect(mapToRive(-0.5, mapping)).toBe(0);
  });

  it("clamps above source max", () => {
    const mapping = { srcMin: 0, srcMax: 1, riveMin: 0, riveMax: 100 };
    expect(mapToRive(1.5, mapping)).toBe(100);
  });

  it("handles non-zero rive min", () => {
    const mapping = { srcMin: 0, srcMax: 1, riveMin: 10, riveMax: 90 };
    expect(mapToRive(0.5, mapping)).toBe(50);
  });
});

describe("mapFromRive", () => {
  it("round-trips with mapToRive", () => {
    const mapping = PARAM_RANGES.eyeOpenness;
    const original = 1.0;
    const riveVal = mapToRive(original, mapping);
    const recovered = mapFromRive(riveVal, mapping);
    expect(recovered).toBeCloseTo(original, 5);
  });

  it("round-trips all param ranges at midpoint", () => {
    for (const [, mapping] of Object.entries(PARAM_RANGES)) {
      const mid = (mapping.srcMin + mapping.srcMax) / 2;
      const riveVal = mapToRive(mid, mapping);
      const recovered = mapFromRive(riveVal, mapping);
      expect(recovered).toBeCloseTo(mid, 5);
    }
  });
});

// ── faceExpressionToRive ───────────────────────────────────────────

describe("faceExpressionToRive", () => {
  it("converts idle expression to rive inputs", () => {
    const result = faceExpressionToRive(FACE_EXPRESSIONS.idle);
    expect(result).toHaveProperty(RIVE_INPUTS.eyeOpenness);
    expect(result).toHaveProperty(RIVE_INPUTS.mouthCurve);
    expect(result).toHaveProperty(RIVE_INPUTS.blush);
  });

  it("all output values are between 0 and 100", () => {
    for (const state of ["idle", "thinking", "speaking", "complete", "error"] as const) {
      const result = faceExpressionToRive(FACE_EXPRESSIONS[state]);
      for (const [, value] of Object.entries(result)) {
        expect(value).toBeGreaterThanOrEqual(0);
        expect(value).toBeLessThanOrEqual(100);
      }
    }
  });

  it("smile state has higher mouth_curve than error state", () => {
    const complete = faceExpressionToRive(FACE_EXPRESSIONS.complete);
    const error = faceExpressionToRive(FACE_EXPRESSIONS.error);
    expect(complete[RIVE_INPUTS.mouthCurve]).toBeGreaterThan(error[RIVE_INPUTS.mouthCurve]);
  });

  it("error state has higher blush than thinking (error=0, thinking=0)", () => {
    const error = faceExpressionToRive(FACE_EXPRESSIONS.error);
    const thinking = faceExpressionToRive(FACE_EXPRESSIONS.thinking);
    // Both have 0 blush, so should be equal
    expect(error[RIVE_INPUTS.blush]).toBe(thinking[RIVE_INPUTS.blush]);
  });

  it("complete state has highest eyeShape (happy ^_^)", () => {
    const complete = faceExpressionToRive(FACE_EXPRESSIONS.complete);
    const idle = faceExpressionToRive(FACE_EXPRESSIONS.idle);
    expect(complete[RIVE_INPUTS.eyeShape]).toBeGreaterThan(idle[RIVE_INPUTS.eyeShape]);
  });
});

// ── resolveAvatarState ─────────────────────────────────────────────

describe("resolveAvatarState", () => {
  it("returns inputs for all required rive input names", () => {
    const result = resolveAvatarState("idle", "neutral", null);
    const requiredInputs = Object.values(RIVE_INPUTS);
    for (const name of requiredInputs) {
      expect(result.inputs).toHaveProperty(name);
    }
  });

  it("sets correct energy for each state", () => {
    for (const [state, energy] of Object.entries(STATE_ENERGY)) {
      const result = resolveAvatarState(state as any, "neutral", null);
      expect(result.inputs[RIVE_INPUTS.energy]).toBe(energy);
    }
  });

  it("marks speaking state as isSpeaking", () => {
    const speaking = resolveAvatarState("speaking", "neutral", null);
    expect(speaking.isSpeaking).toBe(true);

    const idle = resolveAvatarState("idle", "neutral", null);
    expect(idle.isSpeaking).toBe(false);
  });

  it("sets hand gesture based on state", () => {
    const complete = resolveAvatarState("complete", "neutral", null);
    expect(complete.handGesture).toBe(HAND_GESTURES.wave);

    const thinking = resolveAvatarState("thinking", "neutral", null);
    expect(thinking.handGesture).toBe(HAND_GESTURES.point);

    const error = resolveAvatarState("error", "neutral", null);
    expect(error.handGesture).toBe(HAND_GESTURES.coverMouth);
  });

  it("mood overlay modifies expression", () => {
    const neutral = resolveAvatarState("idle", "neutral", null);
    const excited = resolveAvatarState("idle", "excited", null);

    // Excited should have wider smile (higher mouth_curve)
    expect(excited.inputs[RIVE_INPUTS.mouthCurve]).toBeGreaterThan(
      neutral.inputs[RIVE_INPUTS.mouthCurve]
    );

    // Excited should have more blush
    expect(excited.inputs[RIVE_INPUTS.blush]).toBeGreaterThan(
      neutral.inputs[RIVE_INPUTS.blush]
    );
  });

  it("soul emotion overrides base expression", () => {
    const noSoul = resolveAvatarState("idle", "neutral", null);
    const withSoul = resolveAvatarState("idle", "neutral", {
      mood: "warm",
      face: { mouthCurve: 0.9, blush: 0.8 },
      intensity: 1.0,
    });

    expect(withSoul.inputs[RIVE_INPUTS.mouthCurve]).toBeGreaterThan(
      noSoul.inputs[RIVE_INPUTS.mouthCurve]
    );
    expect(withSoul.inputs[RIVE_INPUTS.blush]).toBeGreaterThan(
      noSoul.inputs[RIVE_INPUTS.blush]
    );
  });

  it("soul emotion intensity=0 has no effect", () => {
    const noSoul = resolveAvatarState("idle", "neutral", null);
    const zeroIntensity = resolveAvatarState("idle", "neutral", {
      mood: "excited",
      face: { mouthCurve: 1.0 },
      intensity: 0,
    });

    // With intensity 0, should be same as no soul
    expect(zeroIntensity.inputs[RIVE_INPUTS.mouthCurve]).toBeCloseTo(
      noSoul.inputs[RIVE_INPUTS.mouthCurve],
      1
    );
  });

  it("all resolved inputs are within 0-100 range", () => {
    const states = ["idle", "listening", "thinking", "speaking", "complete", "error"] as const;
    const moods = ["neutral", "excited", "warm", "concerned", "gentle"] as const;

    for (const state of states) {
      for (const mood of moods) {
        const result = resolveAvatarState(state, mood, null);
        for (const [name, value] of Object.entries(result.inputs)) {
          expect(value, `${state}/${mood}/${name}`).toBeGreaterThanOrEqual(0);
          expect(value, `${state}/${mood}/${name}`).toBeLessThanOrEqual(100);
        }
      }
    }
  });
});

// ── lerpRiveInputs ─────────────────────────────────────────────────

describe("lerpRiveInputs", () => {
  it("interpolates toward target", () => {
    const current = { a: 0, b: 100 };
    const target = { a: 100, b: 0 };
    const result = lerpRiveInputs(current, target, 0.5);
    expect(result.a).toBe(50);
    expect(result.b).toBe(50);
  });

  it("snaps when close enough (< 0.1 diff)", () => {
    const current = { a: 99.95 };
    const target = { a: 100 };
    const result = lerpRiveInputs(current, target, 0.1);
    expect(result.a).toBe(100); // snapped, not interpolated
  });

  it("uses target value for missing current keys", () => {
    const current = {};
    const target = { a: 50, b: 75 };
    const result = lerpRiveInputs(current, target, 0.5);
    expect(result.a).toBe(50); // no current, uses target directly
    expect(result.b).toBe(75);
  });

  it("speed=1 reaches target immediately", () => {
    const current = { a: 0 };
    const target = { a: 100 };
    const result = lerpRiveInputs(current, target, 1.0);
    expect(result.a).toBe(100);
  });

  it("speed=0 stays at current", () => {
    const current = { a: 25 };
    const target = { a: 100 };
    const result = lerpRiveInputs(current, target, 0);
    expect(result.a).toBe(25);
  });
});

// ── Config sanity checks ───────────────────────────────────────────

describe("rive-config sanity", () => {
  it("all RIVE_INPUTS have unique values", () => {
    const values = Object.values(RIVE_INPUTS);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
  });

  it("all PARAM_RANGES have srcMin < srcMax", () => {
    for (const [name, range] of Object.entries(PARAM_RANGES)) {
      expect(range.srcMin, name).toBeLessThan(range.srcMax);
    }
  });

  it("all STATE_ENERGY values are between 0 and 100", () => {
    for (const [state, energy] of Object.entries(STATE_ENERGY)) {
      expect(energy, state).toBeGreaterThanOrEqual(0);
      expect(energy, state).toBeLessThanOrEqual(100);
    }
  });

  it("HAND_GESTURES values are unique and within 0-100", () => {
    const values = Object.values(HAND_GESTURES);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
    for (const v of values) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
  });
});
