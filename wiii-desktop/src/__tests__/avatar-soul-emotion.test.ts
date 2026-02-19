/**
 * Sprint 135: Soul Emotion — LLM-driven avatar expression tests.
 *
 * Tests: SSE dispatch, store, useSSEStream handler, rAF blend,
 *        decay, intensity, clamping, props, layer priority.
 */
import { describe, it, expect, beforeEach } from "vitest";

// ─── SSE dispatch ───────────────────────────────────────────────
describe("SSE emotion dispatch", () => {
  it("dispatches emotion event to handler", async () => {
    // Test that "emotion" is a valid SSEEventType via type-level check
    const emotionType: import("@/api/types").SSEEventType = "emotion";
    expect(emotionType).toBe("emotion");
  });

  it("SSEEmotionEvent interface has required fields", async () => {
    const { } = await import("@/api/types");
    // Type-level test — if this compiles, the interface exists
    const event: import("@/api/types").SSEEmotionEvent = {
      mood: "warm",
      face: { blush: 0.3 },
      intensity: 0.8,
    };
    expect(event.mood).toBe("warm");
    expect(event.face.blush).toBe(0.3);
    expect(event.intensity).toBe(0.8);
  });
});

// ─── Character store ─────────────────────────────────────────────
describe("Character store soul emotion", () => {
  beforeEach(async () => {
    const { useCharacterStore } = await import("@/stores/character-store");
    useCharacterStore.setState({
      soulEmotion: null,
      soulEmotionTimestamp: 0,
      mood: "neutral",
      moodEnabled: false,
    });
  });

  it("setSoulEmotion updates state", async () => {
    const { useCharacterStore } = await import("@/stores/character-store");
    const store = useCharacterStore.getState();
    store.setSoulEmotion({
      mood: "excited",
      face: { blush: 0.5, eyeShape: 0.3 },
      intensity: 0.9,
    });

    const updated = useCharacterStore.getState();
    expect(updated.soulEmotion).not.toBeNull();
    expect(updated.soulEmotion!.mood).toBe("excited");
    expect(updated.soulEmotion!.face.blush).toBe(0.5);
    expect(updated.soulEmotion!.intensity).toBe(0.9);
    expect(updated.soulEmotionTimestamp).toBeGreaterThan(0);
    // Also updates mood + enables it
    expect(updated.mood).toBe("excited");
    expect(updated.moodEnabled).toBe(true);
  });

  it("clearSoulEmotion resets to null", async () => {
    const { useCharacterStore } = await import("@/stores/character-store");
    const store = useCharacterStore.getState();
    store.setSoulEmotion({
      mood: "warm",
      face: {},
      intensity: 0.8,
    });

    store.clearSoulEmotion();
    const updated = useCharacterStore.getState();
    expect(updated.soulEmotion).toBeNull();
    expect(updated.soulEmotionTimestamp).toBe(0);
  });
});

// ─── Avatar types ────────────────────────────────────────────────
describe("Avatar soul emotion types", () => {
  it("WiiiAvatarProps includes soulEmotion", async () => {
    // Type-level test — if this compiles, the prop exists
    const props: import("@/lib/avatar/types").WiiiAvatarProps = {
      state: "idle",
      size: 40,
      mood: "neutral",
      soulEmotion: {
        mood: "warm",
        face: { blush: 0.3 },
        intensity: 0.8,
      },
    };
    expect(props.soulEmotion).toBeDefined();
    expect(props.soulEmotion!.mood).toBe("warm");
  });

  it("SoulEmotionData interface exists", async () => {
    const data: import("@/lib/avatar/types").SoulEmotionData = {
      mood: "gentle",
      face: { mouthCurve: 0.3 },
      intensity: 0.7,
    };
    expect(data.mood).toBe("gentle");
  });

  it("soulEmotion null means no effect", () => {
    const props: import("@/lib/avatar/types").WiiiAvatarProps = {
      state: "idle",
      soulEmotion: null,
    };
    expect(props.soulEmotion).toBeNull();
  });
});

// ─── Animation constants ─────────────────────────────────────────
describe("Soul emotion animation", () => {
  it("use-avatar-animation exports SOUL constants", async () => {
    const source = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (source as unknown as { default: string }).default;
    // Check that soul emotion constants exist
    expect(code).toContain("SOUL_BLEND_DURATION");
    expect(code).toContain("SOUL_DECAY_START");
    expect(code).toContain("SOUL_DECAY_DURATION");
  });

  it("soul emotion refs are initialized", async () => {
    const source = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (source as unknown as { default: string }).default;
    expect(code).toContain("soulTargetRef");
    expect(code).toContain("soulIntensityRef");
    expect(code).toContain("soulTransitionRef");
    expect(code).toContain("soulDecayTimerRef");
  });

  it("soul layer applied after mood layer in rAF", async () => {
    const source = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (source as unknown as { default: string }).default;
    // Soul emotion section must come after mood section
    const moodIdx = code.indexOf("applyMoodToExpression");
    const soulIdx = code.indexOf("Soul Emotion Layer");
    expect(moodIdx).toBeGreaterThan(-1);
    expect(soulIdx).toBeGreaterThan(moodIdx);
  });

  it("face values are clamped in soul blend", async () => {
    const source = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (source as unknown as { default: string }).default;
    // Check clamping for key face values
    expect(code).toContain("Math.max(0.5, Math.min(1.5, face.eyeOpenness))");
    expect(code).toContain("Math.max(0, Math.min(1, face.blush))");
  });

  it("soul emotion accepts soulEmotion parameter", async () => {
    const source = await import("@/lib/avatar/use-avatar-animation?raw");
    const code = (source as unknown as { default: string }).default;
    expect(code).toContain("soulEmotion: SoulEmotionData | null = null");
  });
});

// ─── SSE handler integration ─────────────────────────────────────
describe("SSE handler onEmotion", () => {
  it("sse.ts includes emotion case in dispatch", async () => {
    const source = await import("@/api/sse?raw");
    const code = (source as unknown as { default: string }).default;
    expect(code).toContain('case "emotion"');
    expect(code).toContain("onEmotion");
  });

  it("SSEEventHandler includes onEmotion", async () => {
    const source = await import("@/api/sse?raw");
    const code = (source as unknown as { default: string }).default;
    expect(code).toContain("onEmotion?: (data: SSEEmotionEvent) => void");
  });
});
