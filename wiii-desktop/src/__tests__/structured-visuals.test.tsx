import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { VisualPayload } from "@/api/types";
import { VisualBlock } from "@/components/chat/VisualBlock";
import { useChatStore } from "@/stores/chat-store";

vi.mock("@/components/common/InlineHtmlWidget", () => ({
  default: ({ code }: { code: string }) => <div data-testid="inline-widget">{code}</div>,
}));

vi.mock("@/components/common/InlineVisualFrame", () => ({
  InlineVisualFrame: ({ html }: { html: string }) => <div data-testid="inline-visual-frame">{html}</div>,
}));

vi.mock("@/components/common/EmbeddedAppFrame", () => ({
  EmbeddedAppFrame: ({ html }: { html: string }) => <div data-testid="embedded-app-frame">{html}</div>,
}));

function makeVisual(overrides?: Partial<VisualPayload>): VisualPayload {
  return {
    id: "visual-1",
    visual_session_id: "vs-1",
    type: "comparison",
    renderer_kind: "template",
    shell_variant: "editorial",
    patch_strategy: "spec_merge",
    figure_group_id: "fg-visual-1",
    figure_index: 1,
    figure_total: 1,
    pedagogical_role: "comparison",
    chrome_mode: "editorial",
    claim: "Dat hai co che canh nhau de doc nhanh trade-off.",
    narrative_anchor: "after-lead",
    runtime: "svg",
    title: "Softmax vs linear attention",
    summary: "Structured visual summary",
    spec: {
      left: {
        title: "Softmax",
        subtitle: "O(n^2)",
        items: ["Full matrix", "High memory"],
      },
      right: {
        title: "Linear",
        subtitle: "O(n)",
        items: ["Running state", "Cheaper memory"],
      },
    },
    scene: {
      kind: "comparison",
      nodes: [
        { id: "left", label: "Softmax" },
        { id: "right", label: "Linear" },
      ],
      panels: [],
    },
    controls: [
      {
        id: "focus_side",
        type: "chips",
        label: "Focus",
        value: "both",
        options: [
          { value: "both", label: "Both" },
          { value: "left", label: "Softmax" },
          { value: "right", label: "Linear" },
        ],
      },
    ],
    annotations: [
      {
        id: "takeaway",
        title: "Takeaway",
        body: "Linear attention keeps a compact running state.",
      },
    ],
    interaction_mode: "filterable",
    ephemeral: true,
    lifecycle_event: "visual_open",
    ...overrides,
  };
}

function seedPersistedVisualConversation(visual: VisualPayload) {
  useChatStore.setState({
    activeConversationId: "conv-1",
    conversations: [
      {
        id: "conv-1",
        title: "Visual thread",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [
          {
            id: "assistant-1",
            role: "assistant",
            content: "Original explanation",
            timestamp: new Date().toISOString(),
            blocks: [
              {
                type: "visual",
                id: visual.visual_session_id,
                sessionId: visual.visual_session_id,
                visual,
                node: "direct",
                status: "committed",
              },
            ],
          },
        ],
      },
    ],
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: false,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

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
    streamingPreviews: [],
    streamingArtifacts: [],
    pendingStreamMetadata: null,
    visualSessions: {},
    _activeSubagentGroupId: null,
    streamError: "",
    streamCompletedAt: null,
  });
});

describe("Structured visuals", () => {
  it("adds a structured visual block to the streaming store", () => {
    const visual = makeVisual();

    useChatStore.getState().addVisual(visual, "direct");

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({
      type: "visual",
      id: visual.visual_session_id,
      sessionId: visual.visual_session_id,
      node: "direct",
      status: "open",
      displayRole: "artifact",
      presentation: "compact",
    });
  });

  it("patches an existing visual block by session id", () => {
    useChatStore.getState().openVisualSession(makeVisual(), "direct");
    useChatStore.getState().patchVisualSession(
      makeVisual({
        id: "visual-2",
        title: "Updated title",
        summary: "Updated summary",
        lifecycle_event: "visual_patch",
      }),
      "tutor_agent",
    );

    const blocks = useChatStore.getState().streamingBlocks;
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({
      type: "visual",
      node: "tutor_agent",
      status: "open",
    });
    expect((blocks[0] as { visual: VisualPayload }).visual.title).toBe("Updated title");
    expect(useChatStore.getState().visualSessions["vs-1"]?.revisionCount).toBe(2);
  });

  it("patches a persisted visual block in place without creating a streaming duplicate", () => {
    seedPersistedVisualConversation(makeVisual());

    useChatStore.getState().patchVisualSession(
      makeVisual({
        id: "visual-2",
        type: "process",
        title: "Patched process visual",
        summary: "Process summary",
        spec: {
          steps: [
            { title: "Step 1", description: "Transform" },
            { title: "Step 2", description: "Approximate" },
            { title: "Step 3", description: "Aggregate" },
          ],
        },
        lifecycle_event: "visual_patch",
      }),
      "direct",
    );

    const state = useChatStore.getState();
    expect(state.streamingBlocks).toHaveLength(0);

    const conversation = state.conversations.find((item) => item.id === "conv-1");
    const visualBlocks = (conversation?.messages[0]?.blocks || []).filter((block) => block.type === "visual");
    expect(visualBlocks).toHaveLength(1);
    expect((visualBlocks[0] as { visual: VisualPayload }).visual.title).toBe("Patched process visual");
    expect((visualBlocks[0] as { visual: VisualPayload }).visual.type).toBe("process");
  });

  it("keeps a follow-up patch on the original visual block after finalizing the next assistant message", () => {
    const originalVisual = makeVisual();
    seedPersistedVisualConversation(originalVisual);

    const store = useChatStore.getState();
    store.startStreaming();
    store.patchVisualSession(
      makeVisual({
        id: "visual-3",
        type: "process",
        title: "Patched process visual",
        summary: "Process summary",
        spec: {
          steps: [
            { title: "Step 1", description: "Transform" },
            { title: "Step 2", description: "Approximate" },
            { title: "Step 3", description: "Aggregate" },
          ],
        },
        lifecycle_event: "visual_patch",
      }),
      "direct",
    );
    store.appendStreamingContent("Updated takeaway");
    store.finalizeStream({
      processing_time: 1.2,
      model: "gemini-test",
      agent_type: "chat",
    });

    const conversation = useChatStore.getState().conversations.find((item) => item.id === "conv-1");
    const allVisualBlocks = (conversation?.messages || [])
      .flatMap((message) => message.blocks || [])
      .filter((block) => block.type === "visual");

    expect(allVisualBlocks).toHaveLength(1);
    expect((allVisualBlocks[0] as { visual: VisualPayload }).visual.title).toBe("Patched process visual");
    expect(conversation?.messages).toHaveLength(2);
    expect(conversation?.messages[1]?.content).toContain("Updated takeaway");
    expect((conversation?.messages[1]?.blocks || []).some((block) => block.type === "visual")).toBe(false);
  });

  it("commits and disposes visual sessions", () => {
    useChatStore.getState().openVisualSession(makeVisual(), "direct");
    useChatStore.getState().commitVisualSession("vs-1");
    expect(useChatStore.getState().visualSessions["vs-1"]?.status).toBe("committed");

    useChatStore.getState().disposeVisualSession("vs-1");
    expect(useChatStore.getState().visualSessions["vs-1"]?.status).toBe("disposed");
  });

  it("renders structured svg visuals with an accessible label", async () => {
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");
    const visual = makeVisual();

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);
    const shell = screen.getByTestId("visual-block");

    expect(screen.getByText("Softmax vs linear attention")).toBeTruthy();
    expect(screen.getAllByText("Softmax").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Linear").length).toBeGreaterThan(0);
    expect(screen.getByText("Xem phan")).toBeTruthy();
    expect(screen.queryByText("Structured visual summary", { selector: "p" })).toBeNull();
    expect(screen.queryByText("template")).toBeNull();
    expect(screen.queryByText("spec_merge")).toBeNull();
    expect(screen.queryByText("filterable")).toBeNull();
    expect(screen.queryByText(/inline visual/i)).toBeNull();
    expect(shell.getAttribute("data-visual-lifecycle")).toBe("visual_open");

    await waitFor(() => {
      expect(shell.getAttribute("data-visual-cue")).toBe("open");
      expect(dispatchSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "wiii:visual-telemetry",
          detail: expect.objectContaining({
            name: "visual_rendered",
            visual_id: visual.id,
          }),
        }),
      );
    });
  });

  it("uses the article-style shell when an embedded visual is rendered inline with prose", () => {
    const visual = makeVisual({
      summary: "Linear attention keeps a compact running state and avoids a full n x n matrix.",
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} embedded />);

    const shell = screen.getByTestId("visual-block");
    const lede = shell.querySelector(".visual-block-shell__lede");
    expect(shell.getAttribute("data-visual-embedded")).toBe("true");
    expect(shell.className).toContain("visual-block-shell--embedded");
    expect(lede).toBeTruthy();
    expect(lede?.textContent || "").toMatch(/compact running state/i);
  });

  it("renders process visuals as a sequenced flow with a persistent callout", () => {
    const visual = makeVisual({
      type: "process",
      title: "Linear attention flow",
      summary: "Process summary",
      spec: {
        steps: [
          { title: "Project", description: "Project q, k, v into a compact feature space." },
          { title: "Accumulate", description: "Update the running state instead of storing the full matrix." },
          { title: "Emit", description: "Read the answer from the compact state.", signals: ["Running state", "No full matrix"] },
        ],
      },
      controls: [
        {
          id: "current_step",
          type: "range",
          label: "Step",
          value: 3,
          min: 1,
          max: 3,
          step: 1,
        },
      ],
      annotations: [],
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    expect(screen.getByText("Dong chay tung buoc")).toBeTruthy();
    expect(screen.getAllByText("Project").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Accumulate").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Emit").length).toBeGreaterThan(0);
    expect(screen.getByText("Diem can chu y")).toBeTruthy();
    expect(screen.getByText("Running state")).toBeTruthy();
  });

  it("routes app visuals to the embedded app frame", async () => {
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");
    const visual = makeVisual({
      type: "simulation",
      renderer_kind: "app",
      shell_variant: "immersive",
      patch_strategy: "app_state",
      runtime: "sandbox_html",
      fallback_html: "<div>Sandbox fallback</div>",
      controls: [],
      annotations: [],
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    expect(screen.getByTestId("embedded-app-frame").textContent).toContain("Sandbox fallback");

    await waitFor(() => {
      expect(dispatchSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "wiii:visual-telemetry",
          detail: expect.objectContaining({
            name: "visual_rendered",
            visual_id: visual.id,
          }),
        }),
      );
    });
  });

  it("renders architecture visuals as connected layers", () => {
    const visual = makeVisual({
      type: "architecture",
      title: "Layered AI stack",
      summary: "Architecture summary",
      spec: {
        layers: [
          { name: "Interface", components: ["Chat UI", "Controls"], description: "Nhap, doc va dieu huong." },
          { name: "Runtime", components: ["React", "SVG"], description: "Render va patch visual." },
          { name: "Backend", components: ["FastAPI", "SSE"], description: "Sinh va stream payload." },
        ],
      },
      controls: [
        {
          id: "active_layer",
          type: "chips",
          label: "Layer focus",
          value: "all",
          options: [
            { value: "all", label: "All" },
            { value: "layer-1", label: "Interface" },
          ],
        },
      ],
      annotations: [],
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    expect(screen.getByText("Layered AI stack")).toBeTruthy();
    expect(screen.getAllByText("Interface").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Runtime").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Backend").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Lop nhap").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Vung dieu phoi").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Lop dau ra").length).toBeGreaterThan(0);
    expect(screen.getByText("Lop dang xem")).toBeTruthy();
  });

  it("renders concept visuals with a central idea and branches", () => {
    const visual = makeVisual({
      type: "concept",
      title: "Concept map",
      summary: "Concept summary",
      spec: {
        center: {
          title: "Linear attention",
          description: "Y tuong trung tam cua toan bo so do.",
        },
        branches: [
          { title: "Chi phi", items: ["O(N)", "Bo nho tuyen tinh"] },
          { title: "Danh doi", items: ["Xap xi softmax", "Mat mot phan do chinh xac"] },
        ],
      },
      controls: [
        {
          id: "active_branch",
          type: "chips",
          label: "Branch focus",
          value: "all",
          options: [
            { value: "all", label: "All" },
            { value: "branch-1", label: "Chi phi" },
          ],
        },
      ],
      annotations: [],
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    expect(screen.getByText("Y trung tam")).toBeTruthy();
    expect(screen.getByText("Linear attention")).toBeTruthy();
    expect(screen.getAllByText("Chi phi").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Danh doi").length).toBeGreaterThan(0);
    expect(screen.getByText("Nhanh dang xem")).toBeTruthy();
  });

  it("renders chart visuals with a stage, legend, and metrics", () => {
    const visual = makeVisual({
      type: "chart",
      title: "Inference latency trend",
      summary: "Chart summary",
      spec: {
        labels: ["Q1", "Q2", "Q3", "Q4"],
        datasets: [
          {
            label: "Latency",
            data: [12, 18, 10, 22],
          },
        ],
        caption: "Do tre tang manh o quy cuoi.",
      },
      controls: [
        {
          id: "chart_style",
          type: "chips",
          label: "Chart style",
          value: "line",
          options: [
            { value: "bar", label: "Bar" },
            { value: "line", label: "Line" },
            { value: "area", label: "Area" },
          ],
        },
      ],
      annotations: [],
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    expect(screen.getByText("Doc xu huong theo truc")).toBeTruthy();
    expect(screen.getAllByText("Latency").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Series").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Average").length).toBeGreaterThan(0);
    expect(screen.getByText("Gia tri cao nhat")).toBeTruthy();
    expect(screen.getByText("Do tre tang manh o quy cuoi.")).toBeTruthy();
  });

  it("renders timeline visuals with an active milestone callout", () => {
    const visual = makeVisual({
      type: "timeline",
      title: "Rollout timeline",
      summary: "Timeline summary",
      spec: {
        title: "Phat trien visual runtime",
        events: [
          { date: "Sprint 1", title: "Spec", description: "Chot payload va runtime contract." },
          { date: "Sprint 2", title: "Render", description: "Dua visual vao web streaming path." },
          { date: "Sprint 3", title: "Polish", description: "Nang shell va annotation flow." },
        ],
      },
      controls: [
        {
          id: "current_event",
          type: "range",
          label: "Current",
          value: 2,
          min: 1,
          max: 3,
          step: 1,
        },
      ],
      annotations: [],
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    expect(screen.getAllByText("Theo dong thoi gian").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Moc dang xem").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Tong moc").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dang mo").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Render").length).toBeGreaterThan(0);
  });

  it("renders map-lite visuals as focused regions with a side callout", () => {
    const visual = makeVisual({
      type: "map_lite",
      title: "Regional signal map",
      summary: "Map summary",
      spec: {
        title: "Diem nong theo khu vuc",
        regions: [
          { title: "North", description: "Luu luong on dinh." },
          { title: "Central", description: "Nhu cau tang nhanh.", items: ["Peak load", "Need buffer"] },
          { title: "South", description: "Can them giam sat." },
        ],
      },
      controls: [
        {
          id: "active_region",
          type: "chips",
          label: "Region",
          value: "region-2",
          options: [
            { value: "all", label: "All" },
            { value: "region-2", label: "Central" },
          ],
        },
      ],
      annotations: [],
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    expect(screen.getAllByText("Theo tung khu vuc").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Khu vuc dang xem").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Tong cum").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Central").length).toBeGreaterThan(0);
    expect(screen.getByText("Peak load")).toBeTruthy();
  });

  it("renders annotation focus as an editorial callout", () => {
    const visual = makeVisual({
      annotations: [
        {
          id: "takeaway",
          title: "Takeaway",
          body: "Linear attention keeps only a compact state.",
          tone: "accent",
        },
        {
          id: "tradeoff",
          title: "Trade-off",
          body: "Approximation can blur some exact softmax behavior.",
          tone: "warning",
        },
      ],
      scene: {
        kind: "comparison",
        nodes: [],
        panels: [
          {
            id: "panel-1",
            title: "Doc thu tu",
            body: "Bat dau tu chi phi, sau do moi den danh doi.",
          },
        ],
      },
    });

    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    fireEvent.click(screen.getByRole("button", { name: /Diem chot/i }));

    expect(screen.getByText("Linear attention keeps only a compact state.")).toBeTruthy();
    expect(screen.getByText("Goi y doc")).toBeTruthy();
    expect(screen.getByText("Bat dau tu chi phi, sau do moi den danh doi.")).toBeTruthy();
  });

  it("applies iframe bridge control events to the visual session", () => {
    const visual = makeVisual({
      renderer_kind: "inline_html",
      runtime: "sandbox_html",
      fallback_html: "<div>Inline visual</div>",
      controls: [
        {
          id: "focus_side",
          type: "chips",
          label: "Focus",
          value: "both",
          options: [
            { value: "both", label: "Both" },
            { value: "left", label: "Left" },
          ],
        },
      ],
      annotations: [],
    });

    useChatStore.getState().openVisualSession(visual, "direct");
    render(<VisualBlock block={{ type: "visual", id: visual.id, visual }} />);

    act(() => {
      window.dispatchEvent(new CustomEvent("wiii:visual-frame", {
        detail: {
          bridgeType: "control",
          sessionId: "vs-1",
          controlId: "focus_side",
          value: "left",
          focusedNodeId: "focus:left",
        },
      }));
    });

    const session = useChatStore.getState().visualSessions["vs-1"];
    expect(session?.controlValues.focus_side).toBe("left");
    expect(session?.focusedNodeId).toBe("focus:left");
  });
});
