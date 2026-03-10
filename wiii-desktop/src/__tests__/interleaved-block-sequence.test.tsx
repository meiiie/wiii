import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ContentBlock } from "@/api/types";
import { InterleavedBlockSequence } from "@/components/chat/InterleavedBlockSequence";

vi.mock("@/components/common/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div data-testid="answer-block">{content}</div>,
}));

vi.mock("@/components/chat/ThinkingBlock", () => ({
  ThinkingBlock: ({ content, continuation }: { content: string; continuation?: boolean }) => (
    <div data-testid="thinking-block" data-continuation={continuation ? "yes" : "no"}>
      {content}
    </div>
  ),
}));

vi.mock("@/components/chat/ActionText", () => ({
  ActionText: ({ content }: { content: string }) => <div data-testid="action-block">{content}</div>,
}));

vi.mock("@/components/chat/ScreenshotBlock", () => ({
  ScreenshotBlock: () => <div data-testid="screenshot-block">screenshot</div>,
}));

vi.mock("@/components/chat/SubagentGroup", () => ({
  SubagentGroup: () => <div data-testid="subagent-group">group</div>,
}));

vi.mock("@/components/chat/PreviewGroup", () => ({
  PreviewGroup: () => <div data-testid="preview-group">preview</div>,
}));

vi.mock("@/components/chat/ArtifactCard", () => ({
  ArtifactCard: ({ artifact }: { artifact: { title: string } }) => (
    <div data-testid="artifact-card">{artifact.title}</div>
  ),
}));

vi.mock("@/components/chat/ToolExecutionStrip", () => ({
  ToolExecutionStrip: ({ block }: { block: { tool: { name: string } } }) => (
    <div data-testid="tool-strip">{block.tool.name}</div>
  ),
}));

describe("InterleavedBlockSequence", () => {
  it("hides action bridges that duplicate adjacent thinking text", () => {
    const blocks: ContentBlock[] = [
      {
        type: "thinking",
        id: "t1",
        content: "Dang soi lai du lieu can bam.",
        summary: "Dang soi lai du lieu can bam.",
        toolCalls: [],
      },
      {
        type: "action_text",
        id: "a1",
        content: "Dang soi lai du lieu can bam.",
      },
      {
        type: "answer",
        id: "ans1",
        content: "Du lieu da du de chot cau tra loi.",
      },
    ];

    render(
      <InterleavedBlockSequence
        blocks={blocks}
        showThinking
      />,
    );

    expect(screen.getAllByTestId("thinking-block")).toHaveLength(1);
    expect(screen.queryByTestId("action-block")).toBeNull();
    expect(screen.getByTestId("answer-block")).toBeTruthy();
  });

  it("renders answer before artifact even when artifact arrives earlier in block order", () => {
    const blocks: ContentBlock[] = [
      {
        type: "artifact",
        id: "art-1",
        artifact: {
          artifact_id: "art-1",
          artifact_type: "html",
          title: "Landing page",
          content: "<html />",
          metadata: {},
        },
      },
      {
        type: "answer",
        id: "ans-1",
        content: "Minh da tao landing page cho ban.",
      },
    ];

    render(
      <InterleavedBlockSequence
        blocks={blocks}
        showThinking
      />,
    );

    const answer = screen.getByTestId("answer-block");
    const artifact = screen.getByTestId("artifact-card");
    const bodyText = document.body.textContent || "";
    expect(bodyText.indexOf(answer.textContent || "")).toBeLessThan(bodyText.indexOf(artifact.textContent || ""));
  });

  it("renders tool execution as a separate strip between thinking and answer", () => {
    const blocks: ContentBlock[] = [
      {
        type: "thinking",
        id: "t1",
        content: "Can goi cong cu de doi chieu.",
        toolCalls: [],
      },
      {
        type: "tool_execution",
        id: "tool-1",
        tool: { id: "tool-1", name: "tool_web_search" },
        status: "completed",
      },
      {
        type: "answer",
        id: "ans-1",
        content: "Minh da doi chieu xong va day la ket qua.",
      },
    ];

    render(
      <InterleavedBlockSequence
        blocks={blocks}
        showThinking
      />,
    );

    expect(screen.getByTestId("thinking-block")).toBeTruthy();
    expect(screen.getByTestId("tool-strip")).toBeTruthy();
    expect(screen.getByTestId("answer-block")).toBeTruthy();
  });

  it("marks post-tool thinking with the same step as a continuation instead of a fresh block", () => {
    const blocks: ContentBlock[] = [
      {
        type: "thinking",
        id: "t1",
        stepId: "step-1",
        label: "Chuan bi",
        content: "Can chuan bi du lieu.",
        toolCalls: [],
      },
      {
        type: "tool_execution",
        id: "tool-1",
        stepId: "step-1",
        tool: { id: "tool-1", name: "tool_execute_python" },
        status: "completed",
      },
      {
        type: "thinking",
        id: "t2",
        stepId: "step-1",
        label: "code_studio_agent",
        content: "Minh vua nhin lai ket qua chay code.",
        toolCalls: [],
      },
    ];

    render(
      <InterleavedBlockSequence
        blocks={blocks}
        showThinking
      />,
    );

    const thinkingBlocks = screen.getAllByTestId("thinking-block");
    expect(thinkingBlocks).toHaveLength(2);
    expect(thinkingBlocks[0]?.getAttribute("data-continuation")).toBe("no");
    expect(thinkingBlocks[1]?.getAttribute("data-continuation")).toBe("yes");
  });
});
