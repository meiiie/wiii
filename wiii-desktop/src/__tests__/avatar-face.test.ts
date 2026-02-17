/**
 * Sprint 129: SVG Face on Blob — tests.
 * Tests: face config, face geometry, blink controller, face rendering,
 * backward compatibility, CSS updates.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { AvatarState } from "@/lib/avatar/types";

// ---------------------------------------------------------------------------
// 1) Face expression config
// ---------------------------------------------------------------------------
describe("Face expression config", () => {
  it("FACE_EXPRESSIONS has all 6 states defined", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    const states: AvatarState[] = ["idle", "listening", "thinking", "speaking", "complete", "error"];
    for (const s of states) {
      expect(FACE_EXPRESSIONS[s]).toBeDefined();
    }
  });

  it("each expression has all required fields", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    const requiredFields = [
      "eyeOpenness", "pupilSize", "pupilOffsetX", "pupilOffsetY",
      "mouthCurve", "mouthOpenness", "mouthWidth",
      "browRaise", "browTilt", "blinkRate",
    ];
    for (const [, expr] of Object.entries(FACE_EXPRESSIONS)) {
      for (const field of requiredFields) {
        expect(expr).toHaveProperty(field);
      }
    }
  });

  it("idle has slight smile (mouthCurve > 0)", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    expect(FACE_EXPRESSIONS.idle.mouthCurve).toBeGreaterThan(0);
  });

  it("complete has strongest smile", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    expect(FACE_EXPRESSIONS.complete.mouthCurve).toBeGreaterThan(
      FACE_EXPRESSIONS.idle.mouthCurve,
    );
  });

  it("error has frown (negative mouthCurve)", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    expect(FACE_EXPRESSIONS.error.mouthCurve).toBeLessThan(0);
  });

  it("error has wide eyes (eyeOpenness > 1.0)", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    expect(FACE_EXPRESSIONS.error.eyeOpenness).toBeGreaterThan(1.0);
  });

  it("thinking has pupils looking up-right", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    expect(FACE_EXPRESSIONS.thinking.pupilOffsetX).toBeGreaterThan(0);
    expect(FACE_EXPRESSIONS.thinking.pupilOffsetY).toBeLessThan(0);
  });

  it("listening has raised eyebrows (browRaise > 0)", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    expect(FACE_EXPRESSIONS.listening.browRaise).toBeGreaterThan(0);
  });

  it("error has worried furrow (browRaise < 0, browTilt < 0)", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    expect(FACE_EXPRESSIONS.error.browRaise).toBeLessThan(0);
    expect(FACE_EXPRESSIONS.error.browTilt).toBeLessThan(0);
  });

  it("blinkRate is in sane range [5, 25] for all states", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    for (const [, expr] of Object.entries(FACE_EXPRESSIONS)) {
      expect(expr.blinkRate).toBeGreaterThanOrEqual(5);
      expect(expr.blinkRate).toBeLessThanOrEqual(25);
    }
  });

  it("thinking has less blinking than idle (concentrated)", async () => {
    const { FACE_EXPRESSIONS } = await import("@/lib/avatar/face-config");
    expect(FACE_EXPRESSIONS.thinking.blinkRate).toBeLessThan(
      FACE_EXPRESSIONS.idle.blinkRate,
    );
  });
});

// ---------------------------------------------------------------------------
// 2) Face expression interpolation
// ---------------------------------------------------------------------------
describe("lerpFaceExpression", () => {
  it("returns source at t=0", async () => {
    const { FACE_EXPRESSIONS, lerpFaceExpression } = await import("@/lib/avatar/face-config");
    const result = lerpFaceExpression(FACE_EXPRESSIONS.idle, FACE_EXPRESSIONS.error, 0);
    expect(result.mouthCurve).toBe(FACE_EXPRESSIONS.idle.mouthCurve);
    expect(result.eyeOpenness).toBe(FACE_EXPRESSIONS.idle.eyeOpenness);
  });

  it("returns target at t=1", async () => {
    const { FACE_EXPRESSIONS, lerpFaceExpression } = await import("@/lib/avatar/face-config");
    const result = lerpFaceExpression(FACE_EXPRESSIONS.idle, FACE_EXPRESSIONS.error, 1);
    expect(result.mouthCurve).toBe(FACE_EXPRESSIONS.error.mouthCurve);
    expect(result.eyeOpenness).toBe(FACE_EXPRESSIONS.error.eyeOpenness);
  });

  it("returns midpoint values at t=0.5", async () => {
    const { FACE_EXPRESSIONS, lerpFaceExpression } = await import("@/lib/avatar/face-config");
    const from = FACE_EXPRESSIONS.idle;
    const to = FACE_EXPRESSIONS.complete;
    const mid = lerpFaceExpression(from, to, 0.5);
    const expectedCurve = (from.mouthCurve + to.mouthCurve) / 2;
    expect(mid.mouthCurve).toBeCloseTo(expectedCurve, 5);
  });
});

// ---------------------------------------------------------------------------
// 3) Face geometry — dimensions
// ---------------------------------------------------------------------------
describe("Face geometry dimensions", () => {
  it("getFaceDimensions returns all required fields", async () => {
    const { getFaceDimensions } = await import("@/lib/avatar/face-geometry");
    const dims = getFaceDimensions(40);
    expect(dims.eyeSpacing).toBeGreaterThan(0);
    expect(dims.eyeRx).toBeGreaterThan(0);
    expect(dims.eyeRy).toBeGreaterThan(0);
    expect(dims.pupilR).toBeGreaterThan(0);
    expect(dims.browHalfWidth).toBeGreaterThan(0);
    expect(dims.mouthBaseWidth).toBeGreaterThan(0);
    expect(dims.mouthStroke).toBeGreaterThanOrEqual(1);
    expect(dims.browStroke).toBeGreaterThanOrEqual(1);
  });

  it("dimensions scale proportionally with blob radius", async () => {
    const { getFaceDimensions } = await import("@/lib/avatar/face-geometry");
    const small = getFaceDimensions(20);
    const large = getFaceDimensions(40);
    // 2x radius should give ~2x dimensions
    expect(large.eyeSpacing).toBeCloseTo(small.eyeSpacing * 2, 0);
    expect(large.eyeRx).toBeCloseTo(small.eyeRx * 2, 0);
    expect(large.mouthBaseWidth).toBeCloseTo(small.mouthBaseWidth * 2, 0);
  });

  it("pupilR is smaller than eyeRx (pupil fits inside eye)", async () => {
    const { getFaceDimensions } = await import("@/lib/avatar/face-geometry");
    const dims = getFaceDimensions(40);
    expect(dims.pupilR).toBeLessThan(dims.eyeRx);
    expect(dims.pupilR).toBeLessThan(dims.eyeRy);
  });

  it("browY is above eyeY (brows above eyes)", async () => {
    const { getFaceDimensions } = await import("@/lib/avatar/face-geometry");
    const dims = getFaceDimensions(40);
    // Both negative (above center), browY should be more negative
    expect(dims.browY).toBeLessThan(dims.eyeY);
  });

  it("mouthY is below center (positive)", async () => {
    const { getFaceDimensions } = await import("@/lib/avatar/face-geometry");
    const dims = getFaceDimensions(40);
    expect(dims.mouthY).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// 4) Face geometry — mouth path
// ---------------------------------------------------------------------------
describe("Mouth path generation", () => {
  it("generates valid SVG path starting with M", async () => {
    const { generateMouthPath } = await import("@/lib/avatar/face-geometry");
    const path = generateMouthPath(0, 10, { curve: 0.2, openness: 0, width: 1.0 }, 20);
    expect(path).toMatch(/^M /);
  });

  it("closed mouth (openness < 0.05) has no Z closure", async () => {
    const { generateMouthPath } = await import("@/lib/avatar/face-geometry");
    const path = generateMouthPath(0, 10, { curve: 0.2, openness: 0, width: 1.0 }, 20);
    expect(path).not.toContain("Z");
  });

  it("open mouth (openness >= 0.05) has Z closure", async () => {
    const { generateMouthPath } = await import("@/lib/avatar/face-geometry");
    const path = generateMouthPath(0, 10, { curve: 0.2, openness: 0.5, width: 1.0 }, 20);
    expect(path).toContain("Z");
  });

  it("different curve values produce different paths", async () => {
    const { generateMouthPath } = await import("@/lib/avatar/face-geometry");
    const smile = generateMouthPath(0, 10, { curve: 0.5, openness: 0, width: 1.0 }, 20);
    const frown = generateMouthPath(0, 10, { curve: -0.5, openness: 0, width: 1.0 }, 20);
    expect(smile).not.toBe(frown);
  });

  it("wider mouth produces wider path", async () => {
    const { generateMouthPath } = await import("@/lib/avatar/face-geometry");
    const narrow = generateMouthPath(0, 10, { curve: 0, openness: 0, width: 0.5 }, 20);
    const wide = generateMouthPath(0, 10, { curve: 0, openness: 0, width: 1.5 }, 20);
    expect(narrow).not.toBe(wide);
  });

  it("path contains C (cubic bezier) command", async () => {
    const { generateMouthPath } = await import("@/lib/avatar/face-geometry");
    const path = generateMouthPath(0, 10, { curve: 0.2, openness: 0, width: 1.0 }, 20);
    expect(path).toContain("C ");
  });
});

// ---------------------------------------------------------------------------
// 5) Blink controller
// ---------------------------------------------------------------------------
describe("BlinkController", () => {
  it("starts with eyes open (returns 1.0)", async () => {
    const { BlinkController } = await import("@/lib/avatar/blink-controller");
    const ctrl = new BlinkController(15);
    // First frame — should be open (countdown not yet expired)
    expect(ctrl.advance(0.016)).toBe(1.0);
  });

  it("triggerBlink causes eyes to squeeze", async () => {
    const { BlinkController } = await import("@/lib/avatar/blink-controller");
    const ctrl = new BlinkController(15);
    ctrl.triggerBlink();
    // Mid-blink should be < 1.0
    const scale = ctrl.advance(0.075); // ~50% through blink
    expect(scale).toBeLessThan(1.0);
    expect(scale).toBeGreaterThan(0);
  });

  it("blink completes and returns to 1.0", async () => {
    const { BlinkController } = await import("@/lib/avatar/blink-controller");
    const ctrl = new BlinkController(15);
    ctrl.triggerBlink();
    // Advance past blink duration (0.15s)
    ctrl.advance(0.08);
    ctrl.advance(0.08);
    const afterBlink = ctrl.advance(0.016);
    expect(afterBlink).toBe(1.0);
  });

  it("setRate changes blink rate without error", async () => {
    const { BlinkController } = await import("@/lib/avatar/blink-controller");
    const ctrl = new BlinkController(15);
    ctrl.setRate(8);
    expect(ctrl.advance(0.016)).toBe(1.0); // Still works
  });

  it("eventually triggers a natural blink (countdown expires)", async () => {
    const { BlinkController } = await import("@/lib/avatar/blink-controller");
    const ctrl = new BlinkController(60); // Very high rate → short interval
    let foundBlink = false;
    // Simulate 5 seconds at 60fps
    for (let i = 0; i < 300; i++) {
      const scale = ctrl.advance(1 / 60);
      if (scale < 1.0) {
        foundBlink = true;
        break;
      }
    }
    expect(foundBlink).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 6) WiiiAvatar face rendering
// ---------------------------------------------------------------------------
describe("WiiiAvatar face rendering (Sprint 129)", () => {
  it("large tier renders face group with eyes, mouth, eyebrows", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("wiii-face");
    expect(code).toContain("wiii-face-eye");
    expect(code).toContain("wiii-face-brow");
    expect(code).toContain("wiii-face-mouth");
  });

  it("face renders only at large tier, W text at medium tier", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    // Large tier gets FaceGroup
    expect(code).toContain('tier === "large"');
    expect(code).toContain("FaceGroup");
    // Medium tier keeps W text
    expect(code).toContain("<text");
    // JSX text child: indented W between > and </text>
    expect(code).toMatch(/>\s+W\s+<\/text>/);
  });

  it("face has left and right eye (ellipse + circle each)", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Left eye");
    expect(code).toContain("Right eye");
    expect(code).toContain("<ellipse");
    expect(code).toContain('<circle');
    expect(code).toContain('fill="#1a1a1a"');
  });

  it("face has left and right eyebrow (line elements)", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Left eyebrow");
    expect(code).toContain("Right eyebrow");
    expect(code).toContain('strokeLinecap="round"');
  });

  it("face has mouth (path element)", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("Mouth");
    expect(code).toContain("mouthRef");
  });

  it("face imports FaceGroup dependencies", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("getFaceDimensions");
    expect(code).toContain("FACE_EXPRESSIONS");
    expect(code).toContain("generateMouthPath");
  });

  it("face refs are wired from animation hook", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("faceGroupRef");
    expect(code).toContain("leftEyeRef");
    expect(code).toContain("rightEyeRef");
    expect(code).toContain("leftBrowRef");
    expect(code).toContain("rightBrowRef");
    expect(code).toContain("mouthRef");
  });
});

// ---------------------------------------------------------------------------
// 7) Animation hook face integration
// ---------------------------------------------------------------------------
describe("Animation hook face integration (Sprint 129)", () => {
  it("hook imports face modules", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("FACE_EXPRESSIONS");
    expect(code).toContain("lerpFaceExpression");
    expect(code).toContain("getFaceDimensions");
    expect(code).toContain("generateMouthPath");
    expect(code).toContain("BlinkController");
  });

  it("hook creates face refs", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("faceGroupRef");
    expect(code).toContain("leftEyeRef");
    expect(code).toContain("rightEyeRef");
    expect(code).toContain("leftBrowRef");
    expect(code).toContain("rightBrowRef");
    expect(code).toContain("mouthRef");
  });

  it("hook has blink controller ref", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("blinkCtrlRef");
    expect(code).toContain("BlinkController");
  });

  it("rAF loop updates face features for large tier", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    // Face update block
    expect(code).toContain("faceGroupRef.current");
    expect(code).toContain("leftEyeRef.current");
    expect(code).toContain("mouthRef.current");
    // Blink
    expect(code).toContain("blinkCtrlRef.current.advance");
    // Micro-motion
    expect(code).toContain("microX");
    expect(code).toContain("microY");
  });

  it("speaking state has noise-driven mouth oscillation", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain('"speaking"');
    expect(code).toContain("speakNoise");
  });

  it("state transition updates face expression and triggers blink", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("fromFaceRef");
    expect(code).toContain("toFaceRef");
    expect(code).toContain("triggerBlink");
  });
});

// ---------------------------------------------------------------------------
// 8) CSS updates for face
// ---------------------------------------------------------------------------
describe("CSS face GPU hints (Sprint 129)", () => {
  const cssPath = resolve(__dirname, "../lib/avatar/avatar.css");
  const cssCode = readFileSync(cssPath, "utf-8");

  it("has will-change for face eye elements", () => {
    expect(cssCode).toContain("wiii-face-eye");
    expect(cssCode).toContain("will-change: transform");
  });

  it("has will-change for face brow elements", () => {
    expect(cssCode).toContain("wiii-face-brow");
  });

  it("reduced motion resets face will-change", () => {
    // Inside the prefers-reduced-motion block
    expect(cssCode).toContain("wiii-face-eye");
    expect(cssCode).toContain("will-change: auto");
  });
});

// ---------------------------------------------------------------------------
// 9) Barrel exports include face modules
// ---------------------------------------------------------------------------
describe("Barrel exports (Sprint 129)", () => {
  it("index.ts exports face types and functions", async () => {
    const src = await import("@/lib/avatar/index?raw");
    const code = (src as any).default || src;
    expect(code).toContain("FaceExpression");
    expect(code).toContain("FACE_EXPRESSIONS");
    expect(code).toContain("lerpFaceExpression");
    expect(code).toContain("getFaceDimensions");
    expect(code).toContain("generateMouthPath");
    expect(code).toContain("BlinkController");
  });
});

// ---------------------------------------------------------------------------
// 10) Backward compatibility — medium/tiny still show "W"
// ---------------------------------------------------------------------------
describe("Backward compatibility (Sprint 129)", () => {
  it("tiny tier still renders W character (no face)", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    // Tiny tier section should still have W
    expect(code).toContain("wiii-avatar-tiny");
    expect(code).toMatch(/>\s*W\s*<\/motion\.div>/);
  });

  it("memo wrapper is preserved", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("memo(WiiiAvatarInner)");
  });

  it("existing 8 usage sites still work (import WiiiAvatar)", async () => {
    const files = [
      "@/App?raw",
      "@/components/settings/SettingsPage?raw",
      "@/components/chat/MessageList?raw",
      "@/components/chat/WelcomeScreen?raw",
      "@/components/chat/MessageBubble?raw",
      "@/components/layout/Sidebar?raw",
      "@/components/layout/StatusBar?raw",
      "@/components/common/ErrorBoundary?raw",
    ];
    for (const file of files) {
      const src = await import(/* @vite-ignore */ file);
      const code = (src as any).default || src;
      expect(code).toContain("WiiiAvatar");
    }
  });
});
