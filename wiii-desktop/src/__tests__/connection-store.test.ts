import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { checkHealthMock } = vi.hoisted(() => ({
  checkHealthMock: vi.fn(),
}));

vi.mock("@/api/health", () => ({
  checkHealth: checkHealthMock,
}));

import { useConnectionStore } from "@/stores/connection-store";

function resetConnectionStore() {
  useConnectionStore.getState().stopPolling();
  useConnectionStore.setState({
    status: "checking",
    isChecking: false,
    serverVersion: null,
    lastCheckedAt: null,
    errorMessage: null,
    consecutiveFailures: 0,
    pollIntervalId: null,
    onReconnect: null,
  });
}

describe("connection health lifecycle", () => {
  beforeEach(() => {
    checkHealthMock.mockReset();
    resetConnectionStore();
  });

  afterEach(() => {
    resetConnectionStore();
  });

  it("notifies exactly once when a disconnected connection recovers", async () => {
    const onReconnect = vi.fn();
    checkHealthMock.mockResolvedValue({ status: "ok", version: "1.2.0" });
    useConnectionStore.setState({
      status: "disconnected",
      consecutiveFailures: 2,
      onReconnect,
    });

    await useConnectionStore.getState().checkHealth();

    expect(onReconnect).toHaveBeenCalledTimes(1);
    expect(useConnectionStore.getState()).toMatchObject({
      status: "connected",
      isChecking: false,
      serverVersion: "1.2.0",
      consecutiveFailures: 0,
      errorMessage: null,
    });
  });

  it("does not report a reconnection when an already-connected check succeeds", async () => {
    const onReconnect = vi.fn();
    checkHealthMock.mockResolvedValue({ status: "healthy", version: "1.2.0" });
    useConnectionStore.setState({ status: "connected", onReconnect });

    await useConnectionStore.getState().checkHealth();

    expect(onReconnect).not.toHaveBeenCalled();
    expect(useConnectionStore.getState().status).toBe("connected");
  });

  it("degrades on the first failed check and disconnects after the second", async () => {
    checkHealthMock.mockRejectedValue(new Error("service unavailable"));
    useConnectionStore.setState({ status: "connected" });

    await useConnectionStore.getState().checkHealth();
    expect(useConnectionStore.getState()).toMatchObject({
      status: "degraded",
      consecutiveFailures: 1,
      errorMessage: "service unavailable",
    });

    await useConnectionStore.getState().checkHealth();
    expect(useConnectionStore.getState()).toMatchObject({
      status: "disconnected",
      consecutiveFailures: 2,
      errorMessage: "service unavailable",
    });
  });

  it("coalesces overlapping health checks into one request", async () => {
    let resolveHealth!: (value: { status: string; version: string }) => void;
    checkHealthMock.mockReturnValue(new Promise((resolve) => {
      resolveHealth = resolve;
    }));

    const first = useConnectionStore.getState().checkHealth();
    const second = useConnectionStore.getState().checkHealth();

    expect(checkHealthMock).toHaveBeenCalledTimes(1);
    expect(second).toBe(first);

    resolveHealth({ status: "ok", version: "1.2.0" });
    await first;
    expect(useConnectionStore.getState().status).toBe("connected");
  });

  it("ignores a stale health result after polling ownership is stopped", async () => {
    let resolveHealth!: (value: { status: string; version: string }) => void;
    checkHealthMock.mockReturnValue(new Promise((resolve) => {
      resolveHealth = resolve;
    }));
    useConnectionStore.setState({ status: "degraded", consecutiveFailures: 1 });

    const pending = useConnectionStore.getState().checkHealth();
    useConnectionStore.getState().stopPolling();
    resolveHealth({ status: "ok", version: "stale" });
    await pending;

    expect(useConnectionStore.getState()).toMatchObject({
      status: "degraded",
      serverVersion: null,
      consecutiveFailures: 1,
      isChecking: false,
    });
  });
});
