/**
 * useAvatarState — centralized avatar state derivation.
 * Sprint 145: Single source of truth for avatar state, mood, and soul emotion.
 *
 * State priority:
 * 1. streamError && !isStreaming → "error" (persists until next stream start)
 * 2. streamCompletedAt && (now - completedAt < 2000) && !isStreaming → "complete" (2s decay)
 * 3. isStreaming && streamingContent → "speaking"
 * 4. isStreaming && !streamingContent → "thinking"
 * 5. inputFocused → "listening"
 * 6. Default → "idle"
 */
import { useState, useEffect } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useUIStore } from "@/stores/ui-store";
import { useCharacterStore } from "@/stores/character-store";
import type { AvatarState } from "@/lib/avatar/types";
import type { MoodType } from "@/api/types";
import type { SoulEmotionData } from "@/stores/character-store";

/** Complete decay duration for "complete" state (ms) */
const COMPLETE_DECAY_MS = 2000;
/** Soul emotion auto-decay duration (ms) */
const SOUL_EMOTION_DECAY_MS = 30_000;
export interface AvatarStateResult {
  state: AvatarState;
  mood: MoodType | undefined;
  soulEmotion: SoulEmotionData | null;
}

export function useAvatarState(): AvatarStateResult {
  const isStreaming = useChatStore((s) => s.isStreaming);
  const hasStreamingContent = useChatStore((s) => Boolean(s.streamingContent));
  const streamError = useChatStore((s) => s.streamError);
  const streamCompletedAt = useChatStore((s) => s.streamCompletedAt);
  const inputFocused = useUIStore((s) => s.inputFocused);
  const mood = useCharacterStore((s) => s.mood);
  const moodEnabled = useCharacterStore((s) => s.moodEnabled);
  const soulEmotion = useCharacterStore((s) => s.soulEmotion);
  const soulEmotionTimestamp = useCharacterStore((s) => s.soulEmotionTimestamp);

  const [clockRevision, setClockRevision] = useState(0);
  const now = Date.now();

  // Compute effective soul emotion (null if decayed past 30s)
  const effectiveSoulEmotion = (() => {
    if (!soulEmotion || !soulEmotionTimestamp) return null;
    if (now - soulEmotionTimestamp > SOUL_EMOTION_DECAY_MS) return null;
    return soulEmotion;
  })();

  // Derive state
  const deriveState = (): AvatarState => {
    // 1. Error persists until next stream start
    if (streamError && !isStreaming) return "error";
    // 2. Complete state decays after 2s
    if (streamCompletedAt && !isStreaming) {
      if (now - streamCompletedAt < COMPLETE_DECAY_MS) return "complete";
    }
    // 3. Speaking
    if (isStreaming && hasStreamingContent) return "speaking";
    // 4. Thinking
    if (isStreaming) return "thinking";
    // 5. Listening
    if (inputFocused) return "listening";
    // 6. Default
    return "idle";
  };

  const state = deriveState();

  // Wake once at the next semantic deadline instead of polling the whole chat.
  useEffect(() => {
    const current = Date.now();
    const deadlines = [
      streamCompletedAt && !isStreaming
        ? streamCompletedAt + COMPLETE_DECAY_MS
        : null,
      soulEmotion && soulEmotionTimestamp
        ? soulEmotionTimestamp + SOUL_EMOTION_DECAY_MS
        : null,
    ].filter((deadline): deadline is number => deadline !== null && deadline > current);
    if (deadlines.length === 0) return;
    const delay = Math.max(0, Math.min(...deadlines) - current + 1);
    const timer = setTimeout(() => setClockRevision((value) => value + 1), delay);
    return () => clearTimeout(timer);
  }, [clockRevision, streamCompletedAt, isStreaming, soulEmotion, soulEmotionTimestamp]);

  return {
    state,
    mood: moodEnabled ? mood : undefined,
    soulEmotion: effectiveSoulEmotion,
  };
}
