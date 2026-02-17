/**
 * Unit tests for context store (Sprint 80).
 * Tests context info fetching, status computation, compact, clear, polling.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useContextStore } from "@/stores/context-store";

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
});

afterEach(() => {
  // Clean up any polling intervals
  useContextStore.getState().stopPolling();
});

describe("Context Store — Status Computation", () => {
  it("should set green status when utilization < 50%", async () => {
    const lowInfo = { ...mockInfo, utilization: 30 };
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(lowInfo);

    await useContextStore.getState().fetchContextInfo("session-1");

    const state = useContextStore.getState();
    expect(state.status).toBe("green");
    expect(state.info).toEqual(lowInfo);
  });

  it("should set yellow status when utilization 50-75%", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(mockInfo);

    await useContextStore.getState().fetchContextInfo("session-1");

    expect(useContextStore.getState().status).toBe("yellow");
  });

  it("should set orange status when utilization 75-90%", async () => {
    const highInfo = { ...mockInfo, utilization: 82 };
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(highInfo);

    await useContextStore.getState().fetchContextInfo("session-1");

    expect(useContextStore.getState().status).toBe("orange");
  });

  it("should set red status when utilization >= 90%", async () => {
    const criticalInfo = { ...mockInfo, utilization: 95 };
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(criticalInfo);

    await useContextStore.getState().fetchContextInfo("session-1");

    expect(useContextStore.getState().status).toBe("red");
  });
});

describe("Context Store — Fetch", () => {
  it("should fetch context info successfully", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(mockInfo);

    await useContextStore.getState().fetchContextInfo("session-1");

    const state = useContextStore.getState();
    expect(state.info).toEqual(mockInfo);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
    expect(contextApi.fetchContextInfo).toHaveBeenCalledWith("session-1");
  });

  it("should handle fetch error", async () => {
    vi.mocked(contextApi.fetchContextInfo).mockRejectedValue(
      new Error("Network error")
    );

    await useContextStore.getState().fetchContextInfo("session-1");

    const state = useContextStore.getState();
    expect(state.error).toBe("Network error");
    expect(state.isLoading).toBe(false);
  });

  it("should skip fetch when sessionId is empty", async () => {
    await useContextStore.getState().fetchContextInfo("");

    expect(contextApi.fetchContextInfo).not.toHaveBeenCalled();
  });
});

describe("Context Store — Compact & Clear", () => {
  it("should compact and refresh", async () => {
    vi.mocked(contextApi.compactContext).mockResolvedValue({
      status: "compacted",
      session_id: "session-1",
      summary_length: 250,
      messages_summarized: 38,
      message: "Done",
    });
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(mockInfo);

    await useContextStore.getState().compact("session-1");

    expect(contextApi.compactContext).toHaveBeenCalledWith("session-1");
    expect(contextApi.fetchContextInfo).toHaveBeenCalledWith("session-1");
  });

  it("should clear context and reset state", async () => {
    vi.mocked(contextApi.clearContext).mockResolvedValue({
      status: "cleared",
      session_id: "session-1",
      message: "Cleared",
    });

    useContextStore.setState({ info: mockInfo, status: "yellow" });

    await useContextStore.getState().clear("session-1");

    const state = useContextStore.getState();
    expect(state.info).toBeNull();
    expect(state.status).toBe("unknown");
    expect(contextApi.clearContext).toHaveBeenCalledWith("session-1");
  });
});

describe("Context Store — Panel Toggle", () => {
  it("should toggle panel open/close", () => {
    expect(useContextStore.getState().isPanelOpen).toBe(false);

    useContextStore.getState().togglePanel();
    expect(useContextStore.getState().isPanelOpen).toBe(true);

    useContextStore.getState().togglePanel();
    expect(useContextStore.getState().isPanelOpen).toBe(false);
  });
});

describe("Context Store — Polling", () => {
  it("should start and stop polling", () => {
    vi.mocked(contextApi.fetchContextInfo).mockResolvedValue(mockInfo);

    useContextStore.getState().startPolling("session-1", 60000);

    expect(useContextStore.getState().pollIntervalId).not.toBeNull();
    expect(contextApi.fetchContextInfo).toHaveBeenCalledWith("session-1");

    useContextStore.getState().stopPolling();
    expect(useContextStore.getState().pollIntervalId).toBeNull();
  });
});
