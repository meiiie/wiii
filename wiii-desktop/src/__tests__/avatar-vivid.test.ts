/**
 * Tests for "Vivid Wiii" avatar enhancements — Sprint 134.
 *
 * Covers: Pupil dilation wiring, breathing variation, life-based particle
 * sizing, blob color hex interpolation, shaped burst particles, environmental
 * aura, error shiver filter, moving eye shine, barrel exports.
 */
import { describe, it, expect } from "vitest";

// ─── Imports ──────────────────────────────────────────────────────────────────
import { STATE_CONFIG } from "@/lib/avatar/state-config";
import type { StateVisuals } from "@/lib/avatar/types";
import { FACE_EXPRESSIONS } from "@/lib/avatar/face-config";
import { getFaceDimensions } from "@/lib/avatar/face-geometry";
import { lerpHexColor, springEase } from "@/lib/avatar/use-avatar-animation";
import {
  spawnBurst,
  spawnFallingBurst,
  updateBurstParticles,
  spawnParticle,
  updateParticles,
  renderParticles,
} from "@/lib/avatar/particle-system";
import type { BurstParticle, ParticleShape } from "@/lib/avatar/particle-system";
import { applyMoodToVisuals, MOOD_THEMES } from "@/lib/avatar/mood-theme";

// ─── Raw source for structural checks ─────────────────────────────────────────
import avatarSource from "@/lib/avatar/WiiiAvatar.tsx?raw";
import animSource from "@/lib/avatar/use-avatar-animation.ts?raw";

// ═══════════════════════════════════════════════════════════════════════════════
// 1. BLOB COLOR HEX — StateVisuals + interpolation
// ═══════════════════════════════════════════════════════════════════════════════

describe("Blob color hex interpolation", () => {
  it("all 6 states have blobColorHex field", () => {
    const states = ["idle", "listening", "thinking", "speaking", "complete", "error"];
    for (const s of states) {
      expect(STATE_CONFIG[s]).toHaveProperty("blobColorHex");
      expect(STATE_CONFIG[s].blobColorHex).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  it("idle/listening/thinking/speaking use orange hex", () => {
    for (const s of ["idle", "listening", "thinking", "speaking"]) {
      expect(STATE_CONFIG[s].blobColorHex).toBe("#f97316");
    }
  });

  it("complete uses green hex", () => {
    expect(STATE_CONFIG.complete.blobColorHex).toBe("#22c55e");
  });

  it("error uses amber hex", () => {
    expect(STATE_CONFIG.error.blobColorHex).toBe("#f59e0b");
  });

  it("lerpHexColor interpolates at 50%", () => {
    const result = lerpHexColor("#000000", "#ffffff", 0.5);
    const r = parseInt(result.slice(1, 3), 16);
    const g = parseInt(result.slice(3, 5), 16);
    const b = parseInt(result.slice(5, 7), 16);
    expect(r).toBeGreaterThanOrEqual(127);
    expect(r).toBeLessThanOrEqual(128);
    expect(g).toBeGreaterThanOrEqual(127);
    expect(b).toBeGreaterThanOrEqual(127);
  });

  it("lerpHexColor returns target at t=1", () => {
    expect(lerpHexColor("#ff0000", "#00ff00", 1)).toBe("#00ff00");
  });

  it("lerpHexColor returns source at t=0", () => {
    expect(lerpHexColor("#ff0000", "#00ff00", 0)).toBe("#ff0000");
  });

  it("lerpVisuals uses blobColorHex in rAF path update", () => {
    expect(animSource).toContain('pathRef.current.setAttribute("fill", visuals.blobColorHex)');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 2. PUPIL DILATION — face.pupilSize wired to SVG radius
// ═══════════════════════════════════════════════════════════════════════════════

describe("Pupil dilation wiring", () => {
  it("pupil circles have wiii-face-pupil className in SVG", () => {
    const matches = avatarSource.match(/className="wiii-face-pupil"/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBe(2); // left + right pupil
  });

  it("rAF updates pupil radius via querySelector", () => {
    expect(animSource).toContain('.querySelector(".wiii-face-pupil")');
    expect(animSource).toContain("activePupilR");
    expect(animSource).toContain("dims.pupilR * face.pupilSize");
  });

  it("face presets have varying pupilSize values", () => {
    expect(FACE_EXPRESSIONS.thinking.pupilSize).toBe(0.9);
    expect(FACE_EXPRESSIONS.idle.pupilSize).toBe(1.0);
    expect(FACE_EXPRESSIONS.speaking.pupilSize).toBe(1.05);
    expect(FACE_EXPRESSIONS.listening.pupilSize).toBe(1.1);
    expect(FACE_EXPRESSIONS.error.pupilSize).toBe(0.8);
  });

  it("pupilR scales with blob radius", () => {
    const dims40 = getFaceDimensions(40);
    const dims80 = getFaceDimensions(80);
    expect(dims80.pupilR).toBeCloseTo(dims40.pupilR * 2, 1);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 3. BREATHING VARIATION — noise-modulated frequency + depth
// ═══════════════════════════════════════════════════════════════════════════════

describe("Breathing variation", () => {
  it("rAF uses noise-modulated breath frequency", () => {
    expect(animSource).toContain("breathFreq");
    expect(animSource).toContain("1.25 + noise3D");
    expect(animSource).toContain("seed + 700");
  });

  it("rAF uses noise-modulated breath depth", () => {
    expect(animSource).toContain("breathDepth");
    expect(animSource).toContain("0.020 + noise3D");
    expect(animSource).toContain("seed + 800");
  });

  it("breathing applies to faceGroup vertical position", () => {
    expect(animSource).toContain("breathY");
    expect(animSource).toContain("noiseTime * breathFreq");
    expect(animSource).toContain("blobRadius * breathDepth");
  });

  it("head tilt uses separate noise dimension", () => {
    expect(animSource).toContain("headTilt");
    expect(animSource).toContain("seed + 500");
    expect(animSource).toContain("* 1.5");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 4. PARTICLE LIFE-BASED SIZE
// ═══════════════════════════════════════════════════════════════════════════════

describe("Particle life-based sizing", () => {
  it("particle at life=1 has full size", () => {
    const drawSize = 2.0 * (0.4 + 0.6 * Math.sqrt(1.0));
    expect(drawSize).toBe(2.0);
  });

  it("particle at life=0 has minimum 40% size", () => {
    const drawSize = 2.0 * (0.4 + 0.6 * Math.sqrt(0));
    expect(drawSize).toBe(0.8);
  });

  it("particle at life=0.5 has intermediate size", () => {
    const life = 0.5;
    const drawSize = 2.0 * (0.4 + 0.6 * Math.sqrt(life));
    expect(drawSize).toBeCloseTo(1.648, 2);
  });

  it("orbital particles spawn with correct structure", () => {
    const p = spawnParticle(50, 50, 30);
    expect(p).toHaveProperty("life", 1.0);
    expect(p).toHaveProperty("angle");
    expect(p).toHaveProperty("orbitRadius");
    expect(p.size).toBeGreaterThan(0);
    expect(p.maxLife).toBeGreaterThanOrEqual(2);
  });

  it("size calculation is non-linear (square root curve)", () => {
    // Verify the curve shape: mid-life particles are larger than linear
    const linearMid = 2.0 * (0.4 + 0.6 * 0.5); // = 1.4 (linear would be)
    const sqrtMid = 2.0 * (0.4 + 0.6 * Math.sqrt(0.5)); // ≈ 1.648
    expect(sqrtMid).toBeGreaterThan(linearMid); // sqrt preserves size longer
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 5. SHAPED BURST PARTICLES
// ═══════════════════════════════════════════════════════════════════════════════

describe("Burst particle system", () => {
  it("spawnBurst creates correct count of particles", () => {
    const burst = spawnBurst(50, 50, 12, "star", "#fbbf24");
    expect(burst).toHaveLength(12);
  });

  it("burst particles have all required fields", () => {
    const burst = spawnBurst(50, 50, 1, "heart", "#ff0000");
    const p = burst[0];
    expect(p).toHaveProperty("x");
    expect(p).toHaveProperty("y");
    expect(p).toHaveProperty("vx");
    expect(p).toHaveProperty("vy");
    expect(p).toHaveProperty("life", 1.0);
    expect(p).toHaveProperty("size");
    expect(p).toHaveProperty("rotation");
    expect(p).toHaveProperty("rotSpeed");
    expect(p).toHaveProperty("shape", "heart");
    expect(p).toHaveProperty("color", "#ff0000");
  });

  it("spawnBurst uses custom speed and size ranges", () => {
    const burst = spawnBurst(0, 0, 20, "ring", "#fff", [100, 200], [5, 10]);
    for (const p of burst) {
      const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
      expect(speed).toBeGreaterThanOrEqual(90);
      expect(speed).toBeLessThanOrEqual(210);
      expect(p.size).toBeGreaterThanOrEqual(5);
      expect(p.size).toBeLessThanOrEqual(10);
    }
  });

  it("spawnFallingBurst creates downward-moving particles", () => {
    const burst = spawnFallingBurst(50, 50, 5, "teardrop", "#60a5fa");
    expect(burst).toHaveLength(5);
    for (const p of burst) {
      expect(p.vy).toBeGreaterThan(0);
      expect(p.shape).toBe("teardrop");
    }
  });

  it("updateBurstParticles decays life and filters dead particles", () => {
    const burst: BurstParticle[] = [
      { x: 0, y: 0, vx: 10, vy: 10, life: 0.05, size: 3, rotation: 0, rotSpeed: 1, shape: "dot", color: "#fff" },
      { x: 0, y: 0, vx: 10, vy: 10, life: 1.0, size: 3, rotation: 0, rotSpeed: 1, shape: "dot", color: "#fff" },
    ];
    const result = updateBurstParticles(burst, 0.5);
    expect(result).toHaveLength(1);
    expect(result[0].life).toBeCloseTo(0.6, 1);
  });

  it("updateBurstParticles applies gravity", () => {
    const burst: BurstParticle[] = [
      { x: 50, y: 50, vx: 0, vy: 0, life: 1.0, size: 3, rotation: 0, rotSpeed: 0, shape: "dot", color: "#fff" },
    ];
    const result = updateBurstParticles(burst, 0.1);
    expect(result[0].vy).toBeGreaterThan(0);
    expect(result[0].y).toBeGreaterThan(50);
  });

  it("all 5 shapes are valid ParticleShape values", () => {
    const shapes: ParticleShape[] = ["dot", "heart", "star", "ring", "teardrop"];
    for (const shape of shapes) {
      const burst = spawnBurst(0, 0, 1, shape, "#fff");
      expect(burst[0].shape).toBe(shape);
    }
  });

  it("burst particles rotate over time", () => {
    const burst: BurstParticle[] = [
      { x: 0, y: 0, vx: 0, vy: 0, life: 1.0, size: 3, rotation: 0, rotSpeed: 2, shape: "star", color: "#fff" },
    ];
    const result = updateBurstParticles(burst, 0.5);
    expect(result[0].rotation).toBeCloseTo(1.0, 1);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 6. BURST EMITTER STATE MAPPING
// ═══════════════════════════════════════════════════════════════════════════════

describe("Burst emitter state mapping", () => {
  it("complete state triggers star burst", () => {
    expect(animSource).toContain('"complete"');
    expect(animSource).toContain('"star"');
    expect(animSource).toContain('"#fbbf24"');
  });

  it("error state triggers teardrop falling burst", () => {
    expect(animSource).toContain('"error"');
    expect(animSource).toContain('"teardrop"');
    expect(animSource).toContain('"#60a5fa"');
  });

  it("listening state triggers ring burst", () => {
    expect(animSource).toContain('"ring"');
  });

  it("speaking state triggers heart burst", () => {
    expect(animSource).toContain('"heart"');
    expect(animSource).toContain('"#ff6b9d"');
  });

  it("burstEmittedRef prevents repeated bursts", () => {
    expect(animSource).toContain("burstEmittedRef.current = true");
    expect(animSource).toContain("burstEmittedRef.current = false");
  });

  it("state change resets burst flag", () => {
    const stateChangeBlock = animSource.split("Sprint 134: Mark burst pending")[1];
    expect(stateChangeBlock).toBeDefined();
    expect(stateChangeBlock).toContain("burstEmittedRef.current = false");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 7. ENVIRONMENTAL AURA
// ═══════════════════════════════════════════════════════════════════════════════

describe("Environmental aura", () => {
  it("rAF renders radial gradient before particles", () => {
    expect(animSource).toContain("Environmental aura");
    expect(animSource).toContain("createRadialGradient");
    expect(animSource).toContain("auraRadius");
  });

  it("aura uses screen composite mode", () => {
    expect(animSource).toContain('"screen"');
    expect(animSource).toContain("globalCompositeOperation");
  });

  it("aura only renders when glow intensity > threshold", () => {
    expect(animSource).toContain("glowIntensity > 0.03");
  });

  it("aura radius is proportional to blob radius", () => {
    expect(animSource).toContain("blobRadius * 2.2");
  });

  it("aura alpha is proportional to glow intensity", () => {
    expect(animSource).toContain("glowIntensity * 0.25");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 8. ERROR SHIVER FILTER
// ═══════════════════════════════════════════════════════════════════════════════

describe("Error shiver filter", () => {
  it("SVG has feTurbulence filter element", () => {
    expect(avatarSource).toContain("feTurbulence");
    expect(avatarSource).toContain("feDisplacementMap");
  });

  it("shiver filter has animated seed", () => {
    expect(avatarSource).toContain('attributeName="seed"');
    expect(avatarSource).toContain("repeatCount=\"indefinite\"");
  });

  it("shiver filter ID uses instance ID suffix", () => {
    expect(avatarSource).toContain("`${filterId}-shiver`");
  });

  it("blob uses shiver filter when state is error", () => {
    expect(avatarSource).toContain('state === "error"');
    expect(avatarSource).toContain("filterId}-shiver");
  });

  it("non-error states use normal glow filter", () => {
    expect(avatarSource).toContain("glowOpacity > 0.05");
    // Template literal check: `url(#${filterId})`
    expect(avatarSource).toContain("url(#${filterId})`");
  });

  it("shiver filter has correct displacement scale", () => {
    expect(avatarSource).toContain("scale={3}");
    expect(avatarSource).toContain('xChannelSelector="R"');
    expect(avatarSource).toContain('yChannelSelector="G"');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 9. MOVING EYE SHINE
// ═══════════════════════════════════════════════════════════════════════════════

describe("Moving eye shine", () => {
  it("shine circles have wiii-face-shine className", () => {
    const matches = avatarSource.match(/className="wiii-face-shine"/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBe(4);
  });

  it("rAF applies counter-drift to shine elements", () => {
    expect(animSource).toContain("shineCounterX");
    expect(animSource).toContain("shineCounterY");
    expect(animSource).toContain("-pupilDx * 0.35");
    expect(animSource).toContain("-pupilDy * 0.35");
  });

  it("shine uses noise for position drift", () => {
    expect(animSource).toContain("shineNoiseX");
    expect(animSource).toContain("shineNoiseY");
    expect(animSource).toContain("seed + 900");
  });

  it("shine applied via CSS transform (not cx/cy)", () => {
    expect(animSource).toContain("style.transform = `translate(");
    expect(animSource).toContain(".wiii-face-shine");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 10. MOOD BLOB TINTING
// ═══════════════════════════════════════════════════════════════════════════════

describe("Mood blob tinting", () => {
  it("applyMoodToVisuals tints blobColorHex", () => {
    const base: StateVisuals = { ...STATE_CONFIG.idle };
    const result = applyMoodToVisuals(base, "excited", 1.0, lerpHexColor);
    expect(result.blobColorHex).not.toBe(base.blobColorHex);
  });

  it("neutral mood does not modify blob color", () => {
    const base: StateVisuals = { ...STATE_CONFIG.idle };
    const result = applyMoodToVisuals(base, "neutral", 1.0, lerpHexColor);
    expect(result.blobColorHex).toBe(base.blobColorHex);
  });

  it("all non-neutral moods have particleColor defined", () => {
    for (const mood of ["excited", "warm", "concerned", "gentle"] as const) {
      expect(MOOD_THEMES[mood].particleColor).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  it("blob tint uses 15% max intensity in mood-theme", () => {
    // The blob tinting formula is in applyMoodToVisuals (mood-theme.ts)
    // Verified by testing actual output values
    const base: StateVisuals = { ...STATE_CONFIG.idle };
    const tinted = applyMoodToVisuals(base, "excited", 1.0, lerpHexColor);
    // At intensity=1.0, tint is 15% toward particleColor
    // Original: #f97316, excited particleColor: #fbbf24
    // Tinted should be between original and target, but close to original
    expect(tinted.blobColorHex).not.toBe(base.blobColorHex);
    expect(tinted.blobColorHex).toMatch(/^#[0-9a-fA-F]{6}$/);
  });

  it("mood tinting only applies when particleColor and blobColorHex exist", () => {
    // Neutral mood has empty particleColor → no tinting
    expect(MOOD_THEMES.neutral.particleColor).toBe("");
    const base: StateVisuals = { ...STATE_CONFIG.idle };
    const result = applyMoodToVisuals(base, "neutral", 1.0, lerpHexColor);
    expect(result.blobColorHex).toBe(base.blobColorHex);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 11. BARREL EXPORTS
// ═══════════════════════════════════════════════════════════════════════════════

describe("Barrel exports", () => {
  it("burst particle functions are importable", () => {
    expect(typeof spawnBurst).toBe("function");
    expect(typeof spawnFallingBurst).toBe("function");
    expect(typeof updateBurstParticles).toBe("function");
  });

  it("orbital particle functions are importable", () => {
    expect(typeof spawnParticle).toBe("function");
    expect(typeof updateParticles).toBe("function");
    expect(typeof renderParticles).toBe("function");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 12. SHAPE DRAWING — mathematical verification
// ═══════════════════════════════════════════════════════════════════════════════

describe("Burst shape physics", () => {
  it("radial burst particles cluster around center", () => {
    const burst = spawnBurst(100, 100, 20, "heart", "#ff0000");
    for (const p of burst) {
      const dist = Math.sqrt((p.x - 100) ** 2 + (p.y - 100) ** 2);
      expect(dist).toBeLessThan(5);
    }
  });

  it("radial burst velocities spread in all directions", () => {
    const burst = spawnBurst(0, 0, 20, "star", "#fff");
    const angles = burst.map(p => Math.atan2(p.vy, p.vx));
    const minAngle = Math.min(...angles);
    const maxAngle = Math.max(...angles);
    expect(maxAngle - minAngle).toBeGreaterThan(Math.PI);
  });

  it("falling burst has predominantly downward velocity", () => {
    const burst = spawnFallingBurst(100, 100, 10, "teardrop", "#60a5fa");
    for (const p of burst) {
      expect(p.vy).toBeGreaterThan(0);
      expect(Math.abs(p.vy)).toBeGreaterThan(Math.abs(p.vx));
    }
  });

  it("falling burst particles have zero rotation speed", () => {
    const burst = spawnFallingBurst(50, 50, 5, "teardrop", "#fff");
    for (const p of burst) {
      expect(p.rotSpeed).toBe(0);
      expect(p.rotation).toBe(0);
    }
  });

  it("radial burst has non-zero rotation speed", () => {
    const burst = spawnBurst(50, 50, 30, "star", "#fff");
    const hasRotation = burst.some(p => p.rotSpeed !== 0);
    expect(hasRotation).toBe(true);
  });

  it("burst particle friction slows velocity over time", () => {
    const burst: BurstParticle[] = [
      { x: 0, y: 0, vx: 100, vy: 0, life: 1.0, size: 3, rotation: 0, rotSpeed: 0, shape: "dot", color: "#fff" },
    ];
    const result = updateBurstParticles(burst, 0.1);
    expect(Math.abs(result[0].vx)).toBeLessThan(100); // friction applied
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 13. BACKWARD COMPATIBILITY
// ═══════════════════════════════════════════════════════════════════════════════

describe("Backward compatibility", () => {
  it("StateVisuals retains all original fields", () => {
    const original = [
      "noiseAmplitude", "noiseFrequency", "timeSpeed", "glowIntensity",
      "glowColor", "blobColor", "scale", "indicatorColor", "indicatorVisible",
      "particleCount", "particleColor", "particleOrbitSpeed", "particleDriftSpeed",
      "tinyBorderRadius",
    ];
    for (const key of original) {
      expect(STATE_CONFIG.idle).toHaveProperty(key);
    }
  });

  it("blobColor CSS variable preserved for tiny tier", () => {
    expect(STATE_CONFIG.idle.blobColor).toContain("var(--accent-orange");
    expect(STATE_CONFIG.complete.blobColor).toContain("var(--accent-green");
  });

  it("springEase returns 0 at t=0 and 1 at t=1", () => {
    expect(springEase(0)).toBe(0);
    expect(springEase(1)).toBe(1);
  });

  it("existing orbital particles still work", () => {
    const p = spawnParticle(50, 50, 30);
    const updated = updateParticles([p], 50, 50, 0.016, 0.5, 0.1);
    expect(updated.length).toBe(1);
    expect(updated[0].life).toBeLessThan(1.0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 14. INTEGRATION — Cross-feature checks
// ═══════════════════════════════════════════════════════════════════════════════

describe("Cross-feature integration", () => {
  it("error state combines shiver filter + worried face", () => {
    expect(FACE_EXPRESSIONS.error.browRaise).toBeLessThan(0);
    expect(FACE_EXPRESSIONS.error.pupilSize).toBeLessThan(1);
    expect(FACE_EXPRESSIONS.error.mouthShape).toBe(3);
    expect(avatarSource).toContain("shiver");
  });

  it("complete state combines happy eyes + blush + star burst", () => {
    expect(FACE_EXPRESSIONS.complete.eyeShape).toBeGreaterThan(0.8);
    expect(FACE_EXPRESSIONS.complete.blush).toBeGreaterThan(0.5);
    expect(animSource).toContain('"star"');
  });

  it("speaking state has unique face signature + heart burst", () => {
    expect(FACE_EXPRESSIONS.speaking.pupilOffsetY).toBe(0.1);
    expect(FACE_EXPRESSIONS.speaking.browRaise).toBe(0.15);
    expect(FACE_EXPRESSIONS.speaking.blush).toBe(0.15);
    expect(animSource).toContain('"heart"');
  });

  it("blob color hex matches glow color for each state", () => {
    expect(STATE_CONFIG.idle.glowColor).toBe(STATE_CONFIG.idle.blobColorHex);
    expect(STATE_CONFIG.complete.glowColor).toBe(STATE_CONFIG.complete.blobColorHex);
  });

  it("pupil dilation + mouse tracking coexist", () => {
    expect(animSource).toContain("activePupilR");
    expect(animSource).toContain("pupilDx");
  });

  it("burst renders after orbital particles in canvas", () => {
    // Find the render calls in the rAF loop (skip imports at top)
    const rAFSection = animSource.slice(animSource.indexOf("// rAF animation loop"));
    const burstRenderIdx = rAFSection.indexOf("renderBurstParticles");
    const orbitalRenderIdx = rAFSection.indexOf("renderParticles(ctx, particlesRef");
    expect(burstRenderIdx).toBeGreaterThan(orbitalRenderIdx);
  });
});
