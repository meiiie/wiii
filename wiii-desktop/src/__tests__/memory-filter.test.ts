/**
 * Unit tests for memory filtering/search logic (Sprint 105).
 * Tests filter by type, search by value, combined, type counts.
 */
import { describe, it, expect } from "vitest";
import { FACT_TYPE_LABELS } from "@/stores/memory-store";
import type { MemoryItem } from "@/api/types";

// Pure filtering logic extracted for testing (mirrors MemoryTab useMemo)
function filterMemories(
  memories: MemoryItem[],
  filterType: string | null,
  searchQuery: string
): MemoryItem[] {
  let result = memories;
  if (filterType) {
    result = result.filter((m) => m.type === filterType);
  }
  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    result = result.filter(
      (m) =>
        m.value.toLowerCase().includes(q) ||
        (FACT_TYPE_LABELS[m.type] || m.type).toLowerCase().includes(q)
    );
  }
  return result;
}

function computeTypeCounts(memories: MemoryItem[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const mem of memories) {
    counts[mem.type] = (counts[mem.type] || 0) + 1;
  }
  return counts;
}

const mockMemories: MemoryItem[] = [
  { id: "m1", type: "name", value: "Minh", created_at: "2026-02-14T08:00:00Z" },
  { id: "m2", type: "age", value: "25 tuoi", created_at: "2026-02-10T08:00:00Z" },
  { id: "m3", type: "goal", value: "Hoc COLREGs", created_at: "2026-02-12T08:00:00Z" },
  { id: "m4", type: "goal", value: "Thi chung chi hang hai", created_at: "2026-02-13T08:00:00Z" },
  { id: "m5", type: "location", value: "Hai Phong", created_at: "2026-02-11T08:00:00Z" },
  { id: "m6", type: "name", value: "Nguyen Van Minh", created_at: "2026-02-15T08:00:00Z" },
  { id: "m7", type: "hobby", value: "Doc sach", created_at: "2026-02-09T08:00:00Z" },
];

describe("Memory Filter — By Type", () => {
  it("should return all when filterType is null", () => {
    const result = filterMemories(mockMemories, null, "");
    expect(result).toHaveLength(7);
  });

  it("should filter by 'name' type", () => {
    const result = filterMemories(mockMemories, "name", "");
    expect(result).toHaveLength(2);
    expect(result.every((m) => m.type === "name")).toBe(true);
  });

  it("should filter by 'goal' type", () => {
    const result = filterMemories(mockMemories, "goal", "");
    expect(result).toHaveLength(2);
    expect(result.every((m) => m.type === "goal")).toBe(true);
  });

  it("should return empty for non-existent type", () => {
    const result = filterMemories(mockMemories, "emotion", "");
    expect(result).toHaveLength(0);
  });

  it("should filter by 'hobby' type (single item)", () => {
    const result = filterMemories(mockMemories, "hobby", "");
    expect(result).toHaveLength(1);
    expect(result[0].value).toBe("Doc sach");
  });
});

describe("Memory Filter — By Search Query", () => {
  it("should search by value (case-insensitive)", () => {
    const result = filterMemories(mockMemories, null, "minh");
    expect(result).toHaveLength(2);
    expect(result[0].value).toBe("Minh");
    expect(result[1].value).toBe("Nguyen Van Minh");
  });

  it("should search by value with uppercase query", () => {
    const result = filterMemories(mockMemories, null, "COLREGS");
    expect(result).toHaveLength(1);
    expect(result[0].value).toBe("Hoc COLREGs");
  });

  it("should search matching type label", () => {
    // FACT_TYPE_LABELS["hobby"] = "Sở thích"
    const result = filterMemories(mockMemories, null, "sở thích");
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("hobby");
  });

  it("should return empty for no match", () => {
    const result = filterMemories(mockMemories, null, "xyznonexistent");
    expect(result).toHaveLength(0);
  });

  it("should handle whitespace-only search as show all", () => {
    const result = filterMemories(mockMemories, null, "   ");
    expect(result).toHaveLength(7);
  });

  it("should match partial value", () => {
    const result = filterMemories(mockMemories, null, "hang hai");
    expect(result).toHaveLength(1);
    expect(result[0].value).toBe("Thi chung chi hang hai");
  });
});

describe("Memory Filter — Combined Type + Search", () => {
  it("should apply both type filter and search", () => {
    const result = filterMemories(mockMemories, "goal", "colregs");
    expect(result).toHaveLength(1);
    expect(result[0].value).toBe("Hoc COLREGs");
  });

  it("should return empty when type matches but search does not", () => {
    const result = filterMemories(mockMemories, "name", "colregs");
    expect(result).toHaveLength(0);
  });

  it("should return empty when search matches but type does not", () => {
    const result = filterMemories(mockMemories, "age", "minh");
    expect(result).toHaveLength(0);
  });
});

describe("Memory Filter — Type Counts", () => {
  it("should compute correct type counts", () => {
    const counts = computeTypeCounts(mockMemories);
    expect(counts).toEqual({
      name: 2,
      age: 1,
      goal: 2,
      location: 1,
      hobby: 1,
    });
  });

  it("should return empty counts for empty list", () => {
    const counts = computeTypeCounts([]);
    expect(counts).toEqual({});
  });

  it("should count single-type list", () => {
    const singleType: MemoryItem[] = [
      { id: "a", type: "name", value: "A", created_at: "2026-01-01T00:00:00Z" },
      { id: "b", type: "name", value: "B", created_at: "2026-01-01T00:00:00Z" },
    ];
    const counts = computeTypeCounts(singleType);
    expect(counts).toEqual({ name: 2 });
  });
});

describe("Memory Filter — Edge Cases", () => {
  it("should handle empty memories array", () => {
    const result = filterMemories([], "name", "test");
    expect(result).toHaveLength(0);
  });

  it("should handle unknown type in FACT_TYPE_LABELS fallback", () => {
    const withUnknown: MemoryItem[] = [
      { id: "x", type: "custom_type", value: "custom value", created_at: "2026-01-01T00:00:00Z" },
    ];
    // Search by type name when no label exists (falls back to raw type)
    const result = filterMemories(withUnknown, null, "custom_type");
    expect(result).toHaveLength(1);
  });

  it("should filter correctly with special regex chars in search", () => {
    const special: MemoryItem[] = [
      { id: "r1", type: "goal", value: "Learn (advanced) topics", created_at: "2026-01-01T00:00:00Z" },
    ];
    // .includes() is safe from regex issues
    const result = filterMemories(special, null, "(advanced)");
    expect(result).toHaveLength(1);
  });
});
