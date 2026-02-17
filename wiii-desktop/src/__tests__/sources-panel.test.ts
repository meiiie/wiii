/**
 * Sprint 107: SourcesPanel + SourceCitation tests.
 * Tests store-level logic for sources panel open/close, selection.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useUIStore } from "@/stores/ui-store";
import { useChatStore } from "@/stores/chat-store";

beforeEach(() => {
  vi.clearAllMocks();
  useUIStore.setState({
    sidebarOpen: true,
    settingsOpen: false,
    sourcesPanelOpen: false,
    selectedSourceIndex: null,
    commandPaletteOpen: false,
  });
  useChatStore.setState({
    conversations: [],
    activeConversationId: null,
    isLoaded: false,
    isStreaming: false,
    streamingBlocks: [],
  });
});

describe("SourcesPanel — UI store state", () => {
  it("should start with panel closed", () => {
    expect(useUIStore.getState().sourcesPanelOpen).toBe(false);
    expect(useUIStore.getState().selectedSourceIndex).toBeNull();
  });

  it("should toggle panel open", () => {
    useUIStore.getState().toggleSourcesPanel();
    expect(useUIStore.getState().sourcesPanelOpen).toBe(true);
  });

  it("should toggle panel closed", () => {
    useUIStore.setState({ sourcesPanelOpen: true });
    useUIStore.getState().toggleSourcesPanel();
    expect(useUIStore.getState().sourcesPanelOpen).toBe(false);
  });

  it("should select a source by index", () => {
    useUIStore.getState().selectSource(2);
    expect(useUIStore.getState().selectedSourceIndex).toBe(2);
  });

  it("should deselect source with null", () => {
    useUIStore.setState({ selectedSourceIndex: 1 });
    useUIStore.getState().selectSource(null);
    expect(useUIStore.getState().selectedSourceIndex).toBeNull();
  });

  it("should close panel in closeAll", () => {
    useUIStore.setState({ sourcesPanelOpen: true, selectedSourceIndex: 0 });
    useUIStore.getState().closeAll();
    expect(useUIStore.getState().sourcesPanelOpen).toBe(false);
  });
});

describe("SourceCitation — click behavior simulation", () => {
  it("should open panel and select source on badge click", () => {
    // Simulate what SourceCitation.handleClick does
    const index = 1;
    useUIStore.getState().selectSource(index);
    if (!useUIStore.getState().sourcesPanelOpen) {
      useUIStore.getState().toggleSourcesPanel();
    }
    expect(useUIStore.getState().sourcesPanelOpen).toBe(true);
    expect(useUIStore.getState().selectedSourceIndex).toBe(1);
  });

  it("should not re-toggle if panel already open", () => {
    useUIStore.setState({ sourcesPanelOpen: true });
    const index = 0;
    useUIStore.getState().selectSource(index);
    // Panel already open, don't toggle
    if (!useUIStore.getState().sourcesPanelOpen) {
      useUIStore.getState().toggleSourcesPanel();
    }
    expect(useUIStore.getState().sourcesPanelOpen).toBe(true);
    expect(useUIStore.getState().selectedSourceIndex).toBe(0);
  });

  it("should handle selecting different sources sequentially", () => {
    useUIStore.getState().selectSource(0);
    expect(useUIStore.getState().selectedSourceIndex).toBe(0);
    useUIStore.getState().selectSource(2);
    expect(useUIStore.getState().selectedSourceIndex).toBe(2);
    useUIStore.getState().selectSource(1);
    expect(useUIStore.getState().selectedSourceIndex).toBe(1);
  });
});

describe("SourcesPanel — source data from chat store", () => {
  it("should find sources from last assistant message", () => {
    const sources = [
      { title: "COLREGs Rule 15", content: "Crossing situation...", page_number: 15 },
      { title: "SOLAS Chapter II", content: "Fire safety...", page_number: 42 },
    ];
    useChatStore.setState({
      conversations: [
        {
          id: "conv-1",
          title: "Test",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          messages: [
            { id: "m1", role: "user", content: "Hello", timestamp: "2026-01-01T00:00:00Z" },
            {
              id: "m2",
              role: "assistant",
              content: "Here's the answer",
              timestamp: "2026-01-01T00:00:01Z",
              sources,
            },
          ],
        },
      ],
      activeConversationId: "conv-1",
    });

    // Simulate what SourcesPanel does to find sources
    const conv = useChatStore.getState().activeConversation();
    let foundSources: Array<{ title: string; content: string; page_number?: number }> = [];
    if (conv) {
      for (let i = conv.messages.length - 1; i >= 0; i--) {
        const msg = conv.messages[i];
        if (msg.role === "assistant" && msg.sources && msg.sources.length > 0) {
          foundSources = msg.sources;
          break;
        }
      }
    }
    expect(foundSources).toHaveLength(2);
    expect(foundSources[0].title).toBe("COLREGs Rule 15");
  });

  it("should return empty when no assistant messages have sources", () => {
    useChatStore.setState({
      conversations: [
        {
          id: "conv-1",
          title: "Test",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          messages: [
            { id: "m1", role: "user", content: "Hello", timestamp: "2026-01-01T00:00:00Z" },
            { id: "m2", role: "assistant", content: "Hi!", timestamp: "2026-01-01T00:00:01Z" },
          ],
        },
      ],
      activeConversationId: "conv-1",
    });

    const conv = useChatStore.getState().activeConversation();
    let foundSources: unknown[] = [];
    if (conv) {
      for (let i = conv.messages.length - 1; i >= 0; i--) {
        const msg = conv.messages[i];
        if (msg.role === "assistant" && msg.sources && msg.sources.length > 0) {
          foundSources = msg.sources;
          break;
        }
      }
    }
    expect(foundSources).toHaveLength(0);
  });

  it("should return empty when no active conversation", () => {
    useChatStore.setState({
      conversations: [],
      activeConversationId: null,
    });
    const conv = useChatStore.getState().activeConversation();
    expect(conv).toBeUndefined();
  });

  it("should find sources from latest message, not older ones", () => {
    useChatStore.setState({
      conversations: [
        {
          id: "conv-1",
          title: "Test",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          messages: [
            { id: "m1", role: "user", content: "Q1", timestamp: "2026-01-01T00:00:00Z" },
            {
              id: "m2",
              role: "assistant",
              content: "A1",
              timestamp: "2026-01-01T00:00:01Z",
              sources: [{ title: "Old Source", content: "old" }],
            },
            { id: "m3", role: "user", content: "Q2", timestamp: "2026-01-01T00:00:02Z" },
            {
              id: "m4",
              role: "assistant",
              content: "A2",
              timestamp: "2026-01-01T00:00:03Z",
              sources: [{ title: "New Source", content: "new" }],
            },
          ],
        },
      ],
      activeConversationId: "conv-1",
    });

    const conv = useChatStore.getState().activeConversation();
    let foundSources: Array<{ title: string; content: string }> = [];
    if (conv) {
      for (let i = conv.messages.length - 1; i >= 0; i--) {
        const msg = conv.messages[i];
        if (msg.role === "assistant" && msg.sources && msg.sources.length > 0) {
          foundSources = msg.sources;
          break;
        }
      }
    }
    expect(foundSources[0].title).toBe("New Source");
  });
});
