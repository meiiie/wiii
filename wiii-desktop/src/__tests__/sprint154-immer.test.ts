/**
 * Sprint 154: Immer middleware tests for chat-store.
 *
 * Verifies that the immer-based mutations produce correct state
 * without breaking existing behavior.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";

// Reset store between tests
beforeEach(() => {
  useChatStore.setState({
    conversations: [],
    activeConversationId: null,
    searchQuery: "",
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

describe("Sprint 154: Immer middleware — chat-store", () => {
  // =========================================================================
  // Basic CRUD
  // =========================================================================

  it("createConversation adds conversation and sets active", () => {
    const id = useChatStore.getState().createConversation("maritime");
    const state = useChatStore.getState();
    expect(state.conversations).toHaveLength(1);
    expect(state.activeConversationId).toBe(id);
    expect(state.conversations[0].title).toBe("Cuộc trò chuyện mới");
  });

  it("deleteConversation removes conversation and updates active", () => {
    const id1 = useChatStore.getState().createConversation();
    const id2 = useChatStore.getState().createConversation();
    useChatStore.getState().deleteConversation(id2);
    const state = useChatStore.getState();
    expect(state.conversations).toHaveLength(1);
    expect(state.conversations[0].id).toBe(id1);
  });

  it("renameConversation updates title", () => {
    const id = useChatStore.getState().createConversation();
    useChatStore.getState().renameConversation(id, "New Title");
    const conv = useChatStore.getState().conversations.find((c) => c.id === id);
    expect(conv?.title).toBe("New Title");
  });

  it("pinConversation sets pinned flag", () => {
    const id = useChatStore.getState().createConversation();
    useChatStore.getState().pinConversation(id);
    const conv = useChatStore.getState().conversations.find((c) => c.id === id);
    expect(conv?.pinned).toBe(true);
  });

  it("unpinConversation clears pinned flag", () => {
    const id = useChatStore.getState().createConversation();
    useChatStore.getState().pinConversation(id);
    useChatStore.getState().unpinConversation(id);
    const conv = useChatStore.getState().conversations.find((c) => c.id === id);
    expect(conv?.pinned).toBe(false);
  });

  // =========================================================================
  // Streaming mutations (high-frequency — immer eliminates spread overhead)
  // =========================================================================

  it("appendStreamingContent updates flat field and creates answer block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Hello ");
    useChatStore.getState().appendStreamingContent("World");
    const state = useChatStore.getState();
    expect(state.streamingContent).toBe("Hello World");
    expect(state.streamingBlocks).toHaveLength(1);
    expect(state.streamingBlocks[0].type).toBe("answer");
    expect(state.streamingBlocks[0].content).toBe("Hello World");
  });

  it("appendThinkingDelta updates flat field and creates thinking block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendThinkingDelta("Think ", "rag");
    useChatStore.getState().appendThinkingDelta("more", "rag");
    const state = useChatStore.getState();
    expect(state.streamingThinking).toBe("Think more");
    expect(state.streamingBlocks).toHaveLength(1);
    expect(state.streamingBlocks[0].type).toBe("thinking");
    expect(state.streamingBlocks[0].content).toBe("Think more");
  });

  it("openThinkingBlock closes previous and opens new", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Phase 1");
    useChatStore.getState().appendThinkingDelta("content1");
    useChatStore.getState().openThinkingBlock("Phase 2");
    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(2);
    expect(state.streamingBlocks[0].endTime).toBeDefined();
    expect(state.streamingBlocks[1].endTime).toBeUndefined();
    expect(state.streamingBlocks[1].label).toBe("Phase 2");
  });

  it("closeThinkingBlock sets endTime on last open thinking block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Test");
    useChatStore.getState().closeThinkingBlock(1000);
    const block = useChatStore.getState().streamingBlocks[0];
    expect(block.type).toBe("thinking");
    expect(block.endTime).toBeDefined();
  });

  it("appendToolCall adds to flat field and thinking block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Thinking");
    const tc = { id: "tc1", name: "tool_web_search", args: { query: "test" } };
    useChatStore.getState().appendToolCall(tc);
    const state = useChatStore.getState();
    expect(state.streamingToolCalls).toHaveLength(1);
    expect(state.streamingBlocks[0].type).toBe("thinking");
    expect((state.streamingBlocks[0] as any).toolCalls).toHaveLength(1);
  });

  it("updateToolCallResult updates in both flat and block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Test");
    useChatStore.getState().appendToolCall({ id: "tc1", name: "test", args: {} });
    useChatStore.getState().updateToolCallResult("tc1", "Result data");
    const state = useChatStore.getState();
    expect(state.streamingToolCalls[0].result).toBe("Result data");
  });

  it("appendActionText closes thinking block and adds action_text", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Think");
    useChatStore.getState().appendActionText("Action!", "direct");
    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(2);
    expect(state.streamingBlocks[0].endTime).toBeDefined();
    expect(state.streamingBlocks[1].type).toBe("action_text");
    expect(state.streamingBlocks[1].content).toBe("Action!");
  });

  it("appendScreenshot closes thinking and adds screenshot block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendScreenshot({
      url: "https://example.com",
      image: "base64data",
      label: "Test Screenshot",
    });
    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(1);
    expect(state.streamingBlocks[0].type).toBe("screenshot");
  });

  // =========================================================================
  // Phase actions
  // =========================================================================

  it("addOrUpdatePhase creates new phase and closes previous", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().addOrUpdatePhase("Phase 1", "rag");
    useChatStore.getState().addOrUpdatePhase("Phase 2", "tutor");
    const phases = useChatStore.getState().streamingPhases;
    expect(phases).toHaveLength(2);
    expect(phases[0].status).toBe("completed");
    expect(phases[1].status).toBe("active");
  });

  it("appendPhaseThinkingDelta appends to active phase", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().addOrUpdatePhase("Test", "node");
    useChatStore.getState().appendPhaseThinkingDelta("chunk1");
    useChatStore.getState().appendPhaseThinkingDelta("chunk2");
    const phase = useChatStore.getState().streamingPhases[0];
    expect(phase.thinkingContent).toBe("chunk1chunk2");
  });

  // =========================================================================
  // Finalization
  // =========================================================================

  it("finalizeStream creates assistant message and resets state", () => {
    const id = useChatStore.getState().createConversation();
    useChatStore.getState().addUserMessage("Hello");
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Response text");
    useChatStore.getState().finalizeStream({ session_id: "s1" } as any);
    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    expect(state.streamingContent).toBe("");
    const conv = state.conversations.find((c) => c.id === id);
    expect(conv?.messages).toHaveLength(2);
    expect(conv?.messages[1].role).toBe("assistant");
    expect(conv?.messages[1].content).toBe("Response text");
  });

  it("finalizeStream guard prevents double finalization", () => {
    const id = useChatStore.getState().createConversation();
    useChatStore.getState().addUserMessage("Hi");
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Reply");
    useChatStore.getState().finalizeStream();
    useChatStore.getState().finalizeStream(); // second call should be no-op
    const conv = useChatStore.getState().conversations.find((c) => c.id === id);
    // Should have exactly 2 messages (user + 1 assistant), not 3
    expect(conv?.messages).toHaveLength(2);
  });

  it("setStreamError creates error message", () => {
    const id = useChatStore.getState().createConversation();
    useChatStore.getState().addUserMessage("Test");
    useChatStore.getState().startStreaming();
    useChatStore.getState().setStreamError("Connection failed");
    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    expect(state.streamError).toBe("Connection failed");
  });

  it("clearStreaming resets all streaming state", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("test");
    useChatStore.getState().clearStreaming();
    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    expect(state.streamingContent).toBe("");
    expect(state.streamingBlocks).toHaveLength(0);
  });

  // =========================================================================
  // Message feedback
  // =========================================================================

  it("setMessageFeedback updates message in conversation", () => {
    useChatStore.getState().createConversation();
    const msgId = useChatStore.getState().addUserMessage("Test");
    useChatStore.getState().setMessageFeedback(msgId!, "up");
    const conv = useChatStore.getState().activeConversation();
    expect(conv?.messages[0].feedback).toBe("up");
  });
});
