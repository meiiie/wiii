/**
 * Unit tests for Sprint 167: "Không Gian Sáng Tạo" — Artifact System.
 * Tests store logic, type shapes, SSE handler integration, and UI store.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "@/stores/chat-store";
import { useUIStore } from "@/stores/ui-store";
import type {
  ContentBlock,
  ArtifactData,
  ArtifactBlockData,
  ArtifactType,
} from "@/api/types";

// =============================================================================
// Helpers
// =============================================================================

function makeArtifact(overrides?: Partial<ArtifactData>): ArtifactData {
  return {
    artifact_type: "code",
    artifact_id: `art-${Math.random().toString(36).slice(2, 8)}`,
    title: "Test Artifact",
    content: "print('hello')",
    language: "python",
    metadata: {},
    ...overrides,
  };
}

function getBlocks(): ContentBlock[] {
  return useChatStore.getState().streamingBlocks;
}

function getArtifacts(): ArtifactData[] {
  return useChatStore.getState().streamingArtifacts;
}

function findArtifactBlocks(blocks: ContentBlock[]): ArtifactBlockData[] {
  return blocks.filter((b) => b.type === "artifact") as ArtifactBlockData[];
}

// =============================================================================
// Reset
// =============================================================================

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
    streamingPreviews: [],
    streamingArtifacts: [],
    _activeSubagentGroupId: null,
    streamError: "",
    streamCompletedAt: null,
  });

  useUIStore.setState({
    sidebarOpen: true,
    previewPanelOpen: false,
    sourcePanelOpen: false,
    artifactPanelOpen: false,
    selectedArtifactId: null,
    artifactActiveTab: "code",
  });
});

// =============================================================================
// 1. ArtifactData type shape (7 tests)
// =============================================================================
describe("ArtifactData — Type Shape", () => {
  it("creates code artifact with all fields", () => {
    const art = makeArtifact({ artifact_type: "code", language: "python" });
    expect(art.artifact_type).toBe("code");
    expect(art.language).toBe("python");
    expect(art.content).toBeTruthy();
    expect(art.artifact_id).toBeTruthy();
  });

  it("creates html artifact", () => {
    const art = makeArtifact({ artifact_type: "html", content: "<h1>Hi</h1>" });
    expect(art.artifact_type).toBe("html");
    expect(art.content).toContain("<h1>");
  });

  it("creates react artifact", () => {
    const art = makeArtifact({ artifact_type: "react", content: "export default () => <div/>" });
    expect(art.artifact_type).toBe("react");
  });

  it("creates table artifact with JSON content", () => {
    const data = JSON.stringify([{ name: "A", value: 1 }]);
    const art = makeArtifact({ artifact_type: "table", content: data });
    expect(art.artifact_type).toBe("table");
    expect(JSON.parse(art.content)).toHaveLength(1);
  });

  it("creates chart artifact with metadata", () => {
    const art = makeArtifact({
      artifact_type: "chart",
      metadata: { image_url: "data:image/png;base64,abc" },
    });
    expect(art.artifact_type).toBe("chart");
    expect(art.metadata?.image_url).toContain("base64");
  });

  it("creates document artifact", () => {
    const art = makeArtifact({ artifact_type: "document", content: "# Hello" });
    expect(art.artifact_type).toBe("document");
  });

  it("creates excel artifact", () => {
    const art = makeArtifact({ artifact_type: "excel", content: '[{"col":"val"}]' });
    expect(art.artifact_type).toBe("excel");
  });

  it("all 7 artifact types are valid", () => {
    const types: ArtifactType[] = ["code", "html", "react", "table", "chart", "document", "excel"];
    types.forEach((t) => {
      const art = makeArtifact({ artifact_type: t });
      expect(art.artifact_type).toBe(t);
    });
  });

  it("metadata fields are optional", () => {
    const art = makeArtifact({ metadata: undefined });
    expect(art.metadata).toBeUndefined();
  });

  it("execution_status tracks lifecycle", () => {
    const statuses = ["pending", "running", "success", "error"] as const;
    statuses.forEach((s) => {
      const art = makeArtifact({ metadata: { execution_status: s } });
      expect(art.metadata?.execution_status).toBe(s);
    });
  });
});

// =============================================================================
// 2. Chat Store — addArtifact (10 tests)
// =============================================================================
describe("ChatStore — addArtifact", () => {
  it("adds artifact to streamingArtifacts", () => {
    const art = makeArtifact();
    useChatStore.getState().addArtifact(art, "tutor_agent");
    expect(getArtifacts()).toHaveLength(1);
    expect(getArtifacts()[0].artifact_id).toBe(art.artifact_id);
  });

  it("creates ArtifactBlockData in streamingBlocks", () => {
    const art = makeArtifact();
    useChatStore.getState().addArtifact(art, "tutor_agent");
    const blocks = findArtifactBlocks(getBlocks());
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("artifact");
    expect(blocks[0].artifact.artifact_id).toBe(art.artifact_id);
    expect(blocks[0].node).toBe("tutor_agent");
  });

  it("deduplicates by artifact_id", () => {
    const art = makeArtifact({ artifact_id: "dup-001" });
    useChatStore.getState().addArtifact(art, "agent1");
    useChatStore.getState().addArtifact(art, "agent1");
    expect(getArtifacts()).toHaveLength(1);
    expect(findArtifactBlocks(getBlocks())).toHaveLength(1);
  });

  it("allows multiple different artifacts", () => {
    useChatStore.getState().addArtifact(makeArtifact({ artifact_id: "a1" }), "agent");
    useChatStore.getState().addArtifact(makeArtifact({ artifact_id: "a2" }), "agent");
    useChatStore.getState().addArtifact(makeArtifact({ artifact_id: "a3" }), "agent");
    expect(getArtifacts()).toHaveLength(3);
    expect(findArtifactBlocks(getBlocks())).toHaveLength(3);
  });

  it("node is optional (defaults to undefined)", () => {
    const art = makeArtifact();
    useChatStore.getState().addArtifact(art);
    const blocks = findArtifactBlocks(getBlocks());
    expect(blocks[0].node).toBeUndefined();
  });

  it("preserves artifact content integrity", () => {
    const code = 'import pandas as pd\ndf = pd.DataFrame({"a": [1,2,3]})\nprint(df)';
    const art = makeArtifact({ content: code, language: "python" });
    useChatStore.getState().addArtifact(art, "tutor");
    expect(getArtifacts()[0].content).toBe(code);
  });

  it("handles artifact with empty metadata", () => {
    const art = makeArtifact({ metadata: {} });
    useChatStore.getState().addArtifact(art, "agent");
    expect(getArtifacts()[0].metadata).toEqual({});
  });

  it("handles artifact with rich metadata", () => {
    const art = makeArtifact({
      metadata: {
        execution_status: "success",
        output: "Hello World\n",
        image_url: "data:image/png;base64,abc123",
        table_data: [{ x: 1 }],
      },
    });
    useChatStore.getState().addArtifact(art, "agent");
    const stored = getArtifacts()[0];
    expect(stored.metadata?.execution_status).toBe("success");
    expect(stored.metadata?.output).toBe("Hello World\n");
    expect(stored.metadata?.image_url).toContain("base64");
  });
});

// =============================================================================
// 3. Chat Store — startStreaming resets artifacts (3 tests)
// =============================================================================
describe("ChatStore — Streaming Reset", () => {
  it("startStreaming clears streamingArtifacts", () => {
    // Pre-fill
    useChatStore.setState({ streamingArtifacts: [makeArtifact()] });
    expect(getArtifacts()).toHaveLength(1);

    useChatStore.getState().startStreaming();
    expect(getArtifacts()).toHaveLength(0);
  });

  it("clearStreaming clears streamingArtifacts", () => {
    useChatStore.setState({ streamingArtifacts: [makeArtifact()] });
    useChatStore.getState().clearStreaming();
    expect(getArtifacts()).toHaveLength(0);
  });

  it("setStreamError clears streamingArtifacts", () => {
    // setStreamError requires activeConversationId to proceed
    const convId = useChatStore.getState().createConversation();
    useChatStore.getState().setActiveConversation(convId);
    useChatStore.setState({ streamingArtifacts: [makeArtifact()] });
    useChatStore.getState().setStreamError("test error");
    expect(getArtifacts()).toHaveLength(0);
  });
});

// =============================================================================
// 4. Chat Store — finalizeStream persists artifacts (3 tests)
// =============================================================================
describe("ChatStore — finalizeStream Artifacts", () => {
  function setupConversationWithStreaming() {
    const convId = useChatStore.getState().createConversation();
    useChatStore.getState().setActiveConversation(convId);
    useChatStore.getState().addUserMessage("Write code");
    useChatStore.getState().startStreaming();
    return convId;
  }

  it("persists streamingArtifacts to message.artifacts", () => {
    const convId = setupConversationWithStreaming();
    const art1 = makeArtifact({ artifact_id: "fin-1" });
    const art2 = makeArtifact({ artifact_id: "fin-2" });
    useChatStore.getState().addArtifact(art1, "agent");
    useChatStore.getState().addArtifact(art2, "agent");

    useChatStore.getState().finalizeStream();

    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    const lastMsg = conv?.messages[conv.messages.length - 1];
    expect(lastMsg?.artifacts).toHaveLength(2);
    expect(lastMsg?.artifacts?.[0].artifact_id).toBe("fin-1");
    expect(lastMsg?.artifacts?.[1].artifact_id).toBe("fin-2");
  });

  it("finalizeStream clears streamingArtifacts after persist", () => {
    setupConversationWithStreaming();
    useChatStore.getState().addArtifact(makeArtifact(), "agent");
    useChatStore.getState().finalizeStream();
    expect(getArtifacts()).toHaveLength(0);
  });

  it("no artifacts when none were streamed", () => {
    const convId = setupConversationWithStreaming();
    useChatStore.getState().appendStreamingContent("Just text");
    useChatStore.getState().finalizeStream();

    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    const lastMsg = conv?.messages[conv.messages.length - 1];
    // artifacts should be empty array or undefined
    expect(lastMsg?.artifacts?.length ?? 0).toBe(0);
  });
});

// =============================================================================
// 5. UI Store — Artifact Panel (8 tests)
// =============================================================================
describe("UIStore — Artifact Panel", () => {
  it("openArtifact sets panel open and selectedId", () => {
    useUIStore.getState().openArtifact("art-123");
    const state = useUIStore.getState();
    expect(state.artifactPanelOpen).toBe(true);
    expect(state.selectedArtifactId).toBe("art-123");
  });

  it("openArtifact closes preview panel (mutual exclusion)", () => {
    useUIStore.setState({ previewPanelOpen: true });
    useUIStore.getState().openArtifact("art-123");
    expect(useUIStore.getState().previewPanelOpen).toBe(false);
  });

  it("openArtifact closes sources panel (mutual exclusion)", () => {
    useUIStore.setState({ sourcesPanelOpen: true });
    useUIStore.getState().openArtifact("art-123");
    expect(useUIStore.getState().sourcesPanelOpen).toBe(false);
  });

  it("closeArtifact resets panel state", () => {
    useUIStore.getState().openArtifact("art-123");
    useUIStore.getState().closeArtifact();
    const state = useUIStore.getState();
    expect(state.artifactPanelOpen).toBe(false);
    expect(state.selectedArtifactId).toBeNull();
  });

  it("setArtifactTab changes active tab", () => {
    useUIStore.getState().setArtifactTab("preview");
    expect(useUIStore.getState().artifactActiveTab).toBe("preview");
    useUIStore.getState().setArtifactTab("output");
    expect(useUIStore.getState().artifactActiveTab).toBe("output");
    useUIStore.getState().setArtifactTab("code");
    expect(useUIStore.getState().artifactActiveTab).toBe("code");
  });

  it("default tab is code", () => {
    expect(useUIStore.getState().artifactActiveTab).toBe("code");
  });

  it("opening new artifact switches selectedId", () => {
    useUIStore.getState().openArtifact("art-1");
    expect(useUIStore.getState().selectedArtifactId).toBe("art-1");
    useUIStore.getState().openArtifact("art-2");
    expect(useUIStore.getState().selectedArtifactId).toBe("art-2");
  });

  it("closeAll closes artifact panel", () => {
    useUIStore.getState().openArtifact("art-1");
    useUIStore.getState().closeAll();
    expect(useUIStore.getState().artifactPanelOpen).toBe(false);
  });
});

// =============================================================================
// 6. Integration: addArtifact + openArtifact flow (3 tests)
// =============================================================================
describe("Integration — Artifact Flow", () => {
  it("add artifact then open artifact panel", () => {
    const art = makeArtifact({ artifact_id: "flow-1", title: "My Code" });
    useChatStore.getState().addArtifact(art, "tutor_agent");
    useUIStore.getState().openArtifact("flow-1");

    expect(getArtifacts()).toHaveLength(1);
    expect(useUIStore.getState().artifactPanelOpen).toBe(true);
    expect(useUIStore.getState().selectedArtifactId).toBe("flow-1");
  });

  it("multiple artifacts can be added, any can be opened", () => {
    const arts = ["a1", "a2", "a3"].map((id) =>
      makeArtifact({ artifact_id: id, title: `Art ${id}` })
    );
    arts.forEach((a) => useChatStore.getState().addArtifact(a, "agent"));

    useUIStore.getState().openArtifact("a2");
    expect(useUIStore.getState().selectedArtifactId).toBe("a2");

    useUIStore.getState().openArtifact("a3");
    expect(useUIStore.getState().selectedArtifactId).toBe("a3");
  });

  it("artifact blocks interleave with other block types", () => {
    useChatStore.getState().openThinkingBlock("Analyzing...");
    useChatStore.getState().appendThinkingDelta("thinking content");
    useChatStore.getState().closeThinkingBlock();

    useChatStore.getState().addArtifact(
      makeArtifact({ artifact_id: "interleave-1" }),
      "agent"
    );

    useChatStore.getState().appendStreamingContent("Some answer text");

    const blocks = getBlocks();
    const types = blocks.map((b) => b.type);
    expect(types).toContain("thinking");
    expect(types).toContain("artifact");
  });
});

// =============================================================================
// 7. Settings — show_artifacts (2 tests)
// =============================================================================
describe("Settings — show_artifacts", () => {
  it("defaults to true in settings", async () => {
    // Import dynamically to get fresh state
    const { useSettingsStore } = await import("@/stores/settings-store");
    const settings = useSettingsStore.getState().settings;
    expect(settings.show_artifacts).toBe(true);
  });

  it("can be toggled off", async () => {
    const { useSettingsStore } = await import("@/stores/settings-store");
    useSettingsStore.getState().updateSettings({ show_artifacts: false });
    expect(useSettingsStore.getState().settings.show_artifacts).toBe(false);
  });
});
