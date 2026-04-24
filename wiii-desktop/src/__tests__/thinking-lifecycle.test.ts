/**
 * Sprint 64: Thinking lifecycle (open/close) tests.
 * Tests the openThinkingBlock / closeThinkingBlock store actions
 * and the interplay with SSE event dispatch.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";
import type { ContentBlock, ThinkingBlockData } from "@/api/types";

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
  });
});

/** Helper to get current blocks */
function getBlocks(): ContentBlock[] {
  return useChatStore.getState().streamingBlocks;
}

/** Helper to get thinking block at index */
function thinkingAt(blocks: ContentBlock[], i: number): ThinkingBlockData {
  const b = blocks[i];
  expect(b.type).toBe("thinking");
  return b as ThinkingBlockData;
}

describe("openThinkingBlock", () => {
  it("should create a thinking block with label and startTime", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Phan tich cau hoi");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(1);
    const tb = thinkingAt(blocks, 0);
    expect(tb.label).toBe("Phan tich cau hoi");
    expect(tb.content).toBe("");
    expect(tb.toolCalls).toEqual([]);
    expect(tb.startTime).toBeDefined();
    expect(tb.startTime).toBeGreaterThan(0);
    expect(tb.endTime).toBeUndefined();
  });

  it("should close previous open thinking block when opening new one", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Block 1");
    useChatStore.getState().openThinkingBlock("Block 2");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    // First block should be closed (has endTime)
    const tb1 = thinkingAt(blocks, 0);
    expect(tb1.endTime).toBeDefined();
    expect(tb1.endTime).toBeGreaterThan(0);
    // Second block should be open (no endTime)
    const tb2 = thinkingAt(blocks, 1);
    expect(tb2.endTime).toBeUndefined();
    expect(tb2.label).toBe("Block 2");
  });

  it("should work when no previous blocks exist", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("First block");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("thinking");
  });
});

describe("closeThinkingBlock", () => {
  it("should set endTime on last open thinking block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Test");

    const beforeClose = Date.now();
    useChatStore.getState().closeThinkingBlock();

    const blocks = getBlocks();
    const tb = thinkingAt(blocks, 0);
    expect(tb.endTime).toBeDefined();
    expect(tb.endTime!).toBeGreaterThanOrEqual(beforeClose);
    expect(tb.stepState).toBe("completed");
  });

  // Summary-fallback test removed: the "empty thinking block → show summary"
  // fallback moved from the chat-store to render-time in ThinkingBlock.tsx
  // (search for `summaryMode === "body_fallback"`). The store now only
  // tracks lifecycle state; the view layer is responsible for deciding what
  // to display when content is empty. User-visible behavior unchanged.

  it("should compute endTime from startTime + durationMs when provided", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Test");

    const blocks1 = getBlocks();
    const startTime = thinkingAt(blocks1, 0).startTime!;

    useChatStore.getState().closeThinkingBlock(5000);

    const blocks2 = getBlocks();
    const tb = thinkingAt(blocks2, 0);
    expect(tb.endTime).toBe(startTime + 5000);
  });

  it("should be no-op when no open thinking block exists", () => {
    useChatStore.getState().startStreaming();
    // No blocks at all
    useChatStore.getState().closeThinkingBlock();
    expect(getBlocks()).toHaveLength(0);
  });

  it("should be no-op when last block is answer (not thinking)", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Hello");
    const blocksBefore = getBlocks();
    expect(blocksBefore[blocksBefore.length - 1].type).toBe("answer");

    useChatStore.getState().closeThinkingBlock();
    // Answer block should be unchanged
    expect(getBlocks()).toHaveLength(1);
    expect(getBlocks()[0].type).toBe("answer");
  });

  it("should close the most recent open thinking block even after tool rows arrive", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Test");
    useChatStore.getState().appendToolCall({
      id: "tool-1",
      name: "tool_web_search",
      args: { q: "kimi linear attention" },
      node: "tutor_agent",
    });

    useChatStore.getState().closeThinkingBlock(750);

    const blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    const tb = thinkingAt(blocks, 0);
    expect(tb.endTime).toBe(tb.startTime! + 750);
    expect(tb.stepState).toBe("completed");
    expect(blocks[1].type).toBe("tool_execution");
  });

  it("should be no-op when last thinking block is already closed", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Test");
    useChatStore.getState().closeThinkingBlock(3000);

    const endTimeBefore = thinkingAt(getBlocks(), 0).endTime;

    // Close again — should not change
    useChatStore.getState().closeThinkingBlock(9999);
    const endTimeAfter = thinkingAt(getBlocks(), 0).endTime;
    expect(endTimeAfter).toBe(endTimeBefore);
  });
});

describe("Full lifecycle sequence", () => {
  it("should handle: open → content → close → open → content → close", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // First thinking block
    store.openThinkingBlock("Phan tich cau hoi");
    useChatStore.getState().setStreamingThinking("Routing to RAG agent");
    useChatStore.getState().closeThinkingBlock(2000);

    // Second thinking block
    useChatStore.getState().openThinkingBlock("Tra cuu tri thuc");
    useChatStore.getState().setStreamingThinking("Searching knowledge base");
    useChatStore.getState().closeThinkingBlock(5000);

    const blocks = getBlocks();
    expect(blocks).toHaveLength(2);

    const tb1 = thinkingAt(blocks, 0);
    expect(tb1.label).toBe("Phan tich cau hoi");
    expect(tb1.content).toContain("Routing to RAG agent");
    expect(tb1.endTime).toBeDefined();

    const tb2 = thinkingAt(blocks, 1);
    expect(tb2.label).toBe("Tra cuu tri thuc");
    expect(tb2.content).toContain("Searching knowledge base");
    expect(tb2.endTime).toBeDefined();
  });

  it("should handle answer after closed thinking block", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // Thinking block
    store.openThinkingBlock("Analysis");
    useChatStore.getState().setStreamingThinking("Working on it");
    useChatStore.getState().closeThinkingBlock(3000);

    // Answer block
    useChatStore.getState().appendStreamingContent("Here is the answer.");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    expect(blocks[0].type).toBe("thinking");
    expect(blocks[1].type).toBe("answer");
    expect((blocks[1] as any).content).toBe("Here is the answer.");
  });

  it("should handle thinking → answer → thinking → answer (interleaved)", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // Phase 1: think
    store.openThinkingBlock("Phase 1");
    useChatStore.getState().setStreamingThinking("Step 1 reasoning");
    useChatStore.getState().closeThinkingBlock(2000);

    // Phase 1: partial answer
    useChatStore.getState().appendStreamingContent("Partial answer...");

    // Phase 2: think again
    useChatStore.getState().openThinkingBlock("Phase 2");
    useChatStore.getState().setStreamingThinking("Step 2 reasoning");
    useChatStore.getState().closeThinkingBlock(3000);

    // Phase 2: final answer
    useChatStore.getState().appendStreamingContent("Final answer.");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(4);
    expect(blocks[0].type).toBe("thinking");
    expect(blocks[1].type).toBe("answer");
    expect(blocks[2].type).toBe("thinking");
    expect(blocks[3].type).toBe("answer");
  });
});

describe("SSE dispatch integration", () => {
  it("should handle complete RAG flow sequence with Vietnamese labels", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // Guardian: start/end only
    useChatStore.getState().openThinkingBlock("Ki\u1EC3m tra an to\u00E0n");
    useChatStore.getState().closeThinkingBlock(100);

    // Supervisor: start, thinking, end
    useChatStore.getState().openThinkingBlock("Ph\u00E2n t\u00EDch c\u00E2u h\u1ECFi");
    useChatStore.getState().setStreamingThinking("Routing to RAG");
    useChatStore.getState().closeThinkingBlock(2000);

    // RAG: tool calls happen outside thinking block, then thinking block
    useChatStore.getState().openThinkingBlock("Tra c\u1EE9u tri th\u1EE9c");
    useChatStore.getState().setStreamingThinking("T\u00ECm th\u1EA5y 3 ngu\u1ED3n");
    useChatStore.getState().closeThinkingBlock(8000);

    // Partial answer from RAG
    useChatStore.getState().appendStreamingContent("C\u00E2u tr\u1EA3 l\u1EDDi l\u00E0...");

    // Grader: start/end
    useChatStore.getState().openThinkingBlock("Ki\u1EC3m tra ch\u1EA5t l\u01B0\u1EE3ng");
    useChatStore.getState().closeThinkingBlock(3000);

    const blocks = getBlocks();
    // Guardian, Supervisor, RAG, Answer, Grader
    expect(blocks).toHaveLength(5);

    const guardian = thinkingAt(blocks, 0);
    expect(guardian.label).toBe("Ki\u1EC3m tra an to\u00E0n");
    expect(guardian.content).toBe("");
    expect(guardian.endTime).toBeDefined();

    const supervisor = thinkingAt(blocks, 1);
    expect(supervisor.label).toBe("Ph\u00E2n t\u00EDch c\u00E2u h\u1ECFi");
    expect(supervisor.endTime).toBeDefined();

    const rag = thinkingAt(blocks, 2);
    expect(rag.label).toBe("Tra c\u1EE9u tri th\u1EE9c");
    expect(rag.endTime).toBeDefined();

    expect(blocks[3].type).toBe("answer");
    expect((blocks[3] as any).content).toBe("C\u00E2u tr\u1EA3 l\u1EDDi l\u00E0...");

    const grader = thinkingAt(blocks, 4);
    expect(grader.label).toBe("Ki\u1EC3m tra ch\u1EA5t l\u01B0\u1EE3ng");
    expect(grader.endTime).toBeDefined();
  });
});
