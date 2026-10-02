/** Real ACP adapter -> actual session store, with synthetic transport/storage.
 * This checks presentation/durability, not native root proof or live inference.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AcpDriver } from "@/neko-chill/drivers/acp/driver";
import type { AcpTransport } from "@/neko-chill/drivers/acp/client";
import type { NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";
import type { DetectedAgent } from "@/neko-chill/stores/neko-agent-store";

const values = vi.hoisted(() => new Map<string, unknown>());
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn(async (store: string, key: string, fallback: unknown) =>
    values.has(`${store}:${key}`) ? structuredClone(values.get(`${store}:${key}`)) : fallback),
  loadStoreStrict: vi.fn(async (store: string, key: string, fallback: unknown) =>
    values.has(`${store}:${key}`) ? structuredClone(values.get(`${store}:${key}`)) : fallback),
  saveStore: vi.fn(async (store: string, key: string, value: unknown) => {
    values.set(`${store}:${key}`, structuredClone(value));
  }),
  saveStoreStrict: vi.fn(async (store: string, key: string, value: unknown) => {
    values.set(`${store}:${key}`, structuredClone(value));
  }),
  deleteStore: vi.fn(async (store: string, key: string) => { values.delete(`${store}:${key}`); }),
  deleteStoreStrict: vi.fn(async (store: string, key: string) => { values.delete(`${store}:${key}`); }),
  clearStore: vi.fn(async () => {}),
}));

import {
  useNekoSessionStore, _setDriverFactoryForTests, _setNativeControlReaderForTests,
  _clearLiveDriversForTests,
} from "@/neko-chill/stores/neko-session-store";
import { persistSessionStrict } from "@/neko-chill/persistence";
import { RuntimeRegistry } from "@/neko-chill/runtime-manager";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useKnowledgeConnectionStore } from "@/workbench/knowledge";

const WORKSPACE = { path: "E:\\MeiiieGroup\\integration-tests\\wire-projection", name: "wire-projection" };
const AGENT: DetectedAgent = { id: "neko", name: "Neko Core", version: "1.7.0",
  found: true, availability: "available", supportsProfiles: true };
const receipt: NekoTaskReceipt = { version: 1, mode: "fixed-active-task",
  id: "canonical-task", label: "Synthetic work", root: WORKSPACE.path.toLowerCase(),
  activationEpoch: 1, activationId: "activation-one" };
const wireId = "canonical-coordinator";
type Frame = { jsonrpc?: string; id?: number; method?: string; params?: unknown; result?: unknown };
const native = {
  listSessions: async () => [],
  readEvents: async (streamId: string, afterSeq = 0) => ({ streamId, events: [], nextAfterSeq: afterSeq, hasMore: false }),
  unresolvedStartSessionIds: () => [], reconcilableStartSessionIds: async () => [],
  cancelUnresolvedStarts: async () => 0,
};
class Transport implements AcpTransport {
  sent: Frame[] = [];
  lines: Array<(line: string) => void> = [];
  exits: Array<(code: number | null) => void> = [];
  scoped = true;
  killed = false;
  async send(line: string) {
    const frame = JSON.parse(line) as Frame; this.sent.push(frame);
    if (frame.method === "session/close") {
      queueMicrotask(() => this.inject({ jsonrpc: "2.0", id: frame.id,
        result: this.scoped ? { _meta: { "neko.task": receipt } } : {} }));
    }
  }
  onLine(handler: (line: string) => void) { this.lines.push(handler); }
  onExit(handler: (code: number | null) => void) { this.exits.push(handler); }
  async kill() {
    if (this.killed) return;
    this.killed = true; this.exits.forEach(handler => handler(0));
  }
  inject(frame: Frame) { this.lines.forEach(handler => handler(JSON.stringify(frame))); }
  respond(method: string, result: unknown) {
    const request = [...this.sent].reverse().find(frame => frame.method === method);
    if (!request) throw new Error("Missing synthetic request");
    this.inject({ jsonrpc: "2.0", id: request.id, result });
  }
}
let transport: Transport;
let activeId: string | null;
let realDriver: AcpDriver;
function session() { return useNekoSessionStore.getState().sessions[activeId!]; }
async function admit(scoped = true, executionInfo?: unknown) {
  _setDriverFactoryForTests(async (_agent, id, launch, onEvent, ownDriver) => {
    transport = new Transport(); transport.scoped = scoped;
    const driver = new AcpDriver({ sessionId: id, cwd: WORKSPACE.path, transport, onEvent,
      ...(launch.taskScope ? { taskScope: {
        label: launch.taskScope.label, authorizedRoot: WORKSPACE.path,
        onAdmitted: (backendId, currentReceipt) => launch.onTaskAdmitted!(backendId, currentReceipt, WORKSPACE.path),
        onCloseOutcome: launch.onTaskCloseOutcome,
      } } : {}),
    });
    realDriver = driver;
    ownDriver(driver); await driver.start(); return driver;
  });
  const creating = useNekoSessionStore.getState().createSession(AGENT, WORKSPACE, null, scoped ? {
    title: receipt.label, projectId: "explicit-project",
    execution: { taskId: "explicit-work-item", runId: "explicit-run", environmentId: "explicit-environment" },
  } : {});
  await vi.waitFor(() => expect(transport?.sent.some(frame => frame.method === "initialize")).toBe(true));
  transport.respond("initialize", { protocolVersion: 1,
    agentCapabilities: { loadSession: true, sessionCapabilities: { resume: {}, close: {} } },
    ...(scoped ? { _meta: { "neko.taskProtocol": { version: 1, mode: "fixed-active-task" },
      ...(executionInfo ? { "neko.executionProtocol": { version: 1 } } : {}) } } : {}),
  });
  await vi.waitFor(() => expect(transport.sent.some(frame => frame.method === "session/new")).toBe(true));
  transport.respond("session/new", { sessionId: wireId,
    ...(scoped ? { _meta: { "neko.task": receipt,
      ...(executionInfo ? { "neko.execution": executionInfo } : {}) } } : {}),
  });
  activeId = await creating;
  expect(session().status).toBe("idle");
}

describe("scoped prompt receipt failures preserve store error and uncertain turn state", () => {
  beforeEach(() => {
    _clearLiveDriversForTests(); values.clear(); activeId = null;
    transport = undefined as unknown as Transport;
    useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, hydrated: false, hydrating: false, hydrationError: null });
    useNekoAgentStore.setState({ agents: [AGENT], isLoading: false, error: null });
    useKnowledgeConnectionStore.setState({ status: "disconnected", error: null });
    _setNativeControlReaderForTests(() => native);
  });
  afterEach(async () => {
    if (activeId) await useNekoSessionStore.getState().closeSession(activeId);
    _clearLiveDriversForTests(); _setDriverFactoryForTests(undefined);
    _setNativeControlReaderForTests(undefined);
  });

  it("keeps the newest report arriving after registry commit but before UI installation", async () => {
    const original = RuntimeRegistry.prototype.replace;
    const spy = vi.spyOn(RuntimeRegistry.prototype, "replace").mockImplementation(async function(this: RuntimeRegistry, ...args: Parameters<typeof original>) {
      const replacement = await original.apply(this, args);
      queueMicrotask(() => transport.inject({ jsonrpc: "2.0", method: "session/update", params: {
        sessionId: wireId, _meta: { "neko.task": receipt, "neko.execution": {
          version: 1, taskId: receipt.id, root: receipt.root, activationEpoch: receipt.activationEpoch,
          activationId: receipt.activationId, authorityId: null, policyId: "a".repeat(64),
          bashTarget: "host", bashExecutor: "local-process", nativeBackend: null,
          confinement: "none", osAuthority: "not-attested", approval: { mode: "auto", yolo: true },
        } }, update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "queued boundary" } },
      } }));
      return replacement;
    });
    try {
      await admit(true, { version: 1, taskId: receipt.id, root: receipt.root, activationEpoch: receipt.activationEpoch,
        activationId: receipt.activationId, authorityId: null, policyId: "a".repeat(64), bashTarget: "host",
        bashExecutor: "local-process", nativeBackend: null, confinement: "none", osAuthority: "not-attested",
        approval: { mode: "default", yolo: false } });
      expect(session().executionProjection?.value).toMatchObject({ status: "reported", approvalMode: "auto", yolo: true });
      expect(transport.sent.some(frame => frame.method === "session/prompt")).toBe(false);
    } finally { spy.mockRestore(); }
  });

  it("keeps execution reports ephemeral and clears them on normal close", async () => {
    await admit(true, { version: 1, taskId: receipt.id, root: receipt.root, activationEpoch: receipt.activationEpoch,
  activationId: receipt.activationId, authorityId: null, policyId: "a".repeat(64), bashTarget: "host",
  bashExecutor: "local-process", nativeBackend: null, confinement: "none", osAuthority: "not-attested",
  approval: { mode: "auto", yolo: false } });
    expect(session().executionProjection?.value).toMatchObject({ status: "reported", bashTarget: "host", approvalMode: "auto" });
    expect(session().executionProjection?.providerInstanceId).toBe(session().runtime?.instanceId);
    await persistSessionStrict(session());
    const snapshot = values.get(`neko-chill-sessions.json:session:${activeId}`) as Record<string, unknown>;
    expect(snapshot).not.toHaveProperty("executionProjection");
    await useNekoSessionStore.getState().closeSession(activeId!);
    expect(session().runtime).toBeNull();
    expect(session().executionProjection).toBeUndefined();
  });

  it("rejects a mismatched execution fact at the store seam and ignores another backend", async () => {
    await admit(true, { version: 1, taskId: receipt.id, root: receipt.root, activationEpoch: receipt.activationEpoch,
  activationId: receipt.activationId, authorityId: null, policyId: "a".repeat(64), bashTarget: "host",
  bashExecutor: "local-process", nativeBackend: null, confinement: "none", osAuthority: "not-attested",
  approval: { mode: "auto", yolo: false } });
    const projection = session().executionProjection!.value;
    if (projection.status !== "reported") throw new Error("missing reported state");
    useNekoSessionStore.getState().handleEvent({ type: "neko-execution-info", sessionId: activeId!,
      backendSessionId: "foreign-backend", projection: { ...projection, taskId: "foreign-task" } });
    expect(session().executionProjection!.value).toEqual(projection);
    useNekoSessionStore.getState().handleEvent({ type: "neko-execution-info", sessionId: activeId!,
      backendSessionId: wireId, projection: { ...projection, taskId: "foreign-task" } });
    expect(session().executionProjection!.value).toEqual({ status: "unverified" });
  });

  it.each([
    ["missing", { stopReason: "cancelled" }],
    ["wrong task", { stopReason: "end_turn", _meta: { "neko.task": { ...receipt, id: "foreign-task" } } }],
    ["stale activation", { stopReason: "cancelled", _meta: { "neko.task": { ...receipt, activationId: "old-activation" } } }],
    ["wrong root", { stopReason: "end_turn", _meta: { "neko.task": { ...receipt, root: "e:\\unapproved" } } }],
  ])("keeps a %s result receipt from reopening the composer or persisting a canonical terminal", async (_label, result) => {
    await admit();
    const prompting = useNekoSessionStore.getState().sendPrompt("One synthetic explicit request");
    await vi.waitFor(() => expect(transport.sent.some(frame => frame.method === "session/prompt")).toBe(true));
    transport.respond("session/prompt", result);
    await prompting;
    expect(session().status).toBe("error");
    expect(session().statusDetail).toBeTruthy();
    expect(session().events.filter(event => event.data.type === "turn-terminal")).toEqual([]);
    await persistSessionStrict(session());
    const snapshot = values.get(`neko-chill-sessions.json:session:${activeId}`) as { events: Array<{ data: { type: string } }> };
    expect(snapshot.events.filter(event => event.data.type === "turn-terminal")).toEqual([]);
    await useNekoSessionStore.getState().sendPrompt("This must not dispatch after the receipt failure");
    expect(transport.sent.filter(frame => frame.method === "session/prompt")).toHaveLength(1);
  });

  it("preserves a legacy provider's ordinary terminal without adding a task receipt requirement", async () => {
    await admit(false);
    const prompting = useNekoSessionStore.getState().sendPrompt("Legacy synthetic request");
    await vi.waitFor(() => expect(transport.sent.some(frame => frame.method === "session/prompt")).toBe(true));
    transport.respond("session/prompt", { stopReason: "end_turn" });
    await prompting;
    expect(session().status).toBe("idle");
    expect(session().events.filter(event => event.data.type === "turn-terminal")).toHaveLength(1);
    expect(session().taskScope).toBeUndefined();
  });

  it("revokes an already pending approval when prompt receipt validation fails, even for a late Allow", async () => {
    await admit();
    const prompting = useNekoSessionStore.getState().sendPrompt("Synthetic request with a pending edit");
    await vi.waitFor(() => expect(transport.sent.some(frame => frame.method === "session/prompt")).toBe(true));
    transport.inject({ jsonrpc: "2.0", id: 900, method: "session/request_permission", params: {
      sessionId: wireId, _meta: { "neko.task": receipt },
      toolCall: { toolCallId: "edit-fixture", title: "Edit synthetic fixture" },
      options: [{ optionId: "allow", name: "Allow once", kind: "allow_once" }],
    } });
    await vi.waitFor(() => expect(session().pendingPermission).not.toBeNull());
    const oldRequestId = session().pendingPermission!.requestId;
    transport.respond("session/prompt", { stopReason: "end_turn", _meta: {
      "neko.task": { ...receipt, activationId: "unverified-activation" },
    } });
    await prompting;
    expect(session().status).toBe("error");
    expect(session().pendingPermission).toBeNull();
    expect(session().resolvingPermissionId).toBeNull();
    await useNekoSessionStore.getState().resolvePermission("allow");
    await realDriver.resolvePermission({ requestId: oldRequestId, optionId: "allow" });
    await vi.waitFor(() => expect(transport.sent.filter(frame => frame.id === 900)).toHaveLength(1));
    expect(transport.sent.filter(frame => frame.id === 900)).toEqual([
      { jsonrpc: "2.0", id: 900, result: { outcome: { outcome: "cancelled" } } },
    ]);
    expect(session().events.filter(event => event.data.type === "turn-terminal")).toEqual([]);
  });
});
