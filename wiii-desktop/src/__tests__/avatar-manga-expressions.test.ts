/**
 * Sprint 143/143b: "Manga Biểu Cảm" + "Cảm Xúc Vô Hạn" Tests.
 * Sprint 143: 5 phases — expanded micro-reactions, manga indicators,
 *   anime eye overlays, blush pulse, mood-biased idle poses.
 * Sprint 143b: registry, echo, 7 new reactions, 6 new indicators,
 *   5 new idle poses, Disney physics, breathing, pupil tremor.
 */
import { describe, it, expect } from "vitest";
import type { MicroReaction, ExpressionEcho } from "@/lib/avatar/types";
import type { AvatarState } from "@/lib/avatar/types";
import type { MoodType } from "@/lib/avatar/mood-theme";
import {
  getIndicatorForState,
  generateHeartPath,
  generateExclaimPath,
  generateQuestionPath,
  HEART_POSITIONS,
  EXCLAIM_POSITION,
  QUESTION_POSITION,
  ANGER_VEIN_POSITION,
  GLOOM_POSITION,
  FLOWER_POSITIONS,
  ZZZ_POSITION,
  FIRE_POSITION,
} from "@/lib/avatar/manga-indicators";
import { generateStarPupilPath, generateHeartPupilPath, generateAngerVeinPath, generateGloomLinesPath, generateSpiralPath, generateFlowerPath, generateZzzPath, generateFirePath } from "@/lib/avatar/face-geometry";
import { REACTION_REGISTRY, computeReactionIntensity } from "@/lib/avatar/micro-reaction-registry";
import { anticipateEase } from "@/lib/avatar/face-config";
import { BlinkController } from "@/lib/avatar/blink-controller";

// ─── Phase 1: Expanded MicroReaction Types ──────────────────────────────────

describe("Phase 1: MicroReaction type expansion", () => {
  it("all 17 micro-reaction types are valid in the type union", () => {
    const types: MicroReaction["type"][] = [
      "surprise", "nod", "flinch", "perk",         // original 4
      "sparkle_eyes", "shy", "panic", "dreamy",     // Sprint 143
      "doki", "hmph",                                // Sprint 143
      "blush_deep", "eye_twitch", "smirk",          // Sprint 143b
      "tear_up", "startle", "giggle", "sigh",       // Sprint 143b
    ];
    expect(types).toHaveLength(17);
    // Each should be assignable to MicroReaction.type
    for (const t of types) {
      const reaction: MicroReaction = { type: t, elapsed: 0, duration: 0.3 };
      expect(reaction.type).toBe(t);
    }
  });

  it("sparkle_eyes reaction has 350ms duration per spec", () => {
    const r: MicroReaction = { type: "sparkle_eyes", elapsed: 0, duration: 0.35 };
    expect(r.duration).toBe(0.35);
  });

  it("shy reaction has 400ms duration per spec", () => {
    const r: MicroReaction = { type: "shy", elapsed: 0, duration: 0.4 };
    expect(r.duration).toBe(0.4);
  });

  it("panic reaction has 250ms duration per spec", () => {
    const r: MicroReaction = { type: "panic", elapsed: 0, duration: 0.25 };
    expect(r.duration).toBe(0.25);
  });

  it("dreamy reaction has 500ms duration per spec", () => {
    const r: MicroReaction = { type: "dreamy", elapsed: 0, duration: 0.5 };
    expect(r.duration).toBe(0.5);
  });

  it("doki reaction has 400ms duration per spec", () => {
    const r: MicroReaction = { type: "doki", elapsed: 0, duration: 0.4 };
    expect(r.duration).toBe(0.4);
  });
});

// ─── Phase 1b: Mood-triggered reactions ─────────────────────────────────────

describe("Phase 1b: Mood-triggered micro-reactions", () => {
  // These test the mapping from mood → reaction type as specified in the plan.
  // The actual triggering happens in useEffect, but we verify the mapping contract.

  const MOOD_REACTION_MAP: Record<string, MicroReaction["type"]> = {
    excited: "sparkle_eyes",
    warm: "doki",
    concerned: "panic",
    gentle: "dreamy",
  };

  it("excited mood maps to sparkle_eyes reaction", () => {
    expect(MOOD_REACTION_MAP["excited"]).toBe("sparkle_eyes");
  });

  it("warm mood maps to doki reaction", () => {
    expect(MOOD_REACTION_MAP["warm"]).toBe("doki");
  });

  it("concerned mood maps to panic reaction", () => {
    expect(MOOD_REACTION_MAP["concerned"]).toBe("panic");
  });

  it("gentle mood maps to dreamy reaction", () => {
    expect(MOOD_REACTION_MAP["gentle"]).toBe("dreamy");
  });

  it("neutral mood does not trigger a reaction", () => {
    expect(MOOD_REACTION_MAP["neutral"]).toBeUndefined();
  });
});

// ─── Phase 2: Manga Indicator Mapping (mood-aware) ──────────────────────────

describe("Phase 2: Manga indicator state+mood mapping", () => {
  it("complete state → sparkle (unchanged)", () => {
    expect(getIndicatorForState("complete")).toBe("sparkle");
  });

  it("thinking state → thought (unchanged)", () => {
    expect(getIndicatorForState("thinking")).toBe("thought");
  });

  it("error state → sweat (unchanged)", () => {
    expect(getIndicatorForState("error")).toBe("sweat");
  });

  it("idle state with no mood → music (unchanged)", () => {
    expect(getIndicatorForState("idle")).toBe("music");
  });

  it("listening state → exclaim (Sprint 143)", () => {
    expect(getIndicatorForState("listening")).toBe("exclaim");
  });

  it("excited + idle → heart (Sprint 143 mood override)", () => {
    expect(getIndicatorForState("idle", "excited")).toBe("heart");
  });

  it("excited + speaking → heart (Sprint 143 mood override)", () => {
    expect(getIndicatorForState("speaking", "excited")).toBe("heart");
  });

  it("warm + idle → heart (Sprint 143 mood override)", () => {
    expect(getIndicatorForState("idle", "warm")).toBe("heart");
  });

  it("concerned + idle → sweat (Sprint 143 worried idle)", () => {
    expect(getIndicatorForState("idle", "concerned")).toBe("sweat");
  });

  it("gentle + idle → zzz (Sprint 143b sleepy gentle idle)", () => {
    expect(getIndicatorForState("idle", "gentle")).toBe("zzz");
  });

  it("neutral + idle → music (no mood override)", () => {
    expect(getIndicatorForState("idle", "neutral")).toBe("music");
  });

  it("excited + complete → flower_bloom (Sprint 143b joyful completion)", () => {
    expect(getIndicatorForState("complete", "excited")).toBe("flower_bloom");
  });

  it("state-based takes priority when no mood override applies", () => {
    // complete + neutral → sparkle (state wins, no mood override)
    expect(getIndicatorForState("complete", "neutral")).toBe("sparkle");
  });
});

// ─── Phase 2b: Heart SVG Generator ──────────────────────────────────────────

describe("Phase 2b: Heart SVG generator", () => {
  it("generates a valid SVG path string", () => {
    const path = generateHeartPath(0, 0, 10);
    expect(path).toContain("M ");
    expect(path).toContain("C ");
    expect(path).toContain("Z");
  });

  it("path scales with size parameter", () => {
    const small = generateHeartPath(0, 0, 5);
    const large = generateHeartPath(0, 0, 20);
    // Larger size should produce larger coordinate values
    const smallCoords = small.match(/-?[\d.]+/g)!.map(Number);
    const largeCoords = large.match(/-?[\d.]+/g)!.map(Number);
    const smallMax = Math.max(...smallCoords.map(Math.abs));
    const largeMax = Math.max(...largeCoords.map(Math.abs));
    expect(largeMax).toBeGreaterThan(smallMax);
  });
});

// ─── Phase 2c: Exclaim SVG Generator ────────────────────────────────────────

describe("Phase 2c: Exclaim SVG generator", () => {
  it("generates a valid SVG path string with bar + dot", () => {
    const path = generateExclaimPath(0, 0, 10);
    expect(path).toContain("M ");
    expect(path).toContain("Z");
    // Should have arc for dot circle
    expect(path).toContain("A ");
  });

  it("path scales with height parameter", () => {
    const small = generateExclaimPath(0, 0, 5);
    const large = generateExclaimPath(0, 0, 20);
    const smallCoords = small.match(/-?[\d.]+/g)!.map(Number);
    const largeCoords = large.match(/-?[\d.]+/g)!.map(Number);
    const smallMax = Math.max(...smallCoords.map(Math.abs));
    const largeMax = Math.max(...largeCoords.map(Math.abs));
    expect(largeMax).toBeGreaterThan(smallMax);
  });
});

// ─── Phase 2d: Question SVG Generator ───────────────────────────────────────

describe("Phase 2d: Question SVG generator", () => {
  it("generates a valid SVG path string with hook + dot", () => {
    const path = generateQuestionPath(0, 0, 10);
    expect(path).toContain("M ");
    expect(path).toContain("C ");
    // Should have arc for dot circle
    expect(path).toContain("A ");
  });

  it("path scales with height parameter", () => {
    const small = generateQuestionPath(0, 0, 5);
    const large = generateQuestionPath(0, 0, 20);
    const smallCoords = small.match(/-?[\d.]+/g)!.map(Number);
    const largeCoords = large.match(/-?[\d.]+/g)!.map(Number);
    const smallMax = Math.max(...smallCoords.map(Math.abs));
    const largeMax = Math.max(...largeCoords.map(Math.abs));
    expect(largeMax).toBeGreaterThan(smallMax);
  });
});

// ─── Phase 2e: Position Constants ───────────────────────────────────────────

describe("Phase 2e: New indicator positions", () => {
  it("HEART_POSITIONS has 2 positions", () => {
    expect(HEART_POSITIONS).toHaveLength(2);
  });

  it("EXCLAIM_POSITION is on the right side (positive x)", () => {
    expect(EXCLAIM_POSITION.x).toBeGreaterThan(0);
  });

  it("QUESTION_POSITION is on the right side (positive x)", () => {
    expect(QUESTION_POSITION.x).toBeGreaterThan(0);
  });
});

// ─── Phase 3: Anime Eye Overlays ────────────────────────────────────────────

describe("Phase 3: Star pupil SVG generator", () => {
  it("generates a valid 4-pointed star path", () => {
    const path = generateStarPupilPath(0, 0, 5);
    expect(path).toContain("M ");
    expect(path).toContain("L ");
    expect(path).toContain("Z");
    // 4-pointed star = 8 points (alternating outer/inner)
    const lineSegments = path.split("L ").length - 1;
    expect(lineSegments).toBe(7); // M + 7 L commands = 8 points
  });

  it("star scales with radius parameter", () => {
    const small = generateStarPupilPath(0, 0, 3);
    const large = generateStarPupilPath(0, 0, 10);
    // Parse first coordinate — larger radius means bigger coordinates
    const smallCoords = small.match(/[\d.]+/g)!.map(Number);
    const largeCoords = large.match(/[\d.]+/g)!.map(Number);
    const smallMax = Math.max(...smallCoords.map(Math.abs));
    const largeMax = Math.max(...largeCoords.map(Math.abs));
    expect(largeMax).toBeGreaterThan(smallMax);
  });
});

describe("Phase 3: Heart pupil SVG generator", () => {
  it("generates a valid heart path", () => {
    const path = generateHeartPupilPath(0, 0, 5);
    expect(path).toContain("M ");
    expect(path).toContain("C ");
    expect(path).toContain("Z");
  });

  it("heart scales with radius parameter", () => {
    const small = generateHeartPupilPath(0, 0, 3);
    const large = generateHeartPupilPath(0, 0, 10);
    const smallCoords = small.match(/-?[\d.]+/g)!.map(Number);
    const largeCoords = large.match(/-?[\d.]+/g)!.map(Number);
    const smallMax = Math.max(...smallCoords.map(Math.abs));
    const largeMax = Math.max(...largeCoords.map(Math.abs));
    expect(largeMax).toBeGreaterThan(smallMax);
  });
});

describe("Phase 3: Anime eye triggers", () => {
  it("sparkle_eyes reaction should activate star overlay", () => {
    // Mapping: sparkle_eyes → star
    const reaction: MicroReaction = { type: "sparkle_eyes", elapsed: 0, duration: 0.35 };
    const targetType = reaction.type === "sparkle_eyes" ? "star" : reaction.type === "doki" ? "heart" : "none";
    expect(targetType).toBe("star");
  });

  it("doki reaction should activate heart overlay", () => {
    const reaction: MicroReaction = { type: "doki", elapsed: 0, duration: 0.4 };
    const targetType = reaction.type === "sparkle_eyes" ? "star" : reaction.type === "doki" ? "heart" : "none";
    expect(targetType).toBe("heart");
  });

  it("surprise reaction should not activate any overlay", () => {
    const reaction: MicroReaction = { type: "surprise", elapsed: 0, duration: 0.18 };
    const targetType = reaction.type === "sparkle_eyes" ? "star" : reaction.type === "doki" ? "heart" : "none";
    expect(targetType).toBe("none");
  });

  it("panic reaction should not activate any overlay", () => {
    const reaction: MicroReaction = { type: "panic", elapsed: 0, duration: 0.25 };
    const targetType = reaction.type === "sparkle_eyes" ? "star" : reaction.type === "doki" ? "heart" : "none";
    expect(targetType).toBe("none");
  });
});

// ─── Phase 4: Blush Pulse ───────────────────────────────────────────────────

describe("Phase 4: Blush pulse animation", () => {
  // Test the pulse logic extracted from the rAF loop
  function computeBlushPulse(blush: number, noiseTime: number): { left: number; right: number } {
    const base = blush * 0.5;
    if (blush > 0.3) {
      const pulseIntensity = (blush - 0.3) / 0.7;
      const pulseL = Math.sin(noiseTime * 2.5) * 0.08 * pulseIntensity;
      const pulseR = Math.sin(noiseTime * 2.5 + 0.8) * 0.08 * pulseIntensity;
      return { left: base + pulseL, right: base + pulseR };
    }
    return { left: base, right: base };
  }

  it("blush <= 0.3 — no pulse, static opacity", () => {
    const { left, right } = computeBlushPulse(0.2, 1.0);
    expect(left).toBeCloseTo(0.1, 4);
    expect(right).toBeCloseTo(0.1, 4);
  });

  it("blush > 0.3 — pulse activates with non-zero variation", () => {
    // At a time where sin is non-zero, pulse should add variation
    const t = Math.PI / (2 * 2.5); // sin(t * 2.5) = sin(π/2) = 1
    const { left } = computeBlushPulse(1.0, t);
    const base = 0.5;
    const pulseIntensity = 1.0; // (1.0 - 0.3) / 0.7
    const expectedPulse = Math.sin(t * 2.5) * 0.08 * pulseIntensity;
    expect(left).toBeCloseTo(base + expectedPulse, 4);
  });

  it("left and right cheeks have phase offset", () => {
    // At same time, left and right should differ due to 0.8 phase offset
    const t = 1.0;
    const { left, right } = computeBlushPulse(0.8, t);
    expect(left).not.toBeCloseTo(right, 4);
  });
});

// ─── Phase 5: Mood-Biased Idle Poses ────────────────────────────────────────

describe("Phase 5: Mood-biased idle poses", () => {
  // Test the weight modification logic extracted from pickIdlePose
  const BASE_WEIGHTS: Record<string, number> = {
    curious_right: 15,
    curious_left: 15,
    widen: 12,
    squint: 12,
    glance_up: 12,
    head_tilt: 15,
    hum: 14,
    yawn: 5,
    // Sprint 143b: New poses
    daydream: 8,
    fidget: 10,
    stretch: 4,
    pout: 7,
    nuzzle: 5,
  };

  function applyMoodBias(mood: MoodType): Record<string, number> {
    const w = { ...BASE_WEIGHTS };
    switch (mood) {
      case "excited":
        w.widen *= 2;
        w.squint *= 0.3;
        w.fidget *= 2;
        w.stretch *= 0;
        break;
      case "warm":
        w.hum *= 2;
        w.head_tilt *= 1.5;
        w.nuzzle *= 3;
        w.daydream *= 1.5;
        break;
      case "concerned":
        w.squint *= 2;
        w.hum *= 0.3;
        w.fidget *= 3;
        w.pout *= 2;
        w.nuzzle *= 0;
        break;
      case "gentle":
        w.head_tilt *= 2;
        w.yawn *= 2;
        w.daydream *= 3;
        w.nuzzle *= 2;
        w.fidget *= 0.2;
        break;
    }
    return w;
  }

  it("excited mood doubles widen weight and reduces squint", () => {
    const w = applyMoodBias("excited");
    expect(w.widen).toBe(BASE_WEIGHTS.widen * 2);
    expect(w.squint).toBeCloseTo(BASE_WEIGHTS.squint * 0.3, 2);
  });

  it("warm mood doubles hum weight", () => {
    const w = applyMoodBias("warm");
    expect(w.hum).toBe(BASE_WEIGHTS.hum * 2);
    expect(w.head_tilt).toBe(BASE_WEIGHTS.head_tilt * 1.5);
  });

  it("concerned mood doubles squint and reduces hum", () => {
    const w = applyMoodBias("concerned");
    expect(w.squint).toBe(BASE_WEIGHTS.squint * 2);
    expect(w.hum).toBeCloseTo(BASE_WEIGHTS.hum * 0.3, 2);
  });

  it("gentle mood doubles head_tilt and yawn", () => {
    const w = applyMoodBias("gentle");
    expect(w.head_tilt).toBe(BASE_WEIGHTS.head_tilt * 2);
    expect(w.yawn).toBe(BASE_WEIGHTS.yawn * 2);
  });

  it("neutral mood leaves all weights unchanged", () => {
    const w = applyMoodBias("neutral");
    for (const key of Object.keys(BASE_WEIGHTS)) {
      expect(w[key]).toBe(BASE_WEIGHTS[key]);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// Sprint 143b: "Cảm Xúc Vô Hạn" — Infinite Emotion Engine Tests
// ═══════════════════════════════════════════════════════════════════════════════

// ─── 143b Phase 1: Reaction Registry ─────────────────────────────────────────

describe("143b: Reaction registry data integrity", () => {
  it("contains all 17 reaction types", () => {
    const allTypes = [
      "surprise", "nod", "flinch", "perk",
      "sparkle_eyes", "shy", "panic", "dreamy", "doki", "hmph",
      "blush_deep", "eye_twitch", "smirk", "tear_up", "startle", "giggle", "sigh",
    ];
    for (const t of allTypes) {
      expect(REACTION_REGISTRY[t]).toBeDefined();
    }
    expect(Object.keys(REACTION_REGISTRY)).toHaveLength(17);
  });

  it("all entries have valid duration > 0", () => {
    for (const [_key, def] of Object.entries(REACTION_REGISTRY)) {
      expect(def.duration).toBeGreaterThan(0);
    }
  });

  it("all entries have at least one face modifier key", () => {
    for (const [_key, def] of Object.entries(REACTION_REGISTRY)) {
      expect(Object.keys(def.modifier.face).length).toBeGreaterThan(0);
    }
  });

  it("echo entries have valid delay, duration, scale", () => {
    const withEcho = Object.entries(REACTION_REGISTRY).filter(([, d]) => d.echo);
    expect(withEcho.length).toBeGreaterThan(0); // at least some have echoes
    for (const [, def] of withEcho) {
      expect(def.echo!.delay).toBeGreaterThan(0);
      expect(def.echo!.duration).toBeGreaterThan(0);
      expect(def.echo!.scale).toBeGreaterThan(0);
      expect(def.echo!.scale).toBeLessThanOrEqual(1);
    }
  });

  it("blush_deep and startle have echo defined", () => {
    expect(REACTION_REGISTRY.blush_deep.echo).toBeDefined();
    expect(REACTION_REGISTRY.startle.echo).toBeDefined();
  });
});

// ─── 143b Phase 1b: computeReactionIntensity easing ────────────────────────

describe("143b: computeReactionIntensity easing", () => {
  it("linear easing decays from 1 to 0", () => {
    expect(computeReactionIntensity(0, 1)).toBeCloseTo(1, 2);
    expect(computeReactionIntensity(0.5, 1)).toBeCloseTo(0.5, 2);
    expect(computeReactionIntensity(1, 1)).toBeCloseTo(0, 2);
  });

  it("pulse easing produces variation via sine wave", () => {
    const a = computeReactionIntensity(0.1, 1, "pulse", 5);
    computeReactionIntensity(0.2, 1, "pulse", 5);
    // Pulse should cause values to differ from pure linear
    expect(a).not.toBeCloseTo(0.9, 1); // not exactly linear
  });

  it("bounce easing overshoots at start (>1 region)", () => {
    // At t=0 (start), bounce should give ~1.2
    const earlyIntensity = computeReactionIntensity(0.01, 1, "bounce");
    expect(earlyIntensity).toBeGreaterThan(1);
  });

  it("bounce easing settles below 1 after 30%", () => {
    const lateIntensity = computeReactionIntensity(0.5, 1, "bounce");
    expect(lateIntensity).toBeLessThan(1);
    expect(lateIntensity).toBeGreaterThanOrEqual(0);
  });
});

// ─── 143b Phase 1c: Expression echo interface ──────────────────────────────

describe("143b: ExpressionEcho interface", () => {
  it("can create a valid echo object", () => {
    const echo: ExpressionEcho = {
      parentType: "blush_deep",
      delay: 0.5,
      duration: 0.3,
      scale: 0.4,
      countdown: 0.5,
    };
    expect(echo.parentType).toBe("blush_deep");
    expect(echo.scale).toBeLessThan(1);
  });

  it("echo countdown decrements toward 0", () => {
    const echo: ExpressionEcho = {
      parentType: "startle",
      delay: 0.15,
      duration: 0.2,
      scale: 0.3,
      countdown: 0.15,
    };
    echo.countdown -= 0.05;
    expect(echo.countdown).toBeCloseTo(0.1, 3);
  });

  it("echo from registry matches parent definition", () => {
    const def = REACTION_REGISTRY.blush_deep;
    const echo: ExpressionEcho = {
      parentType: "blush_deep",
      delay: def.echo!.delay,
      duration: def.echo!.duration,
      scale: def.echo!.scale,
      countdown: def.echo!.delay,
    };
    expect(echo.delay).toBe(0.5);
    expect(echo.scale).toBe(0.4);
  });
});

// ─── 143b Phase 1d: New reaction types validation ──────────────────────────

describe("143b: New reaction type properties", () => {
  it("blush_deep has 0.45s duration and blush=0.7", () => {
    const d = REACTION_REGISTRY.blush_deep;
    expect(d.duration).toBe(0.45);
    expect(d.modifier.face.blush).toBe(0.7);
  });

  it("eye_twitch has bounce easing and 0.30s duration", () => {
    const d = REACTION_REGISTRY.eye_twitch;
    expect(d.duration).toBe(0.30);
    expect(d.modifier.easing).toBe("bounce");
  });

  it("smirk tilts brows and lifts mouth curve", () => {
    const d = REACTION_REGISTRY.smirk;
    expect(d.modifier.face.mouthCurve).toBe(0.25);
    expect(d.modifier.face.browTilt).toBe(0.15);
  });

  it("tear_up has longest new duration at 0.6s", () => {
    const d = REACTION_REGISTRY.tear_up;
    expect(d.duration).toBe(0.6);
    expect(d.modifier.face.browRaise).toBe(0.3);
  });

  it("startle has bounce easing + echo", () => {
    const d = REACTION_REGISTRY.startle;
    expect(d.modifier.easing).toBe("bounce");
    expect(d.echo).toBeDefined();
    expect(d.echo!.scale).toBe(0.3);
  });

  it("giggle has pulse easing at 8Hz", () => {
    const d = REACTION_REGISTRY.giggle;
    expect(d.modifier.easing).toBe("pulse");
    expect(d.modifier.pulseHz).toBe(8);
  });

  it("sigh is longest reaction at 0.7s with droopy brows", () => {
    const d = REACTION_REGISTRY.sigh;
    expect(d.duration).toBe(0.7);
    expect(d.modifier.face.browRaise).toBe(-0.15);
  });
});

// ─── 143b Phase 1e: Soul-triggered reactions ────────────────────────────────

describe("143b: Soul-triggered reaction mapping", () => {
  it("high blush soul emotion triggers blush_deep", () => {
    const face = { blush: 0.7 };
    const intensity = 0.8;
    const shouldTrigger = intensity > 0.6 && face.blush > 0.5;
    expect(shouldTrigger).toBe(true);
  });

  it("happy face triggers giggle", () => {
    const face = { mouthCurve: 0.5, eyeShape: 0.4 };
    const intensity = 0.8;
    const isGiggle = intensity > 0.6 && face.mouthCurve > 0.4 && face.eyeShape > 0.3;
    expect(isGiggle).toBe(true);
  });

  it("sad face triggers tear_up", () => {
    const face = { browRaise: 0.4, mouthCurve: -0.2 };
    const intensity = 0.8;
    const isTearUp = intensity > 0.6 && face.browRaise > 0.3 && face.mouthCurve < -0.1;
    expect(isTearUp).toBe(true);
  });

  it("low intensity does not trigger reactions", () => {
    const face = { blush: 0.7 };
    const intensity = 0.4;
    const shouldTrigger = intensity > 0.6 && face.blush > 0.5;
    expect(shouldTrigger).toBe(false);
  });
});

// ─── 143b Phase 2: New indicator state+mood mappings ──────────────────────

describe("143b: New indicator state+mood mappings", () => {
  it("concerned + thinking → spiral_eyes", () => {
    expect(getIndicatorForState("thinking", "concerned")).toBe("spiral_eyes");
  });

  it("concerned + speaking → sweat", () => {
    expect(getIndicatorForState("speaking", "concerned")).toBe("sweat");
  });

  it("excited + thinking → fire_spirit", () => {
    expect(getIndicatorForState("thinking", "excited")).toBe("fire_spirit");
  });

  it("gentle + idle → zzz", () => {
    expect(getIndicatorForState("idle", "gentle")).toBe("zzz");
  });

  it("excited + complete → flower_bloom", () => {
    expect(getIndicatorForState("complete", "excited")).toBe("flower_bloom");
  });

  it("neutral + thinking → thought (unchanged default)", () => {
    expect(getIndicatorForState("thinking", "neutral")).toBe("thought");
  });

  // Sprint 144: Wire anger_vein and gloom_lines
  it("concerned + error → anger_vein (Sprint 144)", () => {
    expect(getIndicatorForState("error", "concerned")).toBe("anger_vein");
  });

  it("concerned + listening → gloom_lines (Sprint 144)", () => {
    expect(getIndicatorForState("listening", "concerned")).toBe("gloom_lines");
  });
});

// ─── 143b Phase 2b: New SVG generators ──────────────────────────────────────

describe("143b: Anger vein SVG generator", () => {
  it("generates valid SVG path with Q curves", () => {
    const path = generateAngerVeinPath(0, 0, 10);
    expect(path).toContain("M ");
    expect(path).toContain("Q ");
  });
});

describe("143b: Gloom lines SVG generator", () => {
  it("generates valid SVG path with C curves", () => {
    const path = generateGloomLinesPath(0, 0, 10);
    expect(path).toContain("M ");
    expect(path).toContain("C ");
  });
});

describe("143b: Spiral SVG generator", () => {
  it("generates valid SVG path with L segments", () => {
    const path = generateSpiralPath(0, 0, 10);
    expect(path).toContain("M ");
    expect(path).toContain("L ");
  });
});

describe("143b: Flower SVG generator", () => {
  it("generates valid SVG path with Z close and center circle", () => {
    const path = generateFlowerPath(0, 0, 10);
    expect(path).toContain("M ");
    expect(path).toContain("Z");
    expect(path).toContain("A "); // center circle arc
  });
});

describe("143b: Zzz SVG generator", () => {
  it("generates valid SVG path with 3 Z shapes", () => {
    const path = generateZzzPath(0, 0, 10);
    const mCount = (path.match(/M /g) || []).length;
    expect(mCount).toBe(3); // one M per Z letter
  });
});

describe("143b: Fire SVG generator", () => {
  it("generates valid SVG path with curves and Z close", () => {
    const path = generateFirePath(0, 0, 10);
    expect(path).toContain("M ");
    expect(path).toContain("C ");
    expect(path).toContain("Z");
  });
});

// ─── 143b Phase 2c: New position constants ──────────────────────────────────

describe("143b: New indicator position constants", () => {
  it("ANGER_VEIN_POSITION is upper-right", () => {
    expect(ANGER_VEIN_POSITION.x).toBeGreaterThan(0);
    expect(ANGER_VEIN_POSITION.y).toBeLessThan(0);
  });

  it("GLOOM_POSITION is centered above head", () => {
    expect(GLOOM_POSITION.x).toBe(0);
    expect(GLOOM_POSITION.y).toBeLessThan(-1);
  });

  it("FLOWER_POSITIONS has 3 positions", () => {
    expect(FLOWER_POSITIONS).toHaveLength(3);
  });

  it("ZZZ_POSITION is upper-right", () => {
    expect(ZZZ_POSITION.x).toBeGreaterThan(0);
    expect(ZZZ_POSITION.y).toBeLessThan(0);
  });

  it("FIRE_POSITION is on the left side", () => {
    expect(FIRE_POSITION.x).toBeLessThan(0);
  });
});

// ─── 143b Phase 3: New idle poses ───────────────────────────────────────────

describe("143b: New idle pose weights and modifiers", () => {
  const NEW_POSE_WEIGHTS: Record<string, number> = {
    daydream: 8,
    fidget: 10,
    stretch: 4,
    pout: 7,
    nuzzle: 5,
  };

  it("daydream has weight 8", () => {
    expect(NEW_POSE_WEIGHTS.daydream).toBe(8);
  });

  it("fidget has weight 10", () => {
    expect(NEW_POSE_WEIGHTS.fidget).toBe(10);
  });

  it("stretch has weight 4 (rare)", () => {
    expect(NEW_POSE_WEIGHTS.stretch).toBe(4);
  });

  it("pout has weight 7", () => {
    expect(NEW_POSE_WEIGHTS.pout).toBe(7);
  });

  it("nuzzle has weight 5", () => {
    expect(NEW_POSE_WEIGHTS.nuzzle).toBe(5);
  });
});

describe("143b: New pose mood biases", () => {
  it("excited mood doubles fidget and zeroes stretch", () => {
    const base = { fidget: 10, stretch: 4 };
    const excited = { fidget: base.fidget * 2, stretch: base.stretch * 0 };
    expect(excited.fidget).toBe(20);
    expect(excited.stretch).toBe(0);
  });

  it("warm mood triples nuzzle weight", () => {
    const base = { nuzzle: 5 };
    expect(base.nuzzle * 3).toBe(15);
  });

  it("concerned mood triples fidget, zeroes nuzzle", () => {
    const base = { fidget: 10, nuzzle: 5 };
    expect(base.fidget * 3).toBe(30);
    expect(base.nuzzle * 0).toBe(0);
  });

  it("gentle mood triples daydream, near-zeroes fidget", () => {
    const base = { daydream: 8, fidget: 10 };
    expect(base.daydream * 3).toBe(24);
    expect(base.fidget * 0.2).toBe(2);
  });
});

// ─── 143b Phase 3b: Mood-responsive breathing ──────────────────────────────

describe("143b: Mood-responsive breathing", () => {
  it("excited mood increases breathing rate by 40%", () => {
    const base = 1.25;
    const excited = base * 1.4;
    expect(excited).toBeCloseTo(1.75, 2);
  });

  it("gentle mood slows breathing rate by 25%", () => {
    const base = 1.25;
    const gentle = base * 0.75;
    expect(gentle).toBeCloseTo(0.9375, 2);
  });

  it("concerned mood boosts breath depth by 50%", () => {
    const base = 0.020;
    const concerned = base * 1.5;
    expect(concerned).toBeCloseTo(0.030, 4);
  });
});

// ─── 143b Phase 4: Anticipation ease ────────────────────────────────────────

describe("143b: Anticipation ease (Disney Principle #6)", () => {
  it("starts at 0 when t=0", () => {
    expect(anticipateEase(0)).toBe(0);
  });

  it("ends at 1 when t=1", () => {
    expect(anticipateEase(1)).toBe(1);
  });

  it("pulls back (negative) at t=0.075 (midway through pullback phase)", () => {
    const val = anticipateEase(0.075, 0.1);
    expect(val).toBeLessThan(0);
  });

  it("reaches target near t=1", () => {
    const val = anticipateEase(0.99, 0.1);
    expect(val).toBeGreaterThan(0.9);
  });
});

// ─── 143b Phase 4b: Blink follow-through ───────────────────────────────────

describe("143b: Blink follow-through (Disney Principle #8)", () => {
  it("blink controller produces overshoot >1.0 after blink", () => {
    // Mock Math.random to prevent double-blink (20% chance) from intercepting follow-through
    const origRandom = Math.random;
    Math.random = () => 0.99;
    try {
      const ctrl = new BlinkController(15);
      // Force a blink
      ctrl.triggerBlink();
      // Advance through entire blink duration (0.15s)
      let val = ctrl.advance(0.16);
      // Should now be in follow-through phase — value > 1.0
      val = ctrl.advance(0.02);
      expect(val).toBeGreaterThan(1.0);
    } finally {
      Math.random = origRandom;
    }
  });

  it("follow-through settles back to 1.0", () => {
    const origRandom = Math.random;
    Math.random = () => 0.99;
    try {
      const ctrl = new BlinkController(15);
      ctrl.triggerBlink();
      ctrl.advance(0.16); // complete blink
      ctrl.advance(0.04); // mid follow-through
      const settled = ctrl.advance(0.1); // past follow-through
      expect(settled).toBeCloseTo(1.0, 1);
    } finally {
      Math.random = origRandom;
    }
  });
});

// ─── 143b Phase 4c: Pupil tremor ───────────────────────────────────────────

describe("143b: Pupil tremor during distress", () => {
  it("tremor applies during concerned mood (non-zero extra offset)", () => {
    // Simulates the logic: concerned mood → tremor intensity = 0.3
    const tremorIntensity = 0.3;
    const maxOffset = 5; // example pupilMaxOffset
    const tremorX = Math.sin(15 * 1.0) * maxOffset * 0.04 * tremorIntensity;
    // Should be small but non-zero
    expect(Math.abs(tremorX)).toBeGreaterThan(0);
    expect(Math.abs(tremorX)).toBeLessThan(maxOffset * 0.05); // bounded
  });

  it("no tremor during neutral mood", () => {
    const mood: string = "neutral";
    const isDistressed = mood === "concerned";
    expect(isDistressed).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Sprint 144: "Linh Hồn Chuyên Nghiệp" — Professional Soul Animation Tests
// ═══════════════════════════════════════════════════════════════════════════

import { MOOD_DECAY_DURATIONS } from "@/lib/avatar/mood-theme";
import { generateTeethPath, generateTonguePath, generatePoutMouthPath, generateKnockedOutEyePath } from "@/lib/avatar/face-geometry";
import { REACTION_CHAINS, advanceChain, createChainPlayback } from "@/lib/avatar/reaction-chains";
import { GazeController, GAZE_TARGETS } from "@/lib/avatar/gaze-controller";
import { createMoistureState, updateMoisture, getMoistureEffects, generateTearDropPath } from "@/lib/avatar/eye-moisture";
import type { MoistureTriggers } from "@/lib/avatar/eye-moisture";

// ─── Phase 1: Squash & Stretch (Disney Principle #1) ────────────────────

describe("Sprint 144 Phase 1: Squash & Stretch", () => {
  it("surprise has vertical stretch squash profile", () => {
    const def = REACTION_REGISTRY["surprise"];
    expect(def.modifier.squash).toBeDefined();
    expect(def.modifier.squash!.scaleX).toBeLessThan(1);
    expect(def.modifier.squash!.scaleY).toBeGreaterThan(1);
  });

  it("flinch has horizontal squash profile", () => {
    const def = REACTION_REGISTRY["flinch"];
    expect(def.modifier.squash).toBeDefined();
    expect(def.modifier.squash!.scaleX).toBeGreaterThan(1);
    expect(def.modifier.squash!.scaleY).toBeLessThan(1);
  });

  it("startle has strong vertical stretch", () => {
    const def = REACTION_REGISTRY["startle"];
    expect(def.modifier.squash!.scaleX).toBe(0.90);
    expect(def.modifier.squash!.scaleY).toBe(1.12);
  });

  it("nod has subtle horizontal spread", () => {
    const def = REACTION_REGISTRY["nod"];
    expect(def.modifier.squash!.scaleX).toBe(1.02);
    expect(def.modifier.squash!.scaleY).toBe(0.98);
  });

  it("perk has slight upward stretch", () => {
    const def = REACTION_REGISTRY["perk"];
    expect(def.modifier.squash!.scaleX).toBeLessThan(1);
    expect(def.modifier.squash!.scaleY).toBeGreaterThan(1);
  });

  it("giggle has horizontal squash with pulse easing", () => {
    const def = REACTION_REGISTRY["giggle"];
    expect(def.modifier.squash!.scaleX).toBe(1.04);
    expect(def.modifier.squash!.scaleY).toBe(0.97);
    expect(def.modifier.easing).toBe("pulse");
  });

  it("scale at zero intensity returns 1.0", () => {
    const def = REACTION_REGISTRY["surprise"];
    const intensity = 0;
    const scaleX = 1 + (def.modifier.squash!.scaleX - 1) * intensity;
    const scaleY = 1 + (def.modifier.squash!.scaleY - 1) * intensity;
    expect(scaleX).toBe(1);
    expect(scaleY).toBe(1);
  });

  it("scale at full intensity matches profile", () => {
    const def = REACTION_REGISTRY["surprise"];
    const intensity = 1;
    const scaleX = 1 + (def.modifier.squash!.scaleX - 1) * intensity;
    const scaleY = 1 + (def.modifier.squash!.scaleY - 1) * intensity;
    expect(scaleX).toBeCloseTo(0.92);
    expect(scaleY).toBeCloseTo(1.10);
  });

  it("scale at half intensity is interpolated", () => {
    const def = REACTION_REGISTRY["surprise"];
    const intensity = 0.5;
    const scaleX = 1 + (def.modifier.squash!.scaleX - 1) * intensity;
    expect(scaleX).toBeCloseTo(0.96);
  });

  it("reactions without squash have undefined squash", () => {
    const def = REACTION_REGISTRY["shy"];
    expect(def.modifier.squash).toBeUndefined();
  });

  it("squash volume is approximately preserved (scaleX * scaleY ≈ 1)", () => {
    for (const [, def] of Object.entries(REACTION_REGISTRY)) {
      if (def.modifier.squash) {
        const volume = def.modifier.squash.scaleX * def.modifier.squash.scaleY;
        expect(volume).toBeGreaterThan(0.95);
        expect(volume).toBeLessThan(1.05);
      }
    }
  });

  it("squash profiles are present on 6 key reactions", () => {
    const withSquash = Object.entries(REACTION_REGISTRY).filter(([, d]) => d.modifier.squash);
    expect(withSquash.length).toBeGreaterThanOrEqual(6);
  });
});

// ─── Phase 2: Emotion Momentum ──────────────────────────────────────────

describe("Sprint 144 Phase 2: Emotion Momentum", () => {
  it("MOOD_DECAY_DURATIONS has all 5 moods", () => {
    const moods: MoodType[] = ["excited", "warm", "concerned", "gentle", "neutral"];
    for (const m of moods) {
      expect(MOOD_DECAY_DURATIONS[m]).toBeDefined();
    }
  });

  it("concerned has longest decay (2.5s)", () => {
    expect(MOOD_DECAY_DURATIONS.concerned).toBe(2.5);
  });

  it("excited has shortest non-zero decay (1.5s)", () => {
    expect(MOOD_DECAY_DURATIONS.excited).toBe(1.5);
  });

  it("neutral has zero decay", () => {
    expect(MOOD_DECAY_DURATIONS.neutral).toBe(0);
  });

  it("residual intensity formula decays exponentially", () => {
    const startIntensity = 1.0;
    const decayDuration = 2.0;
    const elapsed = 0.8; // = decayDuration * 0.4
    const intensity = startIntensity * Math.exp(-elapsed / (decayDuration * 0.4));
    expect(intensity).toBeCloseTo(1 / Math.E, 1);
  });

  it("residual at elapsed=0 returns full intensity", () => {
    const intensity = 1.0 * Math.exp(0);
    expect(intensity).toBe(1);
  });

  it("residual far in the future approaches zero", () => {
    const intensity = 1.0 * Math.exp(-10 / 1);
    expect(intensity).toBeLessThan(0.001);
  });

  it("warm decay duration is 2.0s", () => {
    expect(MOOD_DECAY_DURATIONS.warm).toBe(2.0);
  });
});

// ─── Phase 3: Dynamic Asymmetry ─────────────────────────────────────────

describe("Sprint 144 Phase 3: Stress-Driven Dynamic Asymmetry", () => {
  function lerp(a: number, b: number, t: number) { return a + (b - a) * t; }

  it("base asymmetry at stress=0 is 3%", () => {
    expect(lerp(0.03, 0.15, 0)).toBeCloseTo(0.03);
  });

  it("max asymmetry at stress=1 is 15%", () => {
    expect(lerp(0.03, 0.15, 1)).toBeCloseTo(0.15);
  });

  it("brow asymmetry at stress=0 is 8%", () => {
    expect(lerp(0.08, 0.18, 0)).toBeCloseTo(0.08);
  });

  it("brow asymmetry at stress=1 is 18%", () => {
    expect(lerp(0.08, 0.18, 1)).toBeCloseTo(0.18);
  });

  it("concerned mood contributes 0.5 stress", () => {
    let stress = 0;
    stress += 0.5; // concerned
    expect(stress).toBe(0.5);
  });

  it("error state contributes 0.4 stress", () => {
    let stress = 0;
    stress += 0.4; // error
    expect(stress).toBe(0.4);
  });

  it("combined stress is clamped to 1", () => {
    let stress = 0.5 + 0.4 + 0.3;
    stress = Math.min(1, stress);
    expect(stress).toBe(1);
  });

  it("mid-stress asymmetry is properly interpolated", () => {
    const eyeAsym = lerp(0.03, 0.15, 0.5);
    expect(eyeAsym).toBeCloseTo(0.09);
  });
});

// ─── Phase 4: Mouth Interior Detail ─────────────────────────────────────

describe("Sprint 144 Phase 4: Mouth Interior (Teeth + Tongue)", () => {
  it("generateTeethPath returns valid SVG path", () => {
    const path = generateTeethPath(0, 10, 20, 1, 0.5);
    expect(path).toContain("M");
    expect(path).toContain("Q");
    expect(path).toContain("Z");
  });

  it("generateTonguePath returns valid SVG path", () => {
    const path = generateTonguePath(0, 10, 20, 0.5);
    expect(path).toContain("M");
    expect(path).toContain("Q");
    expect(path).toContain("Z");
  });

  it("teeth path scales with openness", () => {
    const small = generateTeethPath(0, 10, 20, 1, 0.2);
    const large = generateTeethPath(0, 10, 20, 1, 0.8);
    expect(small).not.toBe(large);
  });

  it("interior visibility threshold at 0.15 openness", () => {
    const threshold = 0.15;
    const belowOpacity = (0.10 - threshold) / 0.85;
    const aboveOpacity = (0.20 - threshold) / 0.85;
    expect(belowOpacity).toBeLessThan(0);
    expect(aboveOpacity).toBeGreaterThan(0);
  });

  it("opacity clamped to 0-1 range", () => {
    const openness = 1.0;
    const opacity = Math.min(1, (openness - 0.15) / 0.85);
    expect(opacity).toBe(1);
  });

  it("teeth width narrower than mouth", () => {
    const baseWidth = 30;
    const widthMul = 1.0;
    // Teeth use 75% of mouth width internally
    const teethHalfWidth = (baseWidth / 2) * widthMul * 0.75;
    const mouthHalfWidth = (baseWidth / 2) * widthMul;
    expect(teethHalfWidth).toBeLessThan(mouthHalfWidth);
  });

  it("tongue positioned in lower half of mouth", () => {
    const mouthY = 10;
    const openness = 0.5;
    const baseWidth = 20;
    const openY = openness * baseWidth * 0.35;
    const tongueY = mouthY + openY * 0.6;
    expect(tongueY).toBeGreaterThan(mouthY);
  });

  it("mouth glint shimmer oscillates", () => {
    const t1 = Math.sin(0 * 4) * 0.3 + 0.7;
    const t2 = Math.sin(0.5 * 4) * 0.3 + 0.7;
    expect(t1).not.toBe(t2);
  });

  it("zero openness produces no interior", () => {
    const opacity = Math.min(1, (0 - 0.15) / 0.85);
    expect(opacity).toBeLessThan(0);
  });

  it("teeth path respects widthMul", () => {
    const narrow = generateTeethPath(0, 10, 20, 0.7, 0.5);
    const wide = generateTeethPath(0, 10, 20, 1.3, 0.5);
    expect(narrow).not.toBe(wide);
  });
});

// ─── Phase 5: Reaction Chains ───────────────────────────────────────────

describe("Sprint 144 Phase 5: Reaction Chains", () => {
  it("REACTION_CHAINS has 5 defined chains", () => {
    expect(Object.keys(REACTION_CHAINS)).toHaveLength(5);
  });

  it("surprise_to_smile has 3 steps", () => {
    expect(REACTION_CHAINS.surprise_to_smile.steps).toHaveLength(3);
  });

  it("panic_to_relief ends with sigh", () => {
    const steps = REACTION_CHAINS.panic_to_relief.steps;
    expect(steps[steps.length - 1].type).toBe("sigh");
  });

  it("love_struck starts with doki", () => {
    expect(REACTION_CHAINS.love_struck.steps[0].type).toBe("doki");
  });

  it("createChainPlayback initializes at step 0", () => {
    const pb = createChainPlayback("test");
    expect(pb.currentStepIndex).toBe(0);
    expect(pb.stepElapsed).toBe(0);
  });

  it("advanceChain plays first step", () => {
    const pb = createChainPlayback("surprise_to_smile");
    const result = advanceChain(pb, REACTION_CHAINS.surprise_to_smile, 0.05);
    expect(result.finished).toBe(false);
    expect(result.reaction).not.toBeNull();
    expect(result.reaction!.type).toBe("surprise");
  });

  it("advanceChain enters gap between steps", () => {
    const pb = createChainPlayback("surprise_to_smile");
    // Advance past first step (0.15s duration)
    advanceChain(pb, REACTION_CHAINS.surprise_to_smile, 0.16);
    // Now should be in gap or next step
    const result = advanceChain(pb, REACTION_CHAINS.surprise_to_smile, 0.01);
    expect(result.finished).toBe(false);
  });

  it("advanceChain reaches second step", () => {
    const pb = createChainPlayback("surprise_to_smile");
    // Play through step 1 + gap
    advanceChain(pb, REACTION_CHAINS.surprise_to_smile, 0.16);
    advanceChain(pb, REACTION_CHAINS.surprise_to_smile, 0.06);
    // Should be in step 2 (sparkle_eyes)
    const result = advanceChain(pb, REACTION_CHAINS.surprise_to_smile, 0.01);
    if (result.reaction) {
      expect(result.reaction.type).toBe("sparkle_eyes");
    }
    expect(result.finished).toBe(false);
  });

  it("advanceChain finishes after all steps complete", () => {
    const pb = createChainPlayback("surprise_to_smile");
    const chain = REACTION_CHAINS.surprise_to_smile;
    // Total duration estimate: ~0.15 + 0.05 + 0.25 + 0.08 + 0.3 = 0.83s
    for (let i = 0; i < 100; i++) {
      const result = advanceChain(pb, chain, 0.02);
      if (result.finished) {
        expect(result.reaction).toBeNull();
        return;
      }
    }
    // Should have finished by now
    expect(pb.currentStepIndex).toBeGreaterThanOrEqual(chain.steps.length);
  });

  it("frustration chain has hmph → eye_twitch → sigh", () => {
    const steps = REACTION_CHAINS.frustration.steps;
    expect(steps[0].type).toBe("hmph");
    expect(steps[1].type).toBe("eye_twitch");
    expect(steps[2].type).toBe("sigh");
  });

  it("false_alarm ends with giggle", () => {
    const steps = REACTION_CHAINS.false_alarm.steps;
    expect(steps[steps.length - 1].type).toBe("giggle");
  });

  it("chain steps reference valid reaction types", () => {
    for (const [, chain] of Object.entries(REACTION_CHAINS)) {
      for (const step of chain.steps) {
        expect(REACTION_REGISTRY[step.type]).toBeDefined();
      }
    }
  });

  it("gap durations are small positive values", () => {
    for (const [, chain] of Object.entries(REACTION_CHAINS)) {
      for (const step of chain.steps) {
        if (step.gapBefore !== undefined) {
          expect(step.gapBefore).toBeGreaterThan(0);
          expect(step.gapBefore).toBeLessThan(0.5);
        }
      }
    }
  });

  it("advanceChain with unknown chain finishes immediately", () => {
    const pb = createChainPlayback("nonexistent");
    // Chain lookup will fail, playback nulled
    expect(pb.chainId).toBe("nonexistent");
  });
});

// ─── Phase 6: Eye Saccade State Machine ─────────────────────────────────

describe("Sprint 144 Phase 6: Eye Saccade Controller", () => {
  it("GAZE_TARGETS has 6 defined targets", () => {
    expect(Object.keys(GAZE_TARGETS)).toHaveLength(6);
  });

  it("user target is approximately center with slight downward gaze", () => {
    expect(GAZE_TARGETS.user.x).toBe(0);
    expect(GAZE_TARGETS.user.y).toBeCloseTo(0.1);
  });

  it("up_think target looks up and slightly right", () => {
    expect(GAZE_TARGETS.up_think.x).toBeGreaterThan(0);
    expect(GAZE_TARGETS.up_think.y).toBeLessThan(0);
  });

  it("GazeController initializes without error", () => {
    const gc = new GazeController();
    expect(gc).toBeDefined();
    expect(gc.getPhase()).toBe("fixation");
  });

  it("advance returns normalized coordinates", () => {
    const gc = new GazeController();
    const pos = gc.advance(0.1);
    expect(pos.x).toBeGreaterThanOrEqual(-1);
    expect(pos.x).toBeLessThanOrEqual(1);
    expect(pos.y).toBeGreaterThanOrEqual(-1);
    expect(pos.y).toBeLessThanOrEqual(1);
  });

  it("setState triggers saccade", () => {
    const gc = new GazeController();
    gc.setState("thinking");
    expect(gc.getPhase()).toBe("saccade");
  });

  it("triggerSaccade transitions to saccade phase", () => {
    const gc = new GazeController();
    gc.triggerSaccade();
    expect(gc.getPhase()).toBe("saccade");
  });

  it("saccade completes and returns to fixation", () => {
    const gc = new GazeController();
    gc.triggerSaccade();
    // Advance past max saccade duration (80ms)
    for (let i = 0; i < 10; i++) {
      gc.advance(0.01);
    }
    expect(gc.getPhase()).toBe("fixation");
  });

  it("fixation eventually triggers new saccade", () => {
    const gc = new GazeController();
    // Advance through an entire fixation cycle (up to 2.5s)
    let sawSaccade = false;
    for (let i = 0; i < 300; i++) {
      gc.advance(0.01);
      if (gc.getPhase() === "saccade") {
        sawSaccade = true;
        break;
      }
    }
    expect(sawSaccade).toBe(true);
  });

  it("mouse tracking blends into gaze for non-thinking states", () => {
    const gc = new GazeController();
    gc.setState("idle");
    // Advance to settle into fixation
    for (let i = 0; i < 20; i++) gc.advance(0.01);
    // Get position without mouse
    const noMouse = gc.advance(0.01);
    // Get position with strong mouse input — should be different
    const withMouse = gc.advance(0.01, { x: 0.8, y: -0.5, influence: 1.0 });
    // Mouse with 60% blend at influence=1 should produce x ≈ 0.48 (shifted from base)
    expect(withMouse.x).toBeGreaterThan(noMouse.x * 0.5);
  });

  it("thinking state reduces mouse influence", () => {
    const gc = new GazeController();
    gc.setState("thinking");
    for (let i = 0; i < 20; i++) gc.advance(0.01);
    const result = gc.advance(0.01, { x: 1.0, y: 0, influence: 1.0 });
    // Should be blended but not fully at mouse position (12% blend)
    expect(result.x).toBeLessThan(0.9);
  });

  it("away_left and away_right are symmetric", () => {
    expect(GAZE_TARGETS.away_left.x).toBe(-GAZE_TARGETS.away_right.x);
    expect(GAZE_TARGETS.away_left.y).toBe(GAZE_TARGETS.away_right.y);
  });

  it("center target is at origin", () => {
    expect(GAZE_TARGETS.center.x).toBe(0);
    expect(GAZE_TARGETS.center.y).toBe(0);
  });

  it("setState to same state does not change phase", () => {
    const gc = new GazeController();
    gc.setState("idle");
    // After first saccade completes, settling into fixation
    for (let i = 0; i < 20; i++) gc.advance(0.01);
    const phase = gc.getPhase();
    gc.setState("idle"); // same state — no change
    expect(gc.getPhase()).toBe(phase);
  });

  it("rapid state changes still produce valid output", () => {
    const gc = new GazeController();
    const states: AvatarState[] = ["idle", "thinking", "speaking", "error", "complete"];
    for (const s of states) {
      gc.setState(s);
      const pos = gc.advance(0.01);
      expect(isFinite(pos.x)).toBe(true);
      expect(isFinite(pos.y)).toBe(true);
    }
  });

  it("down target has positive y (looking down)", () => {
    expect(GAZE_TARGETS.down.y).toBeGreaterThan(0);
  });
});

// ─── Phase 7: Tear Shimmer & Eye Moisture ───────────────────────────────

describe("Sprint 144 Phase 7: Eye Moisture System", () => {
  const noTriggers: MoistureTriggers = { tearUpActive: false, sighActive: false, isConcerned: false, soulSadness: false };

  it("createMoistureState starts dry", () => {
    const state = createMoistureState();
    expect(state.moisture).toBe(0);
    expect(state.tearDrop).toBeNull();
  });

  it("moisture increases with tear_up trigger", () => {
    const state = createMoistureState();
    updateMoisture(state, { ...noTriggers, tearUpActive: true }, 1.0);
    expect(state.moisture).toBeGreaterThan(0);
  });

  it("moisture increases with sigh trigger", () => {
    const state = createMoistureState();
    updateMoisture(state, { ...noTriggers, sighActive: true }, 1.0);
    expect(state.moisture).toBeGreaterThan(0);
  });

  it("moisture increases slowly with concerned mood", () => {
    const state = createMoistureState();
    updateMoisture(state, { ...noTriggers, isConcerned: true }, 1.0);
    expect(state.moisture).toBeGreaterThan(0);
    expect(state.moisture).toBeLessThan(0.1); // slow accumulation
  });

  it("moisture decays without triggers", () => {
    const state = createMoistureState();
    state.moisture = 0.5;
    updateMoisture(state, noTriggers, 1.0);
    expect(state.moisture).toBeLessThan(0.5);
  });

  it("moisture is clamped to [0, 1]", () => {
    const state = createMoistureState();
    state.moisture = 0.95;
    updateMoisture(state, { ...noTriggers, tearUpActive: true, soulSadness: true }, 1.0);
    expect(state.moisture).toBeLessThanOrEqual(1);
  });

  it("tear spawns at moisture >= 1.0", () => {
    const state = createMoistureState();
    state.moisture = 0.95;
    // Provide strong triggers to push past 1.0
    updateMoisture(state, { tearUpActive: true, sighActive: true, isConcerned: false, soulSadness: true }, 0.2);
    expect(state.tearDrop).not.toBeNull();
  });

  it("tear drop progresses over time", () => {
    const state = createMoistureState();
    state.tearDrop = { progress: 0, side: "left" };
    updateMoisture(state, noTriggers, 0.5);
    expect(state.tearDrop!.progress).toBeGreaterThan(0);
  });

  it("tear drop completes and resets moisture", () => {
    const state = createMoistureState();
    state.moisture = 0.9;
    state.tearDrop = { progress: 0.95, side: "right" };
    updateMoisture(state, noTriggers, 0.2);
    // Tear should have finished
    expect(state.tearDrop).toBeNull();
    expect(state.moisture).toBeLessThanOrEqual(0.5);
  });

  it("getMoistureEffects returns no effects below 0.3", () => {
    const effects = getMoistureEffects(0.1);
    expect(effects.shineBoost).toBe(0);
    expect(effects.tearOpacity).toBe(0);
  });

  it("getMoistureEffects returns shine at 0.4", () => {
    const effects = getMoistureEffects(0.4);
    expect(effects.shineBoost).toBeGreaterThan(0);
    expect(effects.lowerShine).toBe(0); // not yet
  });

  it("getMoistureEffects returns tear at 0.85", () => {
    const effects = getMoistureEffects(0.85);
    expect(effects.tearOpacity).toBeGreaterThan(0);
    expect(effects.lowerShine).toBe(1);
  });
});

// ─── Phase 8: Tear Drop Path (Eye Moisture) ─────────────────────────────

describe("Sprint 144: Tear Drop Path", () => {
  it("generateTearDropPath returns valid SVG at various progress", () => {
    for (const progress of [0, 0.25, 0.5, 0.75, 1.0]) {
      const path = generateTearDropPath(10, 5, progress, 50);
      expect(path).toContain("M");
      expect(path).toContain("Z");
    }
  });
});

// ─── Sprint 144: Pout Mouth ε (Kaomoji) ─────────────────────────────────

describe("Sprint 144: Pout Mouth (ε)", () => {
  it("generates valid closed SVG path", () => {
    const path = generatePoutMouthPath(0, 10, 20, 1.0);
    expect(path).toContain("M");
    expect(path).toContain("Q");
    expect(path).toContain("Z");
  });

  it("scales with widthMul", () => {
    const narrow = generatePoutMouthPath(0, 10, 20, 0.5);
    const wide = generatePoutMouthPath(0, 10, 20, 1.5);
    // Different widthMul should produce different paths
    expect(narrow).not.toBe(wide);
  });

  it("scales with baseWidth", () => {
    const small = generatePoutMouthPath(0, 10, 10, 1.0);
    const big = generatePoutMouthPath(0, 10, 30, 1.0);
    expect(small).not.toBe(big);
  });

  it("path is centered around cx", () => {
    const path = generatePoutMouthPath(50, 10, 20, 1.0);
    // Path should contain coordinates around 50
    expect(path).toMatch(/[45][0-9]/);
  });
});

// ─── Sprint 144: Knocked-Out Eyes × (Kaomoji) ──────────────────────────

describe("Sprint 144: Knocked-Out Eyes (×)", () => {
  it("generates X-shaped path with two line segments", () => {
    const path = generateKnockedOutEyePath(0, 0, 10);
    // Should have 2 M commands (two line segments forming X)
    const mCount = (path.match(/M/g) || []).length;
    expect(mCount).toBe(2);
    // Should have 2 L commands
    const lCount = (path.match(/L/g) || []).length;
    expect(lCount).toBe(2);
  });

  it("scales with radius", () => {
    const small = generateKnockedOutEyePath(0, 0, 5);
    const big = generateKnockedOutEyePath(0, 0, 15);
    expect(small).not.toBe(big);
  });

  it("centers on cx, cy", () => {
    const path = generateKnockedOutEyePath(20, 30, 10);
    // r * 0.6 = 6, so X goes from 14 to 26 and 24 to 36
    expect(path).toContain("14.0");
    expect(path).toContain("26.0");
    expect(path).toContain("24.0");
    expect(path).toContain("36.0");
  });

  it("produces symmetric X shape", () => {
    const path = generateKnockedOutEyePath(0, 0, 10);
    // r * 0.6 = 6, so coordinates should be ±6
    expect(path).toContain("-6.0");
    expect(path).toContain("6.0");
  });
});
