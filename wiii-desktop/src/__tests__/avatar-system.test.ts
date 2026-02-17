/**
 * Sprint 115: Living Avatar System — Foundation tests.
 * Sprint 119: Visual Polish + Accessibility tests.
 * Tests: state config, noise engine, blob geometry, particle system,
 * backward compatibility, accessibility, component source checks,
 * color lerping, reduced motion, aria labels.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { AvatarState } from "@/lib/avatar/types";

// ---------------------------------------------------------------------------
// 1) State config
// ---------------------------------------------------------------------------
describe("Avatar state config", () => {
  it("getSizeTier returns correct tier for boundary values", async () => {
    const { getSizeTier } = await import("@/lib/avatar/state-config");
    expect(getSizeTier(14)).toBe("tiny");
    expect(getSizeTier(20)).toBe("tiny");
    expect(getSizeTier(21)).toBe("medium");
    expect(getSizeTier(24)).toBe("medium");
    expect(getSizeTier(36)).toBe("medium");
    expect(getSizeTier(37)).toBe("large");
    expect(getSizeTier(40)).toBe("large");
    expect(getSizeTier(48)).toBe("large");
  });

  it("STATE_CONFIG has all 6 states defined", async () => {
    const { STATE_CONFIG } = await import("@/lib/avatar/state-config");
    const states = ["idle", "listening", "thinking", "speaking", "complete", "error"];
    for (const s of states) {
      expect(STATE_CONFIG[s]).toBeDefined();
    }
  });

  it("each state has all required visual fields", async () => {
    const { STATE_CONFIG } = await import("@/lib/avatar/state-config");
    const requiredFields = [
      "noiseAmplitude", "noiseFrequency", "timeSpeed",
      "glowIntensity", "glowColor", "blobColor", "scale",
      "indicatorColor", "indicatorVisible",
      "particleCount", "particleColor", "particleOrbitSpeed", "particleDriftSpeed",
      "tinyBorderRadius",
    ];
    for (const [, config] of Object.entries(STATE_CONFIG)) {
      for (const field of requiredFields) {
        expect(config).toHaveProperty(field);
      }
    }
  });

  it("noise amplitudes are in sane range [0, 0.3]", async () => {
    const { STATE_CONFIG } = await import("@/lib/avatar/state-config");
    for (const [, config] of Object.entries(STATE_CONFIG)) {
      expect(config.noiseAmplitude).toBeGreaterThanOrEqual(0);
      expect(config.noiseAmplitude).toBeLessThanOrEqual(0.3);
    }
  });

  it("getBlobResolution returns correct values per tier", async () => {
    const { getBlobResolution } = await import("@/lib/avatar/state-config");
    expect(getBlobResolution("tiny")).toBe(0);
    expect(getBlobResolution("medium")).toBe(48);
    expect(getBlobResolution("large")).toBe(64);
  });

  it("thinking state has higher noise amplitude than idle", async () => {
    const { STATE_CONFIG } = await import("@/lib/avatar/state-config");
    expect(STATE_CONFIG.thinking.noiseAmplitude).toBeGreaterThan(
      STATE_CONFIG.idle.noiseAmplitude,
    );
  });

  it("complete state uses green glow color", async () => {
    const { STATE_CONFIG } = await import("@/lib/avatar/state-config");
    expect(STATE_CONFIG.complete.glowColor).toContain("22c55e");
  });

  it("error state uses amber glow color and hides indicator", async () => {
    const { STATE_CONFIG } = await import("@/lib/avatar/state-config");
    expect(STATE_CONFIG.error.glowColor).toContain("f59e0b");
    expect(STATE_CONFIG.error.indicatorVisible).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 2) Noise engine
// ---------------------------------------------------------------------------
describe("Noise engine", () => {
  it("getNoiseGenerator returns same singleton instance", async () => {
    const { getNoiseGenerator } = await import("@/lib/avatar/noise-engine");
    const gen1 = getNoiseGenerator();
    const gen2 = getNoiseGenerator();
    expect(gen1).toBe(gen2);
  });

  it("sampleBlobNoise returns values near 1.0 within amplitude", async () => {
    const { sampleBlobNoise } = await import("@/lib/avatar/noise-engine");
    const amp = 0.12;
    for (let angle = 0; angle < Math.PI * 2; angle += 0.5) {
      const val = sampleBlobNoise(angle, 0, 1.5, amp, 0);
      expect(val).toBeGreaterThanOrEqual(1.0 - amp - 0.001);
      expect(val).toBeLessThanOrEqual(1.0 + amp + 0.001);
    }
  });

  it("different seeds produce different values", async () => {
    const { sampleBlobNoise } = await import("@/lib/avatar/noise-engine");
    const val1 = sampleBlobNoise(0.5, 1.0, 1.5, 0.1, 0);
    const val2 = sampleBlobNoise(0.5, 1.0, 1.5, 0.1, 42);
    expect(val1).not.toBe(val2);
  });

  it("amplitude 0 returns exactly 1.0", async () => {
    const { sampleBlobNoise } = await import("@/lib/avatar/noise-engine");
    const val = sampleBlobNoise(1.0, 0.5, 1.0, 0, 7);
    expect(val).toBe(1.0);
  });
});

// ---------------------------------------------------------------------------
// 3) Blob geometry
// ---------------------------------------------------------------------------
describe("Blob geometry", () => {
  it("generateBlobPath starts with M and ends with Z", async () => {
    const { generateBlobPath } = await import("@/lib/avatar/blob-geometry");
    const path = generateBlobPath(50, 50, 40, 48, 0, 1.2, 0.06, 0);
    expect(path).toMatch(/^M /);
    expect(path).toMatch(/ Z$/);
  });

  it("different times produce different paths", async () => {
    const { generateBlobPath } = await import("@/lib/avatar/blob-geometry");
    const p1 = generateBlobPath(50, 50, 40, 48, 0, 1.2, 0.06, 0);
    const p2 = generateBlobPath(50, 50, 40, 48, 1.5, 1.2, 0.06, 0);
    expect(p1).not.toBe(p2);
  });

  it("amplitude 0 produces near-circular path", async () => {
    const { generateBlobPath } = await import("@/lib/avatar/blob-geometry");
    const path = generateBlobPath(50, 50, 40, 48, 0, 1.2, 0, 0);
    // First point should be at distance ~40 from center (50,50)
    const match = path.match(/^M ([\d.]+) ([\d.]+)/);
    expect(match).not.toBeNull();
    if (match) {
      const x = parseFloat(match[1]);
      const y = parseFloat(match[2]);
      const dist = Math.sqrt((x - 50) ** 2 + (y - 50) ** 2);
      expect(dist).toBeCloseTo(40, 0);
    }
  });

  it("resolution < 3 returns empty string", async () => {
    const { generateBlobPath } = await import("@/lib/avatar/blob-geometry");
    expect(generateBlobPath(50, 50, 40, 2, 0, 1.2, 0.06, 0)).toBe("");
    expect(generateBlobPath(50, 50, 40, 0, 0, 1.2, 0.06, 0)).toBe("");
  });

  it("path contains C (cubic bezier) commands", async () => {
    const { generateBlobPath } = await import("@/lib/avatar/blob-geometry");
    const path = generateBlobPath(50, 50, 40, 48, 0, 1.2, 0.06, 0);
    expect(path).toContain("C ");
  });
});

// ---------------------------------------------------------------------------
// 4) Particle system
// ---------------------------------------------------------------------------
describe("Particle system", () => {
  it("spawnParticle returns valid particle with life=1", async () => {
    const { spawnParticle } = await import("@/lib/avatar/particle-system");
    const p = spawnParticle(50, 50, 40);
    expect(p.life).toBe(1.0);
    expect(p.maxLife).toBeGreaterThanOrEqual(2);
    expect(p.maxLife).toBeLessThanOrEqual(5);
    expect(p.size).toBeGreaterThan(0);
    expect(p.orbitRadius).toBeGreaterThan(0);
  });

  it("updateParticles removes dead particles", async () => {
    const { spawnParticle, updateParticles } = await import("@/lib/avatar/particle-system");
    const p = spawnParticle(50, 50, 40);
    p.life = 0.01;
    p.maxLife = 0.01;
    const result = updateParticles([p], 50, 50, 1.0, 0.5, 0);
    expect(result.length).toBe(0);
  });

  it("updateParticles keeps alive particles with decreased life", async () => {
    const { spawnParticle, updateParticles } = await import("@/lib/avatar/particle-system");
    const p = spawnParticle(50, 50, 40);
    p.life = 1.0;
    p.maxLife = 10;
    const result = updateParticles([p], 50, 50, 0.016, 0.5, 0);
    expect(result.length).toBe(1);
    expect(result[0].life).toBeLessThan(1.0);
  });

  it("updateParticles with empty array returns empty", async () => {
    const { updateParticles } = await import("@/lib/avatar/particle-system");
    const result = updateParticles([], 50, 50, 0.016, 0.5, 0);
    expect(result).toEqual([]);
  });

  it("particle position changes after update", async () => {
    const { spawnParticle, updateParticles } = await import("@/lib/avatar/particle-system");
    const p = spawnParticle(50, 50, 40);
    const origX = p.x;
    const origY = p.y;
    p.maxLife = 10;
    updateParticles([p], 50, 50, 0.1, 1.0, 0.5);
    // Position should have changed due to orbital motion
    expect(p.x !== origX || p.y !== origY).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 5) Backward compatibility
// ---------------------------------------------------------------------------
describe("Backward compatibility", () => {
  it("re-export file exports WiiiAvatar and AvatarState from @/lib/avatar", async () => {
    const src = await import("@/components/common/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("WiiiAvatar");
    expect(code).toContain("AvatarState");
    expect(code).toContain("@/lib/avatar");
  });

  it("barrel index exports WiiiAvatar and STATE_CONFIG", async () => {
    const src = await import("@/lib/avatar/index?raw");
    const code = (src as any).default || src;
    expect(code).toContain("WiiiAvatar");
    expect(code).toContain("AvatarState");
    expect(code).toContain("STATE_CONFIG");
  });

  it("all 8 usage sites import from components/common/WiiiAvatar", async () => {
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

// ---------------------------------------------------------------------------
// 6) CSS accessibility
// ---------------------------------------------------------------------------
describe("Avatar CSS accessibility", () => {
  // CSS ?raw imports return [] in Vitest/jsdom — use fs.readFileSync instead
  const cssPath = resolve(__dirname, "../lib/avatar/avatar.css");
  const cssCode = readFileSync(cssPath, "utf-8");

  it("should have prefers-reduced-motion handling", () => {
    expect(cssCode).toContain("prefers-reduced-motion");
  });

  it("should have will-change performance hints", () => {
    expect(cssCode).toContain("will-change");
  });

  it("should have contain property for layout isolation", () => {
    expect(cssCode).toContain("contain:");
  });
});

// ---------------------------------------------------------------------------
// 7) Component source checks
// ---------------------------------------------------------------------------
describe("WiiiAvatar component source", () => {
  it("should be wrapped with memo()", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("memo(WiiiAvatarInner)");
  });

  it("should have 3-tier rendering (tiny/medium/large)", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("tiny");
    expect(code).toContain("canvas");
    expect(code).toContain("<svg");
    expect(code).toContain("<path");
  });

  it("should use IntersectionObserver for visibility pausing", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("IntersectionObserver");
  });

  it("should have frame-time capping at 100ms", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("0.1");
    expect(code).toContain("requestAnimationFrame");
  });

  it("should have unique filter IDs per instance", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("_instanceCounter");
    expect(code).toContain("filterId");
  });

  it("should import avatar.css for styles", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain("avatar.css");
  });
});

// ---------------------------------------------------------------------------
// 8) Sprint 119: Color lerping
// ---------------------------------------------------------------------------
describe("Color lerping (Sprint 119)", () => {
  it("lerpHexColor returns target at t=1", async () => {
    const { lerpHexColor } = await import("@/lib/avatar/use-avatar-animation");
    expect(lerpHexColor("#f97316", "#22c55e", 1)).toBe("#22c55e");
  });

  it("lerpHexColor returns source at t=0", async () => {
    const { lerpHexColor } = await import("@/lib/avatar/use-avatar-animation");
    expect(lerpHexColor("#f97316", "#22c55e", 0)).toBe("#f97316");
  });

  it("lerpHexColor returns identity when from === to", async () => {
    const { lerpHexColor } = await import("@/lib/avatar/use-avatar-animation");
    expect(lerpHexColor("#aabbcc", "#aabbcc", 0.5)).toBe("#aabbcc");
  });

  it("lerpHexColor at t=0.5 returns midpoint color", async () => {
    const { lerpHexColor } = await import("@/lib/avatar/use-avatar-animation");
    // Midpoint between #000000 and #ffffff should be ~#808080
    const mid = lerpHexColor("#000000", "#ffffff", 0.5);
    // Each channel: lerp(0, 255, 0.5) = 128 = 0x80
    expect(mid).toBe("#808080");
  });

  it("lerpHexColor at t=0.5 between orange and green", async () => {
    const { lerpHexColor } = await import("@/lib/avatar/use-avatar-animation");
    const mid = lerpHexColor("#f97316", "#22c55e", 0.5);
    // Should be a valid 7-char hex string
    expect(mid).toMatch(/^#[0-9a-f]{6}$/);
    // Should be different from both endpoints
    expect(mid).not.toBe("#f97316");
    expect(mid).not.toBe("#22c55e");
  });

  it("lerpHexColor handles invalid hex gracefully", async () => {
    const { lerpHexColor } = await import("@/lib/avatar/use-avatar-animation");
    // Non-hex strings should return target (fallback)
    expect(lerpHexColor("not-hex", "#22c55e", 0.5)).toBe("#22c55e");
  });

  it("lerpVisuals now uses color lerping for glowColor", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("lerpHexColor(from.glowColor");
    expect(code).toContain("lerpHexColor(from.indicatorColor");
    expect(code).toContain("lerpHexColor(from.particleColor");
  });
});

// ---------------------------------------------------------------------------
// 9) Sprint 119: Reduced motion support
// ---------------------------------------------------------------------------
describe("Reduced motion support (Sprint 119)", () => {
  it("animation hook checks prefers-reduced-motion via matchMedia", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    expect(code).toContain("prefers-reduced-motion");
    expect(code).toContain("matchMedia");
    expect(code).toContain("prefersReducedMotionRef");
  });

  it("rAF loop has reduced motion early return", async () => {
    const src = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (src as any).default || src;
    // Check that the rAF skips when reduced motion is enabled
    expect(code).toContain("prefersReducedMotionRef.current");
    // The matchMedia listener responds to changes
    expect(code).toContain("addEventListener");
    expect(code).toContain("removeEventListener");
  });

  it("CSS has animation: none for reduced motion", () => {
    const cssPath = resolve(__dirname, "../lib/avatar/avatar.css");
    const css = readFileSync(cssPath, "utf-8");
    expect(css).toContain("animation: none !important");
    expect(css).toContain("transition: none !important");
  });
});

// ---------------------------------------------------------------------------
// 10) Sprint 119: Aria accessibility labels
// ---------------------------------------------------------------------------
describe("Aria accessibility (Sprint 119)", () => {
  it("component has role=img and aria-label", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain('role="img"');
    expect(code).toContain("aria-label={ariaLabel}");
  });

  it("STATE_LABELS has all 6 states with Vietnamese text", async () => {
    const { STATE_LABELS } = await import("@/lib/avatar/WiiiAvatar");
    const states = ["idle", "listening", "thinking", "speaking", "complete", "error"];
    for (const s of states) {
      expect(STATE_LABELS[s as AvatarState]).toBeDefined();
      expect(STATE_LABELS[s as AvatarState]).toContain("Wiii");
    }
  }, 15000);

  it("thinking state label contains 'suy nghi'", async () => {
    const { STATE_LABELS } = await import("@/lib/avatar/WiiiAvatar");
    expect(STATE_LABELS.thinking).toContain("suy ngh");
  });

  it("error state label indicates error", async () => {
    const { STATE_LABELS } = await import("@/lib/avatar/WiiiAvatar");
    expect(STATE_LABELS.error).toContain("lỗi");
  });

  it("SVG element has aria-hidden for decorative content", async () => {
    const src = await import("@/lib/avatar/WiiiAvatar?raw");
    const code = (src as any).default || src;
    expect(code).toContain('aria-hidden="true"');
  });

  it("barrel index exports STATE_LABELS and lerpHexColor", async () => {
    const src = await import("@/lib/avatar/index?raw");
    const code = (src as any).default || src;
    expect(code).toContain("STATE_LABELS");
    expect(code).toContain("lerpHexColor");
  });
});
