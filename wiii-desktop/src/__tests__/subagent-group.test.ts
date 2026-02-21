/**
 * Unit tests for Sprint 164: Subagent UX Visualization.
 * Tests the subagent group store logic, SSE detection, and integration flow.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";
import type {
  ContentBlock,
  ThinkingBlockData,
  SubagentGroupBlockData,
  AggregationSummary,
} from "@/api/types";
import { _parseParallelTargets } from "@/hooks/useSSEStream";

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
    _activeSubagentGroupId: null,
    streamError: "",
    streamCompletedAt: null,
  });
});

function getBlocks(): ContentBlock[] {
  return useChatStore.getState().streamingBlocks;
}

function findGroup(blocks: ContentBlock[]): SubagentGroupBlockData | undefined {
  return blocks.find((b) => b.type === "subagent_group") as SubagentGroupBlockData | undefined;
}

// =============================================================================
// Store tests (12)
// =============================================================================
describe("SubagentGroup — Store", () => {
  it("openSubagentGroup creates SubagentGroupBlockData in streamingBlocks", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Triển khai song song", ["rag", "tutor"]);

    const blocks = getBlocks();
    expect(blocks).toHaveLength(1);

    const group = blocks[0] as SubagentGroupBlockData;
    expect(group.type).toBe("subagent_group");
    expect(group.label).toBe("Triển khai song song");
    expect(group.workers).toHaveLength(2);
    expect(group.workers[0].agentName).toBe("rag");
    expect(group.workers[1].agentName).toBe("tutor");
    expect(group.startTime).toBeGreaterThan(0);
    expect(group.endTime).toBeUndefined();
  });

  it("openSubagentGroup sets _activeSubagentGroupId", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Test", ["rag"]);

    const groupId = useChatStore.getState()._activeSubagentGroupId;
    expect(groupId).toBeTruthy();

    const group = findGroup(getBlocks());
    expect(groupId).toBe(group?.id);
  });

  it("openSubagentGroup closes open thinking block first", () => {
    useChatStore.getState().startStreaming();
    // Open a thinking block
    useChatStore.getState().openThinkingBlock("Supervisor");
    useChatStore.getState().appendThinkingDelta("some content");

    // Open subagent group — should close the thinking block
    useChatStore.getState().openSubagentGroup("Dispatch", ["rag", "tutor"]);

    const blocks = getBlocks();
    // First: closed thinking, Second: subagent_group
    expect(blocks).toHaveLength(2);
    const thinkingBlock = blocks[0] as ThinkingBlockData;
    expect(thinkingBlock.type).toBe("thinking");
    expect(thinkingBlock.endTime).toBeDefined();

    expect(blocks[1].type).toBe("subagent_group");
  });

  it("openSubagentGroup initializes workers from agentNames", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Multi", ["rag", "tutor", "direct"]);

    const group = findGroup(getBlocks())!;
    expect(group.workers).toHaveLength(3);
    for (const w of group.workers) {
      expect(w.status).toBe("active");
      expect(w.startTime).toBeGreaterThan(0);
      expect(w.endTime).toBeUndefined();
    }
  });

  it("closeSubagentGroup sets endTime and clears _activeSubagentGroupId", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Test", ["rag"]);

    expect(useChatStore.getState()._activeSubagentGroupId).toBeTruthy();

    useChatStore.getState().closeSubagentGroup();

    expect(useChatStore.getState()._activeSubagentGroupId).toBeNull();
    const group = findGroup(getBlocks())!;
    expect(group.endTime).toBeDefined();
    expect(group.endTime).toBeGreaterThan(0);
  });

  it("closeSubagentGroup marks active workers as completed", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Test", ["rag", "tutor"]);
    useChatStore.getState().closeSubagentGroup();

    const group = findGroup(getBlocks())!;
    for (const w of group.workers) {
      expect(w.status).toBe("completed");
      expect(w.endTime).toBeDefined();
    }
  });

  it("closeSubagentGroup is no-op when no active group", () => {
    useChatStore.getState().startStreaming();

    // Should not throw
    useChatStore.getState().closeSubagentGroup();

    expect(getBlocks()).toHaveLength(0);
    expect(useChatStore.getState()._activeSubagentGroupId).toBeNull();
  });

  it("setAggregationSummary attaches to most recent subagent_group block", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Group 1", ["rag"]);
    useChatStore.getState().closeSubagentGroup();

    const summary: AggregationSummary = {
      strategy: "synthesize",
      primaryAgent: "rag",
      confidence: 0.87,
      reasoning: "Both have value",
    };
    useChatStore.getState().setAggregationSummary(summary);

    const group = findGroup(getBlocks())!;
    expect(group.aggregation).toEqual(summary);
  });

  it("openThinkingBlock tags with groupId and workerNode when inside subagent group", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Test", ["rag"]);

    const groupId = useChatStore.getState()._activeSubagentGroupId;
    useChatStore.getState().openThinkingBlock("Tra cứu", undefined, "rag");

    const blocks = getBlocks();
    const thinkingBlocks = blocks.filter((b) => b.type === "thinking") as ThinkingBlockData[];
    expect(thinkingBlocks).toHaveLength(1);
    expect(thinkingBlocks[0].groupId).toBe(groupId);
    expect(thinkingBlocks[0].workerNode).toBe("rag");
  });

  it("openThinkingBlock does NOT tag when no active group (backward compat)", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openThinkingBlock("Normal thinking");

    const blocks = getBlocks();
    const tb = blocks[0] as ThinkingBlockData;
    expect(tb.groupId).toBeUndefined();
  });

  it("appendThinkingDelta tags new block with groupId", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Test", ["tutor"]);

    const groupId = useChatStore.getState()._activeSubagentGroupId;
    useChatStore.getState().appendThinkingDelta("some text", "tutor");

    const blocks = getBlocks();
    const thinkingBlocks = blocks.filter((b) => b.type === "thinking") as ThinkingBlockData[];
    expect(thinkingBlocks).toHaveLength(1);
    expect(thinkingBlocks[0].groupId).toBe(groupId);
    expect(thinkingBlocks[0].workerNode).toBe("tutor");
  });

  it("markWorkerCompleted marks specific worker as completed", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Test", ["rag", "tutor"]);
    useChatStore.getState().markWorkerCompleted("rag");

    const group = findGroup(getBlocks())!;
    expect(group.workers[0].agentName).toBe("rag");
    expect(group.workers[0].status).toBe("completed");
    expect(group.workers[0].endTime).toBeDefined();
    // Tutor should still be active
    expect(group.workers[1].agentName).toBe("tutor");
    expect(group.workers[1].status).toBe("active");
  });

  it("appendWorkerStatus adds status message to specific worker", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Test", ["rag", "tutor"]);
    useChatStore.getState().appendWorkerStatus("rag", "Tìm kiếm trong kho tri thức...");
    useChatStore.getState().appendWorkerStatus("tutor", "Phân tích câu hỏi...");
    useChatStore.getState().appendWorkerStatus("rag", "Đánh giá tài liệu...");

    const group = findGroup(getBlocks())!;
    expect(group.workers[0].statusMessages).toEqual([
      "Tìm kiếm trong kho tri thức...",
      "Đánh giá tài liệu...",
    ]);
    expect(group.workers[1].statusMessages).toEqual([
      "Phân tích câu hỏi...",
    ]);
  });

  it("startStreaming resets _activeSubagentGroupId", () => {
    useChatStore.getState().startStreaming();
    useChatStore.getState().openSubagentGroup("Test", ["rag"]);

    expect(useChatStore.getState()._activeSubagentGroupId).toBeTruthy();

    useChatStore.getState().startStreaming();

    expect(useChatStore.getState()._activeSubagentGroupId).toBeNull();
    expect(getBlocks()).toHaveLength(0);
  });
});

// =============================================================================
// SSE detection tests (3)
// =============================================================================
describe("SubagentGroup — SSE Detection", () => {
  it("_parseParallelTargets extracts agent names from colon format", () => {
    expect(_parseParallelTargets("Triển khai song song: rag, tutor")).toEqual(["rag", "tutor"]);
    expect(_parseParallelTargets("Dispatching: rag_agent, tutor_agent")).toEqual([
      "rag_agent",
      "tutor_agent",
    ]);
  });

  it("_parseParallelTargets handles empty and malformed input", () => {
    expect(_parseParallelTargets("")).toEqual([]);
    expect(_parseParallelTargets("No agents here!")).toEqual([]);
    expect(_parseParallelTargets("Just text: , ")).toEqual([]);
  });

  it("_parseParallelTargets extracts from simple comma list", () => {
    expect(_parseParallelTargets("rag, tutor, direct")).toEqual(["rag", "tutor", "direct"]);
  });
});

// =============================================================================
// Integration tests (3)
// =============================================================================
describe("SubagentGroup — Integration", () => {
  it("full parallel dispatch flow: dispatch → thinking per agent → aggregator → answer", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // 1. Supervisor thinking
    store.openThinkingBlock("Phân tích câu hỏi");
    store.appendThinkingDelta("Routing to parallel...");
    store.closeThinkingBlock();

    // 2. Parallel dispatch opens group
    store.openSubagentGroup("Triển khai song song: rag, tutor", ["rag", "tutor"]);

    // 3. RAG worker: thinking_start → status → thinking_delta → thinking_end
    store.openThinkingBlock("Tra cứu tri thức", undefined, "rag");
    store.appendWorkerStatus("rag", "Tìm kiếm trong kho tri thức...");
    store.appendThinkingDelta("Searching COLREG Rule 7...", "rag");
    store.appendWorkerStatus("rag", "Đánh giá tài liệu...");
    store.closeThinkingBlock();
    store.markWorkerCompleted("rag");

    // 4. Tutor worker: thinking_start → status → thinking_delta → thinking_end
    store.openThinkingBlock("Soạn bài giảng", undefined, "tutor");
    store.appendWorkerStatus("tutor", "Phân tích câu hỏi...");
    store.appendThinkingDelta("Preparing lesson on COLREG...", "tutor");
    store.closeThinkingBlock();
    store.markWorkerCompleted("tutor");

    // 5. Aggregator closes group
    store.closeSubagentGroup();
    store.setAggregationSummary({
      strategy: "synthesize",
      primaryAgent: "rag",
      confidence: 0.87,
      reasoning: "Both agents provided useful content",
    });

    // 6. Answer
    store.appendStreamingContent("Here is the combined answer.");

    const blocks = getBlocks();

    // Expect: thinking(supervisor), subagent_group, thinking(rag), thinking(tutor), answer
    const types = blocks.map((b) => b.type);
    expect(types).toContain("thinking");
    expect(types).toContain("subagent_group");
    expect(types).toContain("answer");

    // Verify group has aggregation
    const group = findGroup(blocks)!;
    expect(group.aggregation?.strategy).toBe("synthesize");
    expect(group.endTime).toBeDefined();

    // Verify workers completed with status messages
    expect(group.workers[0].status).toBe("completed");
    expect(group.workers[0].statusMessages).toEqual([
      "Tìm kiếm trong kho tri thức...",
      "Đánh giá tài liệu...",
    ]);
    expect(group.workers[1].status).toBe("completed");
    expect(group.workers[1].statusMessages).toEqual(["Phân tích câu hỏi..."]);

    // Verify grouped thinking blocks have groupId + workerNode
    const groupedThinking = blocks.filter(
      (b) => b.type === "thinking" && (b as ThinkingBlockData).groupId === group.id,
    ) as ThinkingBlockData[];
    expect(groupedThinking.length).toBeGreaterThanOrEqual(2);
    expect(groupedThinking.find((b) => b.workerNode === "rag")).toBeDefined();
    expect(groupedThinking.find((b) => b.workerNode === "tutor")).toBeDefined();
  });

  it("non-subagent flow unchanged (backward compatibility)", () => {
    const store = useChatStore.getState();
    store.startStreaming();

    // Normal flow without subagent group
    store.openThinkingBlock("Phân tích");
    store.appendThinkingDelta("thinking...");
    store.closeThinkingBlock();

    store.appendStreamingContent("Answer here.");

    const blocks = getBlocks();
    expect(blocks).toHaveLength(2);
    expect(blocks[0].type).toBe("thinking");
    expect(blocks[1].type).toBe("answer");

    // No groupId on thinking block
    const tb = blocks[0] as ThinkingBlockData;
    expect(tb.groupId).toBeUndefined();

    // No subagent_group blocks
    expect(findGroup(blocks)).toBeUndefined();
  });

  it("finalizeStream preserves subagent_group blocks", () => {
    const convId = "test-conv-164";
    // Set up conversation directly (avoid Tauri storage in test)
    useChatStore.setState({
      activeConversationId: convId,
      conversations: [
        {
          id: convId,
          title: "Test",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          messages: [
            { id: "msg-1", role: "user", content: "Test question", timestamp: new Date().toISOString() },
          ],
        },
      ],
    });

    const store = useChatStore.getState();
    store.startStreaming();

    // Build subagent flow
    store.openSubagentGroup("Dispatch", ["rag"]);
    store.openThinkingBlock("RAG");
    store.appendThinkingDelta("content");
    store.closeThinkingBlock();
    store.closeSubagentGroup();
    store.appendStreamingContent("Final answer");

    // Finalize
    store.finalizeStream({ processing_time: 1.0, model: "gemini", agent_type: "rag" } as any);

    // Get saved message (re-read state after immer mutation)
    const freshState = useChatStore.getState();
    const conv = freshState.conversations[0];
    const lastMsg = conv.messages[conv.messages.length - 1];
    expect(lastMsg.role).toBe("assistant");
    expect(lastMsg.blocks).toBeDefined();

    // Verify subagent_group block is preserved in saved message
    const savedGroup = lastMsg.blocks!.find((b) => b.type === "subagent_group");
    expect(savedGroup).toBeDefined();
    expect((savedGroup as SubagentGroupBlockData).workers).toHaveLength(1);
  });
});
