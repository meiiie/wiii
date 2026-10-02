/** Independent store acceptance: a receipt is never live admission until its
 * strict snapshot write and the current preparation's lifecycle gate succeed.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Driver, DriverEvent, PermissionDecision } from "@/neko-chill/drivers/types";
import type { DetectedAgent } from "@/neko-chill/stores/neko-agent-store";
import type { NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";
import { AcpTransportError } from "@/neko-chill/drivers/acp/errors";

const memory = vi.hoisted(() => ({
  values: new Map<string, unknown>(), failBoundSnapshot: false,
  boundWriteGate: null as Promise<void> | null,
  boundWriteEntered: null as (() => void) | null,
  loadWriteGate: null as Promise<void> | null,
  loadWriteEntered: null as (() => void) | null,
}));
function copy<T>(value: T): T { return structuredClone(value); }
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn(async (store: string, key: string, fallback: unknown) =>
    memory.values.has(`${store}:${key}`) ? copy(memory.values.get(`${store}:${key}`)) : fallback),
  loadStoreStrict: vi.fn(async (store: string, key: string, fallback: unknown) =>
    memory.values.has(`${store}:${key}`) ? copy(memory.values.get(`${store}:${key}`)) : fallback),
  saveStore: vi.fn(async (store: string, key: string, value: unknown) => {
    memory.values.set(`${store}:${key}`, copy(value));
  }),
  saveStoreStrict: vi.fn(async (store: string, key: string, value: unknown) => {
    const snapshot = value as { entry?: { taskScope?: { state?: string } } };
    if (store === "neko-chill-sessions.json" && key.startsWith("session:")
      && snapshot?.entry?.taskScope?.state === "bound") {
      memory.boundWriteEntered?.();
      if (memory.boundWriteGate) await memory.boundWriteGate;
      if (memory.failBoundSnapshot) {
        memory.failBoundSnapshot = false;
        throw new Error("synthetic receipt snapshot write rejected");
      }
    }
    if (store === "neko-chill-sessions.json" && key.startsWith("session:")
      && snapshot?.entry?.taskScope?.state === "pending-load") {
      memory.loadWriteEntered?.();
      if (memory.loadWriteGate) await memory.loadWriteGate;
    }
    memory.values.set(`${store}:${key}`, copy(value));
  }),
  deleteStore: vi.fn(async (store: string, key: string) => { memory.values.delete(`${store}:${key}`); }),
  deleteStoreStrict: vi.fn(async (store: string, key: string) => { memory.values.delete(`${store}:${key}`); }),
  clearStore: vi.fn(async () => {}),
}));

import {
  useNekoSessionStore, _setDriverFactoryForTests,
  _setNativeControlReaderForTests, _clearLiveDriversForTests,
} from "@/neko-chill/stores/neko-session-store";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useKnowledgeConnectionStore } from "@/workbench/knowledge";

type TestFactory = NonNullable<Parameters<typeof _setDriverFactoryForTests>[0]>;
type Launch = Parameters<TestFactory>[2];
const AGENT: DetectedAgent = {
  id: "neko", name: "Neko Core", version: "1.7.0", found: true,
  availability: "available", supportsProfiles: true,
};
const WORKSPACE = { path: "E:\\MeiiieGroup\\integration-tests\\scope-fixture", name: "scope-fixture" };
const OPTIONS = { title: "Sửa bug tổng", projectId: "explicit-project", execution: {
  taskId: "explicit-work-item", runId: "explicit-run", environmentId: "explicit-environment",
} };
const nativeControl = {
  listSessions: vi.fn(async () => []),
  readEvents: vi.fn(async (streamId: string, afterSeq = 0) => ({ streamId, events: [], nextAfterSeq: afterSeq, hasMore: false })),
  unresolvedStartSessionIds: vi.fn(() => []),
  reconcilableStartSessionIds: vi.fn(async () => []),
  cancelUnresolvedStarts: vi.fn(async () => 0),
};
function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>(done => { resolve = done; });
  return { promise, resolve };
}
function session(id: string) { return useNekoSessionStore.getState().sessions[id]; }
function snapshot(id: string) {
  return memory.values.get(`neko-chill-sessions.json:session:${id}`) as {
    entry?: { taskScope?: { state: string; receipt?: NekoTaskReceipt; reason?: string }; backendSessionId?: string };
    messages?: unknown[];
  } | undefined;
}
function freshReceipt(launch: Launch): NekoTaskReceipt {
  const prior = launch.taskScope?.receipt;
  return { version: 1, mode: "fixed-active-task", id: prior?.id ?? "canonical-task",
    label: launch.taskScope!.label, root: WORKSPACE.path.toLowerCase(),
    activationEpoch: prior ? prior.activationEpoch + 1 : 1,
    activationId: prior ? "activation-two" : "activation-one" };
}

class FakeDriver implements Driver {
  readonly kind = "acp" as const;
  readonly runtime: Driver["runtime"] = { capabilities: ["prompt", "cancel", "permission-resolution", "session-config"],
    contextContinuity: "process", workspaceIsolation: "advisory" };
  prompts: string[] = [];
  promptMappings: unknown[] = [];
  disposed = 0;
  closeOutcome: "acknowledged" | "uncertain" = "acknowledged";
  constructor(readonly sessionId: string, readonly backendSessionId: string,
    readonly launch: Launch, readonly emit: (event: DriverEvent) => void) {}
  async start() {}
  async prompt(text: string) {
    this.promptMappings.push(copy(snapshot(this.sessionId)?.entry?.taskScope));
    this.prompts.push(text);
  }
  async cancel() {}
  async resolvePermission(_decision: PermissionDecision) {}
  async dispose() {
    this.disposed += 1;
    await this.launch.onTaskCloseOutcome?.(this.closeOutcome);
  }
}
const drivers: FakeDriver[] = [];
const launches: Launch[] = [];
const launchSessionIds: string[] = [];
let retrieve = vi.fn();
function useAdmittingFactory(modify?: (driver: FakeDriver) => Promise<void> | void) {
  _setDriverFactoryForTests(async (_agent, id, launch, onEvent, ownDriver) => {
    launches.push(launch); launchSessionIds.push(id);
    const driver = new FakeDriver(id, launch.backendSessionId ?? `coordinator-${id}`, launch, onEvent);
    drivers.push(driver); ownDriver(driver);
    await modify?.(driver);
    if (launch.taskScope) await launch.onTaskAdmitted!(driver.backendSessionId, freshReceipt(launch), WORKSPACE.path);
    return driver;
  });
}
async function createScoped() {
  return useNekoSessionStore.getState().createSession(AGENT, WORKSPACE, null, OPTIONS);
}
async function coldHydrate(id: string) {
  _clearLiveDriversForTests();
  useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, hydrated: false, hydrating: false, hydrationError: null });
  await useNekoSessionStore.getState().hydrate();
  useNekoSessionStore.getState().setActiveSession(id);
}

describe("Neko scoped store admission, durability and replay boundaries", () => {
  beforeEach(() => {
    _clearLiveDriversForTests();
    memory.values.clear(); memory.failBoundSnapshot = false;
    memory.boundWriteGate = null; memory.boundWriteEntered = null;
    memory.loadWriteGate = null; memory.loadWriteEntered = null;
    drivers.length = 0; launches.length = 0; launchSessionIds.length = 0;
    useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, hydrated: false, hydrating: false, hydrationError: null });
    useNekoAgentStore.setState({ agents: [AGENT], isLoading: false, error: null });
    _setNativeControlReaderForTests(() => nativeControl);
    retrieve = vi.fn(async (query: string) => ({ contextId: "external-context", query,
      renderedContext: "EXTERNAL_GLOBAL_KNOWLEDGE", sources: [] }));
    useKnowledgeConnectionStore.setState({ status: "ready", error: null, retrieve });
    useAdmittingFactory();
  });
  afterEach(() => {
    _clearLiveDriversForTests();
    _setDriverFactoryForTests(undefined); _setNativeControlReaderForTests(undefined);
    memory.boundWriteGate = null; memory.boundWriteEntered = null;
    memory.loadWriteGate = null; memory.loadWriteEntered = null;
    useKnowledgeConnectionStore.setState({ status: "disconnected", error: null });
  });

  it("dispatches an explicit launch only to its admitted session after navigation", async () => {
    const target = await createScoped();
    const other = await useNekoSessionStore.getState().createSession(AGENT, WORKSPACE, null);
    expect(useNekoSessionStore.getState().activeSessionId).toBe(other);
    await useNekoSessionStore.getState().sendPromptToSession(target, "Targeted Work goal");
    expect(drivers[0].prompts).toEqual(["Targeted Work goal"]);
    expect(drivers[1].prompts).toEqual([]);
    expect(useNekoSessionStore.getState().activeSessionId).toBe(other);
  });

  it("preserves the Work title across provider metadata and the full first prompt", async () => {
    const id = await createScoped();
    drivers[0].emit({ type: "session-info", sessionId: id, title: "(no messages)" });
    expect(session(id).title).toBe(OPTIONS.title);
    await useNekoSessionStore.getState().sendPromptToSession(id, "Goal\n\nTiêu chí chấp nhận:\n- Keep files");
    drivers[0].emit({ type: "session-info", sessionId: id, title: "Goal criteria summary" });
    expect(session(id).title).toBe(OPTIONS.title);
    expect(session(id).messages[0].text).toContain("Tiêu chí chấp nhận");
  });

  it("strictly stores pending-new before the factory can construct a scoped runtime", async () => {
    useAdmittingFactory(driver => {
      expect(snapshot(driver.sessionId)?.entry?.taskScope?.state).toBe("pending-new");
      expect(session(driver.sessionId).status).toBe("connecting");
      expect(driver.launch.taskScope).toMatchObject({ label: OPTIONS.title });
      expect(driver.launch.taskScope?.receipt).toBeUndefined();
    });
    const id = await createScoped();
    expect(session(id).status).toBe("idle");
    expect(snapshot(id)?.entry?.taskScope?.state).toBe("bound");
    expect(session(id).backendSessionId).toBe(drivers[0].backendSessionId);
  });

  it("blocks first prompt until the receipt's strict snapshot write has completed", async () => {
    const gate = deferred(); let entered = false;
    memory.boundWriteGate = gate.promise; memory.boundWriteEntered = () => { entered = true; };
    const creating = createScoped();
    try {
      await vi.waitFor(() => expect(entered).toBe(true));
      const id = launchSessionIds[0];
      expect(session(id).status).toBe("connecting");
      expect(snapshot(id)?.entry?.taskScope?.state).toBe("pending-new");
      await useNekoSessionStore.getState().sendPrompt("Must not dispatch early");
      expect(drivers[0].prompts).toEqual([]);
    } finally { gate.resolve(); }
    const id = await creating;
    expect(session(id).status).toBe("idle");
    await useNekoSessionStore.getState().sendPrompt("Now explicit user request");
    expect(drivers[0].prompts).toEqual(["Now explicit user request"]);
    expect(drivers[0].promptMappings[0]).toMatchObject({ state: "bound", receipt: { id: "canonical-task" } });
  });

  it("retains recovery state and dispatches nothing if strict receipt persistence fails", async () => {
    memory.failBoundSnapshot = true;
    const id = await createScoped();
    expect(session(id).status).toBe("error");
    expect(session(id).taskScope).toMatchObject({ state: "recovery-required" });
    expect(drivers[0].disposed).toBeGreaterThanOrEqual(1);
    await useNekoSessionStore.getState().sendPrompt("Must not replay");
    expect(drivers[0].prompts).toEqual([]);
    expect(launches).toHaveLength(1);
  });

  it("does not treat a successful factory without the admission callback as idle", async () => {
    _setDriverFactoryForTests(async (_agent, id, launch, onEvent, ownDriver) => {
      launches.push(launch);
      const driver = new FakeDriver(id, `unadmitted-${id}`, launch, onEvent);
      drivers.push(driver); ownDriver(driver);
      return driver;
    });
    const id = await createScoped();
    expect(session(id).status).toBe("error");
    expect(session(id).taskScope).toMatchObject({ state: "recovery-required" });
    expect(session(id).runtime).toBeNull();
    expect(drivers[0].disposed).toBeGreaterThanOrEqual(1);
    await useNekoSessionStore.getState().sendPrompt("No admission, no prompt");
    expect(drivers[0].prompts).toEqual([]);
  });

  it("rejects a late admission from a preparation closed before its response arrived", async () => {
    const proceed = deferred(); const entered = deferred();
    let rejected: unknown;
    _setDriverFactoryForTests(async (_agent, id, launch, onEvent, ownDriver) => {
      launches.push(launch); launchSessionIds.push(id);
      const driver = new FakeDriver(id, `late-${id}`, launch, onEvent);
      drivers.push(driver); ownDriver(driver); entered.resolve();
      await proceed.promise;
      try { await launch.onTaskAdmitted!(driver.backendSessionId, freshReceipt(launch), WORKSPACE.path); }
      catch (error) { rejected = error; throw error; }
      return driver;
    });
    const creating = createScoped();
    await entered.promise;
    const id = launchSessionIds[0];
    const closing = useNekoSessionStore.getState().closeSession(id);
    expect(session(id).closePending).toBe(true);
    proceed.resolve();
    await Promise.allSettled([creating, closing]);
    expect(rejected).toBeInstanceOf(Error);
    expect(session(id).status).not.toBe("idle");
    expect(session(id).runtime).toBeNull();
    expect(snapshot(id)?.entry?.taskScope?.state).not.toBe("bound");
    expect(drivers[0].prompts).toEqual([]);
  });

  it("does not attach global Knowledge to scoped prompts while preserving explicit legacy behavior", async () => {
    const scoped = await createScoped();
    await useNekoSessionStore.getState().sendPrompt("Scoped request");
    expect(retrieve).not.toHaveBeenCalled();
    expect(drivers[0].prompts).toEqual(["Scoped request"]);
    expect(session(scoped).events.some(event => event.data.type === "knowledge-context")).toBe(false);
    const legacy = await useNekoSessionStore.getState().createSession(AGENT, WORKSPACE);
    expect(session(legacy).taskScope).toBeUndefined();
    expect(launches[1].taskScope).toBeUndefined();
    await useNekoSessionStore.getState().sendPrompt("Legacy explicit request");
    expect(retrieve).toHaveBeenCalledTimes(1);
    expect(drivers[1].prompts[0]).toContain("EXTERNAL_GLOBAL_KNOWLEDGE");
  });

  it("preserves a different provider's explicit execution without opting it into the Neko task lane", async () => {
    const alternative = { ...AGENT, id: "claude", name: "Claude Code" };
    const id = await useNekoSessionStore.getState().createSession(alternative, WORKSPACE, null, OPTIONS);
    expect(session(id).taskScope).toBeUndefined();
    expect(launches[0].taskScope).toBeUndefined();
    expect(launches[0].onTaskAdmitted).toBeUndefined();
    await useNekoSessionStore.getState().sendPrompt("Alternative provider request");
    expect(retrieve).toHaveBeenCalledTimes(1);
    expect(drivers[0].prompts[0]).toContain("Alternative provider request");
  });

  it("keeps durable receipt through repeated history-only restarts, then explicitly loads a fresh activation", async () => {
    const id = await createScoped();
    const saved = session(id).taskScope;
    await coldHydrate(id);
    expect(session(id).taskScope).toMatchObject({ state: "bound", receipt: { id: "canonical-task", activationEpoch: 1 } });
    // A journal reconciliation snapshot must not fabricate load intent.
    await (await import("@/neko-chill/persistence")).persistSessionStrict(session(id));
    await coldHydrate(id);
    expect(session(id).taskScope).toMatchObject({ state: "bound", receipt: { activationEpoch: 1 } });
    expect(launches).toHaveLength(1);
    expect(drivers.every(driver => driver.prompts.length === 0)).toBe(true);
    expect(session(id).runtime).toBeNull();
    await useNekoSessionStore.getState().sendPrompt("New explicit prompt after restart");
    expect(launches).toHaveLength(2);
    expect(launches[1].backendSessionId).toBe(launches[0].backendSessionId ?? drivers[0].backendSessionId);
    expect(launches[1].taskScope?.receipt).toMatchObject({ id: "canonical-task", activationEpoch: 1, activationId: "activation-one" });
    expect(session(id).taskScope).toMatchObject({ state: "bound", receipt: { id: "canonical-task", activationEpoch: 2, activationId: "activation-two" } });
    expect(session(id).taskScope).not.toEqual(saved);
    expect(drivers[1].prompts).toEqual(["New explicit prompt after restart"]);
  });

  it("acquires scoped load synchronously so two sends during the strict write create at most one load", async () => {
    const id = await createScoped();
    await coldHydrate(id);
    const gate = deferred(); let entered = false;
    memory.loadWriteGate = gate.promise; memory.loadWriteEntered = () => { entered = true; };
    const first = useNekoSessionStore.getState().sendPrompt("The first explicit request");
    try {
      await vi.waitFor(() => expect(entered).toBe(true));
      expect(session(id).status).toBe("connecting");
      await useNekoSessionStore.getState().sendPrompt("The concurrent request must not dispatch");
      expect(launches).toHaveLength(1);
    } finally { gate.resolve(); }
    await first;
    expect(launches).toHaveLength(2);
    expect(drivers[1].prompts).toEqual(["The first explicit request"]);
    expect(session(id).messages.filter(message => message.role === "user").map(message => message.text)).toEqual(["The first explicit request"]);
  });

  it("does not spawn or prompt if close wins while scoped load persistence is still pending", async () => {
    const id = await createScoped();
    await coldHydrate(id);
    const gate = deferred(); let entered = false;
    memory.loadWriteGate = gate.promise; memory.loadWriteEntered = () => { entered = true; };
    const loading = useNekoSessionStore.getState().sendPrompt("Will be closed before spawning");
    let closing: Promise<void> | undefined;
    try {
      await vi.waitFor(() => expect(entered).toBe(true));
      closing = useNekoSessionStore.getState().closeSession(id);
      expect(session(id).closePending).toBe(true);
      expect(launches).toHaveLength(1);
    } finally { gate.resolve(); }
    await Promise.allSettled([loading, ...(closing ? [closing] : [])]);
    expect(launches).toHaveLength(1);
    expect(drivers.every(driver => driver.prompts.length === 0)).toBe(true);
    expect(session(id).runtime).toBeNull();
    expect(session(id).status).not.toBe("idle");
  });

  it("blocks corrupt persisted scoped metadata without falling back to legacy or calling a factory", async () => {
    const id = await createScoped();
    const key = `neko-chill-sessions.json:session:${id}`;
    const saved = copy(memory.values.get(key)) as { entry: { taskScope: unknown } };
    saved.entry.taskScope = { version: 99, state: "bound" };
    memory.values.set(key, saved);
    await coldHydrate(id);
    expect(session(id).taskScope).toMatchObject({ state: "invalid" });
    const starts = launches.length;
    await useNekoSessionStore.getState().sendPrompt("No legacy fallback");
    expect(launches).toHaveLength(starts);
    expect(session(id).messages).toEqual([]);
  });

  it("keeps an uncertain session/new mapping and never retries or replaces it on a later prompt", async () => {
    _setDriverFactoryForTests(async (_agent, _id, launch) => {
      launches.push(launch);
      throw new AcpTransportError("timeout", "session/new", 1, "Synthetic lost new response");
    });
    const id = await createScoped();
    expect(session(id).taskScope).toMatchObject({ state: "recovery-required", receipt: null });
    useNekoSessionStore.setState(state => ({ sessions: { ...state.sessions, [id]: { ...state.sessions[id], status: "exited" } } }));
    await useNekoSessionStore.getState().sendPrompt("Do not replace unknown task");
    expect(launches).toHaveLength(1);
    expect(session(id).messages).toEqual([]);
  });

  it("keeps the prior receipt after uncertain load and does not replay a second attempt", async () => {
    const id = await createScoped();
    await coldHydrate(id);
    _setDriverFactoryForTests(async (_agent, _id, launch) => {
      launches.push(launch);
      throw new AcpTransportError("timeout", "session/load", 2, "Synthetic lost load response");
    });
    await useNekoSessionStore.getState().sendPrompt("One explicit load attempt");
    expect(session(id).taskScope).toMatchObject({ state: "recovery-required", receipt: { id: "canonical-task", activationEpoch: 1 } });
    useNekoSessionStore.setState(state => ({ sessions: { ...state.sessions, [id]: { ...state.sessions[id], status: "exited" } } }));
    await useNekoSessionStore.getState().sendPrompt("No ambiguous replay");
    expect(launches).toHaveLength(2);
    expect(session(id).messages).toEqual([]);
  });

  it("retains a receipt-bearing mapping when close is uncertain and prevents respawn", async () => {
    const id = await createScoped();
    const original = session(id).taskScope;
    drivers[0].closeOutcome = "uncertain";
    await useNekoSessionStore.getState().closeSession(id);
    expect(session(id).taskScope).toMatchObject({ state: "recovery-required", reason: "close-unconfirmed",
      receipt: { id: "canonical-task", activationEpoch: 1 } });
    expect(session(id).taskScope).not.toEqual(original);
    expect(snapshot(id)?.entry?.taskScope?.state).toBe("recovery-required");
    await useNekoSessionStore.getState().sendPrompt("No respawn after uncertain close");
    expect(launches).toHaveLength(1);
    expect(drivers[0].prompts).toEqual([]);
  });
});
