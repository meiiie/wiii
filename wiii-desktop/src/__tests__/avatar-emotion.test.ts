/**
 * Tests for WiiiEmotionEngine — Sprint 132.
 * Mood → visual mapping, expression modifiers, visual overrides,
 * prop wiring, source integration, barrel exports.
 */
import { describe, it, expect } from "vitest";

// ─── Imports ──────────────────────────────────────────────────────────────────
import {
  MOOD_THEMES,
  applyMoodToExpression,
  applyMoodToVisuals,
} from "@/lib/avatar/mood-theme";
import type { MoodType, MoodTheme } from "@/lib/avatar/mood-theme";
import { FACE_EXPRESSIONS } from "@/lib/avatar/face-config";
import type { FaceExpression } from "@/lib/avatar/face-config";
import type { StateVisuals } from "@/lib/avatar/types";
import { STATE_CONFIG } from "@/lib/avatar/state-config";
import { lerpHexColor } from "@/lib/avatar/use-avatar-animation";

// ═══════════════════════════════════════════════════════════════════════════════
// MOOD THEMES
// ═══════════════════════════════════════════════════════════════════════════════

describe("Mood themes: structure", () => {
  const MOODS: MoodType[] = ["excited", "warm", "concerned", "gentle", "neutral"];

  it("all 5 mood types have themes defined", () => {
    for (const mood of MOODS) {
      expect(MOOD_THEMES[mood]).toBeDefined();
    }
  });

  it("each theme has all required fields", () => {
    const requiredKeys: (keyof MoodTheme)[] = [
      "particleColor",
      "indicatorColor",
      "expressionMod",
      "noiseAmplitudeMod",
      "timeSpeedMod",
      "particleCountMod",
      "glowIntensityBoost",
    ];
    for (const mood of MOODS) {
      for (const key of requiredKeys) {
        expect(MOOD_THEMES[mood]).toHaveProperty(key);
      }
    }
  });

  it("neutral theme has identity multipliers", () => {
    const n = MOOD_THEMES.neutral;
    expect(n.noiseAmplitudeMod).toBe(1.0);
    expect(n.timeSpeedMod).toBe(1.0);
    expect(n.particleCountMod).toBe(1.0);
    expect(n.glowIntensityBoost).toBe(0.0);
    expect(n.particleColor).toBe("");
    expect(n.indicatorColor).toBe("");
  });

  it("neutral expressionMod is empty", () => {
    expect(Object.keys(MOOD_THEMES.neutral.expressionMod)).toHaveLength(0);
  });
});

describe("Mood themes: emotional character", () => {
  it("excited has increased animation speed", () => {
    expect(MOOD_THEMES.excited.timeSpeedMod).toBeGreaterThan(1.0);
  });

  it("excited has more particles", () => {
    expect(MOOD_THEMES.excited.particleCountMod).toBeGreaterThan(1.0);
  });

  it("excited has higher noise amplitude", () => {
    expect(MOOD_THEMES.excited.noiseAmplitudeMod).toBeGreaterThan(1.0);
  });

  it("gentle has slower animation", () => {
    expect(MOOD_THEMES.gentle.timeSpeedMod).toBeLessThan(1.0);
  });

  it("gentle has fewer particles", () => {
    expect(MOOD_THEMES.gentle.particleCountMod).toBeLessThan(1.0);
  });

  it("gentle has less noise", () => {
    expect(MOOD_THEMES.gentle.noiseAmplitudeMod).toBeLessThan(1.0);
  });

  it("concerned has slightly faster animation", () => {
    expect(MOOD_THEMES.concerned.timeSpeedMod).toBeGreaterThan(1.0);
  });

  it("warm has warm orange particle color", () => {
    expect(MOOD_THEMES.warm.particleColor).toMatch(/^#f/i); // orange family
  });

  it("concerned has blue particle color", () => {
    expect(MOOD_THEMES.concerned.particleColor).toMatch(/^#6/i); // blue family
  });

  it("gentle has purple particle color", () => {
    expect(MOOD_THEMES.gentle.particleColor).toMatch(/^#c/i); // purple family
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// EXPRESSION MODIFIERS
// ═══════════════════════════════════════════════════════════════════════════════

describe("applyMoodToExpression: neutral passthrough", () => {
  it("neutral mood returns base expression unchanged", () => {
    const base = FACE_EXPRESSIONS.idle;
    const result = applyMoodToExpression(base, "neutral");
    expect(result).toEqual(base);
  });

  it("zero intensity returns base expression unchanged", () => {
    const base = FACE_EXPRESSIONS.idle;
    const result = applyMoodToExpression(base, "excited", 0);
    expect(result).toEqual(base);
  });
});

describe("applyMoodToExpression: excited mood", () => {
  const base = FACE_EXPRESSIONS.idle;
  const result = applyMoodToExpression(base, "excited", 1.0);

  it("increases mouthCurve (smile)", () => {
    expect(result.mouthCurve).toBeGreaterThan(base.mouthCurve);
  });

  it("increases eyeOpenness", () => {
    expect(result.eyeOpenness).toBeGreaterThan(base.eyeOpenness);
  });

  it("increases blush", () => {
    expect(result.blush).toBeGreaterThan(base.blush);
  });

  it("increases pupilSize (dilated)", () => {
    expect(result.pupilSize).toBeGreaterThan(base.pupilSize);
  });
});

describe("applyMoodToExpression: concerned mood", () => {
  const base = FACE_EXPRESSIONS.idle;
  const result = applyMoodToExpression(base, "concerned", 1.0);

  it("lowers browRaise (furrowed)", () => {
    expect(result.browRaise).toBeLessThan(base.browRaise);
  });

  it("decreases mouthCurve (slight frown)", () => {
    expect(result.mouthCurve).toBeLessThan(base.mouthCurve);
  });
});

describe("applyMoodToExpression: intensity blending", () => {
  const base = FACE_EXPRESSIONS.idle;

  it("half intensity applies half the modifier", () => {
    const full = applyMoodToExpression(base, "excited", 1.0);
    const half = applyMoodToExpression(base, "excited", 0.5);
    // The delta at half should be approximately half the delta at full
    const fullDelta = full.mouthCurve - base.mouthCurve;
    const halfDelta = half.mouthCurve - base.mouthCurve;
    expect(halfDelta).toBeCloseTo(fullDelta * 0.5, 2);
  });

  it("result values are clamped to valid ranges", () => {
    // Use a base with already high blush and apply excited (more blush)
    const highBlush: FaceExpression = { ...base, blush: 0.95 };
    const result = applyMoodToExpression(highBlush, "excited", 1.0);
    expect(result.blush).toBeLessThanOrEqual(1.0);
    expect(result.blush).toBeGreaterThanOrEqual(0);
  });

  it("browRaise is clamped to [-1, 1]", () => {
    const lowBrow: FaceExpression = { ...base, browRaise: -0.95 };
    const result = applyMoodToExpression(lowBrow, "concerned", 1.0);
    expect(result.browRaise).toBeGreaterThanOrEqual(-1);
  });
});

describe("applyMoodToExpression: warm mood adds happy-eye hint", () => {
  const base = FACE_EXPRESSIONS.idle;
  const result = applyMoodToExpression(base, "warm", 1.0);

  it("increases eyeShape (happy-eye hint)", () => {
    expect(result.eyeShape).toBeGreaterThan(base.eyeShape);
  });

  it("increases blush slightly", () => {
    expect(result.blush).toBeGreaterThan(base.blush);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// VISUAL MODIFIERS
// ═══════════════════════════════════════════════════════════════════════════════

describe("applyMoodToVisuals: neutral passthrough", () => {
  const baseVisuals = STATE_CONFIG.idle as StateVisuals;

  it("neutral mood returns visuals unchanged", () => {
    const result = applyMoodToVisuals(baseVisuals, "neutral", 1.0, lerpHexColor);
    expect(result).toEqual(baseVisuals);
  });

  it("zero intensity returns visuals unchanged", () => {
    const result = applyMoodToVisuals(baseVisuals, "excited", 0, lerpHexColor);
    expect(result).toEqual(baseVisuals);
  });
});

describe("applyMoodToVisuals: excited mood", () => {
  const baseVisuals = STATE_CONFIG.idle as StateVisuals;
  const result = applyMoodToVisuals(baseVisuals, "excited", 1.0, lerpHexColor);

  it("increases noise amplitude", () => {
    expect(result.noiseAmplitude).toBeGreaterThan(baseVisuals.noiseAmplitude);
  });

  it("increases time speed", () => {
    expect(result.timeSpeed).toBeGreaterThan(baseVisuals.timeSpeed);
  });

  it("increases particle count", () => {
    expect(result.particleCount).toBeGreaterThan(baseVisuals.particleCount);
  });

  it("boosts glow intensity", () => {
    expect(result.glowIntensity).toBeGreaterThan(baseVisuals.glowIntensity);
  });

  it("blends particle color toward gold", () => {
    expect(result.particleColor).not.toBe(baseVisuals.particleColor);
  });
});

describe("applyMoodToVisuals: gentle mood", () => {
  const baseVisuals = STATE_CONFIG.idle as StateVisuals;
  const result = applyMoodToVisuals(baseVisuals, "gentle", 1.0, lerpHexColor);

  it("decreases noise amplitude", () => {
    expect(result.noiseAmplitude).toBeLessThan(baseVisuals.noiseAmplitude);
  });

  it("slows time speed", () => {
    expect(result.timeSpeed).toBeLessThan(baseVisuals.timeSpeed);
  });

  it("reduces particle count", () => {
    expect(result.particleCount).toBeLessThanOrEqual(baseVisuals.particleCount);
  });

  it("blends particle color toward purple", () => {
    expect(result.particleColor).not.toBe(baseVisuals.particleColor);
  });
});

describe("applyMoodToVisuals: glow intensity capped at 1.0", () => {
  it("does not exceed 1.0 even with high base + boost", () => {
    const highGlow: StateVisuals = { ...STATE_CONFIG.idle as StateVisuals, glowIntensity: 0.95 };
    const result = applyMoodToVisuals(highGlow, "excited", 1.0, lerpHexColor);
    expect(result.glowIntensity).toBeLessThanOrEqual(1.0);
  });
});

describe("applyMoodToVisuals: color blending intensity", () => {
  it("particle color blending is capped at 50% (tint, not override)", () => {
    const baseVisuals = STATE_CONFIG.idle as StateVisuals;
    const result = applyMoodToVisuals(baseVisuals, "concerned", 1.0, lerpHexColor);
    // At 50% blend, result should be between base and mood color
    // It should NOT equal the mood color exactly
    expect(result.particleColor).not.toBe(MOOD_THEMES.concerned.particleColor);
    expect(result.particleColor).not.toBe(baseVisuals.particleColor);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// PROP WIRING
// ═══════════════════════════════════════════════════════════════════════════════

describe("WiiiAvatarProps includes mood", () => {
  it("types.ts has MoodType in source", async () => {
    const mod = await import("@/lib/avatar/types?raw");
    const code = mod.default;
    expect(code).toContain("MoodType");
    expect(code).toContain("mood?");
  });

  it("WiiiAvatar accepts mood prop in source", async () => {
    const mod = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = mod.default;
    expect(code).toContain('mood = "neutral"');
  });

  it("useAvatarAnimation accepts mood parameter", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain('mood: MoodType = "neutral"');
  });
});

describe("Mood wired to animation hook", () => {
  it("animation hook imports mood-theme functions", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("applyMoodToExpression");
    expect(code).toContain("applyMoodToVisuals");
  });

  it("animation hook tracks mood transitions", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("prevMoodRef");
    expect(code).toContain("moodTransitionRef");
    expect(code).toContain("fromMoodRef");
    expect(code).toContain("toMoodRef");
  });

  it("mood transition duration is 0.6s", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("dt / 0.6");
  });

  it("mood crossfade applies both from and to moods", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    // Should apply fromMood at (1 - moodT) and toMood at moodT
    expect(code).toContain("fromMoodRef.current, 1 - moodT");
    expect(code).toContain("toMoodRef.current, moodT");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// UI COMPONENT WIRING
// ═══════════════════════════════════════════════════════════════════════════════

describe("StatusBar passes mood to avatar", () => {
  it("StatusBar source contains mood prop on WiiiAvatar", async () => {
    const mod = await import("@/components/layout/StatusBar?raw");
    const code = mod.default;
    expect(code).toContain("mood={");
    expect(code).toContain("moodEnabled");
  });
});

describe("MessageList passes mood to avatar", () => {
  it("MessageList uses useAvatarState for mood passthrough", async () => {
    const mod = await import("@/components/chat/MessageList?raw");
    const code = mod.default;
    // Sprint 145: mood provided via centralized useAvatarState hook
    expect(code).toContain("useAvatarState");
  });

  it("MessageList passes avatarMood prop to streaming avatar", async () => {
    const mod = await import("@/components/chat/MessageList?raw");
    const code = mod.default;
    expect(code).toContain("mood={avatarMood}");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BARREL EXPORTS
// ═══════════════════════════════════════════════════════════════════════════════

describe("Barrel exports include emotion engine", () => {
  it("index.ts exports MOOD_THEMES", async () => {
    const barrel = await import("@/lib/avatar/index");
    expect(barrel.MOOD_THEMES).toBeDefined();
    expect(typeof barrel.MOOD_THEMES.excited).toBe("object");
  });

  it("index.ts exports applyMoodToExpression", async () => {
    const barrel = await import("@/lib/avatar/index");
    expect(typeof barrel.applyMoodToExpression).toBe("function");
  });

  it("index.ts exports applyMoodToVisuals", async () => {
    const barrel = await import("@/lib/avatar/index");
    expect(typeof barrel.applyMoodToVisuals).toBe("function");
  });

  it("pre-existing exports still work", async () => {
    const barrel = await import("@/lib/avatar/index");
    expect(typeof barrel.springEase).toBe("function");
    expect(typeof barrel.lerpHexColor).toBe("function");
    expect(typeof barrel.getIndicatorForState).toBe("function");
    expect(barrel.FACE_EXPRESSIONS).toBeDefined();
    expect(barrel.STATE_CONFIG).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BACKWARD COMPATIBILITY
// ═══════════════════════════════════════════════════════════════════════════════

describe("Backward compatibility: no mood = no change", () => {
  it("WiiiAvatar defaults mood to neutral when not provided", async () => {
    const mod = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = mod.default;
    expect(code).toContain('mood = "neutral"');
  });

  it("useAvatarAnimation defaults mood to neutral", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain('mood: MoodType = "neutral"');
  });

  it("neutral mood expression is pure identity", () => {
    const base = FACE_EXPRESSIONS.speaking;
    const result = applyMoodToExpression(base, "neutral", 1.0);
    expect(result.mouthCurve).toBe(base.mouthCurve);
    expect(result.eyeOpenness).toBe(base.eyeOpenness);
    expect(result.blush).toBe(base.blush);
  });

  it("neutral mood visuals are pure identity", () => {
    const base = STATE_CONFIG.thinking as StateVisuals;
    const result = applyMoodToVisuals(base, "neutral", 1.0, lerpHexColor);
    expect(result.noiseAmplitude).toBe(base.noiseAmplitude);
    expect(result.timeSpeed).toBe(base.timeSpeed);
    expect(result.particleCount).toBe(base.particleCount);
  });
});
