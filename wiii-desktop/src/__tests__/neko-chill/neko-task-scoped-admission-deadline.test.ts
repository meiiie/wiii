/** Real adapter -> session store; responses are silently dropped while transport stays alive.
 * No native process, model, real account or user data is used.
 * The original two expected-RED cases are preserved in round10-timeout-repro.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AcpDriver, ACP_SCOPED_ADMISSION_TIMEOUT_MS } from "@/neko-chill/drivers/acp/driver";
import type { DriverEvent } from "@/neko-chill/drivers/types";
import type { AcpTransport } from "@/neko-chill/drivers/acp/client";
import type { NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";
import type { DetectedAgent } from "@/neko-chill/stores/neko-agent-store";

const memory = vi.hoisted(() => new Map<string, unknown>());
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn(async (store: string, key: string, fallback: unknown) =>
    memory.has(`${store}:${key}`) ? structuredClone(memory.get(`${store}:${key}`)) : fallback),
  loadStoreStrict: vi.fn(async (store: string, key: string, fallback: unknown) =>
    memory.has(`${store}:${key}`) ? structuredClone(memory.get(`${store}:${key}`)) : fallback),
  saveStore: vi.fn(async (store: string, key: string, value: unknown) => {
    memory.set(`${store}:${key}`, structuredClone(value));
  }),
  saveStoreStrict: vi.fn(async (store: string, key: string, value: unknown) => {
    memory.set(`${store}:${key}`, structuredClone(value));
  }),
  deleteStore: vi.fn(async (store: string, key: string) => { memory.delete(`${store}:${key}`); }),
  deleteStoreStrict: vi.fn(async (store: string, key: string) => { memory.delete(`${store}:${key}`); }),
  clearStore: vi.fn(async () => {}),
}));
import {
  useNekoSessionStore, _setDriverFactoryForTests, _setNativeControlReaderForTests,
  _clearLiveDriversForTests,
} from "@/neko-chill/stores/neko-session-store";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useKnowledgeConnectionStore } from "@/workbench/knowledge";

type Frame = { jsonrpc?: string; id?: number; method?: string; params?: Record<string, unknown>; result?: unknown };
type Snapshot = { entry: { taskScope: { state: string; receipt: NekoTaskReceipt | null; reason?: string; backendSessionId?: string } };
  events: Array<{ data: { type: string } }> };
const workspace = { path: "E:\\MeiiieGroup\\integration-tests\\silent-drop-fixture", name: "silent-drop-fixture" };
const agent: DetectedAgent = { id: "neko", name: "Neko Core", version: "1.7.0", found: true,
  availability: "available", supportsProfiles: true };
const initialReceipt: NekoTaskReceipt = { version: 1, mode: "fixed-active-task", id: "synthetic-task",
  label: "Synthetic silent-drop work", root: workspace.path.toLowerCase(),
  activationEpoch: 1, activationId: "synthetic-activation-one" };
const coordinatorId = "synthetic-coordinator";
const options = { title: initialReceipt.label, projectId: "synthetic-project", execution: {
  taskId: "synthetic-work-item", runId: "synthetic-run", environmentId: "synthetic-environment",
} };
const nativeReader = {
  listSessions: async () => [],
  readEvents: async (streamId: string, afterSeq = 0) => ({ streamId, events: [], nextAfterSeq: afterSeq, hasMore: false }),
  unresolvedStartSessionIds: () => [], reconcilableStartSessionIds: async () => [], cancelUnresolvedStarts: async () => 0,
};
class AliveTransport implements AcpTransport {
  readonly sent: Frame[] = [];
  killed = false;
  private readonly lines: Array<(line: string) => void> = [];
  private readonly exits: Array<(code: number | null) => void> = [];
  constructor(readonly currentReceipt: NekoTaskReceipt) {}
  async send(line: string): Promise<void> {
    const frame = JSON.parse(line) as Frame; this.sent.push(frame);
    if (frame.method === "session/close") queueMicrotask(() => this.inject({ jsonrpc: "2.0", id: frame.id,
      result: { _meta: { "neko.task": this.currentReceipt } } }));
  }
  onLine(handler: (line: string) => void): void { this.lines.push(handler); }
  onExit(handler: (code: number | null) => void): void { this.exits.push(handler); }
  async kill(): Promise<void> {
    if (this.killed) return; this.killed = true; this.exits.forEach(handler => handler(0));
  }
  inject(frame: Frame): void { this.lines.forEach(handler => handler(JSON.stringify(frame))); }
  respond(method: string, result: unknown): void {
    const request = this.sent.find(frame => frame.method === method);
    if (!request) throw new Error(`Missing synthetic request ${method}`);
    this.inject({ jsonrpc: "2.0", id: request.id, result });
  }
  announceBeforeReceipt(): void {
    const _meta = { "neko.task": this.currentReceipt };
    this.inject({ jsonrpc: "2.0", method: "session/update", params: { sessionId: coordinatorId, _meta,
      update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "Must remain buffered" } } } });
    this.inject({ jsonrpc: "2.0", id: 990, method: "session/request_permission", params: { sessionId: coordinatorId, _meta,
      toolCall: { toolCallId: "synthetic-edit", title: "Synthetic edit before admission" },
      options: [{ optionId: "allow", name: "Allow once", kind: "allow_once" }] } });
  }
}
const transports: AliveTransport[] = [];
let activeId: string | null = null;
async function drain(): Promise<void> { for (let index = 0; index < 100; index++) await Promise.resolve(); }
function live() { return useNekoSessionStore.getState().sessions[activeId!]; }
function snapshot(): Snapshot {
  const value = memory.get(`neko-chill-sessions.json:session:${activeId}`);
  if (!value) throw new Error("Missing synthetic durable snapshot");
  return structuredClone(value) as Snapshot;
}
function frames(method: string): Frame[] { return transports.flatMap(transport => transport.sent.filter(frame => frame.method === method)); }
function init(transport: AliveTransport): void {
  transport.respond("initialize", { protocolVersion: 1,
    agentCapabilities: { loadSession: true, sessionCapabilities: { resume: {}, close: {} } },
    _meta: { "neko.taskProtocol": { version: 1, mode: "fixed-active-task" } },
  });
}
async function pendingAdmission(kind: "initialize" | "new" | "load") {
  let settled = false;
  const creating = useNekoSessionStore.getState().createSession(agent, workspace, null, options);
  await drain(); activeId = useNekoSessionStore.getState().activeSessionId;
  expect(activeId).toBeTruthy(); const first = transports[0]; expect(first).toBeDefined();
  if (kind === "initialize") {
    void creating.then(() => { settled = true; }, () => { settled = true; });
    return { transport: first, operation: creating, method: "initialize", settled: () => settled };
  }
  init(first); await drain(); expect(frames("session/new")).toHaveLength(1);
  if (kind === "new") {
    void creating.then(() => { settled = true; }, () => { settled = true; });
    return { transport: first, operation: creating, method: "session/new", settled: () => settled };
  }
  first.respond("session/new", { sessionId: coordinatorId, _meta: { "neko.task": initialReceipt } });
  await creating; expect(live().status).toBe("idle");
  await useNekoSessionStore.getState().closeSession(activeId!);
  expect(first.killed).toBe(true);
  const loading = useNekoSessionStore.getState().sendPrompt("One explicit synthetic resume request");
  void loading.then(() => { settled = true; }, () => { settled = true; });
  await drain(); const second = transports[1]; expect(second).toBeDefined();
  init(second); await drain(); expect(frames("session/resume")).toHaveLength(1);
  return { transport: second, operation: loading, method: "session/resume", settled: () => settled };
}
async function coldRestartBlocked(): Promise<void> {
  const count = transports.length; const id = activeId!;
  _clearLiveDriversForTests();
  useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, hydrated: false, hydrating: false, hydrationError: null });
  await useNekoSessionStore.getState().hydrate(); useNekoSessionStore.getState().setActiveSession(id); activeId = id;
  expect(live().taskScope?.state).toBe("recovery-required");
  await useNekoSessionStore.getState().sendPrompt("Cold restart must not replay an uncertain request");
  expect(transports).toHaveLength(count); expect(frames("session/prompt")).toHaveLength(0);
}

beforeEach(() => {
  vi.useFakeTimers(); _clearLiveDriversForTests(); memory.clear(); transports.length = 0; activeId = null;
  useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, hydrated: false, hydrating: false, hydrationError: null });
  useNekoAgentStore.setState({ agents: [agent], isLoading: false, error: null });
  useKnowledgeConnectionStore.setState({ status: "disconnected", error: null });
  _setNativeControlReaderForTests(() => nativeReader);
  _setDriverFactoryForTests(async (_agent, id, launch, onEvent, ownDriver) => {
    const prior = launch.taskScope?.receipt;
    const current = prior ? { ...prior, activationEpoch: prior.activationEpoch + 1, activationId: "synthetic-activation-two" }
      : launch.taskScope!.label === initialReceipt.label ? initialReceipt
        : { ...initialReceipt, id: "different-task", label: launch.taskScope!.label, activationId: "different-activation" };
    const transport = new AliveTransport(current); transports.push(transport);
    const driver = new AcpDriver({ sessionId: id, cwd: workspace.path, resumeSessionId: launch.backendSessionId,
      transport, onEvent, taskScope: { label: launch.taskScope!.label, authorizedRoot: workspace.path,
        expectedReceipt: prior,
        onAdmitted: (wireId, receipt) => launch.onTaskAdmitted!(wireId, receipt, workspace.path),
        onCloseOutcome: launch.onTaskCloseOutcome,
      },
    });
    ownDriver(driver); await driver.start(); return driver;
  });
});
afterEach(() => {
  _clearLiveDriversForTests(); _setDriverFactoryForTests(undefined); _setNativeControlReaderForTests(undefined);
  vi.useRealTimers();
});

describe("Scoped silent-response deadline: actual adapter -> actual session store", () => {
  it.each(["initialize", "new", "load"] as const)("bounds %s despite an alive transport, retains unknown outcome and blocks cold replay", async kind => {
    const pending = await pendingAdmission(kind); pending.transport.announceBeforeReceipt(); await drain();
    await vi.advanceTimersByTimeAsync(ACP_SCOPED_ADMISSION_TIMEOUT_MS - 1); await drain();
    expect(pending.settled()).toBe(false); expect(pending.transport.killed).toBe(false);
    expect(live().status).toBe("connecting"); expect(live().taskScope?.state).toBe(kind === "load" ? "pending-load" : "pending-new");
    expect(live().messages).toEqual([]); expect(live().pendingPermission).toBeNull();
    expect(frames("session/prompt")).toHaveLength(0);
    expect(pending.transport.sent.filter(frame => frame.id === 990)).toEqual([
      { jsonrpc: "2.0", id: 990, result: { outcome: { outcome: "cancelled" } } },
    ]);
    const countsBefore = { new: frames("session/new").length, load: frames("session/resume").length };
    await vi.advanceTimersByTimeAsync(1); await drain(); await pending.operation;
    expect(pending.settled()).toBe(true);
    expect(pending.transport.killed).toBe(true);
    expect(live().statusDetail).toContain(`${pending.method} timed out`);
    expect(live().taskScope?.state).toBe("recovery-required");
    expect(snapshot().entry.taskScope.state).toBe("recovery-required");
    expect(snapshot().entry.taskScope.reason).toBe(kind === "load" ? "load-response-uncertain" : "new-response-uncertain");
    expect(snapshot().entry.taskScope.receipt).toEqual(kind === "load" ? initialReceipt : null);
    expect(live().events.filter(event => event.data.type === "turn-terminal")).toEqual([]);
    expect(snapshot().events.filter(event => event.data.type === "turn-terminal")).toEqual([]);
    // A response delivered after expiry cannot complete the abandoned admission.
    if (kind === "initialize") init(pending.transport);
    else pending.transport.respond(pending.method, {
      ...(kind === "new" ? { sessionId: coordinatorId } : {}),
      _meta: { "neko.task": pending.transport.currentReceipt },
    });
    pending.transport.announceBeforeReceipt(); await drain();
    expect(live().taskScope?.state).toBe("recovery-required");
    expect(live().messages).toEqual([]); expect(live().pendingPermission).toBeNull();
    expect(snapshot().entry.taskScope.receipt).toEqual(kind === "load" ? initialReceipt : null);
    await coldRestartBlocked();
    expect({ new: frames("session/new").length, load: frames("session/resume").length }).toEqual(countsBefore);
    console.info("WIII_SCOPED_DEADLINE", JSON.stringify({ kind, deadlineMs: ACP_SCOPED_ADMISSION_TIMEOUT_MS,
      ownedProcessStopped: pending.transport.killed, persistedState: snapshot().entry.taskScope.state,
      reason: snapshot().entry.taskScope.reason,
      retainedReceipt: snapshot().entry.taskScope.receipt !== null, promptRpcCount: frames("session/prompt").length,
      ...countsBefore, coldRestartBlocked: true }));
  });
});

describe("Per-request policy and stale generation isolation", () => {
  it("starts a fresh new/resume budget after initialize, rather than a whole-bootstrap deadline", async () => {
    let settled = false;
    const operation = useNekoSessionStore.getState().createSession(agent, workspace, null, options);
    void operation.then(() => { settled = true; });
    await drain(); activeId = useNekoSessionStore.getState().activeSessionId; const transport = transports[0];
    await vi.advanceTimersByTimeAsync(25_000); init(transport); await drain();
    expect(frames("session/new")).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(ACP_SCOPED_ADMISSION_TIMEOUT_MS - 1); await drain();
    expect(settled).toBe(false); expect(transport.killed).toBe(false);
    await vi.advanceTimersByTimeAsync(1); await drain(); await operation;
    expect(settled).toBe(true); expect(transport.killed).toBe(true);
    expect(snapshot().entry.taskScope.state).toBe("recovery-required");
    expect(frames("session/prompt")).toHaveLength(0);
  });

  it.each(["new", "load"] as const)("superseded %s generation cannot route late result, permission or prompt into a different work item", async kind => {
    const pending = await pendingAdmission(kind);
    const oldId = activeId!;
    await vi.advanceTimersByTimeAsync(ACP_SCOPED_ADMISSION_TIMEOUT_MS); await drain(); await pending.operation;
    const createNext = useNekoSessionStore.getState().createSession(agent, workspace, null, {
      ...options, title: "Different explicit work item", execution: { ...options.execution, taskId: "different-work-item" },
    });
    await drain(); const newId = useNekoSessionStore.getState().activeSessionId!; expect(newId).not.toBe(oldId);
    const next = transports[transports.length - 1]; init(next); await drain();
    const freshReceipt = next.currentReceipt;
    next.respond("session/new", { sessionId: "different-coordinator", _meta: { "neko.task": freshReceipt } });
    await createNext; activeId = newId; expect(live().status).toBe("idle");
    pending.transport.respond(pending.method, {
      ...(kind === "new" ? { sessionId: coordinatorId } : {}), _meta: { "neko.task": pending.transport.currentReceipt },
    });
    pending.transport.announceBeforeReceipt(); await drain();
    expect(useNekoSessionStore.getState().sessions[oldId].taskScope?.state).toBe("recovery-required");
    expect(live().taskScope?.state).toBe("bound"); expect(live().messages).toEqual([]);
    expect(live().pendingPermission).toBeNull(); expect(frames("session/prompt")).toHaveLength(0);
    expect(next.sent.some(frame => frame.id === 990)).toBe(false);
    // Normal End for the new work item, using its matching ACK; no uncertain request is replayed.
    await useNekoSessionStore.getState().closeSession(newId);
  });

  it.each(["initialize", "new"] as const)("keeps legacy %s unbounded at30s", async kind => {
    const transport = new AliveTransport(initialReceipt); const events: DriverEvent[] = [];
    const driver = new AcpDriver({ sessionId: "legacy-local", cwd: workspace.path, transport, onEvent: event => events.push(event) });
    let settled = false; const operation = driver.start().then(() => { settled = true; }, () => { settled = true; });
    await drain(); if (kind === "new") { init(transport); await drain(); }
    await vi.advanceTimersByTimeAsync(ACP_SCOPED_ADMISSION_TIMEOUT_MS); await drain();
    expect(settled).toBe(false); expect(transport.killed).toBe(false);
    expect(transport.sent.filter(frame => frame.method === "session/prompt")).toHaveLength(0);
    await driver.dispose(); await operation;
    expect(events.some(event => event.type === "turn-finished")).toBe(false);
  });
});
