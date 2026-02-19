/**
 * Sprint 141: ThinkingFlow store actions tests.
 *
 * Tests the 7 new phase actions on chat-store:
 * addOrUpdatePhase, appendPhaseThinking, appendPhaseThinkingDelta,
 * closeActivePhase, appendPhaseStatus, appendPhaseToolCall,
 * updatePhaseToolCallResult.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";

// Reset store between tests
beforeEach(() => {
  useChatStore.setState({
    streamingPhases: [],
    isStreaming: false,
    streamingBlocks: [],
    streamingContent: "",
    streamingThinking: "",
    streamingSources: [],
    streamingStep: "",
    streamingToolCalls: [],
    streamingStartTime: null,
    streamingSteps: [],
    streamingDomainNotice: "",
  });
});

describe("ThinkingFlow store actions", () => {
  it("addOrUpdatePhase creates a new active phase", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Phân tích câu hỏi", "supervisor");

    const phases = useChatStore.getState().streamingPhases;
    expect(phases).toHaveLength(1);
    expect(phases[0].label).toBe("Phân tích câu hỏi");
    expect(phases[0].node).toBe("supervisor");
    expect(phases[0].status).toBe("active");
    expect(phases[0].thinkingContent).toBe("");
    expect(phases[0].toolCalls).toEqual([]);
    expect(phases[0].statusMessages).toEqual([]);
  });

  it("addOrUpdatePhase closes previous active phase and creates new one", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Phân tích câu hỏi", "supervisor");
    store.addOrUpdatePhase("Tra cứu tri thức", "rag_agent");

    const phases = useChatStore.getState().streamingPhases;
    expect(phases).toHaveLength(2);
    expect(phases[0].status).toBe("completed");
    expect(phases[0].endTime).toBeDefined();
    expect(phases[1].status).toBe("active");
    expect(phases[1].label).toBe("Tra cứu tri thức");
  });

  it("appendPhaseThinking appends to active phase", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Tra cứu tri thức", "rag_agent");
    store.appendPhaseThinking("Found relevant documents...");

    const phases = useChatStore.getState().streamingPhases;
    expect(phases[0].thinkingContent).toBe("Found relevant documents...");

    store.appendPhaseThinking("Analyzing COLREGs Rule 15.");
    const updated = useChatStore.getState().streamingPhases;
    expect(updated[0].thinkingContent).toBe(
      "Found relevant documents...\nAnalyzing COLREGs Rule 15."
    );
  });

  it("appendPhaseThinkingDelta appends incrementally", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Suy nghĩ", "direct");
    store.appendPhaseThinkingDelta("Hel");
    store.appendPhaseThinkingDelta("lo ");
    store.appendPhaseThinkingDelta("World");

    const phases = useChatStore.getState().streamingPhases;
    expect(phases[0].thinkingContent).toBe("Hello World");
  });

  it("closeActivePhase sets completed + endTime", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Kiểm tra an toàn", "guardian");

    store.closeActivePhase(150);

    const phases = useChatStore.getState().streamingPhases;
    expect(phases[0].status).toBe("completed");
    expect(phases[0].endTime).toBeDefined();
    // endTime = startTime + durationMs
    expect(phases[0].endTime! - phases[0].startTime).toBe(150);
  });

  it("closeActivePhase with no durationMs uses Date.now()", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Kiểm tra", "grader");
    store.closeActivePhase();

    const phases = useChatStore.getState().streamingPhases;
    expect(phases[0].status).toBe("completed");
    expect(phases[0].endTime).toBeDefined();
  });

  it("appendPhaseStatus appends to active phase statusMessages", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Tra cứu tri thức", "rag_agent");
    store.appendPhaseStatus("📚 Đã tra cứu: knowledge_search", "rag_agent");
    store.appendPhaseStatus("📄 Tìm thấy 3 nguồn tham khảo", "rag_agent");

    const phases = useChatStore.getState().streamingPhases;
    expect(phases[0].statusMessages).toEqual([
      "📚 Đã tra cứu: knowledge_search",
      "📄 Tìm thấy 3 nguồn tham khảo",
    ]);
  });

  it("appendPhaseStatus creates new phase when no active phase exists", () => {
    const store = useChatStore.getState();
    // No active phase — should create one
    store.appendPhaseStatus("🚀 Bắt đầu xử lý câu hỏi...");

    const phases = useChatStore.getState().streamingPhases;
    expect(phases).toHaveLength(1);
    expect(phases[0].label).toBe("🚀 Bắt đầu xử lý câu hỏi...");
    expect(phases[0].status).toBe("active");
  });

  it("appendPhaseToolCall adds tool to active phase", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Tra cứu", "rag_agent");
    store.appendPhaseToolCall({
      id: "tc-1",
      name: "knowledge_search",
      args: { query: "COLREGs" },
    });

    const phases = useChatStore.getState().streamingPhases;
    expect(phases[0].toolCalls).toHaveLength(1);
    expect(phases[0].toolCalls[0].name).toBe("knowledge_search");
  });

  it("updatePhaseToolCallResult finds and updates tool across phases", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Phase 1", "rag_agent");
    store.appendPhaseToolCall({
      id: "tc-1",
      name: "knowledge_search",
      args: {},
    });
    store.addOrUpdatePhase("Phase 2", "grader");

    // Update tool in Phase 1 while Phase 2 is active
    store.updatePhaseToolCallResult("tc-1", "Found 3 documents");

    const phases = useChatStore.getState().streamingPhases;
    expect(phases[0].toolCalls[0].result).toBe("Found 3 documents");
  });

  it("startStreaming resets streamingPhases", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Test", "test");
    expect(useChatStore.getState().streamingPhases).toHaveLength(1);

    useChatStore.setState({ conversations: [], activeConversationId: null });
    store.startStreaming();
    expect(useChatStore.getState().streamingPhases).toEqual([]);
  });

  it("clearStreaming resets streamingPhases", () => {
    const store = useChatStore.getState();
    store.addOrUpdatePhase("Test", "test");
    store.clearStreaming();
    expect(useChatStore.getState().streamingPhases).toEqual([]);
  });

  it("full RAG flow sequence produces correct phases", () => {
    const store = useChatStore.getState();

    // 1. Status → creates phase via appendPhaseStatus
    store.appendPhaseStatus("🚀 Bắt đầu xử lý câu hỏi...");

    // 2. Guardian thinking lifecycle
    store.addOrUpdatePhase("Kiểm tra an toàn", "guardian");
    store.closeActivePhase(50);

    // 3. Supervisor thinking lifecycle
    store.addOrUpdatePhase("Phân tích câu hỏi", "supervisor");
    store.appendPhaseThinking("Routing to RAG agent for knowledge lookup");
    store.appendPhaseStatus("→ 📚 Tra cứu tri thức", "supervisor");
    store.closeActivePhase(200);

    // 4. RAG agent with tool calls
    store.addOrUpdatePhase("Tra cứu tri thức", "rag_agent");
    store.appendPhaseToolCall({
      id: "tc-1",
      name: "knowledge_search",
      args: { query: "COLREGs Rule 15" },
    });
    store.updatePhaseToolCallResult("tc-1", "Found 5 documents");
    store.appendPhaseStatus("📚 Đã tra cứu: knowledge_search", "rag_agent");
    store.appendPhaseThinking("Analyzing crossing situation rules...");
    store.closeActivePhase(3000);

    // 5. Grader
    store.addOrUpdatePhase("Kiểm tra chất lượng", "grader");
    store.closeActivePhase(100);

    const phases = useChatStore.getState().streamingPhases;
    expect(phases).toHaveLength(5);
    expect(phases.map((p) => p.label)).toEqual([
      "🚀 Bắt đầu xử lý câu hỏi...",
      "Kiểm tra an toàn",
      "Phân tích câu hỏi",
      "Tra cứu tri thức",
      "Kiểm tra chất lượng",
    ]);
    expect(phases.every((p) => p.status === "completed")).toBe(true);
    expect(phases[2].thinkingContent).toBe("Routing to RAG agent for knowledge lookup");
    expect(phases[3].toolCalls).toHaveLength(1);
    expect(phases[3].toolCalls[0].result).toBe("Found 5 documents");
    expect(phases[3].statusMessages).toContain("📚 Đã tra cứu: knowledge_search");
  });
});
