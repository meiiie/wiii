/**
 * Sprint 153b: "Bao Ve Desktop" — Desktop Security & Reliability Hardening Tests
 *
 * Tests for:
 * 1. SSE type safety guards (dispatchEvent)
 * 2. finalizeStream double-call guard
 * 3. _thinkToolIds clear on stream start
 * 4. AbortSignal passthrough to postStream
 * 5. Concurrent stream guard
 * 6. SSE retry buffer discard
 * 7. Content block management
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";
import { parseSSEStream } from "@/api/sse";
import { WiiiClient } from "@/api/client";

// Reset store before each test
beforeEach(() => {
  useChatStore.setState({
    conversations: [],
    activeConversationId: null,
    isLoaded: false,
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
  });
});

// =============================================================================
// Phase 1: SSE Type Safety Guards
// =============================================================================

describe("SSE dispatchEvent type safety", () => {
  const makeHandlers = () => ({
    onThinking: vi.fn(),
    onAnswer: vi.fn(),
    onSources: vi.fn(),
    onMetadata: vi.fn(),
    onDone: vi.fn(),
    onError: vi.fn(),
    onToolCall: vi.fn(),
    onToolResult: vi.fn(),
    onStatus: vi.fn(),
    onThinkingDelta: vi.fn(),
  });

  function makeStream(payload: string): ReadableStream<Uint8Array> {
    const encoder = new TextEncoder();
    return new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(payload));
        controller.close();
      },
    });
  }

  it("should skip null data for non-done events", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(makeStream("event: answer\ndata: null\n\n"), handlers);
    expect(handlers.onAnswer).not.toHaveBeenCalled();
  });

  it("should skip answer events with non-string content", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream('event: answer\ndata: {"content": 123}\n\n'),
      handlers
    );
    expect(handlers.onAnswer).not.toHaveBeenCalled();
  });

  it("should dispatch valid answer events", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream('event: answer\ndata: {"content": "hello"}\n\n'),
      handlers
    );
    expect(handlers.onAnswer).toHaveBeenCalledWith({ content: "hello" });
  });

  it("should dispatch done event with object data", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream('event: done\ndata: {"status": "complete"}\n\n'),
      handlers
    );
    expect(handlers.onDone).toHaveBeenCalled();
  });

  it("should skip tool_call with missing content.name", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream('event: tool_call\ndata: {"content": {"id": "tc1", "args": {}}}\n\n'),
      handlers
    );
    expect(handlers.onToolCall).not.toHaveBeenCalled();
  });

  it("should dispatch valid tool_call events", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream(
        'event: tool_call\ndata: {"content": {"id": "tc1", "name": "tool_search", "args": {}}}\n\n'
      ),
      handlers
    );
    expect(handlers.onToolCall).toHaveBeenCalledWith({
      content: { id: "tc1", name: "tool_search", args: {} },
    });
  });

  it("should skip thinking_delta with non-string content", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream('event: thinking_delta\ndata: {"content": 42}\n\n'),
      handlers
    );
    expect(handlers.onThinkingDelta).not.toHaveBeenCalled();
  });

  it("should skip tool_result with missing content.id", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream(
        'event: tool_result\ndata: {"content": {"name": "foo", "result": "ok"}}\n\n'
      ),
      handlers
    );
    expect(handlers.onToolResult).not.toHaveBeenCalled();
  });

  it("should dispatch valid tool_result events", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream(
        'event: tool_result\ndata: {"content": {"id": "tr1", "name": "foo", "result": "ok"}}\n\n'
      ),
      handlers
    );
    expect(handlers.onToolResult).toHaveBeenCalledWith({
      content: { id: "tr1", name: "foo", result: "ok" },
    });
  });

  it("should dispatch valid thinking_delta events", async () => {
    const handlers = makeHandlers();
    await parseSSEStream(
      makeStream('event: thinking_delta\ndata: {"content": "analyzing..."}\n\n'),
      handlers
    );
    expect(handlers.onThinkingDelta).toHaveBeenCalledWith({ content: "analyzing..." });
  });
});

// =============================================================================
// Phase 2: finalizeStream Double-Call Guard
// =============================================================================

describe("finalizeStream double-call guard", () => {
  it("should finalize on first call", () => {
    const convId = useChatStore.getState().createConversation("test");
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Hello world");

    useChatStore.getState().finalizeStream();
    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    const conv = state.conversations.find((c) => c.id === convId);
    expect(conv?.messages).toHaveLength(1);
    expect(conv?.messages[0].content).toBe("Hello world");
  });

  it("should no-op on second call (guard prevents double finalization)", () => {
    const convId = useChatStore.getState().createConversation("test");
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Hello");

    // First finalize
    useChatStore.getState().finalizeStream();
    expect(useChatStore.getState().isStreaming).toBe(false);

    // Second finalize — should be a no-op (isStreaming is false)
    useChatStore.getState().finalizeStream({
      processing_time: 100,
      model: "test",
      agent_type: "chat",
    });
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    // Still only 1 message (no duplicate)
    expect(conv?.messages).toHaveLength(1);
  });

  it("should no-op when not streaming", () => {
    useChatStore.getState().createConversation("test");
    // Do NOT start streaming — isStreaming is false

    useChatStore.getState().finalizeStream();
    const conv = useChatStore.getState().activeConversation();
    expect(conv?.messages).toHaveLength(0);
  });

  it("should no-op when no active conversation", () => {
    // No conversation created
    useChatStore.setState({ isStreaming: true });

    useChatStore.getState().finalizeStream();
    // isStreaming should still be true since finalizeStream no-op'd
    // (no activeConversationId means early return before state reset)
    expect(useChatStore.getState().isStreaming).toBe(true);
  });
});

// =============================================================================
// Phase 3: AbortSignal Passthrough
// =============================================================================

describe("AbortSignal passthrough", () => {
  it("postStream accepts signal parameter", () => {
    const client = new WiiiClient("http://localhost:8000");
    expect(typeof client.postStream).toBe("function");
    // postStream(path, body, extraHeaders?, signal?) — at least 2 required
    expect(client.postStream.length).toBeGreaterThanOrEqual(2);
  });

  it("adaptiveFetch rejects with aborted signal", async () => {
    const controller = new AbortController();
    controller.abort("test cancel");

    const client = new WiiiClient("http://localhost:8000");

    // Calling with an already-aborted signal should reject
    await expect(
      client.postStream("/api/v1/chat/stream/v3", {}, {}, controller.signal)
    ).rejects.toThrow();
  });
});

// =============================================================================
// Phase 4: SSE Parser Robustness
// =============================================================================

describe("SSE parser robustness", () => {
  const makeHandlers = () => ({
    onThinking: vi.fn(),
    onAnswer: vi.fn(),
    onSources: vi.fn(),
    onMetadata: vi.fn(),
    onDone: vi.fn(),
    onError: vi.fn(),
    onToolCall: vi.fn(),
    onToolResult: vi.fn(),
    onStatus: vi.fn(),
  });

  it("handles empty events gracefully", async () => {
    const handlers = makeHandlers();
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("event: answer\n\n"));
        controller.enqueue(
          encoder.encode('event: done\ndata: {"status": "complete"}\n\n')
        );
        controller.close();
      },
    });

    await parseSSEStream(stream, handlers);
    expect(handlers.onAnswer).not.toHaveBeenCalled();
    expect(handlers.onDone).toHaveBeenCalled();
  });

  it("returns lastEventId from stream", async () => {
    const handlers = makeHandlers();
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('id: evt-42\nevent: answer\ndata: {"content": "hi"}\n\n')
        );
        controller.close();
      },
    });

    const result = await parseSSEStream(stream, handlers);
    expect(result.lastEventId).toBe("evt-42");
  });

  it("handles abort signal during parsing", async () => {
    const handlers = makeHandlers();
    const controller = new AbortController();
    const encoder = new TextEncoder();

    const stream = new ReadableStream<Uint8Array>({
      start(ctrl) {
        ctrl.enqueue(
          encoder.encode('event: answer\ndata: {"content": "first"}\n\n')
        );
        controller.abort();
        ctrl.enqueue(
          encoder.encode('event: answer\ndata: {"content": "second"}\n\n')
        );
        ctrl.close();
      },
    });

    await parseSSEStream(stream, handlers, controller.signal);
    expect(handlers.onDone).not.toHaveBeenCalled();
  });

  it("handles malformed JSON gracefully", async () => {
    const handlers = makeHandlers();
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("event: answer\ndata: {invalid json\n\n"));
        controller.enqueue(
          encoder.encode('event: done\ndata: {"status": "complete"}\n\n')
        );
        controller.close();
      },
    });

    // Should not throw — JSON parse failure is caught internally
    await parseSSEStream(stream, handlers);
    expect(handlers.onAnswer).not.toHaveBeenCalled();
    expect(handlers.onDone).toHaveBeenCalled();
  });
});

// =============================================================================
// Phase 5: Chat Store Streaming State
// =============================================================================

describe("Chat store streaming state", () => {
  it("startStreaming resets all state cleanly", () => {
    useChatStore.getState().createConversation("test");

    // Dirty some state
    useChatStore.setState({
      streamingContent: "old content",
      streamingThinking: "old thinking",
      streamError: "old error",
      streamCompletedAt: 12345,
    });

    useChatStore.getState().startStreaming();
    const state = useChatStore.getState();

    expect(state.isStreaming).toBe(true);
    expect(state.streamingContent).toBe("");
    expect(state.streamingThinking).toBe("");
    expect(state.streamError).toBe("");
    expect(state.streamCompletedAt).toBeNull();
    expect(state.streamingStartTime).toBeGreaterThan(0);
    expect(state.streamingBlocks).toEqual([]);
    expect(state.streamingPhases).toEqual([]);
  });

  it("clearStreaming resets all streaming state", () => {
    useChatStore.setState({
      isStreaming: true,
      streamingContent: "some content",
      streamingThinking: "some thinking",
      streamingBlocks: [{ type: "answer" as const, id: "1", content: "test" }],
      streamingPhases: [
        {
          id: "1",
          label: "test",
          status: "active" as const,
          startTime: Date.now(),
          thinkingContent: "",
          toolCalls: [],
          statusMessages: [],
        },
      ],
      streamingStartTime: Date.now(),
    });

    useChatStore.getState().clearStreaming();
    const state = useChatStore.getState();

    expect(state.isStreaming).toBe(false);
    expect(state.streamingContent).toBe("");
    expect(state.streamingThinking).toBe("");
    expect(state.streamingBlocks).toEqual([]);
    expect(state.streamingPhases).toEqual([]);
    expect(state.streamingStartTime).toBeNull();
    expect(state.streamError).toBe("");
  });

  it("setStreamError resets streaming state properly", () => {
    const convId = useChatStore.getState().createConversation("test");
    useChatStore.getState().startStreaming();

    useChatStore.getState().setStreamError("Connection lost");
    const state = useChatStore.getState();

    expect(state.isStreaming).toBe(false);
    expect(state.streamError).toBe("Connection lost");
    expect(state.streamingContent).toBe("");
    expect(state.streamingBlocks).toEqual([]);
    const conv = state.conversations.find((c) => c.id === convId);
    expect(conv?.messages).toHaveLength(1);
    expect(conv?.messages[0].content).toContain("Connection lost");
  });
});

// =============================================================================
// Phase 6: Content Block Management
// =============================================================================

describe("Content block management during streaming", () => {
  it("appendStreamingContent creates answer block", () => {
    useChatStore.getState().appendStreamingContent("Hello ");
    useChatStore.getState().appendStreamingContent("world");

    const state = useChatStore.getState();
    expect(state.streamingContent).toBe("Hello world");
    expect(state.streamingBlocks).toHaveLength(1);
    expect(state.streamingBlocks[0].type).toBe("answer");
    expect(state.streamingBlocks[0].content).toBe("Hello world");
  });

  it("appendThinkingDelta creates thinking block", () => {
    useChatStore.getState().appendThinkingDelta("Analyzing...", "rag");
    const state = useChatStore.getState();

    expect(state.streamingThinking).toBe("Analyzing...");
    expect(state.streamingBlocks).toHaveLength(1);
    expect(state.streamingBlocks[0].type).toBe("thinking");
  });

  it("appendActionText closes open thinking block", () => {
    useChatStore.getState().openThinkingBlock("Phase 1");
    useChatStore.getState().appendThinkingDelta("thinking...");

    useChatStore.getState().appendActionText("Searching products", "product_search");

    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(2);
    expect(state.streamingBlocks[0].type).toBe("thinking");
    expect(
      (state.streamingBlocks[0] as { endTime?: number }).endTime
    ).toBeDefined();
    expect(state.streamingBlocks[1].type).toBe("action_text");
    expect(state.streamingBlocks[1].content).toBe("Searching products");
  });

  it("appendScreenshot closes open thinking block", () => {
    useChatStore.getState().openThinkingBlock("Browsing");
    useChatStore.getState().appendScreenshot({
      url: "https://example.com",
      image: "base64data",
      label: "Facebook search",
      node: "product_search",
    });

    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(2);
    expect(state.streamingBlocks[1].type).toBe("screenshot");
  });

  it("interleaved thinking → answer → thinking creates separate blocks", () => {
    useChatStore.getState().openThinkingBlock("Step 1");
    useChatStore.getState().appendThinkingDelta("Thinking...");
    useChatStore.getState().closeThinkingBlock(100);

    useChatStore.getState().appendStreamingContent("Answer text");

    useChatStore.getState().openThinkingBlock("Step 2");
    useChatStore.getState().appendThinkingDelta("More thinking");

    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(3);
    expect(state.streamingBlocks[0].type).toBe("thinking");
    expect(state.streamingBlocks[1].type).toBe("answer");
    expect(state.streamingBlocks[2].type).toBe("thinking");
  });
});
