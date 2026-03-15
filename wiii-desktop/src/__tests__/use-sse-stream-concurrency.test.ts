import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSSEStream } from "@/hooks/useSSEStream";
import { useChatStore } from "@/stores/chat-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useDomainStore } from "@/stores/domain-store";
import { useOrgStore } from "@/stores/org-store";
import { useContextStore } from "@/stores/context-store";
import { useCharacterStore } from "@/stores/character-store";
import { usePageContextStore } from "@/stores/page-context-store";
import { useHostContextStore } from "@/stores/host-context-store";
import type { VisualPayload } from "@/api/types";
import { sendMessageStream } from "@/api/chat";

vi.mock("@/api/chat", () => ({
  sendMessageStream: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  initClient: vi.fn(),
}));

vi.mock("@/lib/visual-telemetry", () => ({
  trackVisualTelemetry: vi.fn(),
}));

function makeVisual(overrides?: Partial<VisualPayload>): VisualPayload {
  return {
    id: "visual-patch-1",
    visual_session_id: "vs-1",
    type: "process",
    renderer_kind: "template",
    shell_variant: "editorial",
    patch_strategy: "spec_merge",
    figure_group_id: "fg-vs-1",
    figure_index: 1,
    figure_total: 1,
    pedagogical_role: "mechanism",
    chrome_mode: "editorial",
    claim: "Figure nay mo ta quy trinh duoc patch trong cung session.",
    narrative_anchor: "after-lead",
    runtime: "svg",
    title: "Patched process",
    summary: "Updated process visual",
    spec: {
      steps: [
        { title: "Step 1", description: "Transform inputs" },
        { title: "Step 2", description: "Aggregate efficiently" },
        { title: "Step 3", description: "Approximation error appears here" },
      ],
    },
    scene: { kind: "process", nodes: [], panels: [] },
    controls: [],
    annotations: [],
    interaction_mode: "guided",
    ephemeral: true,
    lifecycle_event: "visual_patch",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();

  useSettingsStore.setState((state) => ({
    ...state,
    settings: {
      ...state.settings,
      server_url: "http://127.0.0.1:8001",
      api_key: "local-dev-key",
      user_id: "sse-race-user",
      user_role: "admin",
      display_name: "SSE Race",
    },
    isLoaded: true,
  }));

  useDomainStore.setState({
    activeDomainId: "maritime",
    domains: [],
    isLoading: false,
    orgAllowedDomains: [],
  });

  useOrgStore.setState({
    activeOrgId: null,
    organizations: [],
    isLoading: false,
    multiTenantEnabled: false,
    subdomainOrgId: null,
    orgSettings: null,
    permissions: [],
    orgRole: null,
    adminContext: null,
  });

  useContextStore.setState({
    info: null,
    status: "unknown",
    isLoading: false,
    isPanelOpen: false,
    error: null,
    pollIntervalId: null,
  });

  useCharacterStore.getState().reset();
  usePageContextStore.getState().clear();
  useHostContextStore.getState().clear();

  useChatStore.setState({
    conversations: [],
    activeConversationId: null,
    isLoaded: true,
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
    streamingPreviews: [],
    streamingArtifacts: [],
    pendingStreamMetadata: null,
    visualSessions: {},
    _activeSubagentGroupId: null,
    streamError: "",
    streamCompletedAt: null,
  });
});

describe("useSSEStream concurrency", () => {
  it("does not let an aborted previous stream retry against the new controller", async () => {
    const sendMessageStreamMock = vi.mocked(sendMessageStream);

    sendMessageStreamMock.mockImplementationOnce(
      async (_request, _handlers, abortSignal) =>
        new Promise((_resolve, reject) => {
          if (abortSignal?.aborted) {
            reject(new DOMException("Aborted", "AbortError"));
            return;
          }
          abortSignal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );

    sendMessageStreamMock.mockImplementationOnce(async (_request, handlers) => {
      handlers.onVisualPatch?.({
        content: makeVisual(),
        node: "direct",
        display_role: "artifact",
        presentation: "compact",
      });
      handlers.onVisualCommit?.({
        content: {
          visual_session_id: "vs-1",
          status: "committed",
        },
        node: "direct",
        display_role: "artifact",
        presentation: "compact",
      });
      return {
        lastEventId: null,
        sawDone: true,
        eventOrder: ["visual_patch", "visual_commit", "done"],
      };
    });

    const { result } = renderHook(() => useSSEStream());

    let firstSend: Promise<void>;
    let secondSend: Promise<void>;

    await act(async () => {
      firstSend = result.current.sendMessage("First prompt");
      await Promise.resolve();
      secondSend = result.current.sendMessage("Follow-up patch");
      await Promise.allSettled([firstSend!, secondSend!]);
    });

    expect(sendMessageStreamMock).toHaveBeenCalledTimes(2);

    const conversation = useChatStore.getState().activeConversation();
    expect(conversation).toBeTruthy();

    const assistantMessages = conversation?.messages.filter((message) => message.role === "assistant") || [];
    expect(assistantMessages).toHaveLength(1);

    const visualBlocks = (assistantMessages[0]?.blocks || []).filter((block) => block.type === "visual");
    expect(visualBlocks).toHaveLength(1);
    expect((visualBlocks[0] as { visual: VisualPayload }).visual.title).toBe("Patched process");
    expect((visualBlocks[0] as { visual: VisualPayload }).visual.type).toBe("process");
    expect(useChatStore.getState().streamError).toBe("");
  });
});
