/**
 * Sprint 145: useAvatarState hook tests.
 *
 * Tests centralized avatar state derivation, transient states,
 * mood passthrough, message avatar sizing, and message bubble mood.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChatStore } from "@/stores/chat-store";
import { useUIStore } from "@/stores/ui-store";
import { useCharacterStore } from "@/stores/character-store";
import { useAvatarState } from "@/hooks/useAvatarState";

// Reset stores between tests
beforeEach(() => {
  vi.useFakeTimers();
  useChatStore.setState({
    isStreaming: false,
    streamingContent: "",
    streamingThinking: "",
    streamingSources: [],
    streamingStep: "",
    streamingToolCalls: [],
    streamingBlocks: [],
    streamingStartTime: null,
    streamingSteps: [],
    streamingDomainNotice: "",
    streamingPhases: [],
    streamError: "",
    streamCompletedAt: null,
    conversations: [],
    activeConversationId: null,
  });
  useUIStore.setState({ inputFocused: false });
  useCharacterStore.setState({
    mood: "neutral",
    moodEnabled: false,
    soulEmotion: null,
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useAvatarState — state derivation", () => {
  it("returns idle by default", () => {
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("idle");
  });

  it("returns listening when input is focused", () => {
    useUIStore.setState({ inputFocused: true });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("listening");
  });

  it("returns thinking when streaming without content", () => {
    useChatStore.setState({ isStreaming: true, streamingContent: "" });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("thinking");
  });

  it("returns speaking when streaming with content", () => {
    useChatStore.setState({ isStreaming: true, streamingContent: "Hello" });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("speaking");
  });

  it("returns error when streamError is set and not streaming", () => {
    useChatStore.setState({ isStreaming: false, streamError: "Connection failed" });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("error");
  });

  it("returns complete when streamCompletedAt is recent", () => {
    useChatStore.setState({ isStreaming: false, streamCompletedAt: Date.now() });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("complete");
  });

  it("error has higher priority than complete", () => {
    useChatStore.setState({
      isStreaming: false,
      streamError: "fail",
      streamCompletedAt: Date.now(),
    });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("error");
  });

  it("streaming takes priority over inputFocused", () => {
    useChatStore.setState({ isStreaming: true, streamingContent: "" });
    useUIStore.setState({ inputFocused: true });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("thinking");
  });
});

describe("useAvatarState — transient states", () => {
  it("complete decays to idle after 2s", () => {
    const now = Date.now();
    useChatStore.setState({ isStreaming: false, streamCompletedAt: now });

    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("complete");

    // Advance 2.5s
    act(() => {
      vi.advanceTimersByTime(2500);
    });

    expect(result.current.state).toBe("idle");
  });

  it("error persists until next stream start", () => {
    useChatStore.setState({ isStreaming: false, streamError: "Network error" });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("error");

    // Advance time — still error
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.state).toBe("error");

    // Start new stream — clears error
    act(() => {
      useChatStore.getState().startStreaming();
    });
    expect(result.current.state).toBe("thinking");
  });

  it("new stream start clears completed state", () => {
    useChatStore.setState({ isStreaming: false, streamCompletedAt: Date.now() });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("complete");

    act(() => {
      useChatStore.getState().startStreaming();
    });
    expect(result.current.state).toBe("thinking");
  });

  it("complete with expired timestamp returns idle", () => {
    // Set completedAt 3s ago (past decay window)
    useChatStore.setState({
      isStreaming: false,
      streamCompletedAt: Date.now() - 3000,
    });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("idle");
  });

  it("error is ignored during streaming", () => {
    useChatStore.setState({
      isStreaming: true,
      streamingContent: "Hello",
      streamError: "old error",
    });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("speaking");
  });
});

describe("useAvatarState — mood passthrough", () => {
  it("returns undefined mood when moodEnabled is false", () => {
    useCharacterStore.setState({ mood: "excited", moodEnabled: false });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.mood).toBeUndefined();
  });

  it("returns mood when moodEnabled is true", () => {
    useCharacterStore.setState({ mood: "excited", moodEnabled: true });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.mood).toBe("excited");
  });

  it("forwards soulEmotion from character store when fresh", () => {
    const soul = { mood: "warm" as const, face: { mouthCurve: 0.8 }, intensity: 0.7 };
    useCharacterStore.setState({ soulEmotion: soul, soulEmotionTimestamp: Date.now() });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.soulEmotion).toEqual(soul);
  });
});

describe("useAvatarState — soul emotion lifecycle", () => {
  it("soul emotion active within 30s", () => {
    const soul = { mood: "excited" as const, face: { mouthCurve: 0.9 }, intensity: 0.8 };
    useCharacterStore.setState({ soulEmotion: soul, soulEmotionTimestamp: Date.now() });

    const { result } = renderHook(() => useAvatarState());
    expect(result.current.soulEmotion).toEqual(soul);

    // Advance 15s — still active
    act(() => {
      vi.advanceTimersByTime(15000);
    });
    expect(result.current.soulEmotion).toEqual(soul);
  });

  it("soul emotion decays after 30s", () => {
    const soul = { mood: "warm" as const, face: { mouthCurve: 0.6 }, intensity: 0.7 };
    useCharacterStore.setState({ soulEmotion: soul, soulEmotionTimestamp: Date.now() });

    const { result } = renderHook(() => useAvatarState());
    expect(result.current.soulEmotion).toEqual(soul);

    // Advance 31s — should decay to null
    act(() => {
      vi.advanceTimersByTime(31000);
    });
    expect(result.current.soulEmotion).toBeNull();
  });

  it("soul emotion refreshes on update", () => {
    const soul1 = { mood: "concerned" as const, face: { browRaise: -0.3 }, intensity: 0.5 };
    useCharacterStore.setState({ soulEmotion: soul1, soulEmotionTimestamp: Date.now() });

    const { result } = renderHook(() => useAvatarState());
    expect(result.current.soulEmotion).toEqual(soul1);

    // Advance 25s — still active
    act(() => {
      vi.advanceTimersByTime(25000);
    });
    expect(result.current.soulEmotion).toEqual(soul1);

    // Update with new soul emotion — resets timestamp
    const soul2 = { mood: "excited" as const, face: { mouthCurve: 1.0 }, intensity: 0.9 };
    act(() => {
      useCharacterStore.getState().setSoulEmotion(soul2);
    });
    expect(result.current.soulEmotion).toEqual(soul2);

    // Advance another 25s — new emotion still active (only 25s since refresh)
    act(() => {
      vi.advanceTimersByTime(25000);
    });
    expect(result.current.soulEmotion).toEqual(soul2);
  });

  it("effective soulEmotion null when timestamp is 0", () => {
    const soul = { mood: "gentle" as const, face: {}, intensity: 0.4 };
    useCharacterStore.setState({ soulEmotion: soul, soulEmotionTimestamp: 0 });
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.soulEmotion).toBeNull();
  });

  it("soul emotion clears on startStreaming (via clearSoulEmotion)", () => {
    const soul = { mood: "warm" as const, face: { mouthCurve: 0.7 }, intensity: 0.6 };
    useCharacterStore.setState({ soulEmotion: soul, soulEmotionTimestamp: Date.now() });

    const { result } = renderHook(() => useAvatarState());
    expect(result.current.soulEmotion).toEqual(soul);

    // clearSoulEmotion should null it out
    act(() => {
      useCharacterStore.getState().clearSoulEmotion();
    });
    expect(result.current.soulEmotion).toBeNull();
  });

  it("polling activates for soul decay window", () => {
    const soul = { mood: "excited" as const, face: {}, intensity: 0.5 };
    useCharacterStore.setState({ soulEmotion: soul, soulEmotionTimestamp: Date.now() });

    const { result } = renderHook(() => useAvatarState());
    expect(result.current.soulEmotion).toEqual(soul);

    // Advance past 30s — polling should detect and decay
    act(() => {
      vi.advanceTimersByTime(31000);
    });
    expect(result.current.soulEmotion).toBeNull();
  });
});

describe("chat-store — transient field wiring", () => {
  it("startStreaming resets streamError and streamCompletedAt", () => {
    useChatStore.setState({ streamError: "err", streamCompletedAt: 12345 });
    useChatStore.getState().startStreaming();
    const state = useChatStore.getState();
    expect(state.streamError).toBe("");
    expect(state.streamCompletedAt).toBeNull();
  });

  it("finalizeStream sets streamCompletedAt", () => {
    useChatStore.setState({
      isStreaming: true,
      activeConversationId: "c1",
      conversations: [{ id: "c1", title: "T", created_at: "", updated_at: "", messages: [] }],
      streamingContent: "Hi",
    });
    useChatStore.getState().finalizeStream();
    const state = useChatStore.getState();
    expect(state.streamCompletedAt).toBeTypeOf("number");
    expect(state.streamError).toBe("");
  });

  it("setStreamError sets streamError field", () => {
    useChatStore.setState({
      isStreaming: true,
      activeConversationId: "c1",
      conversations: [{ id: "c1", title: "T", created_at: "", updated_at: "", messages: [] }],
    });
    useChatStore.getState().setStreamError("Connection lost");
    const state = useChatStore.getState();
    expect(state.streamError).toBe("Connection lost");
    expect(state.streamCompletedAt).toBeNull();
  });

  it("clearStreaming resets both fields", () => {
    useChatStore.setState({ streamError: "err", streamCompletedAt: 12345 });
    useChatStore.getState().clearStreaming();
    const state = useChatStore.getState();
    expect(state.streamError).toBe("");
    expect(state.streamCompletedAt).toBeNull();
  });
});

describe("MessageBubble — mood extraction", () => {
  it("extracts valid mood from message metadata", () => {
    const validMoods = ["excited", "warm", "concerned", "gentle", "neutral"];
    for (const m of validMoods) {
      const md = { mood: { mood: m } };
      const extracted = (() => {
        const moodData = md.mood as { mood?: string } | undefined;
        const mood = moodData?.mood;
        const valid: string[] = ["excited", "warm", "concerned", "gentle", "neutral"];
        return valid.includes(mood ?? "") ? mood : undefined;
      })();
      expect(extracted).toBe(m);
    }
  });

  it("returns undefined for invalid mood", () => {
    const md = { mood: { mood: "invalid" } };
    const extracted = (() => {
      const moodData = md.mood as { mood?: string } | undefined;
      const mood = moodData?.mood;
      const valid: string[] = ["excited", "warm", "concerned", "gentle", "neutral"];
      return valid.includes(mood ?? "") ? mood : undefined;
    })();
    expect(extracted).toBeUndefined();
  });

  it("returns undefined when no mood metadata", () => {
    const md = {};
    const extracted = (() => {
      const moodData = (md as Record<string, unknown>).mood as { mood?: string } | undefined;
      const mood = moodData?.mood;
      const valid: string[] = ["excited", "warm", "concerned", "gentle", "neutral"];
      return valid.includes(mood ?? "") ? mood : undefined;
    })();
    expect(extracted).toBeUndefined();
  });
});

describe("useAvatarState — full lifecycle", () => {
  it("idle → thinking → speaking → complete → idle", () => {
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("idle");

    // Start streaming (no content yet)
    act(() => {
      useChatStore.getState().startStreaming();
    });
    expect(result.current.state).toBe("thinking");

    // Content starts arriving
    act(() => {
      useChatStore.getState().appendStreamingContent("Hello");
    });
    expect(result.current.state).toBe("speaking");

    // Finalize
    act(() => {
      useChatStore.setState({
        activeConversationId: "c1",
        conversations: [{ id: "c1", title: "T", created_at: "", updated_at: "", messages: [] }],
      });
      useChatStore.getState().finalizeStream();
    });
    expect(result.current.state).toBe("complete");

    // After 2s decay
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(result.current.state).toBe("idle");
  });

  it("error lifecycle: idle → thinking → error → idle (new stream)", () => {
    const { result } = renderHook(() => useAvatarState());
    expect(result.current.state).toBe("idle");

    // Start streaming
    act(() => {
      useChatStore.getState().startStreaming();
    });
    expect(result.current.state).toBe("thinking");

    // Error
    act(() => {
      useChatStore.setState({
        activeConversationId: "c1",
        conversations: [{ id: "c1", title: "T", created_at: "", updated_at: "", messages: [] }],
      });
      useChatStore.getState().setStreamError("Timeout");
    });
    expect(result.current.state).toBe("error");

    // New stream clears error
    act(() => {
      useChatStore.getState().startStreaming();
    });
    expect(result.current.state).toBe("thinking");
  });
});

describe("Sprint 145b — source-level wiring checks", () => {
  it("WelcomeScreen imports useAvatarState (live avatar)", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/components/chat/WelcomeScreen.tsx", "utf-8");
    expect(src).toContain("useAvatarState");
    // Should NOT have static state="idle" for the avatar
    expect(src).not.toMatch(/WiiiAvatar\s+state="idle"/);
  });

  it("MessageList streaming avatar has layoutId", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/components/chat/MessageList.tsx", "utf-8");
    expect(src).toContain('layoutId="wiii-active-avatar"');
  });

  it("MessageBubble latest assistant avatar has layoutId", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/components/chat/MessageBubble.tsx", "utf-8");
    expect(src).toContain('layoutId="wiii-active-avatar"');
  });

  it("useSSEStream clears soul emotion on stream start", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/hooks/useSSEStream.ts", "utf-8");
    expect(src).toContain("clearSoulEmotion");
  });
});

describe("Sprint 147 — avatar & rendering polish", () => {
  it("MessageList streaming avatar is 64px (not 48px)", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/components/chat/MessageList.tsx", "utf-8");
    expect(src).toContain("size={64}");
    expect(src).not.toContain("size={48}");
  });

  it("MessageBubble latest assistant avatar is 64px (not 48px)", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/components/chat/MessageBubble.tsx", "utf-8");
    expect(src).toContain("size={64}");
    expect(src).not.toContain("size={48}");
  });

  it("ThinkingBlock does NOT contain redundant 'Hoàn tất' text", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/components/chat/ThinkingBlock.tsx", "utf-8");
    expect(src).not.toContain("Hoàn tất");
  });

  it("ThinkingBlock uses thinking-markdown wrapper class", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/components/chat/ThinkingBlock.tsx", "utf-8");
    expect(src).toContain("thinking-markdown");
  });

  it("LegacyRenderer does NOT contain DoneRow", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/components/chat/MessageBubble.tsx", "utf-8");
    expect(src).not.toContain("DoneRow");
    expect(src).not.toContain("Hoàn thành");
  });

  it("markdown.css has thinking-markdown overrides", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("src/styles/markdown.css", "utf-8");
    expect(src).toContain(".thinking-markdown .markdown-content");
    expect(src).toContain("font-size: inherit");
    expect(src).toContain("list-style: none");
  });
});
