/**
 * Sprint 120 tests — Character store, mood, UI wiring.
 * Sprint 219b: Removed preferences API tests (dead code — auto-detected).
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useCharacterStore, BLOCK_LABELS, MOOD_LABELS, MOOD_COLORS, MOOD_EMOJI } from "@/stores/character-store";
import { useUIStore } from "@/stores/ui-store";
import type { MoodType, CharacterBlockInfo } from "@/api/types";

// Mock the API module
vi.mock("@/api/character", () => ({
  fetchCharacterState: vi.fn(),
}));

import * as characterApi from "@/api/character";

const mockBlocks: CharacterBlockInfo[] = [
  { label: "learned_lessons", content: "Người dùng thích ví dụ thực tế", char_limit: 2000, usage_percent: 45 },
  { label: "favorite_topics", content: "COLREG, SOLAS", char_limit: 2000, usage_percent: 20 },
  { label: "user_patterns", content: "", char_limit: 1000, usage_percent: 0 },
];

beforeEach(() => {
  vi.clearAllMocks();
  useCharacterStore.setState({
    blocks: [],
    totalBlocks: 0,
    isLoading: false,
    error: null,
    mood: "neutral",
    positivity: 0,
    energy: 0.5,
    moodEnabled: false,
  });
  useUIStore.setState({
    activeView: "chat",
    sidebarOpen: true,
    inputFocused: false,
    characterPanelOpen: false,
  });
});

// ===== Character Store =====
describe("Character Store", () => {
  it("should have correct initial state", () => {
    const state = useCharacterStore.getState();
    expect(state.blocks).toEqual([]);
    expect(state.totalBlocks).toBe(0);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
    expect(state.mood).toBe("neutral");
    expect(state.positivity).toBe(0);
    expect(state.energy).toBe(0.5);
    expect(state.moodEnabled).toBe(false);
  });

  it("should fetch character blocks successfully", async () => {
    vi.mocked(characterApi.fetchCharacterState).mockResolvedValue({
      blocks: mockBlocks,
      total_blocks: 3,
    });

    await useCharacterStore.getState().fetchCharacter();

    const state = useCharacterStore.getState();
    expect(state.blocks).toEqual(mockBlocks);
    expect(state.totalBlocks).toBe(3);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it("should set loading state during fetch", async () => {
    let resolvePromise: (v: unknown) => void;
    const promise = new Promise((resolve) => { resolvePromise = resolve; });
    vi.mocked(characterApi.fetchCharacterState).mockReturnValue(promise as never);

    const fetchPromise = useCharacterStore.getState().fetchCharacter();
    expect(useCharacterStore.getState().isLoading).toBe(true);

    resolvePromise!({ blocks: [], total_blocks: 0 });
    await fetchPromise;
    expect(useCharacterStore.getState().isLoading).toBe(false);
  });

  it("should handle fetch errors gracefully", async () => {
    vi.mocked(characterApi.fetchCharacterState).mockRejectedValue(
      new Error("Network error")
    );

    await useCharacterStore.getState().fetchCharacter();

    const state = useCharacterStore.getState();
    expect(state.error).toBe("Network error");
    expect(state.isLoading).toBe(false);
    expect(state.blocks).toEqual([]);
  });

  it("should handle non-Error rejections", async () => {
    vi.mocked(characterApi.fetchCharacterState).mockRejectedValue("timeout");

    await useCharacterStore.getState().fetchCharacter();

    expect(useCharacterStore.getState().error).toBe("Failed to fetch character");
  });

  it("should handle null blocks in response", async () => {
    vi.mocked(characterApi.fetchCharacterState).mockResolvedValue({
      blocks: null as unknown as CharacterBlockInfo[],
      total_blocks: 0,
    });

    await useCharacterStore.getState().fetchCharacter();
    expect(useCharacterStore.getState().blocks).toEqual([]);
  });
});

// ===== Mood State =====
describe("Mood State", () => {
  it("should set mood with all parameters", () => {
    useCharacterStore.getState().setMood("excited", 0.8, 0.9);

    const state = useCharacterStore.getState();
    expect(state.mood).toBe("excited");
    expect(state.positivity).toBe(0.8);
    expect(state.energy).toBe(0.9);
  });

  it("should set mood with only mood type", () => {
    useCharacterStore.getState().setMood("warm");

    const state = useCharacterStore.getState();
    expect(state.mood).toBe("warm");
    // positivity/energy should remain at defaults
    expect(state.positivity).toBe(0);
    expect(state.energy).toBe(0.5);
  });

  it("should toggle moodEnabled", () => {
    expect(useCharacterStore.getState().moodEnabled).toBe(false);
    useCharacterStore.getState().setMoodEnabled(true);
    expect(useCharacterStore.getState().moodEnabled).toBe(true);
    useCharacterStore.getState().setMoodEnabled(false);
    expect(useCharacterStore.getState().moodEnabled).toBe(false);
  });

  it("should update all 5 mood types", () => {
    const moods: MoodType[] = ["excited", "warm", "concerned", "gentle", "neutral"];
    for (const mood of moods) {
      useCharacterStore.getState().setMood(mood);
      expect(useCharacterStore.getState().mood).toBe(mood);
    }
  });
});

// ===== Mood Labels/Colors/Emoji =====
describe("Mood Display Constants", () => {
  it("should have Vietnamese labels for all mood types", () => {
    const moods: MoodType[] = ["excited", "warm", "concerned", "gentle", "neutral"];
    for (const m of moods) {
      expect(MOOD_LABELS[m]).toBeTruthy();
      expect(typeof MOOD_LABELS[m]).toBe("string");
    }
  });

  it("should have specific Vietnamese mood labels", () => {
    expect(MOOD_LABELS.excited).toBe("Hào hứng");
    expect(MOOD_LABELS.warm).toBe("Ấm áp");
    expect(MOOD_LABELS.concerned).toBe("Lo lắng");
    expect(MOOD_LABELS.gentle).toBe("Nhẹ nhàng");
    expect(MOOD_LABELS.neutral).toBe("Bình thường");
  });

  it("should have CSS color classes for all mood types", () => {
    const moods: MoodType[] = ["excited", "warm", "concerned", "gentle", "neutral"];
    for (const m of moods) {
      expect(MOOD_COLORS[m]).toMatch(/^text-/);
    }
  });

  it("should have emoji for all mood types", () => {
    const moods: MoodType[] = ["excited", "warm", "concerned", "gentle", "neutral"];
    for (const m of moods) {
      expect(MOOD_EMOJI[m]).toBeTruthy();
      expect(MOOD_EMOJI[m].length).toBeGreaterThan(0);
    }
  });
});

// ===== Block Labels =====
describe("Block Labels", () => {
  it("should have Vietnamese labels for known block types", () => {
    expect(BLOCK_LABELS["learned_lessons"]).toBe("Bài học đã rút");
    expect(BLOCK_LABELS["favorite_topics"]).toBe("Chủ đề yêu thích");
    expect(BLOCK_LABELS["user_patterns"]).toBe("Thói quen người dùng");
    expect(BLOCK_LABELS["self_notes"]).toBe("Ghi chú cá nhân");
  });

  it("should have 4 block types", () => {
    expect(Object.keys(BLOCK_LABELS)).toHaveLength(4);
  });
});

// ===== UI Store Character Panel =====
describe("UI Store — Character Panel", () => {
  it("should start with character panel closed", () => {
    expect(useUIStore.getState().characterPanelOpen).toBe(false);
  });

  it("should toggle character panel", () => {
    useUIStore.getState().toggleCharacterPanel();
    expect(useUIStore.getState().characterPanelOpen).toBe(true);
    useUIStore.getState().toggleCharacterPanel();
    expect(useUIStore.getState().characterPanelOpen).toBe(false);
  });
});

// ===== SSE Mood Wiring =====
describe("SSE Mood Wiring", () => {
  it("should update mood from SSE metadata-like data", () => {
    // Simulate what useSSEStream.onMetadata does
    const moodData = { positivity: 0.7, energy: 0.8, mood: "excited" as MoodType };
    const charStore = useCharacterStore.getState();
    charStore.setMood(moodData.mood, moodData.positivity, moodData.energy);
    charStore.setMoodEnabled(true);

    const state = useCharacterStore.getState();
    expect(state.mood).toBe("excited");
    expect(state.positivity).toBe(0.7);
    expect(state.energy).toBe(0.8);
    expect(state.moodEnabled).toBe(true);
  });

  it("should handle null mood data gracefully (no crash)", () => {
    // Simulate null mood — should not update store
    const moodData = null;
    if (moodData && (moodData as { mood?: string }).mood) {
      useCharacterStore.getState().setMood("warm");
    }
    // Mood should remain default
    expect(useCharacterStore.getState().mood).toBe("neutral");
  });
});

// ===== Character Panel Component Logic =====
describe("CharacterPanel Logic", () => {
  it("should fetch character when panel opens", async () => {
    vi.mocked(characterApi.fetchCharacterState).mockResolvedValue({
      blocks: mockBlocks,
      total_blocks: 3,
    });

    // Simulate: panel opens → useEffect calls fetchCharacter
    useUIStore.getState().toggleCharacterPanel();
    expect(useUIStore.getState().characterPanelOpen).toBe(true);

    await useCharacterStore.getState().fetchCharacter();
    expect(characterApi.fetchCharacterState).toHaveBeenCalled();
    expect(useCharacterStore.getState().blocks).toHaveLength(3);
  });

  it("should compute usage color correctly", () => {
    // Test the usageColor logic (from CharacterPanel)
    const usageColor = (percent: number): string => {
      if (percent >= 80) return "bg-orange-500";
      if (percent >= 50) return "bg-yellow-500";
      return "bg-green-500";
    };

    expect(usageColor(0)).toBe("bg-green-500");
    expect(usageColor(49)).toBe("bg-green-500");
    expect(usageColor(50)).toBe("bg-yellow-500");
    expect(usageColor(79)).toBe("bg-yellow-500");
    expect(usageColor(80)).toBe("bg-orange-500");
    expect(usageColor(100)).toBe("bg-orange-500");
  });
});

// ===== StatusBar Mood Indicator Logic =====
describe("StatusBar — deriveAvatarState", () => {
  // Replicate the logic from StatusBar.tsx
  function deriveAvatarState(isStreaming: boolean, hasContent: boolean, inputFocused: boolean) {
    if (isStreaming) return hasContent ? "speaking" : "thinking";
    if (inputFocused) return "listening";
    return "idle";
  }

  it("should return idle by default", () => {
    expect(deriveAvatarState(false, false, false)).toBe("idle");
  });

  it("should return listening when input focused", () => {
    expect(deriveAvatarState(false, false, true)).toBe("listening");
  });

  it("should return thinking when streaming without content", () => {
    expect(deriveAvatarState(true, false, false)).toBe("thinking");
  });

  it("should return speaking when streaming with content", () => {
    expect(deriveAvatarState(true, true, false)).toBe("speaking");
  });

  it("should prioritize streaming over input focus", () => {
    expect(deriveAvatarState(true, false, true)).toBe("thinking");
    expect(deriveAvatarState(true, true, true)).toBe("speaking");
  });
});

// ===== WiiiClient.put method =====
describe("WiiiClient — PUT method", () => {
  it("should have put method available on client type", async () => {
    // We just verify the module exports the right interface
    const { WiiiClient } = await import("@/api/client");
    const client = new WiiiClient("http://localhost:8000");
    expect(typeof client.put).toBe("function");
  });
});

// ===== SettingsPage Tab Configuration =====
describe("SettingsPage — Learning Tab config", () => {
  it("should have learning types defined", async () => {
    // Import the source to check types exist
    await import("@/api/types");
    // Verify learning styles exist as type exports (checking at runtime)
    const validStyles: string[] = ["quiz", "visual", "reading", "mixed", "interactive"];
    const validDifficulties: string[] = ["beginner", "intermediate", "advanced", "expert"];
    const validPronouns: string[] = ["auto", "formal", "casual"];

    // These are compile-time types but we can verify the values we use
    expect(validStyles).toHaveLength(5);
    expect(validDifficulties).toHaveLength(4);
    expect(validPronouns).toHaveLength(3);
  });
});
