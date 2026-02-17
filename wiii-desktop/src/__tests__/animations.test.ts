/**
 * Tests for Sprint 104 animation presets and motion integration.
 *
 * Verifies:
 * - All animation presets export correctly with expected shape
 * - Variants have required keys (hidden/visible)
 * - Stagger containers have staggerChildren timing
 * - Spring configs have correct type
 */
import { describe, it, expect } from "vitest";
import {
  messageEntry,
  userMessageEntry,
  aiMessageEntry,
  fadeIn,
  slideDown,
  staggerContainer,
  staggerItem,
  stepEntry,
  stepStagger,
  checkmarkPop,
  sidebarItemEntry,
  pillEntry,
  pillStagger,
} from "@/lib/animations";

describe("Animation Presets — exports", () => {
  it("should export all animation presets", () => {
    expect(messageEntry).toBeDefined();
    expect(userMessageEntry).toBeDefined();
    expect(aiMessageEntry).toBeDefined();
    expect(fadeIn).toBeDefined();
    expect(slideDown).toBeDefined();
    expect(staggerContainer).toBeDefined();
    expect(staggerItem).toBeDefined();
    expect(stepEntry).toBeDefined();
    expect(stepStagger).toBeDefined();
    expect(checkmarkPop).toBeDefined();
    expect(sidebarItemEntry).toBeDefined();
    expect(pillEntry).toBeDefined();
    expect(pillStagger).toBeDefined();
  });
});

describe("Animation Presets — variant shape", () => {
  const presetsWithHiddenVisible = [
    ["messageEntry", messageEntry],
    ["userMessageEntry", userMessageEntry],
    ["aiMessageEntry", aiMessageEntry],
    ["fadeIn", fadeIn],
    ["slideDown", slideDown],
    ["staggerContainer", staggerContainer],
    ["staggerItem", staggerItem],
    ["stepEntry", stepEntry],
    ["stepStagger", stepStagger],
    ["checkmarkPop", checkmarkPop],
    ["sidebarItemEntry", sidebarItemEntry],
    ["pillEntry", pillEntry],
    ["pillStagger", pillStagger],
  ] as const;

  it.each(presetsWithHiddenVisible)(
    "%s should have hidden and visible variants",
    (_name, preset) => {
      expect(preset).toHaveProperty("hidden");
      expect(preset).toHaveProperty("visible");
    }
  );
});

describe("Animation Presets — message directions", () => {
  it("userMessageEntry should slide from right (positive x)", () => {
    const hidden = userMessageEntry.hidden as Record<string, number>;
    expect(hidden.x).toBeGreaterThan(0);
  });

  it("aiMessageEntry should slide from left (negative x)", () => {
    const hidden = aiMessageEntry.hidden as Record<string, number>;
    expect(hidden.x).toBeLessThan(0);
  });

  it("messageEntry should slide from below (positive y)", () => {
    const hidden = messageEntry.hidden as Record<string, number>;
    expect(hidden.y).toBeGreaterThan(0);
  });
});

describe("Animation Presets — stagger timing", () => {
  it("staggerContainer should have staggerChildren", () => {
    const visible = staggerContainer.visible as Record<string, unknown>;
    const transition = visible.transition as Record<string, number>;
    expect(transition.staggerChildren).toBeDefined();
    expect(transition.staggerChildren).toBeGreaterThan(0);
  });

  it("pillStagger should have 50ms stagger", () => {
    const visible = pillStagger.visible as Record<string, unknown>;
    const transition = visible.transition as Record<string, number>;
    expect(transition.staggerChildren).toBe(0.05);
  });

  it("stepStagger should have 100ms stagger", () => {
    const visible = stepStagger.visible as Record<string, unknown>;
    const transition = visible.transition as Record<string, number>;
    expect(transition.staggerChildren).toBe(0.1);
  });
});

describe("Animation Presets — spring config", () => {
  it("checkmarkPop should use spring transition", () => {
    const visible = checkmarkPop.visible as Record<string, unknown>;
    const transition = visible.transition as Record<string, unknown>;
    expect(transition.type).toBe("spring");
    expect(transition.stiffness).toBeDefined();
    expect(transition.damping).toBeDefined();
  });
});

describe("Animation Presets — exit variants", () => {
  it("slideDown should have exit variant", () => {
    expect(slideDown).toHaveProperty("exit");
  });

  it("sidebarItemEntry should have exit variant", () => {
    expect(sidebarItemEntry).toHaveProperty("exit");
  });
});

describe("Animation Presets — opacity values", () => {
  it("all hidden variants should start with opacity 0", () => {
    const presets = [
      messageEntry,
      userMessageEntry,
      aiMessageEntry,
      fadeIn,
      slideDown,
      staggerItem,
      stepEntry,
      sidebarItemEntry,
      pillEntry,
    ];
    for (const preset of presets) {
      const hidden = preset.hidden as Record<string, number>;
      expect(hidden.opacity).toBe(0);
    }
  });

  it("all visible variants should end with opacity 1", () => {
    const presets = [
      messageEntry,
      userMessageEntry,
      aiMessageEntry,
      fadeIn,
      staggerItem,
      stepEntry,
      sidebarItemEntry,
      pillEntry,
    ];
    for (const preset of presets) {
      const visible = preset.visible as Record<string, number>;
      expect(visible.opacity).toBe(1);
    }
  });
});
