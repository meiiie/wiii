/**
 * Unit tests for ContextPanel + ContextTab logic (Sprint 105).
 * Tests store behavior, status computation, compact/clear with toasts.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useContextStore } from "@/stores/context-store";
import { useToastStore } from "@/stores/toast-store";

// Mock the API module
vi.mock("@/api/context", () => ({
  fetchContextInfo: vi.fn(),
  compactContext: vi.fn(),
  clearContext: vi.fn(),
}));

import * as contextApi from "@/api/context";

const mockInfo = {
  effective_window: 128000,
  max_output: 8192,
  total_budget: 32000,
  total_used: 21000,
  utilization: 65.6,
  needs_compaction: false,
  layers: {
    system_prompt: { budget: 4800, used: 4800 },
    core_memory: { budget: 1600, used: 1200 },
    summary: { budget: 3200, used: 2400 },
    recent_messages: { budget: 22400, used: 12600 },
  },
  messages_included: 21,
  messages_dropped: 24,
  has_summary: true,
  session_id: "test-session",
  running_summary_chars: 850,
  total_history_messages: 45,
};

beforeEach(() => {
  vi.clearAllMocks();
  useContextStore.setState({
    info: null,
    status: "unknown",
    isLoading: false,
    isPanelOpen: false,
    error: null,
    pollIntervalId: null,
  });
  useToastStore.setState({ toasts: [] });
});

afterEach(() => {
  useContextStore.getState().stopPolling();
});

describe("Context Panel — Status Thresholds", () => {
  it("should be green when utilization < 50%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      utilization: 10,
    });

    await useContextStore.getState().fetchContextInfo("s1");
    expect(useContextStore.getState().status).toBe("green");
  });

  it("should be green at utilization = 0%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      utilization: 0,
    });

    await useContextStore.getState().fetchContextInfo("s1");
    expect(useContextStore.getState().status).toBe("green");
  });

  it("should be yellow when utilization = 50%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      utilization: 50,
    });

    await useContextStore.getState().fetchContextInfo("s1");
    expect(useContextStore.getState().status).toBe("yellow");
  });

  it("should be yellow when utilization = 74%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      utilization: 74,
    });

    await useContextStore.getState().fetchContextInfo("s1");
    expect(useContextStore.getState().status).toBe("yellow");
  });

  it("should be orange when utilization = 75%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      utilization: 75,
    });

    await useContextStore.getState().fetchContextInfo("s1");
    expect(useContextStore.getState().status).toBe("orange");
  });

  it("should be orange when utilization = 89%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      utilization: 89,
    });

    await useContextStore.getState().fetchContextInfo("s1");
    expect(useContextStore.getState().status).toBe("orange");
  });

  it("should be red when utilization = 90%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      utilization: 90,
    });

    await useContextStore.getState().fetchContextInfo("s1");
    expect(useContextStore.getState().status).toBe("red");
  });

  it("should be red when utilization = 100%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      utilization: 100,
    });

    await useContextStore.getState().fetchContextInfo("s1");
    expect(useContextStore.getState().status).toBe("red");
  });
});

describe("Context Panel — Compact with Refresh", () => {
  it("should compact then refresh info", async () => {
    vi.mocked(contextApi.compactContext).mockResolvedValue({
      status: "compacted",
      session_id: "s1",
      summary_length: 300,
      messages_summarized: 10,
      message: "Done",
    });
    const compactedInfo = { ...mockInfo, utilization: 40 };
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(compactedInfo);

    await useContextStore.getState().compact("s1");

    expect(contextApi.compactContext).toHaveBeenCalledWith("s1");
    // fetchContextInfo called for refresh
    expect(contextApi.fetchContextInfo).toHaveBeenCalledWith("s1");
    expect(useContextStore.getState().status).toBe("green");
  });

  it("should handle compact error", async () => {
    vi.mocked(contextApi.compactContext).mockRejectedValue(
      new Error("Server error")
    );

    await useContextStore.getState().compact("s1");

    expect(useContextStore.getState().error).toBe("Server error");
    expect(useContextStore.getState().isLoading).toBe(false);
  });
});

describe("Context Panel — Clear Resets State", () => {
  it("should clear and reset to unknown", async () => {
    vi.mocked(contextApi.clearContext).mockResolvedValue({
      status: "cleared",
      session_id: "s1",
      message: "Cleared",
    });
    useContextStore.setState({ info: mockInfo, status: "yellow" });

    await useContextStore.getState().clear("s1");

    const state = useContextStore.getState();
    expect(state.info).toBeNull();
    expect(state.status).toBe("unknown");
  });

  it("should handle clear error", async () => {
    vi.mocked(contextApi.clearContext).mockRejectedValue(
      new Error("Forbidden")
    );

    await useContextStore.getState().clear("s1");

    expect(useContextStore.getState().error).toBe("Forbidden");
  });
});

describe("Context Panel — Empty Session Handling", () => {
  it("should skip fetch on empty sessionId", async () => {
    await useContextStore.getState().fetchContextInfo("");
    expect(contextApi.fetchContextInfo).not.toHaveBeenCalled();
  });

  it("should skip compact on empty sessionId", async () => {
    await useContextStore.getState().compact("");
    expect(contextApi.compactContext).not.toHaveBeenCalled();
  });

  it("should skip clear on empty sessionId", async () => {
    await useContextStore.getState().clear("");
    expect(contextApi.clearContext).not.toHaveBeenCalled();
  });
});

describe("Context Panel — Toggle", () => {
  it("should toggle panel open and close", () => {
    expect(useContextStore.getState().isPanelOpen).toBe(false);

    useContextStore.getState().togglePanel();
    expect(useContextStore.getState().isPanelOpen).toBe(true);

    useContextStore.getState().togglePanel();
    expect(useContextStore.getState().isPanelOpen).toBe(false);
  });

  it("should maintain info when toggling panel", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(mockInfo);
    await useContextStore.getState().fetchContextInfo("s1");

    useContextStore.getState().togglePanel();

    expect(useContextStore.getState().info).toEqual(mockInfo);
    expect(useContextStore.getState().isPanelOpen).toBe(true);
  });
});

describe("Context Panel — Needs Compaction Flag", () => {
  it("should report needs_compaction from API", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue({
      ...mockInfo,
      needs_compaction: true,
      utilization: 80,
    });

    await useContextStore.getState().fetchContextInfo("s1");

    expect(useContextStore.getState().info?.needs_compaction).toBe(true);
  });
});
