/** Independent acceptance fixtures. These tests have not been run by this reviewer.
 * Deletion removes Wiii-owned history; it never cleans up Neko task checkpoints.
 * A hydrated receipt alone is not admission or a reason to replay a prompt.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Driver, DriverEvent, PermissionDecision } from "@/neko-chill/drivers/types";
import type { DetectedAgent } from "@/neko-chill/stores/neko-agent-store";
import type { NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";
import { AcpRpcError, AcpTransportError } from "@/neko-chill/drivers/acp/errors";

const memory = vi.hoisted(() => ({
  values: new Map<string, unknown>(),
  recoveryFailuresRemaining: 0,
  rejectRecoveryTranscript: false,
  rejectAllWrites: false,
  rejectedWrites: 0,
}));
function copy<T>(value: T): T { return structuredClone(value); }
async function write(store: string, key: string, value: unknown) {
  const snapshot = value as { entry?: { taskScope?: { state?: string } } };
  const recoveryTranscript = store === "neko-chill-sessions.json" && key.startsWith("session:")
    && snapshot?.entry?.taskScope?.state === "recovery-required";
  if (memory.rejectAllWrites || (recoveryTranscript && (memory.rejectRecoveryTranscript || memory.recoveryFailuresRemaining > 0))) {
    if (recoveryTranscript && memory.recoveryFailuresRemaining > 0) memory.recoveryFailuresRemaining -= 1;
    memory.rejectedWrites += 1;
    throw new Error("synthetic durable write failure");
  }
  memory.values.set(`${store}:${key}`, copy(value));
}
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn(async (store: string, key: string, fallback: unknown) =>
    memory.values.has(`${store}:${key}`) ? copy(memory.values.get(`${store}:${key}`)) : fallback),
  loadStoreStrict: vi.fn(async (store: string, key: string, fallback: unknown) =>
    memory.values.has(`${store}:${key}`) ? copy(memory.values.get(`${store}:${key}`)) : fallback),
  saveStore: vi.fn(write), saveStoreStrict: vi.fn(write),
  deleteStore: vi.fn(async (store: string, key: string) => { memory.values.delete(`${store}:${key}`); }),
  deleteStoreStrict: vi.fn(async (store: string, key: string) => { memory.values.delete(`${store}:${key}`); }),
  clearStore: vi.fn(async () => {}),
}));

import { clearStore, deleteStoreStrict } from "@/lib/storage";
import { persistSessionStrict } from "@/neko-chill/persistence";
import {
  useNekoSessionStore, _setDriverFactoryForTests,
  _setNativeControlReaderForTests, _clearLiveDriversForTests,
} from "@/neko-chill/stores/neko-session-store";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useKnowledgeConnectionStore } from "@/workbench/knowledge";

type TestFactory = NonNullable<Parameters<typeof _setDriverFactoryForTests>[0]>;
type Launch = Parameters<TestFactory>[2];
const AGENT: DetectedAgent = { id: "neko", name: "Neko Core", version: "1.7.0", found: true,
  availability: "available", supportsProfiles: true };
const WORKSPACE = { path: "E:\\MeiiieGroup\\integration-tests\\scope-recovery-fixture", name: "scope-recovery-fixture" };
const OPTIONS = { title: "Kiểm tra đối soát", projectId: "recovery-project", execution: {
  taskId: "recovery-work-item", runId: "recovery-run", environmentId: "recovery-environment",
} };
const nativeControl = {
  listSessions: vi.fn(async () => []),
  readEvents: vi.fn(async (streamId: string, afterSeq = 0) => ({ streamId, events: [], nextAfterSeq: afterSeq, hasMore: false })),
  unresolvedStartSessionIds: vi.fn(() => []), reconcilableStartSessionIds: vi.fn(async () => []),
  cancelUnresolvedStarts: vi.fn(async () => 0),
};
function session(id: string) { return useNekoSessionStore.getState().sessions[id]; }
function snapshot(id: string) {
  return memory.values.get(`neko-chill-sessions.json:session:${id}`) as {
    entry: { taskScope?: { state: string; receipt?: NekoTaskReceipt | null; reason?: string } };
    messages: unknown[];
  } | undefined;
}
function freshReceipt(launch: Launch): NekoTaskReceipt {
  const prior = launch.taskScope?.receipt;
  return { version: 1, mode: "fixed-active-task", id: prior?.id ?? "canonical-recovery-task",
    label: launch.taskScope!.label, root: WORKSPACE.path.toLowerCase(),
    activationEpoch: prior ? prior.activationEpoch + 1 : 1,
    activationId: prior ? "recovery-activation-two" : "recovery-activation-one" };
}
class FakeDriver implements Driver {
  readonly kind = "acp" as const;
  readonly runtime: Driver["runtime"] = { capabilities: ["prompt", "cancel", "permission-resolution", "session-config"],
    contextContinuity: "process", workspaceIsolation: "advisory" };
  prompts: string[] = [];
  disposed = 0;
  closeOutcome: "acknowledged" | "uncertain" = "acknowledged";
  constructor(readonly sessionId: string, readonly backendSessionId: string,
    readonly launch: Launch, readonly emit: (event: DriverEvent) => void) {}
  async start() {}
  async prompt(text: string) { this.prompts.push(text); }
  async cancel() {}
  async resolvePermission(_decision: PermissionDecision) {}
  async dispose() {
    this.disposed += 1;
    await this.launch.onTaskCloseOutcome?.(this.closeOutcome);
  }
}
const drivers: FakeDriver[] = [];
const launches: Launch[] = [];
function useAdmittingFactory() {
  _setDriverFactoryForTests(async (_agent, id, launch, onEvent, ownDriver) => {
    launches.push(launch);
    const driver = new FakeDriver(id, launch.backendSessionId ?? `recovery-coordinator-${id}`, launch, onEvent);
    drivers.push(driver); ownDriver(driver);
    if (launch.taskScope) await launch.onTaskAdmitted!(driver.backendSessionId, freshReceipt(launch), WORKSPACE.path);
    return driver;
  });
}
async function createScoped() { return useNekoSessionStore.getState().createSession(AGENT, WORKSPACE, null, OPTIONS); }
async function coldHydrate(id: string) {
  _clearLiveDriversForTests();
  useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, hydrated: false, hydrating: false, hydrationError: null });
  await useNekoSessionStore.getState().hydrate();
  useNekoSessionStore.getState().setActiveSession(id);
}
function loseResponse(method: "session/new" | "session/load") {
  _setDriverFactoryForTests(async (_agent, _id, launch) => {
    launches.push(launch);
    throw new AcpTransportError("timeout", method, 1, "Synthetic lost task response");
  });
}

describe("Scoped recovery deletion and cold-start boundaries", () => {
  beforeEach(() => {
    _clearLiveDriversForTests();
    memory.values.clear(); memory.recoveryFailuresRemaining = 0;
    memory.rejectRecoveryTranscript = false; memory.rejectAllWrites = false; memory.rejectedWrites = 0;
    drivers.length = 0; launches.length = 0;
    vi.mocked(deleteStoreStrict).mockClear();
    vi.mocked(clearStore).mockClear();
    useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, hydrated: false, hydrating: false, hydrationError: null });
    useNekoAgentStore.setState({ agents: [AGENT], isLoading: false, error: null });
    useKnowledgeConnectionStore.setState({ status: "disconnected", error: null });
    _setNativeControlReaderForTests(() => nativeControl);
    useAdmittingFactory();
  });
  afterEach(() => {
    memory.recoveryFailuresRemaining = 0; memory.rejectRecoveryTranscript = false; memory.rejectAllWrites = false;
    _clearLiveDriversForTests(); _setDriverFactoryForTests(undefined); _setNativeControlReaderForTests(undefined);
  });

  it.each(["session/new", "session/load"] as const)("confirmed deletion after uncertain %s removes Wiii history/mapping without creating or deleting a Neko task", async (method) => {
    let id: string;
    if (method === "session/new") { loseResponse(method); id = await createScoped(); }
    else {
      id = await createScoped(); await coldHydrate(id); loseResponse(method);
      await useNekoSessionStore.getState().sendPrompt("One explicit load, never replay");
    }
    expect(session(id).taskScope).toMatchObject({ state: "recovery-required" });
    expect(snapshot(id)?.entry.taskScope?.state).toBe("recovery-required");
    useNekoSessionStore.setState(state => ({ sessions: { ...state.sessions,
      [id]: { ...state.sessions[id], messages: [{ id: "synthetic-history", role: "user",
        text: "SYNTHETIC_HISTORY_DELETE_MARKER" }] } } }));
    await persistSessionStrict(session(id));
    expect(snapshot(id)?.messages).toMatchObject([{ text: "SYNTHETIC_HISTORY_DELETE_MARKER" }]);
    const nekoCheckpoint = { taskId: "canonical-recovery-task", checkpoint: "synthetic-Neko-owned-content" };
    memory.values.set("synthetic-neko-owned-checkpoint:canonical-recovery-task", copy(nekoCheckpoint));
    const starts = launches.length;
    await useNekoSessionStore.getState().deleteSession(id);
    expect(session(id)).toBeUndefined();
    expect(snapshot(id)).toBeUndefined();
    expect(memory.values.has(`neko-chill-native-runtime.json:session:${id}`)).toBe(false);
    expect(launches).toHaveLength(starts);
    expect(deleteStoreStrict).toHaveBeenCalledTimes(2);
    expect(vi.mocked(deleteStoreStrict).mock.calls.every(([store, key]) =>
      ["neko-chill-sessions.json", "neko-chill-native-runtime.json"].includes(store) && key === `session:${id}`)).toBe(true);
    expect(clearStore).not.toHaveBeenCalled();
    expect(memory.values.get("synthetic-neko-owned-checkpoint:canonical-recovery-task")).toEqual(nekoCheckpoint);
    expect(JSON.stringify([...memory.values.values()])).not.toContain("SYNTHETIC_HISTORY_DELETE_MARKER");
    await coldHydrate(id);
    expect(session(id)).toBeUndefined();
    expect(launches).toHaveLength(starts);
  });

  it("confirmed normal deletion still removes the selected history while preserving another session", async () => {
    const selected = await createScoped();
    const other = await useNekoSessionStore.getState().createSession(AGENT, WORKSPACE, null, { title: "Phiên khác" });
    await useNekoSessionStore.getState().deleteSession(selected);
    expect(session(selected)).toBeUndefined(); expect(snapshot(selected)).toBeUndefined();
    expect(session(other)).toBeDefined(); expect(snapshot(other)).toBeDefined();
    expect(drivers[0].disposed).toBe(1); expect(drivers[1].disposed).toBe(0);
  });

  it("a one-shot strict close recovery write failure is repaired durably before a cold restart can load", async () => {
    const id = await createScoped(); drivers[0].closeOutcome = "uncertain";
    memory.recoveryFailuresRemaining = 1;
    await useNekoSessionStore.getState().closeSession(id);
    expect(memory.rejectedWrites).toBe(1);
    expect(snapshot(id)?.entry.taskScope).toMatchObject({ state: "recovery-required", reason: "close-unconfirmed" });
    const starts = launches.length;
    await coldHydrate(id);
    expect(session(id).taskScope).toMatchObject({ state: "recovery-required", reason: "close-unconfirmed" });
    await useNekoSessionStore.getState().sendPrompt("Do not resume uncertain close");
    expect(launches).toHaveLength(starts); expect(drivers[0].prompts).toEqual([]);
  });

  it("native companion uncertainty blocks an explicit reload even when the transcript retains older bound bytes", async () => {
    const id = await createScoped();
    const olderBound = copy(snapshot(id)); drivers[0].closeOutcome = "uncertain";
    memory.rejectRecoveryTranscript = true;
    await useNekoSessionStore.getState().closeSession(id);
    expect(memory.rejectedWrites).toBeGreaterThanOrEqual(2);
    expect(snapshot(id)).toEqual(olderBound);
    memory.rejectRecoveryTranscript = false;
    const starts = launches.length;
    await coldHydrate(id);
    expect(session(id).events.some(event => event.data.type === "native-runtime-cleanup-uncertain")).toBe(true);
    expect(session(id).taskScope).toMatchObject({ state: "bound", receipt: { activationEpoch: 1 } });
    expect(launches).toHaveLength(starts);
    await useNekoSessionStore.getState().sendPrompt("No unsafe reload from an old bound snapshot");
    expect(launches).toHaveLength(starts); expect(drivers[0].prompts).toEqual([]);
    expect(session(id).status).toBe("error");
  });

  it("complete durable write failure does not cause an automatic prompt/load on hydration", async () => {
    const id = await createScoped();
    const olderBound = copy(snapshot(id)); drivers[0].closeOutcome = "uncertain";
    memory.rejectAllWrites = true;
    await useNekoSessionStore.getState().closeSession(id);
    expect(memory.rejectedWrites).toBeGreaterThanOrEqual(2);
    expect(snapshot(id)).toEqual(olderBound);
    memory.rejectAllWrites = false;
    const starts = launches.length;
    await coldHydrate(id);
    expect(launches).toHaveLength(starts);
    expect(drivers.every(driver => driver.prompts.length === 0)).toBe(true);
    expect(session(id).taskScope).toMatchObject({ state: "bound", receipt: { activationEpoch: 1 } });
    // This asserts no automatic replay only. A later explicit load needs a
    // separate authoritative native-journal/writer-lock conformance fixture.
  });

  it.each(["writer_unavailable", "recovery_required"] as const)("after total write failure an explicit load rejected as %s retains the original receipt without replay/new/legacy fallback", async (kind) => {
    const id = await createScoped(); drivers[0].closeOutcome = "uncertain";
    const originalReceipt = copy(snapshot(id)?.entry.taskScope?.receipt);
    memory.rejectAllWrites = true;
    await useNekoSessionStore.getState().closeSession(id);
    memory.rejectAllWrites = false;
    await coldHydrate(id);
    const starts = launches.length;
    _setDriverFactoryForTests(async (_agent, _id, launch) => {
      launches.push(launch);
      expect(launch.backendSessionId).toBe(drivers[0].backendSessionId);
      expect(launch.taskScope?.receipt).toEqual(originalReceipt);
      expect(snapshot(id)?.entry.taskScope?.state).toBe("pending-load");
      throw new AcpRpcError(2, "session/load", { code: -32002, message: "Task requires explicit recovery",
        data: { "neko.taskError": { version: 1, kind, action: "retain_mapping_and_request_recovery" } } });
    });
    await useNekoSessionStore.getState().sendPrompt("A new explicit request, not a replay");
    expect(launches).toHaveLength(starts + 1);
    expect(session(id).taskScope).toMatchObject({ state: "recovery-required",
      reason: kind === "writer_unavailable" ? "writer-unavailable" : "recovery-required", receipt: originalReceipt });
    expect(snapshot(id)?.entry.taskScope?.receipt).toEqual(originalReceipt);
    expect(drivers[0].prompts).toEqual([]);
    useNekoSessionStore.setState(state => ({ sessions: { ...state.sessions, [id]: { ...state.sessions[id], status: "exited" } } }));
    await useNekoSessionStore.getState().sendPrompt("No automatic recovery replay");
    expect(launches).toHaveLength(starts + 1); expect(drivers).toHaveLength(1);
    expect(session(id).messages).toEqual([]);
  });
});
