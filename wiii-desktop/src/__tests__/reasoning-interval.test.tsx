import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ThinkingBlockData, ToolExecutionBlockData } from "@/api/types";
import { ReasoningInterval, type ReasoningIntervalViewModel } from "@/components/chat/ReasoningInterval";
import { useCodeStudioStore } from "@/stores/code-studio-store";
import { useUIStore } from "@/stores/ui-store";

function resetStores() {
  useCodeStudioStore.setState({
    activeSessionId: null,
    sessions: {},
  });
  useUIStore.setState({
    activeView: "chat",
    sidebarOpen: true,
    sourcesPanelOpen: false,
    selectedSourceIndex: null,
    commandPaletteOpen: false,
    inputFocused: false,
    characterPanelOpen: false,
    previewPanelOpen: false,
    selectedPreviewId: null,
    artifactPanelOpen: false,
    selectedArtifactId: null,
    artifactActiveTab: "code",
    _ephemeralArtifact: null,
    orgManagerTargetOrgId: null,
    codeStudioPanelOpen: false,
  });
}

describe("ReasoningInterval", () => {
  beforeEach(() => {
    resetStores();
  });

  it("renders a Code Studio strip inline for tool_create_visual_code in balanced mode", () => {
    useCodeStudioStore.getState().openSession(
      "vs-code-1",
      "Pendulum App",
      "html",
      1,
      {
        studioLane: "app",
        artifactKind: "html_app",
        qualityProfile: "premium",
        rendererContract: "host_shell",
      },
    );
    useCodeStudioStore.getState().appendCode("vs-code-1", "<div>demo</div>", 0, 64);

    const thinkingBlock: ThinkingBlockData = {
      type: "thinking",
      id: "thinking-1",
      content: "Minh dang khau lai app tuong tac nay cho that muot.",
      toolCalls: [],
      summary: "Dang dung app",
    };

    const toolBlock: ToolExecutionBlockData = {
      type: "tool_execution",
      id: "tool-1",
      status: "pending",
      tool: {
        id: "tool-1",
        name: "tool_create_visual_code",
        args: {
          title: "Pendulum App",
          visual_session_id: "vs-code-1",
        },
        result: "Minh hoa da san sang: Pendulum App",
      },
    };

    const interval: ReasoningIntervalViewModel = {
      id: "interval-1",
      label: "Code Studio",
      isLive: true,
      items: [
        { kind: "thinking", id: "thinking-item", block: thinkingBlock },
        { kind: "tool", id: "tool-item", block: toolBlock },
      ],
      rawBlocks: [thinkingBlock, toolBlock],
    };

    render(
      <ReasoningInterval
        interval={interval}
        thinkingLevel="balanced"
        onOpenInspector={() => {}}
      />,
    );

    expect(useCodeStudioStore.getState().getActiveSessionContext()).toEqual({
      active_session: {
        session_id: "vs-code-1",
        title: "Pendulum App",
        status: "streaming",
        active_version: 1,
        version_count: 0,
        language: "html",
        studio_lane: "app",
        artifact_kind: "html_app",
        quality_profile: "premium",
        renderer_contract: "host_shell",
        has_preview: false,
      },
    });
    expect(document.querySelector(".code-studio-card")).toBeTruthy();
    expect(screen.getByText("Pendulum App")).toBeTruthy();
    expect(screen.queryByText(/html_app/i)).toBeNull();
    expect(screen.queryByText(/premium/i)).toBeNull();
  });
});
