/**
 * Tests for thinking_delta SSE event — Sprint 69.
 *
 * Tests cover:
 * - SSE dispatch for thinking_delta
 * - appendThinkingDelta chat store action
 * - Block creation and accumulation
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";

// Mock matchMedia for jsdom
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Reset store before each test
beforeEach(() => {
  useChatStore.setState({
    conversations: [
      {
        id: "conv-1",
        title: "Test",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
      },
    ],
    activeConversationId: "conv-1",
    isStreaming: true,
    streamingContent: "",
    streamingThinking: "",
    streamingSources: [],
    streamingStep: "",
    streamingToolCalls: [],
    streamingBlocks: [],
    streamingStartTime: Date.now(),
    streamingSteps: [],
    isLoaded: false,
  });
});

// =============================================================================
// SSE Dispatch
// =============================================================================

describe("thinking_delta SSE dispatch", () => {
  it("dispatches handler for thinking_delta event", async () => {
    // Import the dispatch function
    const { parseSSEStream } = await import("@/api/sse");
    const handler = {
      onThinking: vi.fn(),
      onThinkingDelta: vi.fn(),
      onAnswer: vi.fn(),
      onSources: vi.fn(),
      onMetadata: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
      onToolCall: vi.fn(),
      onToolResult: vi.fn(),
      onStatus: vi.fn(),
    };

    // Create a mock SSE stream with a thinking_delta event
    const sseData = `event: thinking_delta\ndata: {"content":"hello","node":"tutor"}\n\nevent: done\ndata: {"status":"complete"}\n\n`;
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(sseData));
        controller.close();
      },
    });

    await parseSSEStream(stream, handler);

    expect(handler.onThinkingDelta).toHaveBeenCalledWith({
      content: "hello",
      node: "tutor",
    });
    expect(handler.onDone).toHaveBeenCalled();
  });

  it("accumulates multiple thinking_delta events", async () => {
    const { parseSSEStream } = await import("@/api/sse");
    const handler = {
      onThinking: vi.fn(),
      onThinkingDelta: vi.fn(),
      onAnswer: vi.fn(),
      onSources: vi.fn(),
      onMetadata: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
      onToolCall: vi.fn(),
      onToolResult: vi.fn(),
      onStatus: vi.fn(),
    };

    const sseData = [
      'event: thinking_delta\ndata: {"content":"tok1","node":"t"}\n\n',
      'event: thinking_delta\ndata: {"content":"tok2","node":"t"}\n\n',
      'event: done\ndata: {"status":"complete"}\n\n',
    ].join("");

    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(sseData));
        controller.close();
      },
    });

    await parseSSEStream(stream, handler);

    expect(handler.onThinkingDelta).toHaveBeenCalledTimes(2);
  });
});

// =============================================================================
// appendThinkingDelta action
// =============================================================================

describe("appendThinkingDelta action", () => {
  it("appends to flat streamingThinking field", () => {
    const store = useChatStore.getState();
    store.appendThinkingDelta("hello ");
    store.appendThinkingDelta("world");

    const state = useChatStore.getState();
    expect(state.streamingThinking).toBe("hello world");
  });

  it("creates new thinking block if no blocks exist without surfacing the raw node as label", () => {
    const store = useChatStore.getState();
    store.appendThinkingDelta("first token", "tutor_agent");

    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(1);
    expect(state.streamingBlocks[0].type).toBe("thinking");
    if (state.streamingBlocks[0].type === "thinking") {
      expect(state.streamingBlocks[0].content).toBe("first token");
      expect(state.streamingBlocks[0].label).toBeUndefined();
    }
  });

  it("appends to existing open thinking block", () => {
    const store = useChatStore.getState();
    store.appendThinkingDelta("hello ");
    store.appendThinkingDelta("world");

    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(1);
    if (state.streamingBlocks[0].type === "thinking") {
      expect(state.streamingBlocks[0].content).toBe("hello world");
    }
  });

  it("creates new block if last block is answer", () => {
    const store = useChatStore.getState();
    // Add an answer block first
    store.appendStreamingContent("answer text");
    // Now append thinking delta
    store.appendThinkingDelta("thinking...");

    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(2);
    expect(state.streamingBlocks[0].type).toBe("answer");
    expect(state.streamingBlocks[1].type).toBe("thinking");
  });

  it("creates new block if last thinking block is closed", () => {
    const store = useChatStore.getState();
    // Open and close a thinking block
    store.openThinkingBlock("first");
    store.closeThinkingBlock();
    // Now append thinking delta
    store.appendThinkingDelta("new thinking");

    const state = useChatStore.getState();
    // Should have 2 thinking blocks: closed + new open
    const thinkingBlocks = state.streamingBlocks.filter(
      (b) => b.type === "thinking"
    );
    expect(thinkingBlocks.length).toBe(2);
  });

  it("preserves toolCalls on existing block", () => {
    const store = useChatStore.getState();
    // Add a tool call to create a thinking block
    store.appendToolCall({
      id: "tc1",
      name: "search",
      args: {},
      node: "tutor",
    });
    // Append thinking delta to same block
    store.appendThinkingDelta("reasoning...");

    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(2);
    const thinkingBlock = state.streamingBlocks.find((block) => block.type === "thinking");
    const toolStrip = state.streamingBlocks.find((block) => block.type === "tool_execution");
    expect(thinkingBlock?.type).toBe("thinking");
    expect(toolStrip?.type).toBe("tool_execution");
    if (thinkingBlock?.type === "thinking") {
      expect(thinkingBlock.toolCalls).toHaveLength(0);
      expect(thinkingBlock.content).toBe("reasoning...");
    }
  });

  it("does not surface raw node names as thinking labels", () => {
    const store = useChatStore.getState();
    store.appendThinkingDelta("tok", "supervisor");

    const state = useChatStore.getState();
    if (state.streamingBlocks[0].type === "thinking") {
      expect(state.streamingBlocks[0].label).toBeUndefined();
    }
  });

  it("uses streamingStep as fallback label when node is undefined", () => {
    useChatStore.setState({ streamingStep: "routing" });
    const store = useChatStore.getState();
    store.appendThinkingDelta("tok");

    const state = useChatStore.getState();
    if (state.streamingBlocks[0].type === "thinking") {
      expect(state.streamingBlocks[0].label).toBe("routing");
    }
  });

  it("ignores replayed multi-word thinking chunks instead of appending them twice", () => {
    const store = useChatStore.getState();

    store.appendThinkingDelta("Minh dang doi chieu so lieu dau vao.");
    store.appendThinkingDelta("Minh dang doi chieu so lieu dau vao.");

    const state = useChatStore.getState();
    const thinkingBlocks = state.streamingBlocks.filter((block) => block.type === "thinking");
    expect(thinkingBlocks).toHaveLength(1);
    if (thinkingBlocks[0]?.type === "thinking") {
      expect(thinkingBlocks[0].content).toBe("Minh dang doi chieu so lieu dau vao.");
    }
  });

  it("keeps a repeated summary delta out of the visible body text", () => {
    const store = useChatStore.getState();
    store.openThinkingBlock(
      "Bat nhip cau hoi",
      "Doc cau nay, minh thay trong do co mot khoang chung xuong.",
      "direct",
      "attune",
      { stepId: "step-summary" },
      "header_only",
    );

    store.appendThinkingDelta(
      "Doc cau nay, minh thay trong do co mot khoang chung xuong.",
      "direct",
      { stepId: "step-summary" },
    );
    store.closeThinkingBlock();

    const state = useChatStore.getState();
    const thinkingBlocks = state.streamingBlocks.filter((block) => block.type === "thinking");
    expect(thinkingBlocks).toHaveLength(1);
    if (thinkingBlocks[0]?.type === "thinking") {
      expect(thinkingBlocks[0].content).toBe("");
      expect(thinkingBlocks[0].summary).toBe("Doc cau nay, minh thay trong do co mot khoang chung xuong.");
      expect(thinkingBlocks[0].summaryMode).toBe("header_only");
    }
  });

  it("reuses the previous step label instead of leaking raw node names after tool execution", () => {
    const store = useChatStore.getState();
    store.openThinkingBlock("Chuan bi cong cu ve bieu do", "Tom tat", "code_studio_agent", "ground", {
      stepId: "step-1",
    });
    store.closeThinkingBlock();
    store.appendToolCall({
      id: "tool-1",
      name: "tool_execute_python",
      args: {},
      node: "code_studio_agent",
    }, {
      stepId: "step-1",
    });
    store.updateToolCallResult("tool-1", "ok", {
      stepId: "step-1",
    });

    store.appendThinkingDelta("Minh vua xem lai ket qua sau khi chay code.", "code_studio_agent", {
      stepId: "step-1",
    });

    const state = useChatStore.getState();
    const thinkingBlocks = state.streamingBlocks.filter((block) => block.type === "thinking");
    expect(thinkingBlocks).toHaveLength(1);
    if (thinkingBlocks[0]?.type === "thinking") {
      expect(thinkingBlocks[0].label).toBe("Chuan bi cong cu ve bieu do");
      expect(thinkingBlocks[0].summary).toBe("Tom tat");
      expect(thinkingBlocks[0].phase).toBe("ground");
      expect(thinkingBlocks[0].content).toContain("Minh vua xem lai ket qua sau khi chay code.");
    }
  });

  it("keeps post-artifact reflection in the same thinking step", () => {
    const store = useChatStore.getState();
    store.openThinkingBlock("Chuan bi cong cu ve bieu do", "Tom tat", "code_studio_agent", "ground", {
      stepId: "step-1",
    });

    store.addArtifact({
      artifact_id: "artifact-1",
      artifact_type: "chart",
      title: "demo.png",
      content: "base64-data",
      metadata: {},
    }, "code_studio_agent", {
      stepId: "step-1",
    });

    store.appendThinkingDelta("Minh vua xem lai file anh sau khi ve xong.", "code_studio_agent", {
      stepId: "step-1",
    });

    const state = useChatStore.getState();
    const thinkingBlocks = state.streamingBlocks.filter((block) => block.type === "thinking");
    expect(thinkingBlocks).toHaveLength(1);
    if (thinkingBlocks[0]?.type === "thinking") {
      expect(thinkingBlocks[0].content).toContain("Minh vua xem lai file anh sau khi ve xong.");
    }
  });

  it("merges late deltas for a completed step instead of creating a duplicate block", () => {
    const store = useChatStore.getState();
    store.openThinkingBlock("Ban giao hinh anh", "Tom tat", "code_studio_agent", "ground", {
      stepId: "step-2",
    });
    store.appendThinkingDelta("Minh dang chuan bi du lieu. ", "code_studio_agent", {
      stepId: "step-2",
    });
    store.closeThinkingBlock();
    store.appendThinkingDelta("Minh vua xac nhan file anh da tao xong.", "code_studio_agent", {
      stepId: "step-2",
    });

    const state = useChatStore.getState();
    const thinkingBlocks = state.streamingBlocks.filter((block) => block.type === "thinking");
    expect(thinkingBlocks).toHaveLength(1);
    if (thinkingBlocks[0]?.type === "thinking") {
      expect(thinkingBlocks[0].content).toContain("Minh dang chuan bi du lieu.");
      expect(thinkingBlocks[0].content).toContain("Minh vua xac nhan file anh da tao xong.");
      expect(thinkingBlocks[0].stepId).toBe("step-2");
    }
  });
});
