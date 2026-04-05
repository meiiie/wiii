import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MessageBubble } from "@/components/chat/MessageBubble";

const interleavedPropsSpy = vi.fn();

vi.mock("@/components/common/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("@/components/common/WiiiAvatar", () => ({
  WiiiAvatar: () => <div data-testid="wiii-avatar" />,
}));

vi.mock("@/components/chat/InterleavedBlockSequence", () => ({
  InterleavedBlockSequence: (props: Record<string, unknown>) => {
    interleavedPropsSpy(props);
    return <div data-testid="interleaved-sequence">interleaved</div>;
  },
}));

vi.mock("@/components/chat/ThinkingBlock", () => ({
  ThinkingBlock: () => <div data-testid="legacy-thinking">thinking</div>,
}));

vi.mock("@/components/chat/ModelSwitchPromptCard", () => ({
  ModelSwitchPromptCard: () => null,
}));

vi.mock("@/components/chat/SourceCitation", () => ({
  SourceCitation: () => <div data-testid="source-citation" />,
}));

vi.mock("@/stores/settings-store", () => ({
  useSettingsStore: (selector: (state: unknown) => unknown) =>
    selector({
      settings: {
        show_thinking: true,
        show_reasoning_trace: true,
        thinking_level: "balanced",
      },
    }),
}));

vi.mock("@/stores/chat-store", () => ({
  useChatStore: () => vi.fn(),
}));

vi.mock("@/stores/toast-store", () => ({
  useToastStore: () => ({ addToast: vi.fn() }),
}));

vi.mock("@/api/feedback", () => ({
  submitFeedback: vi.fn(),
}));

vi.mock("@/lib/date-utils", () => ({
  formatRelativeTime: () => "just now",
  formatAbsoluteTime: () => "2026-03-24T00:00:00Z",
}));

vi.mock("@/hooks/useReducedMotion", () => ({
  useReducedMotion: () => true,
  motionSafe: (_reduced: boolean, variants: unknown) => variants,
}));

describe("MessageBubble fast-path rendering", () => {
  beforeEach(() => {
    interleavedPropsSpy.mockReset();
  });

  it("keeps visible thinking and hides model badge for local social fast-path turns", () => {
    render(
      <MessageBubble
        message={{
          id: "assistant-1",
          role: "assistant",
          content: "Hẹ hẹ~ chào bạn nè.",
          timestamp: "2026-03-24T00:00:00Z",
          blocks: [
            {
              type: "thinking",
              id: "thinking-1",
              content: "Đang nghe nhịp câu chào này.",
              toolCalls: [],
            },
            {
              type: "answer",
              id: "answer-1",
              content: "Hẹ hẹ~ chào bạn nè.",
            },
          ],
          metadata: {
            processing_time: 1.2,
            model: "glm-5",
            agent_type: "direct",
            routing_metadata: {
              method: "always_on_social_fast_path",
              intent: "social",
            },
          },
        }}
      />,
    );

    expect(interleavedPropsSpy).toHaveBeenCalled();
    expect(interleavedPropsSpy.mock.calls[0]?.[0]).toMatchObject({
      showThinking: true,
    });
    expect(screen.getByText("Tổng 1.2s")).toBeTruthy();
    expect(screen.queryByText("glm-5")).toBeNull();
  });
  it("keeps visible thinking and hides model badge for local chatter fast-path turns", () => {
    render(
      <MessageBubble
        message={{
          id: "assistant-2",
          role: "assistant",
          content: "Woa~ minh nghe ra mot tieng cam than nho xiu nhung vui ghe.",
          timestamp: "2026-03-24T00:00:01Z",
          blocks: [
            {
              type: "thinking",
              id: "thinking-2",
              content: "Dang bat nhip vao mot reaction ngan.",
              toolCalls: [],
            },
            {
              type: "answer",
              id: "answer-2",
              content: "Woa~ minh nghe ra mot tieng cam than nho xiu nhung vui ghe.",
            },
          ],
          metadata: {
            processing_time: 0.6,
            model: "glm-5",
            agent_type: "direct",
            routing_metadata: {
              method: "always_on_chatter_fast_path",
              intent: "social",
            },
          },
        }}
      />,
    );

    expect(interleavedPropsSpy).toHaveBeenCalled();
    expect(interleavedPropsSpy.mock.calls.at(-1)?.[0]).toMatchObject({
      showThinking: true,
    });
    expect(screen.queryByText("glm-5")).toBeNull();
  });

  it("hides the runtime model badge when backend marks metadata as non-authoritative", () => {
    render(
      <MessageBubble
        message={{
          id: "assistant-3",
          role: "assistant",
          content: "Minh da ve xong bieu do cho ban.",
          timestamp: "2026-03-25T09:00:00Z",
          blocks: [
            {
              type: "thinking",
              id: "thinking-3",
              summary: "Minh dang gom y chinh truoc khi chot.",
              content: "",
              toolCalls: [],
            },
            {
              type: "answer",
              id: "answer-3",
              content: "Minh da ve xong bieu do cho ban.",
            },
          ],
          metadata: {
            processing_time: 26.5,
            model: "gemini-3.1-flash-lite-preview",
            runtime_authoritative: false,
            agent_type: "direct",
          },
        }}
      />,
    );

    expect(screen.getByText("Tổng 26.5s")).toBeTruthy();
    expect(screen.queryByText("gemini-3.1-flash-lite-preview")).toBeNull();
  });
});
