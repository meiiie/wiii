import { beforeEach, describe, expect, it } from "vitest";
import { useChatStore } from "@/stores/chat-store";

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
    streamingBlocks: [],
    streamingStartTime: null,
    streamingSteps: [],
    pendingStreamMetadata: null,
  });
});

describe("chat-store thinking lifecycle finalize", () => {
  it("prefers lifecycle final_text over thinner live thinking on finalize", () => {
    const store = useChatStore.getState();
    const conversationId = store.createConversation("maritime");
    useChatStore.getState().setActiveConversation(conversationId);

    store.startStreaming();
    store.openThinkingBlock("Đang nghĩ");
    store.setStreamingThinking("Mình đang gom ý.");
    store.closeThinkingBlock(1200);
    store.appendStreamingContent("Đây là câu trả lời.");
    store.setPendingStreamMetadata({
      processing_time: 1.2,
      model: "gemini-3.1-pro-preview",
      agent_type: "direct",
      thinking_content: "Mình đang gom ý.",
      thinking_lifecycle: {
        version: 1,
        turn_id: "turn-1",
        final_text: "Mình đang gom ý và nối lại mạch kể cho thật tự nhiên.",
        final_length: 56,
        live_text: "Mình đang gom ý.",
        live_length: 18,
        segment_count: 2,
        has_tool_continuation: false,
        phases: ["pre_tool", "final_snapshot"],
        provenance_mix: ["live_native", "final_snapshot"],
        segments: [],
      },
    });

    store.finalizeStream();

    const message = useChatStore.getState().conversations[0]?.messages.at(-1);
    expect(message?.thinking).toBe("Mình đang gom ý và nối lại mạch kể cho thật tự nhiên.");
    expect(message?.metadata?.thinking_lifecycle?.final_text).toBe(
      "Mình đang gom ý và nối lại mạch kể cho thật tự nhiên.",
    );
  });
});
