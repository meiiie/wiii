/**
 * Character store — Wiii personality state + mood.
 * Sprint 120: Exposes character blocks and emotional state to UI.
 */
import { create } from "zustand";
import { fetchCharacterState } from "@/api/character";
import type {
  CharacterBlockInfo,
  MoodType,
} from "@/api/types";

/** Vietnamese labels for character block types. */
export const BLOCK_LABELS: Record<string, string> = {
  learned_lessons: "Bài học đã rút",
  favorite_topics: "Chủ đề yêu thích",
  user_patterns: "Thói quen người dùng",
  self_notes: "Ghi chú cá nhân",
};

/** Vietnamese labels for mood states. */
export const MOOD_LABELS: Record<MoodType, string> = {
  excited: "Hào hứng",
  warm: "Ấm áp",
  concerned: "Lo lắng",
  gentle: "Nhẹ nhàng",
  neutral: "Bình thường",
};

/** Mood color mappings for UI. */
export const MOOD_COLORS: Record<MoodType, string> = {
  excited: "text-green-500",
  warm: "text-orange-400",
  concerned: "text-blue-500",
  gentle: "text-purple-400",
  neutral: "text-text-tertiary",
};

/** Mood emoji mappings. */
export const MOOD_EMOJI: Record<MoodType, string> = {
  excited: "\u{1F60A}",
  warm: "\u{2728}",
  concerned: "\u{1F914}",
  gentle: "\u{1F60C}",
  neutral: "\u{1F610}",
};

/** Sprint 135: Soul emotion data from LLM inline tag */
export interface SoulEmotionData {
  mood: MoodType;
  face: Partial<Record<string, number>>;
  intensity: number;
}

interface CharacterState {
  blocks: CharacterBlockInfo[];
  totalBlocks: number;
  isLoading: boolean;
  error: string | null;

  // Mood (updated from SSE metadata)
  mood: MoodType;
  positivity: number;
  energy: number;
  moodEnabled: boolean;

  // Sprint 135: Soul emotion (from LLM inline tag)
  soulEmotion: SoulEmotionData | null;
  soulEmotionTimestamp: number;

  // Actions
  fetchCharacter: () => Promise<void>;
  setMood: (mood: MoodType, positivity?: number, energy?: number) => void;
  setMoodEnabled: (enabled: boolean) => void;
  setSoulEmotion: (emotion: SoulEmotionData) => void;
  clearSoulEmotion: () => void;
}

export const useCharacterStore = create<CharacterState>((set) => ({
  blocks: [],
  totalBlocks: 0,
  isLoading: false,
  error: null,
  mood: "neutral",
  positivity: 0,
  energy: 0.5,
  moodEnabled: false,
  soulEmotion: null,
  soulEmotionTimestamp: 0,

  fetchCharacter: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetchCharacterState();
      set({
        blocks: res.blocks ?? [],
        totalBlocks: res.total_blocks ?? 0,
        isLoading: false,
      });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : "Failed to fetch character",
      });
    }
  },

  setMood: (mood, positivity, energy) =>
    set({
      mood,
      ...(positivity !== undefined ? { positivity } : {}),
      ...(energy !== undefined ? { energy } : {}),
    }),

  setMoodEnabled: (enabled) => set({ moodEnabled: enabled }),

  setSoulEmotion: (emotion) => {
    // Validate: must have mood and numeric intensity
    if (!emotion || typeof emotion.intensity !== "number" || !isFinite(emotion.intensity)) {
      return;
    }
    const validMoods = ["excited", "warm", "concerned", "gentle", "neutral"];
    const mood = validMoods.includes(emotion.mood) ? emotion.mood : "neutral";
    set({
      soulEmotion: { ...emotion, mood, intensity: Math.max(0, Math.min(1, emotion.intensity)) },
      soulEmotionTimestamp: Date.now(),
      // Also update mood + enable it for consistency
      mood,
      moodEnabled: true,
    });
  },

  clearSoulEmotion: () =>
    set({ soulEmotion: null, soulEmotionTimestamp: 0 }),
}));
