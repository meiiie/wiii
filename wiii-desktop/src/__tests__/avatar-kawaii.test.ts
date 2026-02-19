/**
 * Tests for Kawaii Face Phase 1 — Sprint 131.
 * Anime eyes (iris gradient, clipPath, sclera/iris separation),
 * nose dot, blush hash lines, updated proportions.
 */
import { describe, it, expect } from "vitest";
import { getFaceDimensions, generateHappyEyePath } from "@/lib/avatar/face-geometry";
import type { FaceDimensions } from "@/lib/avatar/face-geometry";
import { FACE_EXPRESSIONS, lerpFaceExpression } from "@/lib/avatar/face-config";

// ─── Anime Eye Proportions ─────────────────────────────────────────────────

describe("Kawaii Phase 1: Anime eye proportions", () => {
  const dims = getFaceDimensions(50);

  it("eyes are larger than Sprint 130 (eyeRx >= 0.20 * faceScale)", () => {
    const faceScale = 50 * 0.82;
    expect(dims.eyeRx).toBeGreaterThanOrEqual(faceScale * 0.20);
    expect(dims.eyeRy).toBeGreaterThanOrEqual(faceScale * 0.25);
  });

  it("eyes are closer together (eyeSpacing <= 0.30 * faceScale)", () => {
    const faceScale = 50 * 0.82;
    expect(dims.eyeSpacing).toBeLessThanOrEqual(faceScale * 0.30);
  });

  it("eyes don't overlap (gap between inner edges > 0)", () => {
    // Left eye right edge: -eyeSpacing + eyeRx
    // Right eye left edge: eyeSpacing - eyeRx
    const gap = (dims.eyeSpacing - dims.eyeRx) * 2;
    expect(gap).toBeGreaterThan(0);
  });

  it("pupil is proportionally smaller relative to bigger eye", () => {
    // Pupil should be smaller than iris
    expect(dims.pupilR).toBeLessThan(dims.irisRx);
    expect(dims.pupilR).toBeLessThan(dims.irisRy);
  });

  it("highlights are Ghibli-sized (larger than Sprint 130)", () => {
    const faceScale = 50 * 0.82;
    expect(dims.shineR1).toBeGreaterThanOrEqual(faceScale * 0.055);
    expect(dims.shineR2).toBeGreaterThanOrEqual(faceScale * 0.030);
  });

  it("eyebrows are wider to match bigger eyes", () => {
    const faceScale = 50 * 0.82;
    expect(dims.browHalfWidth).toBeGreaterThanOrEqual(faceScale * 0.16);
  });

  it("mouth is positioned lower (below larger eyes)", () => {
    const faceScale = 50 * 0.82;
    expect(dims.mouthY).toBeGreaterThanOrEqual(faceScale * 0.26);
  });
});

// ─── Iris Dimensions ─────────────────────────────────────────────────────────

describe("Kawaii Phase 1: Iris dimensions", () => {
  const dims = getFaceDimensions(50);

  it("iris is smaller than sclera (visible white border)", () => {
    expect(dims.irisRx).toBeLessThan(dims.eyeRx);
    expect(dims.irisRy).toBeLessThan(dims.eyeRy);
  });

  it("iris is larger than pupil (colored ring visible)", () => {
    expect(dims.irisRx).toBeGreaterThan(dims.pupilR);
    expect(dims.irisRy).toBeGreaterThan(dims.pupilR);
  });

  it("iris is 70-85% of sclera width", () => {
    const ratio = dims.irisRx / dims.eyeRx;
    expect(ratio).toBeGreaterThanOrEqual(0.70);
    expect(ratio).toBeLessThanOrEqual(0.85);
  });

  it("irisRx and irisRy are positive", () => {
    expect(dims.irisRx).toBeGreaterThan(0);
    expect(dims.irisRy).toBeGreaterThan(0);
  });

  it("scales proportionally with blob radius", () => {
    const small = getFaceDimensions(30);
    const large = getFaceDimensions(80);
    expect(large.irisRx).toBeGreaterThan(small.irisRx);
    expect(large.irisRy).toBeGreaterThan(small.irisRy);
  });
});

// ─── Nose Dimensions ─────────────────────────────────────────────────────────

describe("Kawaii Phase 1: Nose", () => {
  const dims = getFaceDimensions(50);

  it("nose is positioned between eyes and mouth", () => {
    expect(dims.noseY).toBeGreaterThan(dims.eyeY);
    expect(dims.noseY).toBeLessThan(dims.mouthY);
  });

  it("nose radius is very small (subtle)", () => {
    const faceScale = 50 * 0.82;
    expect(dims.noseR).toBeLessThan(faceScale * 0.04);
    expect(dims.noseR).toBeGreaterThan(0);
  });

  it("nose scales with blob radius", () => {
    const small = getFaceDimensions(30);
    const large = getFaceDimensions(80);
    expect(large.noseR).toBeGreaterThan(small.noseR);
  });
});

// ─── Blush Hash Line Dimensions ──────────────────────────────────────────────

describe("Kawaii Phase 1: Blush hash lines", () => {
  const dims = getFaceDimensions(50);

  it("blushHashLen is positive", () => {
    expect(dims.blushHashLen).toBeGreaterThan(0);
  });

  it("blushHashGap is positive and smaller than hashLen", () => {
    expect(dims.blushHashGap).toBeGreaterThan(0);
    expect(dims.blushHashGap).toBeLessThan(dims.blushHashLen);
  });

  it("blushHashStroke is thin (< 2px at blobRadius=50)", () => {
    expect(dims.blushHashStroke).toBeLessThan(2);
    expect(dims.blushHashStroke).toBeGreaterThan(0);
  });

  it("hash dimensions scale with blob radius", () => {
    const small = getFaceDimensions(30);
    const large = getFaceDimensions(80);
    expect(large.blushHashLen).toBeGreaterThan(small.blushHashLen);
    expect(large.blushHashGap).toBeGreaterThan(small.blushHashGap);
  });
});

// ─── SVG Source: Iris Gradient ──────────────────────────────────────────────

describe("Kawaii Phase 1: SVG source — iris", () => {
  it("WiiiAvatar contains radialGradient for iris", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("radialGradient");
    expect(code).toContain("wiii-iris-");
  });

  it("WiiiAvatar contains clipPath for eye clipping", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("clipPath");
    expect(code).toContain("wiii-eye-clip-l-");
    expect(code).toContain("wiii-eye-clip-r-");
  });

  it("iris gradient uses amber/orange brand colors", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    // Check for amber gradient stops
    expect(code).toContain("#fbbf24"); // Bright gold
    expect(code).toContain("#d97706"); // Amber
    expect(code).toContain("#92400e"); // Deep brown
  });

  it("iris group has wiii-face-iris class", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-face-iris");
  });

  it("iris is rendered as ellipse with gradient fill", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    // Iris uses url(#gradient) fill
    expect(code).toContain("irisGradId");
    expect(code).toContain("irisRx");
    expect(code).toContain("irisRy");
  });
});

// ─── SVG Source: Nose ────────────────────────────────────────────────────────

describe("Kawaii Phase 1: SVG source — nose", () => {
  it("WiiiAvatar renders nose circle", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-face-nose");
    expect(code).toContain("dims.noseY");
    expect(code).toContain("dims.noseR");
  });

  it("nose has subtle opacity (not fully opaque white)", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    // Check for semi-transparent fill
    expect(code).toContain("rgba(255,255,255,0.35)");
  });
});

// ─── SVG Source: Blush Hash Lines ────────────────────────────────────────────

describe("Kawaii Phase 1: SVG source — blush hash lines", () => {
  it("WiiiAvatar renders blush hash lines", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-face-blush-hash");
    expect(code).toContain("blushHashStroke");
  });

  it("hash lines use pink color matching blush ellipses", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    // Both blush ellipses and hash lines use #ff6b9d
    const pinkMatches = code.match(/#ff6b9d/g);
    expect(pinkMatches).toBeTruthy();
    // Ellipses (2) + hash lines (6 via leftHash + rightHash maps)
    expect(pinkMatches!.length).toBeGreaterThanOrEqual(3);
  });

  it("getBlushHashLines generates 3 lines per cheek", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    // leftHash.map and rightHash.map generate 3 lines each
    expect(code).toContain("leftHash.map");
    expect(code).toContain("rightHash.map");
  });
});

// ─── Animation: Iris Refs ────────────────────────────────────────────────────

describe("Kawaii Phase 1: Animation — iris refs", () => {
  it("AnimationResult includes leftIrisRef and rightIrisRef", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("leftIrisRef");
    expect(code).toContain("rightIrisRef");
  });

  it("eye group uses scaleY only (blink), no translate", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    // Eye group transform should be scale only
    const eyeTransformMatch = code.match(/leftEyeRef\.current\.setAttribute\("transform",\s*`scale\(/);
    expect(eyeTransformMatch).toBeTruthy();
  });

  it("iris group uses translate for gaze tracking", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    // Iris group gets translate for pupil tracking
    const irisTransformMatch = code.match(/leftIrisRef\.current\.setAttribute\("transform",\s*`translate\(/);
    expect(irisTransformMatch).toBeTruthy();
  });

  it("blush hash lines are animated via querySelectorAll", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-face-blush-hash");
    expect(code).toContain("querySelectorAll");
  });
});

// ─── CSS: New Classes ────────────────────────────────────────────────────────

describe("Kawaii Phase 1: CSS classes", () => {
  it("WiiiAvatar references wiii-face-iris class", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-face-iris");
  });

  it("WiiiAvatar references wiii-face-blush-hash class", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-face-blush-hash");
  });

  it("WiiiAvatar references wiii-face-nose class", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-face-nose");
  });
});

// ─── FaceDimensions Interface ────────────────────────────────────────────────

describe("Kawaii Phase 1: FaceDimensions completeness", () => {
  const dims: FaceDimensions = getFaceDimensions(50);

  it("contains all original fields", () => {
    expect(dims.eyeSpacing).toBeDefined();
    expect(dims.eyeY).toBeDefined();
    expect(dims.eyeRx).toBeDefined();
    expect(dims.eyeRy).toBeDefined();
    expect(dims.pupilR).toBeDefined();
    expect(dims.pupilMaxOffset).toBeDefined();
    expect(dims.browY).toBeDefined();
    expect(dims.browHalfWidth).toBeDefined();
    expect(dims.browStroke).toBeDefined();
    expect(dims.mouthY).toBeDefined();
    expect(dims.mouthBaseWidth).toBeDefined();
    expect(dims.mouthStroke).toBeDefined();
  });

  it("contains Sprint 130 fields", () => {
    expect(dims.shineR1).toBeDefined();
    expect(dims.shineR2).toBeDefined();
    expect(dims.shineOffsetX1).toBeDefined();
    expect(dims.shineOffsetY1).toBeDefined();
    expect(dims.shineOffsetX2).toBeDefined();
    expect(dims.shineOffsetY2).toBeDefined();
    expect(dims.blushX).toBeDefined();
    expect(dims.blushY).toBeDefined();
    expect(dims.blushRx).toBeDefined();
    expect(dims.blushRy).toBeDefined();
  });

  it("contains Sprint 131 iris fields", () => {
    expect(dims.irisRx).toBeDefined();
    expect(dims.irisRy).toBeDefined();
  });

  it("contains Sprint 131 nose fields", () => {
    expect(dims.noseY).toBeDefined();
    expect(dims.noseR).toBeDefined();
  });

  it("contains Sprint 131 blush hash fields", () => {
    expect(dims.blushHashLen).toBeDefined();
    expect(dims.blushHashGap).toBeDefined();
    expect(dims.blushHashStroke).toBeDefined();
  });
});

// ─── Face Expressions (unchanged) ────────────────────────────────────────────

describe("Kawaii Phase 1: FaceExpression compatibility", () => {
  it("all 6 state presets still exist", () => {
    expect(FACE_EXPRESSIONS.idle).toBeDefined();
    expect(FACE_EXPRESSIONS.listening).toBeDefined();
    expect(FACE_EXPRESSIONS.thinking).toBeDefined();
    expect(FACE_EXPRESSIONS.speaking).toBeDefined();
    expect(FACE_EXPRESSIONS.complete).toBeDefined();
    expect(FACE_EXPRESSIONS.error).toBeDefined();
  });

  it("lerpFaceExpression still works", () => {
    const result = lerpFaceExpression(FACE_EXPRESSIONS.idle, FACE_EXPRESSIONS.complete, 0.5);
    expect(result.eyeOpenness).toBe(1.0); // Both are 1.0
    expect(result.blush).toBeCloseTo(0.375, 2); // (0.15 + 0.6) / 2
    expect(result.eyeShape).toBeCloseTo(0.45, 2); // (0.05 + 0.85) / 2
  });

  it("FaceExpression has 13 fields (12 base + mouthShape from Phase 2)", () => {
    const keys = Object.keys(FACE_EXPRESSIONS.idle);
    expect(keys.length).toBe(13);
  });
});

// ─── Barrel Exports ──────────────────────────────────────────────────────────

describe("Kawaii Phase 1: Barrel exports", () => {
  it("index.ts exports FaceDimensions type", async () => {
    const src = await import("@/lib/avatar/index?raw");
    const code = (src as any).default || src;
    expect(code).toContain("FaceDimensions");
  });

  it("existing exports still present", async () => {
    const src = await import("@/lib/avatar/index?raw");
    const code = (src as any).default || src;
    expect(code).toContain("WiiiAvatar");
    expect(code).toContain("STATE_LABELS");
    expect(code).toContain("getFaceDimensions");
    expect(code).toContain("generateMouthPath");
    expect(code).toContain("generateHappyEyePath");
    expect(code).toContain("BlinkController");
    expect(code).toContain("lerpHexColor");
    expect(code).toContain("springEase");
  });
});

// ─── Backward Compatibility ──────────────────────────────────────────────────

describe("Kawaii Phase 1: Backward compatibility", () => {
  it("generateHappyEyePath still works with new dimensions", () => {
    const dims = getFaceDimensions(50);
    const path = generateHappyEyePath(-dims.eyeSpacing, dims.eyeY, dims.eyeRx, dims.eyeRy);
    expect(path).toContain("M ");
    expect(path).toContain(" Q ");
  });

  it("medium tier still shows W text (not face)", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    // Medium tier renders text "W", large tier renders FaceGroup
    expect(code).toContain('tier === "large"');
    // JSX: W text inside <text> element
    expect(code).toMatch(/>\s*W\s*<\/text>/);
  });

  it("tiny tier is unchanged (CSS-only)", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-avatar-tiny");
    expect(code).toContain('tier === "tiny"');
  });
});
