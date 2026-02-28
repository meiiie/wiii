/**
 * Unit tests for memory store (Sprint 80).
 * Tests memory fetching, deletion, clear all.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useMemoryStore, FACT_TYPE_LABELS } from "@/stores/memory-store";

// Mock the API module
vi.mock("@/api/memories", () => ({
  fetchMemories: vi.fn(),
  deleteMemory: vi.fn(),
  clearMemories: vi.fn(),
}));

import * as memoriesApi from "@/api/memories";

const mockMemories = [
  { id: "mem-1", type: "name", value: "Minh", created_at: "2026-02-14T08:00:00Z" },
  { id: "mem-2", type: "age", value: "25", created_at: "2026-02-10T08:00:00Z" },
  { id: "mem-3", type: "goal", value: "Learn COLREGs", created_at: "2026-02-12T08:00:00Z" },
];

beforeEach(() => {
  vi.clearAllMocks();
  useMemoryStore.setState({
    memories: [],
    isLoading: false,
    error: null,
  });
});

describe("Memory Store — Fetch", () => {
  it("should fetch memories successfully", async () => {
    vi.mocked(memoriesApi.fetchMemories).mockResolvedValue({
      data: mockMemories,
      total: 3,
    });

    await useMemoryStore.getState().fetchMemories("user-1");

    const state = useMemoryStore.getState();
    expect(state.memories).toEqual(mockMemories);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it("should handle fetch error", async () => {
    vi.mocked(memoriesApi.fetchMemories).mockRejectedValue(
      new Error("Unauthorized")
    );

    await useMemoryStore.getState().fetchMemories("user-1");

    const state = useMemoryStore.getState();
    expect(state.error).toBe("Unauthorized");
    expect(state.isLoading).toBe(false);
  });

  it("should skip fetch when userId is empty", async () => {
    await useMemoryStore.getState().fetchMemories("");

    expect(memoriesApi.fetchMemories).not.toHaveBeenCalled();
  });
});

describe("Memory Store — Delete", () => {
  it("should delete a single memory optimistically", async () => {
    useMemoryStore.setState({ memories: mockMemories });
    vi.mocked(memoriesApi.deleteMemory).mockResolvedValue({
      success: true,
      message: "Deleted",
    });

    await useMemoryStore.getState().deleteOne("user-1", "mem-2");

    const state = useMemoryStore.getState();
    expect(state.memories).toHaveLength(2);
    expect(state.memories.find((m) => m.id === "mem-2")).toBeUndefined();
    expect(memoriesApi.deleteMemory).toHaveBeenCalledWith("user-1", "mem-2");
  });

  it("should set error on delete failure", async () => {
    useMemoryStore.setState({ memories: mockMemories });
    vi.mocked(memoriesApi.deleteMemory).mockRejectedValue(
      new Error("Not found")
    );

    await useMemoryStore.getState().deleteOne("user-1", "mem-99");

    expect(useMemoryStore.getState().error).toBe("Not found");
  });
});

describe("Memory Store — Clear All", () => {
  it("should clear all memories via bulk endpoint", async () => {
    useMemoryStore.setState({ memories: mockMemories });
    vi.mocked(memoriesApi.clearMemories).mockResolvedValue({
      success: true,
      deleted_count: 3,
      message: "Deleted 3 memories",
    });

    await useMemoryStore.getState().clearAll("user-1");

    const state = useMemoryStore.getState();
    expect(state.memories).toEqual([]);
    expect(memoriesApi.clearMemories).toHaveBeenCalledTimes(1);
    expect(memoriesApi.clearMemories).toHaveBeenCalledWith("user-1");
    // Should NOT call deleteMemory individually
    expect(memoriesApi.deleteMemory).not.toHaveBeenCalled();
  });
});

describe("FACT_TYPE_LABELS", () => {
  it("should have labels for all 16 fact types", () => {
    const expectedTypes = [
      "name", "age", "location", "organization", "role", "level",
      "goal", "preference", "weakness", "strength", "learning_style",
      "hobby", "interest", "emotion", "recent_topic", "pronoun_style",
    ];

    for (const type of expectedTypes) {
      expect(FACT_TYPE_LABELS[type]).toBeDefined();
    }
  });
});
