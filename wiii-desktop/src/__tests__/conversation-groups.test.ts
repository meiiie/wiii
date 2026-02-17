/**
 * Unit tests for conversation grouping logic (Sprint 80).
 * Tests time-based grouping, search filtering, pinned sorting.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  groupConversations,
  DOMAIN_BADGES,
} from "@/lib/conversation-groups";
import type { Conversation } from "@/api/types";

function makeConv(
  overrides: Partial<Conversation> & { id: string }
): Conversation {
  return {
    title: "Test conversation",
    created_at: overrides.updated_at || new Date().toISOString(),
    updated_at: new Date().toISOString(),
    messages: [],
    ...overrides,
  };
}

const NOW = new Date("2026-02-14T12:00:00Z");

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("groupConversations", () => {
  it("should return empty array for no conversations", () => {
    const result = groupConversations([]);
    expect(result).toEqual([]);
  });

  it("should group today's conversations", () => {
    const convs = [
      makeConv({ id: "1", title: "Today chat", updated_at: "2026-02-14T10:00:00Z" }),
    ];

    const groups = groupConversations(convs);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Hôm nay");
    expect(groups[0].conversations).toHaveLength(1);
  });

  it("should group yesterday's conversations", () => {
    const convs = [
      makeConv({ id: "1", title: "Yesterday chat", updated_at: "2026-02-13T15:00:00Z" }),
    ];

    const groups = groupConversations(convs);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Hôm qua");
  });

  it("should group this week's conversations", () => {
    const convs = [
      makeConv({ id: "1", title: "Week chat", updated_at: "2026-02-10T10:00:00Z" }),
    ];

    const groups = groupConversations(convs);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Tuần này");
  });

  it("should group older conversations", () => {
    const convs = [
      makeConv({ id: "1", title: "Old chat", updated_at: "2026-01-01T10:00:00Z" }),
    ];

    const groups = groupConversations(convs);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Cũ hơn");
  });

  it("should put pinned conversations in Ghim group first", () => {
    const convs = [
      makeConv({ id: "1", title: "Normal", updated_at: "2026-02-14T10:00:00Z" }),
      makeConv({
        id: "2",
        title: "Pinned",
        updated_at: "2026-01-01T10:00:00Z",
        pinned: true,
      }),
    ];

    const groups = groupConversations(convs);
    expect(groups[0].label).toBe("Ghim");
    expect(groups[0].conversations[0].id).toBe("2");
    expect(groups[1].label).toBe("Hôm nay");
  });

  it("should create multiple time groups", () => {
    const convs = [
      makeConv({ id: "1", title: "Today", updated_at: "2026-02-14T10:00:00Z" }),
      makeConv({ id: "2", title: "Yesterday", updated_at: "2026-02-13T10:00:00Z" }),
      makeConv({ id: "3", title: "Old", updated_at: "2025-12-01T10:00:00Z" }),
    ];

    const groups = groupConversations(convs);
    expect(groups.length).toBeGreaterThanOrEqual(3);
    const labels = groups.map((g) => g.label);
    expect(labels).toContain("Hôm nay");
    expect(labels).toContain("Hôm qua");
    expect(labels).toContain("Cũ hơn");
  });

  it("should filter by search query (case-insensitive)", () => {
    const convs = [
      makeConv({ id: "1", title: "COLREGs Rule 15", updated_at: "2026-02-14T10:00:00Z" }),
      makeConv({ id: "2", title: "SOLAS Chapter", updated_at: "2026-02-14T09:00:00Z" }),
      makeConv({ id: "3", title: "colregs overview", updated_at: "2026-02-13T10:00:00Z" }),
    ];

    const groups = groupConversations(convs, "colregs");

    const allConvs = groups.flatMap((g) => g.conversations);
    expect(allConvs).toHaveLength(2);
    expect(allConvs.map((c) => c.id)).toContain("1");
    expect(allConvs.map((c) => c.id)).toContain("3");
  });

  it("should return empty groups when search has no match", () => {
    const convs = [
      makeConv({ id: "1", title: "COLREGs", updated_at: "2026-02-14T10:00:00Z" }),
    ];

    const groups = groupConversations(convs, "nonexistent");
    expect(groups).toEqual([]);
  });

  it("should sort conversations within groups by updated_at descending", () => {
    const convs = [
      makeConv({ id: "1", title: "Earlier", updated_at: "2026-02-14T08:00:00Z" }),
      makeConv({ id: "2", title: "Later", updated_at: "2026-02-14T11:00:00Z" }),
    ];

    const groups = groupConversations(convs);
    expect(groups[0].conversations[0].id).toBe("2"); // Later first
    expect(groups[0].conversations[1].id).toBe("1");
  });
});

describe("DOMAIN_BADGES", () => {
  it("should have maritime badge", () => {
    expect(DOMAIN_BADGES.maritime).toBe("HH");
  });

  it("should have traffic_law badge", () => {
    expect(DOMAIN_BADGES.traffic_law).toBe("GT");
  });
});
