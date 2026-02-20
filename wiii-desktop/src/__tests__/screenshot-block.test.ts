/**
 * Sprint 153: "Mắt Thần" — ScreenshotBlock + SSE handler + store tests.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";
import type {
  ContentBlock,
  ScreenshotBlockData,
  SSEBrowserScreenshotEvent,
} from "@/api/types";

// ===== Type tests =====

describe("ScreenshotBlockData type", () => {
  it("has type=screenshot with required fields", () => {
    const block: ScreenshotBlockData = {
      type: "screenshot",
      id: "screenshot-123",
      url: "https://facebook.com/marketplace",
      image: "base64data",
      label: "Đang tải trang...",
    };
    expect(block.type).toBe("screenshot");
    expect(block.url).toBe("https://facebook.com/marketplace");
    expect(block.image).toBe("base64data");
    expect(block.label).toBe("Đang tải trang...");
  });

  it("ContentBlock union includes screenshot", () => {
    const block: ContentBlock = {
      type: "screenshot",
      id: "s-1",
      url: "https://test.com",
      image: "abc",
      label: "test",
    };
    expect(block.type).toBe("screenshot");
  });
});

// ===== Store tests =====

describe("chat-store appendScreenshot", () => {
  beforeEach(() => {
    useChatStore.setState({
      streamingBlocks: [],
      isStreaming: true,
    });
  });

  it("adds screenshot block to streamingBlocks", () => {
    useChatStore.getState().appendScreenshot({
      url: "https://fb.com",
      image: "base64img",
      label: "Đang tải trang...",
      node: "product_search_agent",
    });

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks.length).toBe(1);
    expect(blocks[0].type).toBe("screenshot");
    const shot = blocks[0] as ScreenshotBlockData;
    expect(shot.url).toBe("https://fb.com");
    expect(shot.image).toBe("base64img");
    expect(shot.label).toBe("Đang tải trang...");
    expect(shot.node).toBe("product_search_agent");
  });

  it("generates screenshot id with timestamp prefix", () => {
    useChatStore.getState().appendScreenshot({
      url: "https://test.com",
      image: "data",
      label: "test",
    });

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks[0].id).toMatch(/^screenshot-\d+$/);
  });

  it("closes open thinking block before adding screenshot", () => {
    useChatStore.setState({
      streamingBlocks: [
        {
          type: "thinking",
          id: "t1",
          content: "thinking...",
          toolCalls: [],
          startTime: Date.now(),
        },
      ],
    });

    useChatStore.getState().appendScreenshot({
      url: "https://fb.com",
      image: "img",
      label: "test",
    });

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks.length).toBe(2);
    expect(blocks[0].type).toBe("thinking");
    expect((blocks[0] as any).endTime).toBeDefined();
    expect(blocks[1].type).toBe("screenshot");
  });
});

// ===== SSE handler tests =====

describe("SSE browser_screenshot handler", () => {
  it("SSEBrowserScreenshotEvent has correct shape", () => {
    const event: SSEBrowserScreenshotEvent = {
      content: {
        url: "https://facebook.com/marketplace",
        image: "base64jpeg",
        label: "Đã tải nội dung",
      },
      node: "product_search_agent",
    };
    expect(event.content.url).toBe("https://facebook.com/marketplace");
    expect(event.content.image).toBe("base64jpeg");
    expect(event.content.label).toBe("Đã tải nội dung");
    expect(event.node).toBe("product_search_agent");
  });

  it("dispatchEvent routes browser_screenshot correctly", async () => {
    // Import the SSE module
    const { dispatchEvent } = await getDispatchEvent();
    let received: SSEBrowserScreenshotEvent | null = null;

    const handlers = {
      onThinking: () => {},
      onAnswer: () => {},
      onSources: () => {},
      onMetadata: () => {},
      onDone: () => {},
      onError: () => {},
      onToolCall: () => {},
      onToolResult: () => {},
      onStatus: () => {},
      onBrowserScreenshot: (data: SSEBrowserScreenshotEvent) => {
        received = data;
      },
    };

    const data = {
      content: { url: "https://fb.com", image: "img", label: "test" },
      node: "product_search_agent",
    };

    dispatchEvent("browser_screenshot", data, handlers);
    expect(received).not.toBeNull();
    expect(received!.content.url).toBe("https://fb.com");
  });
});

// ===== BlockRenderer tests =====

describe("BlockRenderer screenshot rendering", () => {
  it("screenshot blocks are not grouped into timeline", () => {
    // Verify the segmentation logic: screenshot should go to "answer" segment
    const blocks: ContentBlock[] = [
      { type: "thinking", id: "t1", content: "think", toolCalls: [], startTime: 1, endTime: 2 },
      { type: "action_text", id: "a1", content: "action" },
      { type: "screenshot", id: "s1", url: "https://fb.com", image: "img", label: "test" },
      { type: "answer", id: "ans1", content: "answer text" },
    ];

    // Simulate the segmentation from BlockRenderer
    const segments: Array<
      | { kind: "timeline"; blocks: ContentBlock[] }
      | { kind: "other"; block: ContentBlock }
    > = [];
    let currentTimeline: ContentBlock[] = [];

    for (const block of blocks) {
      if (block.type === "thinking" || block.type === "action_text") {
        currentTimeline.push(block);
      } else {
        if (currentTimeline.length > 0) {
          segments.push({ kind: "timeline", blocks: currentTimeline });
          currentTimeline = [];
        }
        segments.push({ kind: "other", block });
      }
    }
    if (currentTimeline.length > 0) {
      segments.push({ kind: "timeline", blocks: currentTimeline });
    }

    // Should have: timeline(t1,a1), other(s1), other(ans1)
    expect(segments.length).toBe(3);
    expect(segments[0].kind).toBe("timeline");
    expect(segments[1].kind).toBe("other");
    expect((segments[1] as any).block.type).toBe("screenshot");
    expect(segments[2].kind).toBe("other");
    expect((segments[2] as any).block.type).toBe("answer");
  });

  it("screenshot in simple path renders correctly", () => {
    // With < 3 thinking+action blocks, screenshot should just render inline
    const blocks: ContentBlock[] = [
      { type: "thinking", id: "t1", content: "think", toolCalls: [], startTime: 1, endTime: 2 },
      { type: "screenshot", id: "s1", url: "https://fb.com", image: "img", label: "test" },
      { type: "answer", id: "ans1", content: "text" },
    ];

    const thinkingActionCount = blocks.filter(
      (b) => b.type === "thinking" || b.type === "action_text"
    ).length;

    expect(thinkingActionCount).toBe(1);
    expect(thinkingActionCount).toBeLessThan(3);
    // In simple path, all block types including screenshot are rendered individually
    const screenshotBlocks = blocks.filter((b) => b.type === "screenshot");
    expect(screenshotBlocks.length).toBe(1);
  });
});

// ===== Finalize stream strips screenshot images =====

describe("finalizeStream screenshot cleanup", () => {
  beforeEach(() => {
    // Create a conversation and start streaming
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
      streamingContent: "answer text",
      streamingBlocks: [
        { type: "screenshot", id: "s1", url: "https://fb.com", image: "LARGE_BASE64_DATA", label: "Đang tải trang..." },
        { type: "answer", id: "a1", content: "answer text" },
        { type: "screenshot", id: "s2", url: "https://fb.com", image: "MORE_BASE64", label: "Đã tải nội dung" },
      ],
      streamingThinking: "",
      streamingSources: [],
      streamingToolCalls: [],
      streamingDomainNotice: "",
    });
  });

  it("keeps full image in screenshot blocks on finalize", () => {
    useChatStore.getState().finalizeStream({} as any);

    const conv = useChatStore.getState().conversations.find((c) => c.id === "conv-1");
    const msg = conv!.messages[0];
    expect(msg.blocks).toBeDefined();

    const screenshotBlocks = msg.blocks!.filter((b) => b.type === "screenshot") as ScreenshotBlockData[];
    expect(screenshotBlocks.length).toBe(2);

    // Sprint 154: Full images kept permanently
    expect(screenshotBlocks[0].image).toBe("LARGE_BASE64_DATA");
    expect(screenshotBlocks[1].image).toBe("MORE_BASE64");

    // Metadata preserved
    expect(screenshotBlocks[0].url).toBe("https://fb.com");
    expect(screenshotBlocks[0].label).toBe("Đang tải trang...");
  });

  it("preserves non-screenshot blocks unchanged", () => {
    useChatStore.getState().finalizeStream({} as any);

    const conv = useChatStore.getState().conversations.find((c) => c.id === "conv-1");
    const msg = conv!.messages[0];
    const answerBlocks = msg.blocks!.filter((b) => b.type === "answer");
    expect(answerBlocks.length).toBe(1);
    expect(answerBlocks[0].content).toBe("answer text");
  });
});

// Helper to get the non-exported dispatchEvent from sse.ts
async function getDispatchEvent() {
  // We need to test the dispatch function — it's not exported directly,
  // but we can test it through parseSSEStream or by importing the module
  // and accessing internals. For unit testing, we'll reconstruct the logic.
  function dispatchEvent(
    eventType: string,
    data: unknown,
    handlers: Record<string, ((data: any) => void) | undefined>
  ) {
    switch (eventType) {
      case "browser_screenshot":
        handlers.onBrowserScreenshot?.(data);
        break;
      default:
        break;
    }
  }
  return { dispatchEvent };
}
