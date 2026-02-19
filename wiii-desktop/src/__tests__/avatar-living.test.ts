/**
 * Tests for "Living Wiii" enhancements — Sprint 133.
 * Idle personality system, speaking face tuning, mood expression fixes,
 * iris mood tinting, all integrated into the avatar animation hook.
 */
import { describe, it, expect } from "vitest";

// ─── Imports ──────────────────────────────────────────────────────────────────
import {
  FACE_EXPRESSIONS,
  lerpFaceExpression,
} from "@/lib/avatar/face-config";
import type { FaceExpression } from "@/lib/avatar/face-config";
import {
  MOOD_THEMES,
  applyMoodToExpression,
} from "@/lib/avatar/mood-theme";
// MoodType used implicitly via MOOD_THEMES keys

// ═══════════════════════════════════════════════════════════════════════════════
// 1. SPEAKING STATE FACE SIGNATURE
// ═══════════════════════════════════════════════════════════════════════════════

describe("Speaking state: face signature", () => {
  const speaking = FACE_EXPRESSIONS.speaking;
  const idle = FACE_EXPRESSIONS.idle;

  it("speaking has engaged pupil offset (looking toward user)", () => {
    expect(speaking.pupilOffsetY).toBeGreaterThan(0);
    expect(speaking.pupilOffsetY).toBeCloseTo(0.1, 2);
  });

  it("speaking has raised brows (engaged expression)", () => {
    expect(speaking.browRaise).toBeGreaterThan(idle.browRaise);
    expect(speaking.browRaise).toBeCloseTo(0.15, 2);
  });

  it("speaking has engaged blush (≥ idle)", () => {
    expect(speaking.blush).toBeGreaterThanOrEqual(idle.blush);
    expect(speaking.blush).toBeCloseTo(0.15, 2);
  });

  it("speaking has hint of eye warmth (eyeShape > 0)", () => {
    expect(speaking.eyeShape).toBeGreaterThan(0);
    expect(speaking.eyeShape).toBeCloseTo(0.05, 2);
  });

  it("speaking is visually distinct from idle", () => {
    // At least 3 parameters should differ meaningfully
    let diffs = 0;
    const keys: (keyof FaceExpression)[] = [
      "eyeOpenness", "pupilSize", "pupilOffsetX", "pupilOffsetY",
      "mouthCurve", "browRaise", "blush", "eyeShape",
    ];
    for (const k of keys) {
      if (Math.abs(speaking[k] - idle[k]) > 0.02) diffs++;
    }
    expect(diffs).toBeGreaterThanOrEqual(3);
  });

  it("speaking has slightly wider eyes than idle", () => {
    expect(speaking.eyeOpenness).toBeGreaterThanOrEqual(idle.eyeOpenness);
  });

  it("speaking retains high blink rate (animated)", () => {
    expect(speaking.blinkRate).toBe(18);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 2. CONCERNED MOOD — BLUSH SUPPRESSION
// ═══════════════════════════════════════════════════════════════════════════════

describe("Concerned mood: blush suppression", () => {
  it("concerned expressionMod includes negative blush", () => {
    const mod = MOOD_THEMES.concerned.expressionMod;
    expect(mod.blush).toBeDefined();
    expect(mod.blush!).toBeLessThan(0);
  });

  it("concerned reduces blush from complete state", () => {
    const complete = { ...FACE_EXPRESSIONS.complete }; // blush: 0.6
    const result = applyMoodToExpression(complete, "concerned");
    expect(result.blush).toBeLessThan(complete.blush);
  });

  it("concerned blush never goes below 0", () => {
    // idle has blush 0.15, concerned mod is -0.3 → should clamp to 0
    const idle = { ...FACE_EXPRESSIONS.idle };
    const result = applyMoodToExpression(idle, "concerned");
    expect(result.blush).toBeGreaterThanOrEqual(0);
  });

  it("concerned preserves brow furrow from before", () => {
    const mod = MOOD_THEMES.concerned.expressionMod;
    expect(mod.browRaise).toBeLessThan(0);
    expect(mod.browTilt).toBeLessThan(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 3. GENTLE MOOD — DISTINCTIVE PUPIL
// ═══════════════════════════════════════════════════════════════════════════════

describe("Gentle mood: distinctive dreamy pupil", () => {
  it("gentle expressionMod includes negative pupilSize", () => {
    const mod = MOOD_THEMES.gentle.expressionMod;
    expect(mod.pupilSize).toBeDefined();
    expect(mod.pupilSize!).toBeLessThan(0);
  });

  it("gentle reduces pupil size (soft dreamy look)", () => {
    const idle = { ...FACE_EXPRESSIONS.idle }; // pupilSize: 1.0
    const result = applyMoodToExpression(idle, "gentle");
    expect(result.pupilSize).toBeLessThan(idle.pupilSize);
  });

  it("warm does NOT have negative pupilSize (distinct from gentle)", () => {
    const warmMod = MOOD_THEMES.warm.expressionMod;
    expect(warmMod.pupilSize ?? 0).toBeGreaterThanOrEqual(0);
  });

  it("gentle and warm are now more distinct", () => {
    const idle = { ...FACE_EXPRESSIONS.idle };
    const gentle = applyMoodToExpression(idle, "gentle");
    const warm = applyMoodToExpression(idle, "warm");
    // Pupil size should differ
    expect(gentle.pupilSize).not.toBeCloseTo(warm.pupilSize, 1);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 4. IDLE PERSONALITY SYSTEM — Source Analysis
// ═══════════════════════════════════════════════════════════════════════════════

describe("Idle personality system: source verification", () => {
  // We verify the animation hook source contains idle personality code
  // Using raw import to avoid heavy component rendering

  let hookSource: string;

  it("loads hook source", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    hookSource = (mod as { default: string }).default;
    expect(hookSource).toBeTruthy();
  });

  it("defines IdlePose type", () => {
    expect(hookSource).toContain("IdlePose");
    expect(hookSource).toContain("curious_right");
    expect(hookSource).toContain("curious_left");
    expect(hookSource).toContain("widen");
    expect(hookSource).toContain("squint");
    expect(hookSource).toContain("glance_up");
  });

  it("defines IdlePoseState interface", () => {
    expect(hookSource).toContain("IdlePoseState");
    expect(hookSource).toContain("blendIn");
    expect(hookSource).toContain("blendOut");
  });

  it("has idlePoseIntensity function with envelope logic", () => {
    expect(hookSource).toContain("idlePoseIntensity");
    // Should have blend-in, hold, and blend-out phases
    expect(hookSource).toContain("blendIn");
    expect(hookSource).toContain("hold");
    expect(hookSource).toContain("blendOut");
  });

  it("has randomIdleInterval (8-18s range)", () => {
    expect(hookSource).toContain("randomIdleInterval");
    // 8 + Math.random() * 10 gives 8-18
    expect(hookSource).toMatch(/8\s*\+\s*Math\.random\(\)\s*\*\s*10/);
  });

  it("has pickIdlePose with all 5 poses", () => {
    expect(hookSource).toContain("pickIdlePose");
    expect(hookSource).toContain('"curious_right"');
    expect(hookSource).toContain('"curious_left"');
    expect(hookSource).toContain('"widen"');
    expect(hookSource).toContain('"squint"');
    expect(hookSource).toContain('"glance_up"');
  });

  it("defines IDLE_POSE_MODS with facial modifiers", () => {
    expect(hookSource).toContain("IDLE_POSE_MODS");
    // Curious poses have pupil offset
    expect(hookSource).toContain("_pupilX");
    expect(hookSource).toContain("_pupilY");
    // Widen pose has eye openness
    expect(hookSource).toContain("eyeOpenness");
  });

  it("has idleTimerRef and idlePoseRef refs", () => {
    expect(hookSource).toContain("idleTimerRef");
    expect(hookSource).toContain("idlePoseRef");
  });

  it("resets idle personality on state change", () => {
    // In state change useEffect
    expect(hookSource).toContain("idleTimerRef.current = randomIdleInterval()");
  });

  it("only runs idle personality during idle state", () => {
    expect(hookSource).toContain('state === "idle"');
    // The idle personality block is guarded by state check
    expect(hookSource).toContain("idlePoseRef.current");
  });

  it("applies pose intensity to face expression modifiers", () => {
    // Should multiply delta by intensity
    expect(hookSource).toContain("delta * intensity");
  });

  it("checks pose completion and resets", () => {
    expect(hookSource).toContain("idlePoseDuration");
    expect(hookSource).toContain('pose: "none"');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 5. IRIS MOOD TINTING
// ═══════════════════════════════════════════════════════════════════════════════

describe("Iris mood tinting: source verification", () => {
  let hookSource: string;

  it("loads hook source", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    hookSource = (mod as { default: string }).default;
    expect(hookSource).toBeTruthy();
  });

  it("defines MOOD_IRIS_FILTER record", () => {
    expect(hookSource).toContain("MOOD_IRIS_FILTER");
  });

  it("has filter for all 5 moods", () => {
    expect(hookSource).toContain('neutral: ""');
    expect(hookSource).toContain("excited:");
    expect(hookSource).toContain("concerned:");
    expect(hookSource).toContain("gentle:");
    expect(hookSource).toContain("warm:");
  });

  it("neutral has empty filter (no tint)", () => {
    expect(hookSource).toMatch(/neutral:\s*""/);
  });

  it("concerned uses hue-rotate for cooler eye color", () => {
    expect(hookSource).toMatch(/concerned:.*hue-rotate/);
  });

  it("excited uses saturate for brighter eyes", () => {
    expect(hookSource).toMatch(/excited:.*saturate/);
  });

  it("gentle uses hue-rotate for softer color", () => {
    expect(hookSource).toMatch(/gentle:.*hue-rotate/);
  });

  it("applies filter via leftIrisRef and rightIrisRef style", () => {
    expect(hookSource).toContain("leftIrisRef.current.style.filter");
    expect(hookSource).toContain("rightIrisRef.current.style.filter");
  });

  it("tracks previous filter to avoid redundant writes", () => {
    expect(hookSource).toContain("prevIrisFilterRef");
  });

  it("switches filter at mood transition midpoint", () => {
    expect(hookSource).toContain("moodT >= 0.5");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 6. IDLE POSE MATH — Unit Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe("Idle pose intensity envelope", () => {
  // Test the mathematical envelope by reproducing the logic
  function testIntensity(elapsed: number, blendIn: number, hold: number, blendOut: number): number {
    if (elapsed < blendIn) return elapsed / blendIn;
    if (elapsed < blendIn + hold) return 1;
    const fadeElapsed = elapsed - blendIn - hold;
    if (fadeElapsed < blendOut) return 1 - fadeElapsed / blendOut;
    return 0;
  }

  it("starts at 0 intensity", () => {
    expect(testIntensity(0, 0.3, 1.0, 0.5)).toBe(0);
  });

  it("ramps up during blend-in", () => {
    expect(testIntensity(0.15, 0.3, 1.0, 0.5)).toBeCloseTo(0.5, 2);
  });

  it("reaches full intensity during hold", () => {
    expect(testIntensity(0.5, 0.3, 1.0, 0.5)).toBe(1);
    expect(testIntensity(1.0, 0.3, 1.0, 0.5)).toBe(1);
  });

  it("ramps down during blend-out", () => {
    const val = testIntensity(1.55, 0.3, 1.0, 0.5); // 0.25 into blendOut
    expect(val).toBeCloseTo(0.5, 2);
  });

  it("reaches 0 after full duration", () => {
    expect(testIntensity(1.8, 0.3, 1.0, 0.5)).toBe(0);
    expect(testIntensity(2.5, 0.3, 1.0, 0.5)).toBe(0);
  });

  it("total duration matches blendIn + hold + blendOut", () => {
    const total = 0.3 + 1.0 + 0.5;
    expect(total).toBe(1.8);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 7. FACE PRESET DIFFERENTIATION
// ═══════════════════════════════════════════════════════════════════════════════

describe("Face preset differentiation", () => {
  const states = Object.keys(FACE_EXPRESSIONS) as (keyof typeof FACE_EXPRESSIONS)[];

  it("all 6 states have unique visual signatures", () => {
    // Each pair of states should differ in at least 2 key parameters
    const signatureKeys: (keyof FaceExpression)[] = [
      "eyeOpenness", "pupilOffsetX", "pupilOffsetY", "mouthCurve",
      "browRaise", "blush", "eyeShape", "mouthShape",
    ];
    for (let i = 0; i < states.length; i++) {
      for (let j = i + 1; j < states.length; j++) {
        const a = FACE_EXPRESSIONS[states[i]];
        const b = FACE_EXPRESSIONS[states[j]];
        let diffs = 0;
        for (const k of signatureKeys) {
          if (Math.abs(a[k] - b[k]) > 0.03) diffs++;
        }
        expect(diffs).toBeGreaterThanOrEqual(2);
      }
    }
  });

  it("idle and speaking now differ in pupilOffsetY", () => {
    expect(FACE_EXPRESSIONS.idle.pupilOffsetY).toBe(0);
    expect(FACE_EXPRESSIONS.speaking.pupilOffsetY).toBe(0.1);
  });

  it("listening has upward gaze, speaking has slight downward", () => {
    expect(FACE_EXPRESSIONS.listening.pupilOffsetY).toBeLessThan(0); // up
    expect(FACE_EXPRESSIONS.speaking.pupilOffsetY).toBeGreaterThan(0); // down toward user
  });

  it("complete has strongest blush", () => {
    const blushValues = states.map((s) => FACE_EXPRESSIONS[s].blush);
    const maxBlush = Math.max(...blushValues);
    expect(FACE_EXPRESSIONS.complete.blush).toBe(maxBlush);
  });

  it("error has widest eyes + smallest pupils (startled)", () => {
    expect(FACE_EXPRESSIONS.error.eyeOpenness).toBe(1.2);
    expect(FACE_EXPRESSIONS.error.pupilSize).toBe(0.8);
  });

  it("thinking uses dot mouth (shape 2)", () => {
    expect(FACE_EXPRESSIONS.thinking.mouthShape).toBe(2);
  });

  it("idle uses cat-ω mouth (shape 1)", () => {
    expect(FACE_EXPRESSIONS.idle.mouthShape).toBe(1);
  });

  it("error uses wavy mouth (shape 3)", () => {
    expect(FACE_EXPRESSIONS.error.mouthShape).toBe(3);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 8. MOOD EXPRESSION INTERACTIONS
// ═══════════════════════════════════════════════════════════════════════════════

describe("Mood × State expression interactions", () => {
  it("excited + complete = maximum happy (clamped)", () => {
    const result = applyMoodToExpression({ ...FACE_EXPRESSIONS.complete }, "excited");
    // mouthCurve: 0.5 + 0.45 = 0.95 (Sprint 140: bold 3x boost)
    expect(result.mouthCurve).toBeCloseTo(0.95, 2);
    // blush: 0.6 + 0.5 = 1.1 → clamped to 1.0
    expect(result.blush).toBeCloseTo(1.0, 2);
  });

  it("concerned + error = deep worry (clamped brow)", () => {
    const result = applyMoodToExpression({ ...FACE_EXPRESSIONS.error }, "concerned");
    // browRaise: -0.5 + -0.15 = -0.65 → clamped to -1
    expect(result.browRaise).toBeGreaterThanOrEqual(-1);
    // blush: 0 + -0.3 = -0.3 → clamped to 0
    expect(result.blush).toBe(0);
  });

  it("gentle + idle = soft dreamy face", () => {
    const result = applyMoodToExpression({ ...FACE_EXPRESSIONS.idle }, "gentle");
    // eyeOpenness: 1.0 - 0.15 = 0.85 (Sprint 140: bold 3x boost)
    expect(result.eyeOpenness).toBeCloseTo(0.85, 2);
    // pupilSize: 1.0 - 0.1 = 0.9
    expect(result.pupilSize).toBeCloseTo(0.9, 2);
    // mouthCurve: 0.15 + 0.15 = 0.3
    expect(result.mouthCurve).toBeCloseTo(0.3, 2);
  });

  it("warm + speaking = engaged warmth", () => {
    const result = applyMoodToExpression({ ...FACE_EXPRESSIONS.speaking }, "warm");
    // blush: 0.15 + 0.4 = 0.55 (Sprint 140: bold 3x boost)
    expect(result.blush).toBeCloseTo(0.55, 2);
    // eyeShape: 0.05 + 0.35 = 0.40 (Sprint 140: bold 3.5x boost)
    expect(result.eyeShape).toBeCloseTo(0.40, 2);
  });

  it("neutral mood never changes any expression", () => {
    for (const state of Object.keys(FACE_EXPRESSIONS) as (keyof typeof FACE_EXPRESSIONS)[]) {
      const base = { ...FACE_EXPRESSIONS[state] };
      const result = applyMoodToExpression(base, "neutral");
      expect(result).toEqual(base);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 9. BACKWARD COMPATIBILITY
// ═══════════════════════════════════════════════════════════════════════════════

describe("Backward compatibility", () => {
  it("all existing state presets still have required fields", () => {
    const requiredKeys: (keyof FaceExpression)[] = [
      "eyeOpenness", "pupilSize", "pupilOffsetX", "pupilOffsetY",
      "mouthCurve", "mouthOpenness", "mouthWidth", "browRaise",
      "browTilt", "blinkRate", "blush", "eyeShape", "mouthShape",
    ];
    for (const [, preset] of Object.entries(FACE_EXPRESSIONS)) {
      for (const key of requiredKeys) {
        expect(preset[key]).toBeDefined();
        expect(typeof preset[key]).toBe("number");
      }
    }
  });

  it("lerpFaceExpression still works with new values", () => {
    const from = FACE_EXPRESSIONS.idle;
    const to = FACE_EXPRESSIONS.speaking;
    const mid = lerpFaceExpression(from, to, 0.5);
    // Speaking now has pupilOffsetY: 0.1, idle has 0 → mid should be 0.05
    expect(mid.pupilOffsetY).toBeCloseTo(0.05, 2);
    // browRaise: 0 → 0.15 → mid 0.075
    expect(mid.browRaise).toBeCloseTo(0.075, 2);
  });

  it("mood themes all have required fields", () => {
    const requiredKeys: (keyof (typeof MOOD_THEMES)["neutral"])[] = [
      "particleColor", "indicatorColor", "expressionMod",
      "noiseAmplitudeMod", "timeSpeedMod", "particleCountMod", "glowIntensityBoost",
    ];
    for (const [, theme] of Object.entries(MOOD_THEMES)) {
      for (const key of requiredKeys) {
        expect(theme[key]).toBeDefined();
      }
    }
  });

  it("applyMoodToExpression with zero intensity returns base", () => {
    const base = { ...FACE_EXPRESSIONS.idle };
    const result = applyMoodToExpression(base, "excited", 0);
    expect(result).toEqual(base);
  });
});
