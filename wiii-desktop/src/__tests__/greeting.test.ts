/**
 * Unit tests for greeting utility.
 * Sprint 82: Time-aware Vietnamese greetings.
 * Sprint 111: Random greeting variants + Wiii subtitles.
 */
import { describe, it, expect } from "vitest";
import { getGreeting, getTimeOfDay, getWiiiSubtitle } from "@/lib/greeting";

describe("getTimeOfDay", () => {
  it("returns morning for hours 5-11", () => {
    expect(getTimeOfDay(5)).toBe("morning");
    expect(getTimeOfDay(8)).toBe("morning");
    expect(getTimeOfDay(11)).toBe("morning");
  });

  it("returns afternoon for hours 12-17", () => {
    expect(getTimeOfDay(12)).toBe("afternoon");
    expect(getTimeOfDay(14)).toBe("afternoon");
    expect(getTimeOfDay(17)).toBe("afternoon");
  });

  it("returns evening for hours 18-23 and 0-4", () => {
    expect(getTimeOfDay(18)).toBe("evening");
    expect(getTimeOfDay(22)).toBe("evening");
    expect(getTimeOfDay(0)).toBe("evening");
    expect(getTimeOfDay(4)).toBe("evening");
  });
});

describe("getGreeting", () => {
  it("returns morning greeting with name and exclamation", () => {
    const result = getGreeting("Minh", 8);
    expect(result).toContain("Minh!");
    expect(result).toMatch(/^.+, Minh!$/);
  });

  it("returns afternoon greeting with name and exclamation", () => {
    const result = getGreeting("Hải", 14);
    expect(result).toContain("Hải!");
  });

  it("returns evening greeting with name and exclamation", () => {
    const result = getGreeting("An", 20);
    expect(result).toContain("An!");
  });

  it("returns greeting without name when displayName is empty", () => {
    const result = getGreeting("", 8);
    expect(result).not.toContain(",");
    expect(result).toMatch(/!$/);
  });

  it("returns greeting without name when displayName is undefined", () => {
    const result = getGreeting(undefined, 14);
    expect(result).not.toContain(",");
    expect(result).toMatch(/!$/);
  });

  it("trims whitespace from displayName", () => {
    const result = getGreeting("  Minh  ", 8);
    expect(result).toContain("Minh!");
    expect(result).not.toContain("  ");
  });

  it("returns greeting without name when displayName is only whitespace", () => {
    const result = getGreeting("   ", 20);
    expect(result).not.toContain(",");
    expect(result).toMatch(/!$/);
  });

  it("uses current hour when hour is not provided", () => {
    const result = getGreeting("Test");
    // Should contain the name with exclamation
    expect(result).toContain("Test!");
  });

  it("handles midnight (hour 0) as evening", () => {
    const result = getGreeting("Lan", 0);
    expect(result).toContain("Lan!");
  });

  it("returns varied greetings (randomness)", () => {
    // Run multiple times to check we get variety (at least covers the first variant)
    const results = new Set<string>();
    for (let i = 0; i < 30; i++) {
      results.add(getGreeting("X", 8));
    }
    // With 3 variants, 30 tries should produce at least 2 different greetings
    expect(results.size).toBeGreaterThanOrEqual(2);
  });
});

describe("getWiiiSubtitle", () => {
  it("returns a non-empty string", () => {
    const result = getWiiiSubtitle();
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("returns varied subtitles (randomness)", () => {
    const results = new Set<string>();
    for (let i = 0; i < 30; i++) {
      results.add(getWiiiSubtitle());
    }
    // With 5 variants, 30 tries should produce at least 2 unique
    expect(results.size).toBeGreaterThanOrEqual(2);
  });
});
