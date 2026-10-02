import { beforeEach, describe, expect, it, vi } from "vitest";

const native = vi.hoisted(() => ({ invoke: vi.fn(), listen: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: native.invoke }));
vi.mock("@tauri-apps/api/event", () => ({ listen: native.listen }));

const provider = {
  id: "neko", name: "Neko", version: "test", found: true,
  availability: "available", supportsProfiles: true,
};

type StartPayload = { request: { agentSessionId: string; runId: string } };
function installStartResponse(change: Record<string, unknown> = {}) {
  native.invoke.mockImplementation(async (command: string, payload: StartPayload) => {
    if (command === "neko_control_session_list") return [];
    if (command === "neko_control_session_start") return {
      agentSessionId: payload.request.agentSessionId,
      runId: payload.request.runId,
      provider,
      canonicalWorkspacePath: "E:\\Synthetic",
      ...change,
    };
    throw new Error(`Unexpected test command ${command}`);
  });
}

describe("native start result identity correlation", () => {
  beforeEach(() => {
    vi.resetModules();
    native.invoke.mockReset();
    native.listen.mockReset().mockResolvedValue(vi.fn());
    installStartResponse();
  });

  it("accepts the exact requested native identity and propagates its physical launch root", async () => {
    const { getNekoControlClient } = await import("@/neko/control-client");
    const result = await getNekoControlClient().spawnProvider({
      providerId: "neko", clientSessionId: "thread-ok", clientRunId: "generation-ok", workspacePath: "E:/Synthetic",
    });
    const request = native.invoke.mock.calls.find(([command]) => command === "neko_control_session_start")![1].request;
    expect(result.agentSessionId).toBe(request.agentSessionId);
    expect(result.runId).toBe(request.runId);
    expect(result.canonicalWorkspacePath).toBe("E:\\Synthetic");
  });

  it.each([
    { agentSessionId: "foreign-native-session" },
    { runId: "foreign-native-run" },
    { provider: { ...provider, id: "gemini" } },
    { canonicalWorkspacePath: 42 },
  ])("retains an uncertain operation after a foreign or malformed result %j", async (change) => {
    installStartResponse(change);
    const { getNekoControlClient } = await import("@/neko/control-client");
    const client = getNekoControlClient();
    await expect(client.spawnProvider({ providerId: "neko", clientSessionId: "thread-mismatch", workspacePath: "E:/Synthetic" }))
      .rejects.toThrow("unknown_outcome");
    expect(client.unresolvedStartSessionIds()).toContain("thread-mismatch");
    expect(native.invoke.mock.calls.some(([command]) => /session_(?:write|cancel)$/.test(command))).toBe(false);
  });

  it("does not clean up foreign IDs from a mismatched retained start replay", async () => {
    installStartResponse({ agentSessionId: "foreign-native-session" });
    const { getNekoControlClient } = await import("@/neko/control-client");
    const client = getNekoControlClient();
    await expect(client.spawnProvider({ providerId: "neko", clientSessionId: "thread-retained", workspacePath: "E:/Synthetic" }))
      .rejects.toThrow("unknown_outcome");
    await expect(client.cancelUnresolvedStarts("thread-retained")).rejects.toThrow("unknown_outcome");
    expect(client.unresolvedStartSessionIds()).toContain("thread-retained");
    expect(native.invoke.mock.calls.some(([command]) => command === "neko_control_session_cancel")).toBe(false);
  });

  it("keeps legacy native results readable without inventing canonical root proof", async () => {
    installStartResponse({ canonicalWorkspacePath: undefined });
    const { getNekoControlClient } = await import("@/neko/control-client");
    const result = await getNekoControlClient().spawnProvider({ providerId: "neko", clientSessionId: "thread-legacy", workspacePath: "E:/Synthetic" });
    expect(result.canonicalWorkspacePath).toBeUndefined();
  });
});
