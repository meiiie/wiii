/**
 * Unit tests for Sprint 62 interleaved streaming blocks.
 * Tests the block-building logic in chat-store: ContentBlock[] construction
 * from sequences of thinking/content/tool_call/tool_result events.
 *
 * Covers 4 scenarios from reference (wiii-claude-ux-v5.html):
 *   1. Simple: thinking → tool → answer
 *   2. Multi-step: thinking1(tools) → thinking2(tools) → answer
 *   3. Interleaved: thinking1 → answer1 → thinking2 → answer2
 *   4. Direct: thinking → answer (no tools)
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

/** Helper to get thinking block at index (type-narrowed) */
function thinkingAt(blocks: ContentBlock[], i: number): ThinkingBlockData {
  const b = blocks[i];
  expect(b.type).toBe("thinking");
  return b as ThinkingBlockData;
}

/** Helper to get content from a block (answer or action_text) */
function contentOf(block: ContentBlock): string {
  return (block as unknown as { content: string }).content;
}

describe("Streaming Blocks — startStreaming", () => {
  it("should reset streamingBlocks to empty array", () => {
    // Pollute state first
    useChatStore.setState({
      streamingBlocks: [{ type: "answer", id: "old-1", content: "old" }],
    });

    useChatStore.getState().startStreaming();
    expect(getBlocks()).toEqual([]);
  });
});

describe("Streaming Blocks — Simple Scenario", () => {
  // thinking → tool_call → tool_result → answer
  it("should build blocks: [thinking(+tool), answer]", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // 1. Thinking event
    store.setStreamingThinking("Analyzing the question...");

    let blocks = getBlocks();
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("thinking");
    expect(thinkingAt(blocks, 0).content).toBe("Analyzing the question...");
    expect(thinkingAt(blocks, 0).startTime).toBeGreaterThan(0);
    expect(thinkingAt(blocks, 0).endTime).toBeUndefined();

    // 2. Tool call
    useChatStore.getState().appendToolCall({
      id: "tc-1",
      name: "search_documents",
      args: { query: "COLREGs Rule 15" },
    });

    blocks = getBlocks();
    expect(blocks).toHaveLength(1); // still same thinking block
    expect(thinkingAt(blocks, 0).toolCalls).toHaveLength(1);
    expect(thinkingAt(blocks, 0).toolCalls[0].name).toBe("search_documents");

    // 3. Tool result
    useChatStore.getState().updateToolCallResult("tc-1", "Found 3 documents");

    blocks = getBlocks();
    expect(thinkingAt(blocks, 0).toolCalls[0].result).toBe("Found 3 documents");

    // 4. Answer content
    useChatStore.getState().appendStreamingContent("Rule 15 states that...");

    blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    expect(blocks[0].type).toBe("thinking");
    expect(blocks[1].type).toBe("answer");
    expect(contentOf(blocks[1])).toBe("Rule 15 states that...");

    // Thinking block should now have endTime (closed when answer started)
    expect(thinkingAt(blocks, 0).endTime).toBeGreaterThan(0);
  });
});

describe("Streaming Blocks — Multi-step Deep Scenario", () => {
  // thinking1(tools) → thinking2(tools) → answer
  it("should build blocks: [thinking1(tools), thinking2(tools), answer]", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // Step 1: First thinking with tool
    store.setStreamingStep("Phân tích câu hỏi");
    store.setStreamingThinking("Searching knowledge base...");
    useChatStore.getState().appendToolCall({
      id: "tc-1",
      name: "search_documents",
      args: { query: "SOLAS Chapter II" },
    });
    useChatStore.getState().updateToolCallResult("tc-1", "2 documents found");

    let blocks = getBlocks();
    expect(blocks).toHaveLength(1);
    expect(thinkingAt(blocks, 0).label).toBe("Phân tích câu hỏi");
    expect(thinkingAt(blocks, 0).toolCalls).toHaveLength(1);

    // Step 2: Answer chunk 1 (transitions from thinking to answer)
    useChatStore.getState().appendStreamingContent("SOLAS Chapter II covers ");

    blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    expect(blocks[0].type).toBe("thinking");
    expect(blocks[1].type).toBe("answer");
    // First thinking block should be closed
    expect(thinkingAt(blocks, 0).endTime).toBeGreaterThan(0);

    // Step 3: Second thinking (after an answer block — creates NEW thinking block)
    useChatStore.getState().setStreamingStep("Tra cứu bổ sung");
    useChatStore.getState().setStreamingThinking("Need more details on regulation 10...");

    blocks = getBlocks();
    expect(blocks).toHaveLength(3);
    expect(blocks[2].type).toBe("thinking");
    expect(thinkingAt(blocks, 2).label).toBe("Tra cứu bổ sung");
    expect(thinkingAt(blocks, 2).content).toBe("Need more details on regulation 10...");

    // Step 4: Tool call in second thinking block
    useChatStore.getState().appendToolCall({
      id: "tc-2",
      name: "search_documents",
      args: { query: "SOLAS regulation 10" },
    });

    blocks = getBlocks();
    expect(thinkingAt(blocks, 2).toolCalls).toHaveLength(1);
    expect(thinkingAt(blocks, 2).toolCalls[0].id).toBe("tc-2");

    // Step 5: Final answer
    useChatStore.getState().appendStreamingContent("fire protection measures.");

    blocks = getBlocks();
    expect(blocks).toHaveLength(4);
    expect(blocks[3].type).toBe("answer");
    expect(contentOf(blocks[3])).toBe("fire protection measures.");
    // Second thinking should be closed
    expect(thinkingAt(blocks, 2).endTime).toBeGreaterThan(0);
  });
});

describe("Streaming Blocks — Interleaved Scenario", () => {
  // thinking1 → answer1 → thinking2 → answer2
  it("should build blocks: [thinking, answer, thinking, answer]", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // 1. First thinking
    store.setStreamingThinking("Analyzing question...");

    // 2. First answer chunk
    useChatStore.getState().appendStreamingContent("Initial answer: ");

    // 3. More answer content (appends to same answer block)
    useChatStore.getState().appendStreamingContent("Rule 15 applies when...");

    let blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    expect(blocks[0].type).toBe("thinking");
    expect(blocks[1].type).toBe("answer");
    expect(contentOf(blocks[1])).toBe("Initial answer: Rule 15 applies when...");

    // 4. Second thinking (creates new thinking block after answer)
    useChatStore.getState().setStreamingThinking("Looking up crossing situation...");

    blocks = getBlocks();
    expect(blocks).toHaveLength(3);
    expect(blocks[2].type).toBe("thinking");
    expect(thinkingAt(blocks, 2).content).toBe("Looking up crossing situation...");

    // 5. Second answer chunk
    useChatStore.getState().appendStreamingContent(" In a crossing situation...");

    blocks = getBlocks();
    expect(blocks).toHaveLength(4);
    expect(blocks[0].type).toBe("thinking");
    expect(blocks[1].type).toBe("answer");
    expect(blocks[2].type).toBe("thinking");
    expect(blocks[3].type).toBe("answer");
    expect(contentOf(blocks[3])).toBe(" In a crossing situation...");

    // Verify both thinking blocks are closed
    expect(thinkingAt(blocks, 0).endTime).toBeGreaterThan(0);
    expect(thinkingAt(blocks, 2).endTime).toBeGreaterThan(0);
  });
});

describe("Streaming Blocks — Direct Scenario (no tools)", () => {
  // thinking → answer
  it("should build blocks: [thinking, answer]", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // Thinking only
    store.setStreamingThinking("This is a simple greeting.");

    // Answer
    useChatStore.getState().appendStreamingContent("Xin chào! Tôi là Wiii.");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    expect(blocks[0].type).toBe("thinking");
    expect(thinkingAt(blocks, 0).content).toBe("This is a simple greeting.");
    expect(thinkingAt(blocks, 0).toolCalls).toEqual([]);
    expect(blocks[1].type).toBe("answer");
    expect(contentOf(blocks[1])).toBe("Xin chào! Tôi là Wiii.");
  });
});

describe("Streaming Blocks — Answer only (no thinking)", () => {
  it("should build a single answer block when no thinking events", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().appendStreamingContent("Hello ");
    useChatStore.getState().appendStreamingContent("world!");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("answer");
    expect(contentOf(blocks[0])).toBe("Hello world!");
  });
});

describe("Streaming Blocks — Thinking label and step", () => {
  it("should use streamingStep as label for new thinking block", () => {
    useChatStore.getState().startStreaming();

    // Set step first, then thinking
    useChatStore.getState().setStreamingStep("retrieval");
    useChatStore.getState().setStreamingThinking("Searching...");

    const blocks = getBlocks();
    expect(thinkingAt(blocks, 0).label).toBe("retrieval");
  });

  it("should set label on existing thinking block if it has none", () => {
    useChatStore.getState().startStreaming();

    // Thinking without step
    useChatStore.getState().setStreamingThinking("Starting...");

    let blocks = getBlocks();
    expect(thinkingAt(blocks, 0).label).toBeUndefined();

    // Step arrives after thinking started
    useChatStore.getState().setStreamingStep("analysis");

    blocks = getBlocks();
    expect(thinkingAt(blocks, 0).label).toBe("analysis");
  });

  it("should not overwrite existing label on thinking block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().setStreamingStep("step-1");
    useChatStore.getState().setStreamingThinking("First...");

    // Try to change label
    useChatStore.getState().setStreamingStep("step-2");

    const blocks = getBlocks();
    // Label should remain "step-1" because it was already set
    expect(thinkingAt(blocks, 0).label).toBe("step-1");
  });
});

describe("Streaming Blocks — Consecutive thinking events", () => {
  it("should concatenate thinking content in same block", () => {
    useChatStore.getState().startStreaming();

    useChatStore.getState().setStreamingThinking("Line 1");
    useChatStore.getState().setStreamingThinking("Line 2");
    useChatStore.getState().setStreamingThinking("Line 3");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(1);
    expect(thinkingAt(blocks, 0).content).toBe("Line 1\nLine 2\nLine 3");
  });
});

describe("Streaming Blocks — Consecutive answer events", () => {
  it("should concatenate answer content in same block", () => {
    useChatStore.getState().startStreaming();

    useChatStore.getState().appendStreamingContent("Part 1 ");
    useChatStore.getState().appendStreamingContent("Part 2 ");
    useChatStore.getState().appendStreamingContent("Part 3");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("answer");
    expect(contentOf(blocks[0])).toBe("Part 1 Part 2 Part 3");
  });
});

describe("Streaming Blocks — Tool calls in multiple thinking blocks", () => {
  it("should associate tool calls with correct thinking block", () => {
    useChatStore.getState().startStreaming();

    // Thinking 1 with tool
    useChatStore.getState().setStreamingThinking("First search");
    useChatStore.getState().appendToolCall({
      id: "tc-a",
      name: "search",
      args: { q: "alpha" },
    });

    // Answer (closes thinking 1)
    useChatStore.getState().appendStreamingContent("Partial answer...");

    // Thinking 2 with different tool
    useChatStore.getState().setStreamingThinking("Second search");
    useChatStore.getState().appendToolCall({
      id: "tc-b",
      name: "lookup",
      args: { id: "123" },
    });

    const blocks = getBlocks();
    expect(blocks).toHaveLength(3); // thinking, answer, thinking

    // First thinking has tc-a
    expect(thinkingAt(blocks, 0).toolCalls).toHaveLength(1);
    expect(thinkingAt(blocks, 0).toolCalls[0].id).toBe("tc-a");

    // Second thinking has tc-b
    expect(thinkingAt(blocks, 2).toolCalls).toHaveLength(1);
    expect(thinkingAt(blocks, 2).toolCalls[0].id).toBe("tc-b");
  });

  it("should update tool result in correct block", () => {
    useChatStore.getState().startStreaming();

    // Two thinking blocks with tools
    useChatStore.getState().setStreamingThinking("Search 1");
    useChatStore.getState().appendToolCall({ id: "t1", name: "fn1" });
    useChatStore.getState().appendStreamingContent("partial");
    useChatStore.getState().setStreamingThinking("Search 2");
    useChatStore.getState().appendToolCall({ id: "t2", name: "fn2" });

    // Update result for t1 (in first thinking block)
    useChatStore.getState().updateToolCallResult("t1", "result-1");

    // Update result for t2 (in second thinking block)
    useChatStore.getState().updateToolCallResult("t2", "result-2");

    const blocks = getBlocks();
    expect(thinkingAt(blocks, 0).toolCalls[0].result).toBe("result-1");
    expect(thinkingAt(blocks, 2).toolCalls[0].result).toBe("result-2");
  });
});

describe("Streaming Blocks — Tool call without prior thinking", () => {
  it("should create a thinking block for orphan tool call", () => {
    useChatStore.getState().startStreaming();

    // Tool call arrives before any thinking event
    useChatStore.getState().appendToolCall({
      id: "tc-orphan",
      name: "auto_search",
      args: { q: "test" },
    });

    const blocks = getBlocks();
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("thinking");
    expect(thinkingAt(blocks, 0).content).toBe("");
    expect(thinkingAt(blocks, 0).toolCalls).toHaveLength(1);
  });

  it("should create thinking block for tool call after answer block", () => {
    useChatStore.getState().startStreaming();

    // Answer first
    useChatStore.getState().appendStreamingContent("Some text");

    // Tool call after answer
    useChatStore.getState().appendToolCall({
      id: "tc-late",
      name: "correction_search",
    });

    const blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    expect(blocks[0].type).toBe("answer");
    expect(blocks[1].type).toBe("thinking");
    expect(thinkingAt(blocks, 1).toolCalls[0].id).toBe("tc-late");
  });
});

describe("Streaming Blocks — closeLastThinkingBlock", () => {
  it("should set endTime when answer follows thinking", () => {
    useChatStore.getState().startStreaming();

    useChatStore.getState().setStreamingThinking("Analyzing...");

    // Thinking block open (no endTime)
    let blocks = getBlocks();
    expect(thinkingAt(blocks, 0).endTime).toBeUndefined();

    // Answer closes thinking
    useChatStore.getState().appendStreamingContent("Answer");

    blocks = getBlocks();
    expect(thinkingAt(blocks, 0).endTime).toBeDefined();
    expect(thinkingAt(blocks, 0).endTime).toBeGreaterThan(0);
  });

  it("should not set endTime on already-closed thinking blocks", () => {
    useChatStore.getState().startStreaming();

    // thinking → answer → thinking → answer
    useChatStore.getState().setStreamingThinking("T1");
    useChatStore.getState().appendStreamingContent("A1");
    useChatStore.getState().setStreamingThinking("T2");
    useChatStore.getState().appendStreamingContent("A2");

    const blocks = getBlocks();
    const t1End = thinkingAt(blocks, 0).endTime!;
    const t2End = thinkingAt(blocks, 2).endTime!;

    // Both should have endTimes
    expect(t1End).toBeGreaterThan(0);
    expect(t2End).toBeGreaterThan(0);
    // T2 was closed after T1
    expect(t2End).toBeGreaterThanOrEqual(t1End);
  });
});

describe("Streaming Blocks — finalizeStream", () => {
  it("should save blocks on the finalized message", () => {
    const store = useChatStore.getState();
    store.createConversation("maritime");
    store.addUserMessage("Test question");
    store.startStreaming();

    // Build interleaved blocks
    useChatStore.getState().setStreamingThinking("Analyzing...");
    useChatStore.getState().appendStreamingContent("Answer part 1. ");
    useChatStore.getState().setStreamingThinking("More research...");
    useChatStore.getState().appendStreamingContent("Answer part 2.");

    // Finalize
    useChatStore.getState().finalizeStream({
      processing_time: 2.5,
      model: "gemini-2.0",
      agent_type: "rag",
    });

    const conv = useChatStore.getState().conversations[0];
    const msg = conv.messages[1]; // assistant message
    expect(msg.role).toBe("assistant");
    expect(msg.blocks).toBeDefined();
    expect(msg.blocks).toHaveLength(4); // T, A, T, A

    // Verify block types
    expect(msg.blocks![0].type).toBe("thinking");
    expect(msg.blocks![1].type).toBe("answer");
    expect(msg.blocks![2].type).toBe("thinking");
    expect(msg.blocks![3].type).toBe("answer");

    // All thinking blocks should be closed (have endTime)
    const t1 = msg.blocks![0] as ThinkingBlockData;
    const t2 = msg.blocks![2] as ThinkingBlockData;
    expect(t1.endTime).toBeGreaterThan(0);
    expect(t2.endTime).toBeGreaterThan(0);
  });

  it("should close remaining open thinking block on finalize", () => {
    const store = useChatStore.getState();
    store.createConversation("maritime");
    store.addUserMessage("Q");
    store.startStreaming();

    // Thinking but no answer — block stays open during streaming
    useChatStore.getState().setStreamingThinking("Still thinking...");
    useChatStore.getState().appendStreamingContent("Done.");

    // Finalize — should close the thinking block
    useChatStore.getState().finalizeStream({
      processing_time: 1.0,
      model: "gemini",
      agent_type: "rag",
    });

    const msg = useChatStore.getState().conversations[0].messages[1];
    expect(msg.blocks).toHaveLength(2);
    const thinking = msg.blocks![0] as ThinkingBlockData;
    expect(thinking.endTime).toBeGreaterThan(0);
  });

  it("should not save blocks field when no blocks were created", () => {
    const store = useChatStore.getState();
    store.createConversation("maritime");
    store.addUserMessage("Q");
    store.startStreaming();

    // No events at all — finalize with empty content
    useChatStore.getState().finalizeStream({
      processing_time: 0.1,
      model: "gemini",
      agent_type: "chat",
    });

    const msg = useChatStore.getState().conversations[0].messages[1];
    expect(msg.blocks).toBeUndefined(); // empty blocks → undefined
  });

  it("should reset streamingBlocks after finalize", () => {
    const store = useChatStore.getState();
    store.createConversation("maritime");
    store.addUserMessage("Q");
    store.startStreaming();
    useChatStore.getState().appendStreamingContent("Answer");
    useChatStore.getState().finalizeStream({
      processing_time: 0.5,
      model: "gemini",
      agent_type: "rag",
    });

    expect(useChatStore.getState().streamingBlocks).toEqual([]);
  });
});

describe("Streaming Blocks — clearStreaming", () => {
  it("should reset streamingBlocks", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().setStreamingThinking("Thinking...");
    useChatStore.getState().appendStreamingContent("Text");

    useChatStore.getState().clearStreaming();

    expect(getBlocks()).toEqual([]);
  });
});

describe("Streaming Blocks — setStreamError", () => {
  it("should reset streamingBlocks on error", () => {
    const store = useChatStore.getState();
    store.createConversation("test");
    store.addUserMessage("Q");
    store.startStreaming();
    useChatStore.getState().setStreamingThinking("Processing...");

    useChatStore.getState().setStreamError("Timeout");

    expect(getBlocks()).toEqual([]);
  });
});

describe("Streaming Blocks — Backward compatibility with flat fields", () => {
  it("should populate both flat fields and blocks simultaneously", () => {
    useChatStore.getState().startStreaming();

    // Thinking
    useChatStore.getState().setStreamingThinking("T1");
    expect(useChatStore.getState().streamingThinking).toBe("T1");
    expect(getBlocks()).toHaveLength(1);

    // Answer
    useChatStore.getState().appendStreamingContent("A1");
    expect(useChatStore.getState().streamingContent).toBe("A1");
    expect(getBlocks()).toHaveLength(2);

    // More thinking
    useChatStore.getState().setStreamingThinking("T2");
    expect(useChatStore.getState().streamingThinking).toBe("T1\nT2");
    expect(getBlocks()).toHaveLength(3);

    // More answer
    useChatStore.getState().appendStreamingContent("A2");
    expect(useChatStore.getState().streamingContent).toBe("A1A2");
    expect(getBlocks()).toHaveLength(4);

    // Tool calls
    useChatStore.getState().setStreamingThinking("T3");
    useChatStore.getState().appendToolCall({ id: "t", name: "fn" });
    expect(useChatStore.getState().streamingToolCalls).toHaveLength(1);
    expect(thinkingAt(getBlocks(), 4).toolCalls).toHaveLength(1);
  });
});

// ===== Sprint 63: Streaming Steps + Timer =====

describe("Streaming Steps — addStreamingStep", () => {
  it("should accumulate pipeline steps", () => {
    useChatStore.getState().startStreaming();

    useChatStore.getState().addStreamingStep("Phân tích câu hỏi", "supervisor");
    useChatStore.getState().addStreamingStep("Tra cứu tài liệu", "rag_agent");
    useChatStore.getState().addStreamingStep("Tạo câu trả lời", "tutor_agent");

    const steps = useChatStore.getState().streamingSteps;
    expect(steps).toHaveLength(3);
    expect(steps[0].label).toBe("Phân tích câu hỏi");
    expect(steps[0].node).toBe("supervisor");
    expect(steps[1].label).toBe("Tra cứu tài liệu");
    expect(steps[1].node).toBe("rag_agent");
    expect(steps[2].label).toBe("Tạo câu trả lời");
    expect(steps[2].node).toBe("tutor_agent");
  });

  it("should set timestamp on each step", () => {
    useChatStore.getState().startStreaming();

    useChatStore.getState().addStreamingStep("Step 1");
    useChatStore.getState().addStreamingStep("Step 2");

    const steps = useChatStore.getState().streamingSteps;
    expect(steps[0].timestamp).toBeGreaterThan(0);
    expect(steps[1].timestamp).toBeGreaterThanOrEqual(steps[0].timestamp);
  });

  it("should allow steps without node", () => {
    useChatStore.getState().startStreaming();

    useChatStore.getState().addStreamingStep("Loading...");

    const steps = useChatStore.getState().streamingSteps;
    expect(steps[0].node).toBeUndefined();
  });
});

describe("Streaming Steps — startStreaming timer", () => {
  it("should set streamingStartTime on startStreaming", () => {
    const before = Date.now();
    useChatStore.getState().startStreaming();
    const after = Date.now();

    const startTime = useChatStore.getState().streamingStartTime;
    expect(startTime).toBeGreaterThanOrEqual(before);
    expect(startTime).toBeLessThanOrEqual(after);
  });

  it("should reset steps on startStreaming", () => {
    useChatStore.setState({
      streamingSteps: [{ label: "old", timestamp: 1 }],
    });

    useChatStore.getState().startStreaming();

    expect(useChatStore.getState().streamingSteps).toEqual([]);
  });
});

describe("Streaming Steps — clearStreaming resets timer and steps", () => {
  it("should reset streamingStartTime and streamingSteps", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().addStreamingStep("Step 1");

    expect(useChatStore.getState().streamingStartTime).not.toBeNull();
    expect(useChatStore.getState().streamingSteps).toHaveLength(1);

    useChatStore.getState().clearStreaming();

    expect(useChatStore.getState().streamingStartTime).toBeNull();
    expect(useChatStore.getState().streamingSteps).toEqual([]);
  });
});

describe("Streaming Steps — finalizeStream resets timer and steps", () => {
  it("should reset streamingStartTime and streamingSteps after finalize", () => {
    const store = useChatStore.getState();
    store.createConversation("maritime");
    store.addUserMessage("Q");
    store.startStreaming();
    useChatStore.getState().addStreamingStep("Searching...");
    useChatStore.getState().appendStreamingContent("Answer");

    useChatStore.getState().finalizeStream({
      processing_time: 1.0,
      model: "gemini",
      agent_type: "rag",
    });

    expect(useChatStore.getState().streamingStartTime).toBeNull();
    expect(useChatStore.getState().streamingSteps).toEqual([]);
  });
});

describe("Streaming Steps — setStreamError resets timer and steps", () => {
  it("should reset streamingStartTime and streamingSteps on error", () => {
    const store = useChatStore.getState();
    store.createConversation("test");
    store.addUserMessage("Q");
    store.startStreaming();
    useChatStore.getState().addStreamingStep("Processing...");

    useChatStore.getState().setStreamError("Timeout");

    expect(useChatStore.getState().streamingStartTime).toBeNull();
    expect(useChatStore.getState().streamingSteps).toEqual([]);
  });
});

describe("Streaming Steps — Status events should NOT create thinking blocks", () => {
  it("should not create thinking blocks from addStreamingStep", () => {
    useChatStore.getState().startStreaming();

    // Simulate status events (pipeline progress)
    useChatStore.getState().addStreamingStep("Phân tích câu hỏi", "supervisor");
    useChatStore.getState().addStreamingStep("Tra cứu tài liệu", "rag_agent");

    // Steps should be in streamingSteps
    expect(useChatStore.getState().streamingSteps).toHaveLength(2);

    // But NO thinking blocks should be created
    expect(useChatStore.getState().streamingBlocks).toEqual([]);
    expect(useChatStore.getState().streamingThinking).toBe("");
  });
});
