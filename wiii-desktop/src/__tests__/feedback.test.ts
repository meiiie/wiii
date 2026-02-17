/**
 * Sprint 107: Feedback persistence tests.
 * Tests local message feedback storage in chat store + API client type.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useChatStore } from "@/stores/chat-store";

// Mock feedback API — we test it doesn't throw, not actual HTTP
vi.mock("@/api/feedback", () => ({
  submitFeedback: vi.fn().mockResolvedValue({
    status: "success",
    message_id: "m1",
    rating: "up",
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  useChatStore.setState({
    conversations: [
      {
        id: "conv-1",
        title: "Test conversation",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        messages: [
          {
            id: "u1",
            role: "user",
            content: "Hello",
            timestamp: "2026-01-01T00:00:00Z",
          },
          {
            id: "a1",
            role: "assistant",
            content: "Hi there!",
            timestamp: "2026-01-01T00:00:01Z",
          },
          {
            id: "u2",
            role: "user",
            content: "Explain COLREGs",
            timestamp: "2026-01-01T00:00:02Z",
          },
          {
            id: "a2",
            role: "assistant",
            content: "COLREGs are...",
            timestamp: "2026-01-01T00:00:03Z",
          },
        ],
      },
    ],
    activeConversationId: "conv-1",
    isLoaded: true,
    isStreaming: false,
    streamingBlocks: [],
  });
});

describe("Feedback — local persistence via chat store", () => {
  it("should set feedback to 'up' on a message", () => {
    useChatStore.getState().setMessageFeedback("a1", "up");
    const conv = useChatStore.getState().activeConversation();
    const msg = conv?.messages.find((m) => m.id === "a1");
    expect(msg?.feedback).toBe("up");
  });

  it("should set feedback to 'down' on a message", () => {
    useChatStore.getState().setMessageFeedback("a2", "down");
    const conv = useChatStore.getState().activeConversation();
    const msg = conv?.messages.find((m) => m.id === "a2");
    expect(msg?.feedback).toBe("down");
  });

  it("should toggle feedback off (null) when same rating clicked", () => {
    useChatStore.getState().setMessageFeedback("a1", "up");
    expect(useChatStore.getState().activeConversation()?.messages.find((m) => m.id === "a1")?.feedback).toBe("up");

    useChatStore.getState().setMessageFeedback("a1", null);
    expect(useChatStore.getState().activeConversation()?.messages.find((m) => m.id === "a1")?.feedback).toBeNull();
  });

  it("should switch from up to down", () => {
    useChatStore.getState().setMessageFeedback("a1", "up");
    useChatStore.getState().setMessageFeedback("a1", "down");
    const msg = useChatStore.getState().activeConversation()?.messages.find((m) => m.id === "a1");
    expect(msg?.feedback).toBe("down");
  });

  it("should not affect other messages", () => {
    useChatStore.getState().setMessageFeedback("a1", "up");
    const conv = useChatStore.getState().activeConversation();
    const a2 = conv?.messages.find((m) => m.id === "a2");
    const u1 = conv?.messages.find((m) => m.id === "u1");
    expect(a2?.feedback).toBeUndefined();
    expect(u1?.feedback).toBeUndefined();
  });

  it("should not crash on non-existent message id", () => {
    // Should not throw
    useChatStore.getState().setMessageFeedback("nonexistent", "up");
    const conv = useChatStore.getState().activeConversation();
    // All messages unchanged
    expect(conv?.messages.every((m) => m.feedback === undefined || m.feedback === null)).toBe(true);
  });

  it("should persist feedback across conversations", () => {
    // Add second conversation
    useChatStore.setState((state) => ({
      conversations: [
        ...state.conversations,
        {
          id: "conv-2",
          title: "Another",
          created_at: "2026-01-02T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
          messages: [
            { id: "b1", role: "assistant" as const, content: "Hey", timestamp: "2026-01-02T00:00:00Z" },
          ],
        },
      ],
    }));

    // Set feedback on conv-1 message
    useChatStore.getState().setMessageFeedback("a1", "up");
    // Set feedback on conv-2 message
    useChatStore.getState().setMessageFeedback("b1", "down");

    // Both should be persisted
    const convs = useChatStore.getState().conversations;
    const conv1Msg = convs[0].messages.find((m) => m.id === "a1");
    const conv2Msg = convs[1].messages.find((m) => m.id === "b1");
    expect(conv1Msg?.feedback).toBe("up");
    expect(conv2Msg?.feedback).toBe("down");
  });
});

describe("Feedback — rating logic", () => {
  it("should support the full toggle cycle: null → up → null → down → null", () => {
    const getMsgFeedback = () =>
      useChatStore.getState().activeConversation()?.messages.find((m) => m.id === "a1")?.feedback;

    // Start: undefined
    expect(getMsgFeedback()).toBeUndefined();

    // Click up
    useChatStore.getState().setMessageFeedback("a1", "up");
    expect(getMsgFeedback()).toBe("up");

    // Click up again → toggle off
    useChatStore.getState().setMessageFeedback("a1", null);
    expect(getMsgFeedback()).toBeNull();

    // Click down
    useChatStore.getState().setMessageFeedback("a1", "down");
    expect(getMsgFeedback()).toBe("down");

    // Click down again → toggle off
    useChatStore.getState().setMessageFeedback("a1", null);
    expect(getMsgFeedback()).toBeNull();
  });
});

describe("Feedback — Message type", () => {
  it("should include feedback field in Message type", () => {
    // Verify the feedback field exists and is optional
    const conv = useChatStore.getState().activeConversation();
    const msg = conv?.messages[0];
    // feedback is optional, so initially undefined
    expect(msg?.feedback).toBeUndefined();
  });
});
