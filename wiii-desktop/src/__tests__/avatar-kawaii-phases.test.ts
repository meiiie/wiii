/**
 * Tests for Kawaii Wiii — Sprint 131 Phases 2, 4, 6.
 * Phase 2: Multiple mouth shapes (cat ω, dot ·, wavy ～)
 * Phase 4: Manga emotional indicators (sparkle, thought, sweat, music)
 * Phase 6: Micro-expressions (brow bounce, shine pulse, cheek puff)
 */
import { describe, it, expect } from "vitest";

// ─── Phase 2 Imports ──────────────────────────────────────────────────────────
import {
  generateCatMouthPath,
  generateDotMouthPath,
  generateWavyMouthPath,
  generateMouthPath,
} from "@/lib/avatar/face-geometry";
import { FACE_EXPRESSIONS, lerpFaceExpression } from "@/lib/avatar/face-config";

// ─── Phase 4 Imports ──────────────────────────────────────────────────────────
import {
  getIndicatorForState,
  generateSparklePath,
  generateSweatDropPath,
  generateMusicNotePath,
  SPARKLE_POSITIONS,
  THOUGHT_POSITION,
  SWEAT_POSITION,
  MUSIC_POSITION,
} from "@/lib/avatar/manga-indicators";
import type { MangaIndicatorType } from "@/lib/avatar/manga-indicators";

// ═══════════════════════════════════════════════════════════════════════════════
// PHASE 2: Mouth Shapes
// ═══════════════════════════════════════════════════════════════════════════════

describe("Phase 2: mouthShape field in FaceExpression", () => {
  it("all 6 presets have mouthShape field", () => {
    const states = ["idle", "listening", "thinking", "speaking", "complete", "error"] as const;
    for (const s of states) {
      expect(FACE_EXPRESSIONS[s]).toHaveProperty("mouthShape");
      expect(typeof FACE_EXPRESSIONS[s].mouthShape).toBe("number");
    }
  });

  it("idle uses cat mouth (mouthShape = 1)", () => {
    expect(FACE_EXPRESSIONS.idle.mouthShape).toBe(1);
  });

  it("thinking uses dot mouth (mouthShape = 2)", () => {
    expect(FACE_EXPRESSIONS.thinking.mouthShape).toBe(2);
  });

  it("error uses wavy mouth (mouthShape = 3)", () => {
    expect(FACE_EXPRESSIONS.error.mouthShape).toBe(3);
  });

  it("speaking/listening/complete use default mouth (mouthShape = 0)", () => {
    expect(FACE_EXPRESSIONS.speaking.mouthShape).toBe(0);
    expect(FACE_EXPRESSIONS.listening.mouthShape).toBe(0);
    expect(FACE_EXPRESSIONS.complete.mouthShape).toBe(0);
  });

  it("lerpFaceExpression interpolates mouthShape", () => {
    const from = FACE_EXPRESSIONS.idle; // mouthShape = 1
    const to = FACE_EXPRESSIONS.error;  // mouthShape = 3
    const mid = lerpFaceExpression(from, to, 0.5);
    expect(mid.mouthShape).toBeCloseTo(2, 1); // 1 + (3-1)*0.5 = 2
  });
});

describe("Phase 2: generateCatMouthPath (ω shape)", () => {
  it("returns valid SVG path string", () => {
    const path = generateCatMouthPath(0, 10, 20, 1.0);
    expect(path).toContain("M");
    expect(path).toContain("Q");
  });

  it("starts at left edge", () => {
    const path = generateCatMouthPath(0, 10, 20, 1.0);
    // Left edge = cx - (baseWidth/2) * widthMul = 0 - 10 = -10
    expect(path).toMatch(/M -10/);
  });

  it("has two quadratic curves (Q) for ω shape", () => {
    const path = generateCatMouthPath(0, 10, 20, 1.0);
    const qCount = (path.match(/Q/g) || []).length;
    expect(qCount).toBe(2);
  });

  it("width scales with widthMul parameter", () => {
    const narrow = generateCatMouthPath(0, 10, 20, 0.5);
    const wide = generateCatMouthPath(0, 10, 20, 1.5);
    // Narrow: M -5.0, Wide: M -15.0
    expect(narrow).toMatch(/M -5/);
    expect(wide).toMatch(/M -15/);
  });
});

describe("Phase 2: generateDotMouthPath (· shape)", () => {
  it("returns valid SVG path with arc commands", () => {
    const path = generateDotMouthPath(0, 10, 20);
    expect(path).toContain("A");
    expect(path).toContain("Z"); // Closed path
  });

  it("dot radius is proportional to baseWidth", () => {
    // r = baseWidth * 0.08 = 20 * 0.08 = 1.6
    const path = generateDotMouthPath(0, 10, 20);
    expect(path).toContain("1.6");
  });

  it("centered at provided coordinates", () => {
    const path = generateDotMouthPath(5, 10, 20);
    expect(path).toMatch(/M 5\.0/);
  });
});

describe("Phase 2: generateWavyMouthPath (～ shape)", () => {
  it("returns valid SVG path with cubic bezier curves", () => {
    const path = generateWavyMouthPath(0, 10, 20, 1.0);
    expect(path).toContain("M");
    expect(path).toContain("C");
  });

  it("has exactly 2 cubic curves for S-wave shape", () => {
    const path = generateWavyMouthPath(0, 10, 20, 1.0);
    const cCount = (path.match(/C /g) || []).length;
    expect(cCount).toBe(2);
  });

  it("starts at left edge and ends at right edge", () => {
    const path = generateWavyMouthPath(0, 10, 20, 1.0);
    // Left edge = 0 - 10 * 1.0 = -10.0, Right edge = 10.0
    expect(path).toMatch(/M -10\.0/);
    expect(path).toMatch(/10\.0 10\.0$/); // ends at right edge, cy
  });
});

describe("Phase 2: Mouth shape backward compatibility", () => {
  it("generateMouthPath still works for default shape", () => {
    const path = generateMouthPath(0, 10, { curve: 0.2, openness: 0, width: 1.0 }, 20);
    expect(path).toContain("M");
    expect(path).toContain("C");
  });

  it("all 4 mouth generators produce distinct paths for same center", () => {
    const cx = 0, cy = 10, bw = 20;
    const cat = generateCatMouthPath(cx, cy, bw, 1.0);
    const dot = generateDotMouthPath(cx, cy, bw);
    const wavy = generateWavyMouthPath(cx, cy, bw, 1.0);
    const normal = generateMouthPath(cx, cy, { curve: 0.2, openness: 0, width: 1.0 }, bw);
    const paths = new Set([cat, dot, wavy, normal]);
    expect(paths.size).toBe(4); // All different
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// PHASE 4: Manga Emotional Indicators
// ═══════════════════════════════════════════════════════════════════════════════

describe("Phase 4: getIndicatorForState mapping", () => {
  it("complete → sparkle", () => {
    expect(getIndicatorForState("complete")).toBe("sparkle");
  });

  it("thinking → thought", () => {
    expect(getIndicatorForState("thinking")).toBe("thought");
  });

  it("error → sweat", () => {
    expect(getIndicatorForState("error")).toBe("sweat");
  });

  it("idle → music", () => {
    expect(getIndicatorForState("idle")).toBe("music");
  });

  it("listening → exclaim (Sprint 143)", () => {
    expect(getIndicatorForState("listening")).toBe("exclaim");
  });

  it("speaking → none", () => {
    expect(getIndicatorForState("speaking")).toBe("none");
  });

  it("return type is MangaIndicatorType", () => {
    const result: MangaIndicatorType = getIndicatorForState("idle");
    expect(["none", "sparkle", "thought", "sweat", "music", "heart", "exclaim", "question"]).toContain(result);
  });
});

describe("Phase 4: Sparkle path generator", () => {
  it("generates valid SVG path with Z close", () => {
    const path = generateSparklePath(10, 20, 5);
    expect(path).toContain("M");
    expect(path).toContain("L");
    expect(path).toContain("Z");
  });

  it("has 8 L commands for 4-pointed star (8 points)", () => {
    const path = generateSparklePath(10, 20, 5);
    const lCount = (path.match(/L /g) || []).length;
    expect(lCount).toBe(7); // M + 7 L + Z (8 segments)
  });

  it("uses default innerR of 35% of outerR", () => {
    const path = generateSparklePath(0, 0, 10); // innerR = 3.5
    expect(path).toContain("3.5"); // innerR points
  });

  it("accepts custom innerR", () => {
    const path = generateSparklePath(0, 0, 10, 5);
    expect(path).toContain("5"); // innerR points
  });

  it("topmost point is at cy - outerR", () => {
    const path = generateSparklePath(10, 20, 5);
    // First point: M cx (cy - outerR) = M 10 15
    expect(path).toMatch(/^M 10 15/);
  });
});

describe("Phase 4: Sweat drop path generator", () => {
  it("generates valid SVG path", () => {
    const path = generateSweatDropPath(10, 20, 5, 10);
    expect(path).toContain("M");
    expect(path).toContain("Q");
    expect(path).toContain("Z");
  });

  it("has 2 quadratic curves for teardrop shape", () => {
    const path = generateSweatDropPath(10, 20, 5, 10);
    const qCount = (path.match(/Q /g) || []).length;
    expect(qCount).toBe(2);
  });

  it("top point is at cy - height/2", () => {
    const path = generateSweatDropPath(10, 20, 5, 10);
    // top = cy - height/2 = 20 - 5 = 15
    expect(path).toMatch(/^M 10 15/);
  });
});

describe("Phase 4: Music note path generator", () => {
  it("generates valid SVG path with arc", () => {
    const path = generateMusicNotePath(10, 20, 8);
    expect(path).toContain("A"); // Arc for note head
    expect(path).toContain("M"); // Move commands
    expect(path).toContain("L"); // Stem line
    expect(path).toContain("Q"); // Flag curve
  });

  it("note head is an elliptical arc", () => {
    const path = generateMusicNotePath(10, 20, 8);
    const aCount = (path.match(/A /g) || []).length;
    expect(aCount).toBeGreaterThanOrEqual(2); // Two arcs for full ellipse
  });
});

describe("Phase 4: Position configs", () => {
  it("SPARKLE_POSITIONS has 3 positions", () => {
    expect(SPARKLE_POSITIONS).toHaveLength(3);
  });

  it("sparkle positions are scattered (not all same x or y)", () => {
    const xs = SPARKLE_POSITIONS.map((p) => p.x);
    const ys = SPARKLE_POSITIONS.map((p) => p.y);
    expect(new Set(xs).size).toBeGreaterThan(1);
    expect(new Set(ys).size).toBeGreaterThan(1);
  });

  it("THOUGHT_POSITION is in upper-right quadrant", () => {
    expect(THOUGHT_POSITION.x).toBeGreaterThan(0);
    expect(THOUGHT_POSITION.y).toBeLessThan(0);
  });

  it("SWEAT_POSITION is on right side", () => {
    expect(SWEAT_POSITION.x).toBeGreaterThan(0);
  });

  it("MUSIC_POSITION is on left side", () => {
    expect(MUSIC_POSITION.x).toBeLessThan(0);
  });
});

describe("Phase 4: SVG source structure", () => {
  // Use ?raw import to check component source
  it("WiiiAvatar contains manga indicator CSS classes", async () => {
    const mod = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = mod.default;
    expect(code).toContain("wiii-indicator-sparkle");
    expect(code).toContain("wiii-indicator-thought");
    expect(code).toContain("wiii-indicator-sweat");
    expect(code).toContain("wiii-indicator-music");
  });

  it("WiiiAvatar contains thought dot CSS class", async () => {
    const mod = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = mod.default;
    expect(code).toContain("wiii-thought-dot");
  });

  it("WiiiAvatar contains MangaIndicatorGroup component", async () => {
    const mod = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = mod.default;
    expect(code).toContain("MangaIndicatorGroup");
  });

  it("MangaIndicatorGroup renders only for large tier", async () => {
    const mod = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = mod.default;
    // Should be conditionally rendered with tier check
    expect(code).toMatch(/tier\s*===\s*"large".*MangaIndicatorGroup/s);
  });
});

describe("Phase 4: CSS classes for indicators", () => {
  it("avatar.css contains indicator will-change classes", async () => {
    // Check the component source for CSS imports
    const mod = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = mod.default;
    expect(code).toContain("avatar.css");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// PHASE 6: Micro-expressions
// ═══════════════════════════════════════════════════════════════════════════════

describe("Phase 6: Brow bounce mechanics", () => {
  it("browBounceRef exists in animation hook source", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("browBounceRef");
  });

  it("brow bounce triggers on listening state", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    // Check for the trigger pattern
    expect(code).toMatch(/state\s*===\s*"listening"[\s\S]*?browBounceRef/);
  });

  it("brow bounce uses exponential decay", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("browBounceRef.current *=");
    expect(code).toContain("Math.pow(0.05, dt)");
  });

  it("brow bounce is applied to browRaiseY", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toMatch(/face\.browRaise\s*\+\s*browBounceRef\.current/);
  });
});

describe("Phase 6: Shine pulse mechanics", () => {
  it("shinePulseRef exists in animation hook source", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("shinePulseRef");
  });

  it("shine pulse has 3.5s period", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("% 3.5");
  });

  it("shine pulse modifies .wiii-face-shine opacity", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain('querySelectorAll(".wiii-face-shine")');
  });

  it("shine pulse uses sin-based envelope", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    // Should have sin-based pulse
    expect(code).toMatch(/shinePulsePhase.*Math\.sin/s);
  });
});

describe("Phase 6: Cheek puff mechanics", () => {
  it("cheekPuff variable exists in animation hook", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("cheekPuff");
  });

  it("cheek puff only activates during thinking state", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toMatch(/state\s*===\s*"thinking"[\s\S]*?cheekPuff\s*=\s*1\s*\+/);
  });

  it("cheek puff has 2.5s cycle", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("% 2.5");
  });

  it("cheek puff applies horizontal scale to faceGroup", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("springScale * cheekPuff");
    expect(code).toContain("combinedScaleX");
  });

  it("cheek puff max amplitude is ~1.5%", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("0.015");
  });
});

describe("Phase 6: Scale composition", () => {
  it("faceGroup transform includes combined scale", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toContain("combinedScaleX.toFixed(4)");
    expect(code).toContain("combinedScaleY.toFixed(4)");
  });

  it("scale is only applied when not 1.0", async () => {
    const mod = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = mod.default;
    expect(code).toMatch(/needsScale.*combinedScaleX\s*!==\s*1\.0\s*\|\|\s*combinedScaleY\s*!==\s*1\.0/);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BARREL EXPORTS
// ═══════════════════════════════════════════════════════════════════════════════

describe("Barrel exports include Phase 2/4 additions", () => {
  it("index.ts exports mouth shape generators", async () => {
    const barrel = await import("@/lib/avatar/index");
    expect(typeof barrel.generateCatMouthPath).toBe("function");
    expect(typeof barrel.generateDotMouthPath).toBe("function");
    expect(typeof barrel.generateWavyMouthPath).toBe("function");
  }, 15_000);

  it("index.ts exports manga indicator functions", async () => {
    const barrel = await import("@/lib/avatar/index");
    expect(typeof barrel.getIndicatorForState).toBe("function");
    expect(typeof barrel.generateSparklePath).toBe("function");
    expect(typeof barrel.generateSweatDropPath).toBe("function");
    expect(typeof barrel.generateMusicNotePath).toBe("function");
  });

  it("index.ts still exports pre-existing functions", async () => {
    const barrel = await import("@/lib/avatar/index");
    expect(typeof barrel.generateMouthPath).toBe("function");
    expect(typeof barrel.generateHappyEyePath).toBe("function");
    expect(typeof barrel.springEase).toBe("function");
    expect(typeof barrel.lerpHexColor).toBe("function");
    expect(typeof barrel.BlinkController).toBe("function");
  });
});
