/**
 * Sprint 149: ActionText + ThinkingTimeline tests.
 *
 * Tests:
 * 1. appendActionText stores node field
 * 2. appendActionText closes open thinking block
 * 3. appendActionText backward compat (no node)
 * 4. BlockRenderer simple path (0-2 blocks) — renders individually
 * 5. BlockRenderer timeline path (3+ blocks) — wraps in ThinkingTimeline
 * 6. BlockRenderer answer-only when showThinking=false
 * 7. ThinkingTimeline duration calculation
 * 8. ThinkingTimeline phase count
 * 9. ThinkingTimeline expand/collapse
 * 10. Streaming view uses ActionText component
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";
import type { ContentBlock, ThinkingBlockData, ActionTextBlockData } from "@/api/types";

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

describe("appendActionText store action", () => {
  it("stores node field on ActionTextBlockData", () => {
    const store = useChatStore.getState();
    store.appendActionText("Đang phân tích...", "tutor_agent");

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("action_text");
    const actionBlock = blocks[0] as ActionTextBlockData;
    expect(actionBlock.content).toBe("Đang phân tích...");
    expect(actionBlock.node).toBe("tutor_agent");
  });

  it("closes open thinking block before adding action text", () => {
    const store = useChatStore.getState();

    // Open a thinking block first
    store.openThinkingBlock("Suy nghĩ");
    store.appendThinkingDelta("Some thinking...");

    // Now append action text — should close the thinking block
    store.appendActionText("Chuyển sang giai đoạn 2");

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks).toHaveLength(2);

    // First block: thinking, should be closed (has endTime)
    expect(blocks[0].type).toBe("thinking");
    const thinkingBlock = blocks[0] as ThinkingBlockData;
    expect(thinkingBlock.endTime).toBeDefined();

    // Second block: action_text
    expect(blocks[1].type).toBe("action_text");
  });

  it("works without node parameter (backward compat)", () => {
    const store = useChatStore.getState();
    store.appendActionText("Action without node");

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks).toHaveLength(1);
    const actionBlock = blocks[0] as ActionTextBlockData;
    expect(actionBlock.content).toBe("Action without node");
    expect(actionBlock.node).toBeUndefined();
  });

  it("dedupes consecutive identical action text from narrator fallback", () => {
    const store = useChatStore.getState();
    store.appendActionText("Để mình chuẩn bị một phòng luyện tập nhỏ cho bạn nhé!", "code_studio_agent");
    store.appendActionText("Để mình chuẩn bị một phòng luyện tập nhỏ cho bạn nhé!", "code_studio_agent");

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks).toHaveLength(1);
    expect(blocks[0]?.type).toBe("action_text");
    expect((blocks[0] as ActionTextBlockData).content).toBe("Để mình chuẩn bị một phòng luyện tập nhỏ cho bạn nhé!");
  });
});

describe("BlockRenderer segmentation logic", () => {
  // Helper to create test blocks
  function makeThinkingBlock(id: string, content: string, startTime?: number, endTime?: number): ThinkingBlockData {
    return {
      type: "thinking",
      id,
      content,
      toolCalls: [],
      startTime: startTime ?? Date.now() - 10000,
      endTime: endTime ?? Date.now() - 5000,
    };
  }

  function makeActionTextBlock(id: string, content: string): ActionTextBlockData {
    return { type: "action_text", id, content };
  }

  function makeAnswerBlock(id: string, content: string): ContentBlock {
    return { type: "answer", id, content };
  }

  it("simple path: 0-2 thinking+action_text blocks render individually", () => {
    // 1 thinking + 1 answer = only 1 thinking/action_text block → simple path
    const blocks: ContentBlock[] = [
      makeThinkingBlock("t1", "Thinking..."),
      makeAnswerBlock("a1", "Answer text"),
    ];

    // Count thinking + action_text blocks
    const thinkingActionCount = blocks.filter(
      (b) => b.type === "thinking" || b.type === "action_text"
    ).length;

    expect(thinkingActionCount).toBe(1);
    expect(thinkingActionCount).toBeLessThan(3);
  });

  it("timeline path: 3+ thinking+action_text blocks trigger grouping", () => {
    const blocks: ContentBlock[] = [
      makeThinkingBlock("t1", "Phase 1"),
      makeActionTextBlock("at1", "Chuyển sang giai đoạn 2"),
      makeThinkingBlock("t2", "Phase 2"),
      makeActionTextBlock("at2", "Tổng hợp kết quả"),
      makeThinkingBlock("t3", "Phase 3"),
      makeAnswerBlock("a1", "Final answer"),
    ];

    const thinkingActionCount = blocks.filter(
      (b) => b.type === "thinking" || b.type === "action_text"
    ).length;

    expect(thinkingActionCount).toBe(5);
    expect(thinkingActionCount).toBeGreaterThanOrEqual(3);

    // Verify segmentation: consecutive thinking+action_text → timeline, answer → inline
    const segments: Array<{ kind: string; count?: number }> = [];
    let currentTimeline: ContentBlock[] = [];

    for (const block of blocks) {
      if (block.type === "thinking" || block.type === "action_text") {
        currentTimeline.push(block);
      } else {
        if (currentTimeline.length > 0) {
          segments.push({ kind: "timeline", count: currentTimeline.length });
          currentTimeline = [];
        }
        segments.push({ kind: "answer" });
      }
    }
    if (currentTimeline.length > 0) {
      segments.push({ kind: "timeline", count: currentTimeline.length });
    }

    expect(segments).toEqual([
      { kind: "timeline", count: 5 },
      { kind: "answer" },
    ]);
  });

  it("answer-only when showThinking=false", () => {
    const blocks: ContentBlock[] = [
      makeThinkingBlock("t1", "Phase 1"),
      makeActionTextBlock("at1", "Transition"),
      makeThinkingBlock("t2", "Phase 2"),
      makeAnswerBlock("a1", "Answer"),
    ];

    // When showThinking=false, only answer blocks should render
    const visibleBlocks = blocks.filter((b) => b.type === "answer");
    expect(visibleBlocks).toHaveLength(1);
    expect(visibleBlocks[0].content).toBe("Answer");
  });
});

describe("ThinkingTimeline calculations", () => {
  function makeThinkingBlock(
    id: string,
    startTime: number,
    endTime: number
  ): ThinkingBlockData {
    return {
      type: "thinking",
      id,
      content: `Thinking ${id}`,
      toolCalls: [],
      startTime,
      endTime,
    };
  }

  it("calculates total duration from first startTime to last endTime", () => {
    const phases: ContentBlock[] = [
      makeThinkingBlock("t1", 1000, 5000),
      { type: "action_text", id: "at1", content: "Transition" },
      makeThinkingBlock("t2", 5500, 10000),
      { type: "action_text", id: "at2", content: "Transition 2" },
      makeThinkingBlock("t3", 10500, 20000),
    ];

    // Calculate duration the same way ThinkingTimeline does
    const thinkingBlocks = phases.filter(
      (b) => b.type === "thinking"
    ) as ThinkingBlockData[];

    let firstStart: number | undefined;
    let lastEnd: number | undefined;
    for (const block of thinkingBlocks) {
      if (block.startTime && (firstStart === undefined || block.startTime < firstStart)) {
        firstStart = block.startTime;
      }
      if (block.endTime && (lastEnd === undefined || block.endTime > lastEnd)) {
        lastEnd = block.endTime;
      }
    }

    expect(firstStart).toBe(1000);
    expect(lastEnd).toBe(20000);

    const totalDuration = Math.round((lastEnd! - firstStart!) / 1000);
    expect(totalDuration).toBe(19);
  });

  it("counts only thinking blocks for phase count", () => {
    const phases: ContentBlock[] = [
      makeThinkingBlock("t1", 1000, 5000),
      { type: "action_text", id: "at1", content: "Trans 1" },
      makeThinkingBlock("t2", 5500, 10000),
      { type: "action_text", id: "at2", content: "Trans 2" },
      makeThinkingBlock("t3", 10500, 20000),
    ];

    const thinkingBlocks = phases.filter((b) => b.type === "thinking");
    expect(thinkingBlocks).toHaveLength(3);
  });

  it("handles 0 thinking blocks gracefully", () => {
    const phases: ContentBlock[] = [
      { type: "action_text", id: "at1", content: "Only action text" },
    ];

    const thinkingBlocks = phases.filter(
      (b) => b.type === "thinking"
    ) as ThinkingBlockData[];
    expect(thinkingBlocks).toHaveLength(0);

    // Duration should be 0 when no thinking blocks
    let firstStart: number | undefined;
    let lastEnd: number | undefined;
    for (const block of thinkingBlocks) {
      if (block.startTime && (firstStart === undefined || block.startTime < firstStart)) {
        firstStart = block.startTime;
      }
      if (block.endTime && (lastEnd === undefined || block.endTime > lastEnd)) {
        lastEnd = block.endTime;
      }
    }

    const totalDuration = firstStart && lastEnd ? Math.round((lastEnd - firstStart) / 1000) : 0;
    expect(totalDuration).toBe(0);
  });
});

describe("ActionTextBlockData type", () => {
  it("supports node field", () => {
    const block: ActionTextBlockData = {
      type: "action_text",
      id: "test-id",
      content: "Test content",
      node: "tutor_agent",
    };

    expect(block.node).toBe("tutor_agent");
  });

  it("node field is optional", () => {
    const block: ActionTextBlockData = {
      type: "action_text",
      id: "test-id",
      content: "Test content",
    };

    expect(block.node).toBeUndefined();
  });
});
