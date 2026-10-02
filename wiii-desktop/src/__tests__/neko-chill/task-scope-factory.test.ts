import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AdeGraph } from "@/ade/domain";
import type { DriverRuntimeDescriptor } from "@/neko-chill/drivers/types";
import type { NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";

interface MockAcpOptions {
  sessionId: string;
  cwd: string;
  taskScope?: {
    authorizedRoot: string;
    label: string;
    expectedReceipt?: NekoTaskReceipt;
    onAdmitted: (id: string, receipt: NekoTaskReceipt) => Promise<void>;
    onCloseOutcome?: (outcome: "acknowledged" | "uncertain") => Promise<void> | void;
  };
}

const h = vi.hoisted(() => ({
  hydrate: vi.fn(async () => {}),
  work: { hydrated: true, graph: null as unknown as AdeGraph },
  invoke: vi.fn(),
  spawn: vi.fn(),
  start: vi.fn(async (_options: MockAcpOptions) => {}),
  dispose: vi.fn(async () => {}),
  prompt: vi.fn(),
  permission: vi.fn(),
  acpOptions: [] as MockAcpOptions[],
  computerBridge: vi.fn(),
}));

vi.mock("@/ade/store", () => ({ useAdeWorkStore: { getState: () => ({ ...h.work, hydrate: h.hydrate }) } }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("@/neko/control-client", () => ({ getNekoControlClient: () => ({ spawnProvider: h.spawn }) }));
vi.mock("@/neko-computer/agent-bridge", () => ({ createComputerAgentBridge: h.computerBridge }));
vi.mock("@/neko-chill/drivers/acp/driver", () => ({
  AcpDriver: class {
    runtime: DriverRuntimeDescriptor = {
      capabilities: ["prompt", "cancel"], contextContinuity: "process", workspaceIsolation: "advisory",
    };
    readonly kind = "acp";
    constructor(private readonly options: MockAcpOptions) { h.acpOptions.push(options); }
    get sessionId() { return this.options.sessionId; }
    start() { return h.start(this.options); }
    prompt() { return h.prompt(); }
    resolvePermission() { return h.permission(); }
    async cancel() {}
    async setConfigOption() {}
    dispose() { return h.dispose(); }
  },
}));

import { RuntimeRegistry } from "@/neko-chill/runtime-manager";
import { createDriverForAgent, type DriverLaunchConfig } from "@/neko-chill/drivers/factory";

function graph(): AdeGraph {
  return {
    projects: [{ id: "ade-project", name: "Synthetic project" }],
    workspaces: [{ id: "workspace", projectId: "ade-project", kind: "local", roots: ["E:/Project"] }],
    tasks: [{ id: "work-task", projectId: "ade-project", title: "Synthetic work", state: "running" }],
    specs: [],
    environments: [{ id: "environment", projectId: "ade-project", workspaceId: "workspace", kind: "local_workspace", state: "busy" }],
    runs: [{ id: "run", taskId: "work-task", environmentId: "environment", state: "starting", strategy: "single" }],
    agentSessions: [], artifacts: [], evidence: [], approvals: [], attentionItems: [],
  };
}

const agent = (id = "neko") => ({
  id, name: id, found: true, availability: "available" as const, version: "test-version", supportsProfiles: true,
});
const receipt: NekoTaskReceipt = {
  version: 1, mode: "fixed-active-task", id: "neko-task", label: "Synthetic work",
  root: "e:\\project", activationEpoch: 1, activationId: "activation-1",
};
function launch(): DriverLaunchConfig {
  return {
    workspace: { path: "E:/Alias", name: "Alias" },
    // This synthetic launcher identity is kept for its separate Computer gate.
    projectId: "task:run",
    execution: { taskId: "work-task", runId: "run", environmentId: "environment" },
    executionId: "generation", taskScope: { label: "Synthetic work" },
    onTaskAdmitted: vi.fn(async () => {}),
  };
}

describe("fixed task scope factory native boundary", () => {
  beforeEach(() => {
    Object.defineProperty(window, "__TAURI_INTERNALS__", { value: {}, configurable: true });
    h.work = { hydrated: true, graph: graph() };
    h.hydrate.mockReset().mockResolvedValue(undefined);
    h.invoke.mockReset().mockResolvedValue({ path: "E:\\Project", name: "Project" });
    h.spawn.mockReset().mockResolvedValue({
      provider: agent(), agentSessionId: "native-session", runId: "run", transport: {}, canonicalWorkspacePath: "E:\\Project",
    });
    h.start.mockReset().mockResolvedValue(undefined);
    h.dispose.mockReset().mockResolvedValue(undefined);
    h.prompt.mockReset().mockResolvedValue(undefined);
    h.permission.mockReset().mockResolvedValue(undefined);
    h.computerBridge.mockReset();
    h.acpOptions.length = 0;
  });
  afterEach(() => { Reflect.deleteProperty(window, "__TAURI_INTERNALS__"); });

  it("uses native canonical cwd while retaining the original native start alias and ADE IDs", async () => {
    const value = launch();
    h.start.mockImplementationOnce(async (options) => {
      await options.taskScope!.onAdmitted("coordinator", receipt);
    });
    await createDriverForAgent(agent(), "thread", value, vi.fn());
    expect(h.spawn).toHaveBeenCalledWith(expect.objectContaining({
      workspacePath: "E:/Alias", clientRunId: "generation", execution: value.execution,
    }));
    expect(h.acpOptions[0].cwd).toBe("E:\\Project");
    expect(h.acpOptions[0].taskScope?.authorizedRoot).toBe("E:\\Project");
    expect(value.onTaskAdmitted).toHaveBeenCalledWith("coordinator", receipt, "E:\\Project");
    expect(h.computerBridge).toHaveBeenCalledWith({ sessionId: "thread", projectId: "task:run" });
  });

  it("blocks a browser without invoking canonicalization or launching native work", async () => {
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
    await expect(createDriverForAgent(agent(), "thread", launch(), vi.fn())).rejects.toThrow("native Wiii");
    expect(h.invoke).not.toHaveBeenCalled();
    expect(h.spawn).not.toHaveBeenCalled();
  });

  it("requires the async receipt persistence gate before launching a scoped provider", async () => {
    await expect(createDriverForAgent(agent(), "thread", { ...launch(), onTaskAdmitted: undefined }, vi.fn()))
      .rejects.toThrow("mapping");
    expect(h.spawn).not.toHaveBeenCalled();
  });

  it("does not forward scoped intent to another provider", async () => {
    await expect(createDriverForAgent(agent("gemini"), "thread", launch(), vi.fn())).rejects.toThrow("Neko");
    expect(h.spawn).not.toHaveBeenCalled();
  });

  it.each([undefined, "E:\\Other"])("owns and cleans up the native transport before rejecting root proof %s", async (root) => {
    h.spawn.mockResolvedValueOnce({
      provider: agent(), agentSessionId: "native-session", runId: "run", transport: {}, canonicalWorkspacePath: root,
    });
    await expect(createDriverForAgent(agent(), "thread", launch(), vi.fn())).rejects.toThrow("root-mismatch");
    expect(h.dispose).toHaveBeenCalledTimes(1);
    expect(h.start).not.toHaveBeenCalled();
  });

  it("registers an owner before a failing native proof so RuntimeRegistry retains cleanup authority", async () => {
    const own = vi.fn();
    h.spawn.mockResolvedValueOnce({ provider: agent(), agentSessionId: "native-session", runId: "run", transport: {} });
    await expect(createDriverForAgent(agent(), "thread", launch(), vi.fn(), own)).rejects.toThrow("root-mismatch");
    expect(own).toHaveBeenCalledTimes(1);
    expect(h.dispose).not.toHaveBeenCalled();
    expect(h.start).not.toHaveBeenCalled();
  });

  it("blocks a loaded receipt for a different freshly resolved physical host root", async () => {
    await expect(createDriverForAgent(agent(), "thread", {
      ...launch(), backendSessionId: "coordinator", taskScope: { label: receipt.label, receipt: { ...receipt, root: "e:\\other" } },
    }, vi.fn())).rejects.toThrow("root-mismatch");
    expect(h.spawn).not.toHaveBeenCalled();
  });

  it("rechecks replaced ADE graph objects after native spawn and before ACP admission", async () => {
    h.spawn.mockImplementationOnce(async () => {
      const changed = graph();
      changed.workspaces[0].roots = ["E:/Replacement"];
      h.work = { hydrated: true, graph: changed };
      return { provider: agent(), agentSessionId: "native-session", runId: "run", transport: {}, canonicalWorkspacePath: "E:\\Project" };
    });
    await expect(createDriverForAgent(agent(), "thread", launch(), vi.fn())).rejects.toThrow("binding-changed");
    expect(h.start).not.toHaveBeenCalled();
    expect(h.dispose).toHaveBeenCalledTimes(1);
  });

  it("keeps prompt admission closed if the durable receipt callback fails", async () => {
    const value = { ...launch(), onTaskAdmitted: vi.fn(async () => { throw new Error("synthetic persistence failure"); }) };
    h.start.mockImplementationOnce(async (options) => { await options.taskScope!.onAdmitted("coordinator", receipt); });
    await expect(createDriverForAgent(agent(), "thread", value, vi.fn())).rejects.toThrow("synthetic persistence failure");
    expect(h.dispose).toHaveBeenCalledTimes(1);
  });

  it.each(["neko", "gemini"])("preserves the unscoped %s lane without canonical root admission", async (providerId) => {
    h.spawn.mockResolvedValueOnce({ provider: agent(providerId), agentSessionId: "legacy-native", runId: "legacy-run", transport: {} });
    const value = { workspace: { path: "E:/LegacyAlias", name: "Legacy" } };
    await createDriverForAgent(agent(providerId), "legacy-thread", value, vi.fn());
    expect(h.invoke).not.toHaveBeenCalled();
    expect(h.hydrate).not.toHaveBeenCalled();
    expect(h.acpOptions[0].cwd).toBe("E:/LegacyAlias");
    expect(h.acpOptions[0].taskScope).toBeUndefined();
  });
  it("awaits cold Work hydration before scoped resume canonicalization and native spawn", async () => {
    h.work = { hydrated: false, graph: { ...graph(), tasks: [], runs: [] } };
    let ready!: () => void;
    h.hydrate.mockImplementationOnce(() => new Promise<void>((resolve) => {
      ready = () => { h.work = { hydrated: true, graph: graph() }; resolve(); };
    }));
    const value = { ...launch(), backendSessionId: "coordinator", taskScope: { label: receipt.label, receipt } };
    const pending = createDriverForAgent(agent(), "thread", value, vi.fn());
    void pending.catch(() => {});
    expect(h.hydrate).toHaveBeenCalledTimes(1);
    expect(h.invoke).not.toHaveBeenCalled();
    expect(h.spawn).not.toHaveBeenCalled();
    ready();
    await pending;
    expect(h.spawn).toHaveBeenCalledTimes(1);
    expect(h.acpOptions[0].taskScope?.expectedReceipt).toEqual(receipt);
  });

  it("awaits an already pending serialized hydrate rather than treating an empty graph as authoritative", async () => {
    h.work = { hydrated: false, graph: { ...graph(), tasks: [], runs: [] } };
    h.hydrate.mockImplementationOnce(async () => {
      await Promise.resolve();
      h.work = { hydrated: true, graph: graph() };
    });
    await createDriverForAgent(agent(), "thread", launch(), vi.fn());
    expect(h.start).toHaveBeenCalledTimes(1);
    expect(h.spawn).toHaveBeenCalledTimes(1);
  });

  it("does not canonicalize, spawn, or admit a receipt when Work hydration rejects", async () => {
    h.work = { hydrated: false, graph: graph() };
    h.hydrate.mockRejectedValueOnce(new Error("Synthetic owned Work snapshot failed"));
    await expect(createDriverForAgent(agent(), "thread", launch(), vi.fn())).rejects.toThrow("snapshot failed");
    expect(h.invoke).not.toHaveBeenCalled();
    expect(h.spawn).not.toHaveBeenCalled();
    expect(h.start).not.toHaveBeenCalled();
  });

  it("keeps admission closed if hydration completes without a valid hydrated graph", async () => {
    h.work = { hydrated: false, graph: graph() };
    await expect(createDriverForAgent(agent(), "thread", launch(), vi.fn())).rejects.toThrow("work-not-hydrated");
    expect(h.spawn).not.toHaveBeenCalled();
  });

  it("reclaims a late native transport if thread close wins during scoped hydration without prompt or permission", async () => {
    const registry = new RuntimeRegistry();
    h.work = { hydrated: false, graph: graph() };
    let ready!: () => void;
    h.hydrate.mockImplementationOnce(() => new Promise<void>((resolve) => {
      ready = () => { h.work = { hydrated: true, graph: graph() }; resolve(); };
    }));
    const creating = registry.replace("thread", "neko", (instanceId, own) =>
      createDriverForAgent(agent(), "thread", { ...launch(), executionId: instanceId }, vi.fn(), own));
    void creating.catch(() => {});
    await vi.waitFor(() => expect(h.hydrate).toHaveBeenCalledTimes(1));
    const closing = registry.detach("thread");
    ready();
    await expect(creating).rejects.toThrow("cancelled during teardown");
    await closing;
    expect(registry.get("thread")).toBeNull();
    expect(h.dispose).toHaveBeenCalledTimes(1);
    expect(h.start).not.toHaveBeenCalled();
    expect(h.prompt).not.toHaveBeenCalled();
    expect(h.permission).not.toHaveBeenCalled();
  });

});
