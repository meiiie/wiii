import { describe, expect, it, vi } from "vitest";
import { AcpDriver, ACP_ADMISSION_MAX_BYTES, type AcpTaskScopeOptions } from "@/neko-chill/drivers/acp/driver";
import type { AcpTransport } from "@/neko-chill/drivers/acp/client";
import type { DriverEvent } from "@/neko-chill/drivers/types";
import {
  NEKO_TASK_PROTOCOL, buildNekoTaskEchoMeta, buildNekoTaskLoadMeta, buildNekoTaskNewMeta,
  type NekoTaskReceipt,
} from "@/neko-chill/drivers/acp/task-protocol";

type Frame = Record<string, any>;
class ScopeTransport implements AcpTransport {
  readonly sent: Frame[] = [];
  killed = false;
  killFailures = 0;
  killAttempts = 0;
  private readonly lines: Array<(line: string) => void> = [];
  private readonly exits: Array<(code: number | null) => void> = [];
  async send(line: string): Promise<void> { this.sent.push(JSON.parse(line)); }
  onLine(handler: (line: string) => void): void { this.lines.push(handler); }
  onExit(handler: (code: number | null) => void): void { this.exits.push(handler); }
  async kill(): Promise<void> {
    this.killAttempts++;
    if (this.killFailures > 0) { this.killFailures--; throw new Error("Synthetic kill failure"); }
    this.killed = true;
  }
  inject(frame: Frame): void { this.lines.forEach(handler => handler(JSON.stringify(frame))); }
  exit(): void { this.exits.forEach(handler => handler(0)); }
  request(method: string): Frame {
    const request = this.sent.filter(frame => frame.method === method).at(-1);
    if (!request) throw new Error(`Missing synthetic request ${method}`);
    return request;
  }
  result(method: string, result: unknown): void {
    this.inject({ jsonrpc: "2.0", id: this.request(method).id, result });
  }
}
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const root = "E:\\MeiiieGroup\\integration-tests\\scope-fixture";
const backendId = "canonical-session";
const receipt: NekoTaskReceipt = Object.freeze({ version: 1, mode: "fixed-active-task",
  id: "canonical-task", label: "Sửa lỗi riêng", root,
  activationEpoch: 1, activationId: "activation-one" });
const init = { protocolVersion: 1, agentCapabilities: {
  loadSession: true, sessionCapabilities: { resume: {}, close: {} },
}, _meta: { "neko.taskProtocol": NEKO_TASK_PROTOCOL } };
const fullMeta = (current: NekoTaskReceipt = receipt) => ({ "neko.task": current });
const newResult = (current: NekoTaskReceipt = receipt) => ({
  sessionId: backendId, _meta: fullMeta(current), configOptions: [{
    id: "model", name: "Model", category: "model", type: "select", currentValue: "bunny",
    options: [{ value: "bunny", name: "Bunny" }],
  }],
});
function update(transport: ScopeTransport, text: string, current: unknown = receipt, id = backendId): void {
  transport.inject({ jsonrpc: "2.0", method: "session/update", params: {
    sessionId: id, _meta: { "neko.task": current },
    update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text } },
  } });
}
function permission(transport: ScopeTransport, id: number, current: unknown = receipt, sessionId = backendId): void {
  transport.inject({ jsonrpc: "2.0", id, method: "session/request_permission", params: {
    sessionId, _meta: { "neko.task": current },
    toolCall: { toolCallId: "edit-1", title: "Edit synthetic sample" },
    options: [{ optionId: "allow", name: "Allow once", kind: "allow_once" }],
  } });
}
function harness(overrides: Partial<AcpTaskScopeOptions> = {}, resumeSessionId?: string) {
  const transport = new ScopeTransport(); const events: DriverEvent[] = [];
  const admitted = vi.fn(async (_id: string, _receipt: NekoTaskReceipt) => {});
  const closed = vi.fn(async (_outcome: "acknowledged" | "uncertain") => {});
  const driver = new AcpDriver({ sessionId: "local-thread", cwd: root, transport,
    resumeSessionId, onEvent: event => events.push(event), taskScope: {
      authorizedRoot: root, label: receipt.label, onAdmitted: admitted, onCloseOutcome: closed,
      ...overrides,
    },
  });
  return { transport, events, admitted, closed, driver };
}
async function begin(h: ReturnType<typeof harness>, initializeResult: unknown = init) {
  const starting = h.driver.start();
  // Attach before injecting a deliberately invalid protocol result.
  void starting.catch(() => {});
  await tick(); h.transport.result("initialize", initializeResult); await tick();
  return { starting };
}
async function started(h: ReturnType<typeof harness>, result: unknown = newResult()) {
  const { starting } = await begin(h);
  h.transport.result("session/new", result); await starting;
}
async function closeWith(h: ReturnType<typeof harness>, result: unknown = { _meta: fullMeta() }) {
  const closing = h.driver.dispose(); await tick(); h.transport.result("session/close", result); await closing;
}

describe("ACP Neko fixed-task admission and durable mapping gate", () => {
  it.each([
    { protocolVersion: 1 },
    { ...init, _meta: { "neko.taskProtocol": { version: 2, mode: "fixed-active-task" } } },
    { ...init, protocolVersion: 2 },
  ])("fails before session creation for missing/unsupported capability: %j", async advertised => {
    const h = harness(); const { starting } = await begin(h, advertised);
    await expect(starting).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/new")).toHaveLength(0);
    expect(h.admitted).not.toHaveBeenCalled();
    await expect(h.driver.prompt("first prompt")).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/prompt")).toHaveLength(0);
    await h.driver.dispose(); expect(h.closed).not.toHaveBeenCalled();
  });
  it("requires close support before creating a scoped session", async () => {
    const h = harness(); const { starting } = await begin(h, {
      ...init, agentCapabilities: { loadSession: true, sessionCapabilities: { resume: {} } },
    });
    await expect(starting).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/new")).toHaveLength(0);
    await h.driver.dispose();
  });
  it("holds full outer receipts/events and approvals until the mapping commit finishes", async () => {
    let commit!: () => void;
    const persisted = new Promise<void>(resolve => { commit = resolve; });
    const h = harness({ onAdmitted: vi.fn(() => persisted) });
    const { starting } = await begin(h);
    expect(h.transport.request("session/new").params._meta).toEqual(buildNekoTaskNewMeta(receipt.label));
    update(h.transport, "valid buffered");
    update(h.transport, "stale buffered", { ...receipt, activationId: "stale" });
    update(h.transport, "foreign buffered", receipt, "another-session");
    h.transport.result("session/new", newResult()); await tick();
    expect(h.driver.backendSessionId).toBeNull();
    expect(h.events).toHaveLength(0);
    permission(h.transport, 700); await tick();
    expect(h.transport.sent.find(frame => frame.id === 700)?.result).toEqual({ outcome: { outcome: "cancelled" } });
    await expect(h.driver.prompt("too early")).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/prompt")).toHaveLength(0);
    commit(); await starting;
    expect(h.driver.backendSessionId).toBe(backendId);
    expect(h.events.filter(event => event.type === "answer-delta")).toEqual([
      { type: "answer-delta", sessionId: "local-thread", text: "valid buffered" },
    ]);
    expect(h.driver.runtime.capabilities).not.toContain("session-config");
    expect(h.events.filter(event => event.type === "session-controls")).toContainEqual({
      type: "session-controls", sessionId: "local-thread", controls: [],
    });
    await closeWith(h);
  });
  it.each([
    { sessionId: backendId },
    newResult({ ...receipt, root: "E:\\different-root" }),
    newResult({ ...receipt, activationEpoch: 2 }),
  ])("keeps first prompt closed after invalid receipt: %j", async result => {
    const h = harness(); const { starting } = await begin(h);
    h.transport.result("session/new", result); await expect(starting).rejects.toThrow();
    expect(h.admitted).not.toHaveBeenCalled(); expect(h.driver.backendSessionId).toBeNull();
    await expect(h.driver.prompt("first prompt")).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/prompt")).toHaveLength(0);
    await h.driver.dispose(); expect(h.closed).toHaveBeenCalledOnce();
    expect(h.closed).toHaveBeenCalledWith("uncertain");
  });
  it("retains valid private close correlation after durable admission fails", async () => {
    const h = harness({ onAdmitted: vi.fn(async () => { throw new Error("synthetic persistence failure"); }) });
    const { starting } = await begin(h); h.transport.result("session/new", newResult());
    await expect(starting).rejects.toThrow("synthetic persistence failure");
    expect(h.driver.backendSessionId).toBeNull();
    await expect(h.driver.prompt("must not run")).rejects.toThrow();
    const closing = h.driver.dispose(); await tick();
    expect(h.transport.request("session/close").params).toEqual({ sessionId: backendId, _meta: buildNekoTaskEchoMeta(receipt) });
    h.transport.result("session/close", { _meta: fullMeta() }); await closing;
    expect(h.closed).toHaveBeenCalledWith("acknowledged"); expect(h.transport.killed).toBe(true);
  });
  it("kills before waiting for delayed admission persistence, then serializes close outcome", async () => {
    let commit!: () => void; const order: string[] = [];
    const pending = new Promise<void>(resolve => { commit = resolve; });
    const h = harness({ onAdmitted: async () => { await pending; order.push("admission settled"); },
      onCloseOutcome: async outcome => { order.push(outcome); } });
    const { starting } = await begin(h); h.transport.result("session/new", newResult()); await tick();
    const closing = h.driver.dispose(); await tick();
    h.transport.result("session/close", { _meta: fullMeta() }); await tick();
    expect(h.transport.killed).toBe(true); expect(order).toEqual([]);
    commit(); await closing; await expect(starting).rejects.toThrow();
    expect(order).toEqual(["admission settled", "acknowledged"]);
    expect(h.driver.backendSessionId).toBeNull();
    expect(h.events.some(event => event.type === "answer-delta" || event.type === "permission-request")).toBe(false);
  });
  it("loads exact saved mapping, requires a fresh activation and accepts absent response sessionId", async () => {
    const fresh = { ...receipt, activationEpoch: 2, activationId: "activation-two" } as const;
    const h = harness({ expectedReceipt: receipt }, backendId); const { starting } = await begin(h);
    expect(h.transport.request("session/resume").params).toEqual({ sessionId: backendId, cwd: root,
      mcpServers: [], _meta: buildNekoTaskLoadMeta(receipt) });
    update(h.transport, "old activation", receipt); update(h.transport, "fresh activation", fresh);
    h.transport.result("session/resume", { _meta: fullMeta(fresh) }); await starting;
    expect(h.admitted).toHaveBeenCalledWith(backendId, fresh);
    expect(h.events.filter(event => event.type === "answer-delta")).toEqual([
      { type: "answer-delta", sessionId: "local-thread", text: "fresh activation" },
    ]);
    await closeWith(h, { _meta: fullMeta(fresh) });
  });
  it("does not replace/retry a scoped mapping after a typed writer recovery error", async () => {
    const h = harness({ expectedReceipt: receipt }, backendId); const { starting } = await begin(h);
    const request = h.transport.request("session/resume");
    h.transport.inject({ jsonrpc: "2.0", id: request.id, error: { code: -32002, message: "Recovery required", data: {
      "neko.taskError": { version: 1, kind: "writer_unavailable", action: "retain_mapping_and_request_recovery" },
    } } });
    await expect(starting).rejects.toMatchObject({ code: -32002 });
    expect(h.admitted).not.toHaveBeenCalled();
    expect(h.transport.sent.filter(frame => frame.method === "session/resume")).toHaveLength(1);
    expect(h.transport.sent.filter(frame => frame.method === "session/new" || frame.method === "session/prompt")).toHaveLength(0);
    await h.driver.dispose(); expect(h.closed).toHaveBeenCalledWith("uncertain");
  });
  it("does not opt into prior-receipt recovery or accept an extra activation increment", async () => {
    const h = harness({ expectedReceipt: receipt }, backendId); const { starting } = await begin(h);
    h.transport.result("session/resume", { _meta: {
      ...fullMeta({ ...receipt, activationEpoch: 3, activationId: "activation-three" }),
      "neko.taskRecovery": { version: 1, kind: "prior_receipt_retry" },
    } });
    await expect(starting).rejects.toThrow(); expect(h.admitted).not.toHaveBeenCalled();
    await expect(h.driver.prompt("no implicit retry")).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/resume")).toHaveLength(1);
    expect(h.transport.sent.filter(frame => frame.method === "session/new" || frame.method === "session/prompt")).toHaveLength(0);
    await h.driver.dispose(); expect(h.closed).toHaveBeenCalledWith("uncertain");
  });
  it("counts outer metadata in the pre-admission buffer bound", async () => {
    const h = harness(); const { starting } = await begin(h);
    h.transport.inject({ jsonrpc: "2.0", method: "session/update", params: {
      sessionId: backendId, _meta: { ...fullMeta(), syntheticOversize: "a".repeat(ACP_ADMISSION_MAX_BYTES) },
      update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "never projected" } },
    } });
    await expect(starting).rejects.toThrow(); expect(h.admitted).not.toHaveBeenCalled();
    expect(h.events.some(event => event.type === "answer-delta")).toBe(false);
    await expect(h.driver.prompt("first prompt")).rejects.toThrow();
    await h.driver.dispose(); expect(h.transport.killed).toBe(true);
  });
});

describe("ACP Neko fixed-task event, turn and close correlation", () => {
  it("ignores stale/foreign/missing receipt events and cancels permissions without showing approval", async () => {
    const h = harness(); await started(h); h.events.length = 0;
    for (const [index, current] of [null, { ...receipt, activationEpoch: 2 }, { ...receipt, id: "foreign-task" }].entries()) {
      update(h.transport, "must not project", current);
      permission(h.transport, 801 + index, current);
    }
    h.transport.inject({ jsonrpc: "2.0", method: "session/update", params: {
      sessionId: backendId, update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "missing receipt" } },
    } });
    h.transport.inject({ jsonrpc: "2.0", id: 879, method: "session/request_permission", params: {
      sessionId: backendId, toolCall: { title: "Missing receipt" }, options: [],
    } });
    permission(h.transport, 880, receipt, "foreign-session"); await tick();
    expect(h.events).toHaveLength(0);
    const cancelled = h.transport.sent.filter(frame => frame.result?.outcome?.outcome === "cancelled");
    expect(cancelled).toHaveLength(5);
    update(h.transport, "current event"); permission(h.transport, 881); await tick();
    const request = h.events.find(event => event.type === "permission-request");
    expect(request?.type).toBe("permission-request");
    if (request?.type !== "permission-request") throw new Error("Missing permission fixture");
    await h.driver.resolvePermission({ requestId: request.request.requestId, optionId: "allow" });
    await h.driver.resolvePermission({ requestId: request.request.requestId, optionId: "allow" }); await tick();
    expect(h.transport.sent.filter(frame => frame.id === 881)).toEqual([
      { jsonrpc: "2.0", id: 881, result: { outcome: { outcome: "selected", optionId: "allow" } } },
    ]);
    await closeWith(h);
  });
  it("blocks task switching and configuration before wire dispatch", async () => {
    const h = harness(); await started(h);
    await expect(h.driver.prompt(" /task new another ")).rejects.toThrow();
    await expect(h.driver.prompt("/task use other-task")).rejects.toThrow();
    await expect(h.driver.setConfigOption("config:model", "bunny")).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/prompt" || frame.method === "session/set_config_option")).toHaveLength(0);
    const turn = h.driver.prompt("/task status"); await tick();
    expect(h.transport.request("session/prompt").params._meta).toEqual(buildNekoTaskEchoMeta(receipt));
    h.transport.result("session/prompt", { stopReason: "end_turn", _meta: fullMeta() }); await turn;
    expect(h.events).toContainEqual({ type: "turn-finished", sessionId: "local-thread", stopReason: "end_turn" });
    await closeWith(h);
  });
  it("echoes cancel but accepts late tool updates before the receipt-validated terminal", async () => {
    const h = harness(); await started(h); const turn = h.driver.prompt("Read only"); await tick();
    await h.driver.cancel();
    expect(h.transport.request("session/cancel").params).toEqual({ sessionId: backendId, _meta: buildNekoTaskEchoMeta(receipt) });
    expect(h.events.some(event => event.type === "turn-finished")).toBe(false);
    h.transport.inject({ jsonrpc: "2.0", method: "session/update", params: { sessionId: backendId, _meta: fullMeta(),
      update: { sessionUpdate: "tool_call_update", toolCallId: "read-after-cancel", status: "completed" },
    } });
    h.transport.result("session/prompt", { stopReason: "cancelled", _meta: fullMeta() }); await turn;
    expect(h.events.some(event => event.type === "activity" && event.activity.status === "completed")).toBe(true);
    expect(h.events).toContainEqual({ type: "turn-finished", sessionId: "local-thread", stopReason: "cancelled" });
    await closeWith(h);
  });
  it.each([{}, { _meta: fullMeta({ ...receipt, id: "foreign-task" }) },
    { _meta: fullMeta({ ...receipt, activationId: "stale" }) }])(
    "does not turn a missing/stale result receipt into cancellation confirmation: %j", async result => {
      const h = harness(); await started(h); const turn = h.driver.prompt("Synthetic task"); await tick();
      h.transport.result("session/prompt", { stopReason: "cancelled", ...result }); await turn;
      expect(h.events.some(event => event.type === "turn-finished")).toBe(false);
      expect(h.events.some(event => event.type === "error" && event.fatal)).toBe(true);
      await expect(h.driver.prompt("must not retry")).rejects.toThrow();
      expect(h.transport.sent.filter(frame => frame.method === "session/prompt")).toHaveLength(1);
      await closeWith(h);
    });
  it.each([{}, { _meta: fullMeta({ ...receipt, activationEpoch: 2 }) }])(
    "marks a missing/stale close receipt uncertain: %j", async result => {
      const h = harness(); await started(h); await closeWith(h, result);
      expect(h.closed).toHaveBeenCalledOnce(); expect(h.closed).toHaveBeenCalledWith("uncertain");
      expect(h.transport.killed).toBe(true);
      expect(h.transport.sent.filter(frame => frame.method === "session/close")).toHaveLength(1);
    });
  it("cancels a pending scoped permission after an invalid prompt receipt and ignores a late Allow", async () => {
    const h = harness(); await started(h); const turn = h.driver.prompt("Synthetic task"); await tick();
    permission(h.transport, 1200); await tick();
    const request = h.events.find(event => event.type === "permission-request");
    if (request?.type !== "permission-request") throw new Error("Missing permission fixture");
    h.transport.result("session/prompt", { stopReason: "end_turn" }); await turn; await tick();
    expect(h.transport.sent.filter(frame => frame.id === 1200)).toEqual([
      { jsonrpc: "2.0", id: 1200, result: { outcome: { outcome: "cancelled" } } },
    ]);
    await h.driver.resolvePermission({ requestId: request.request.requestId, optionId: "allow" }); await tick();
    expect(h.transport.sent.filter(frame => frame.id === 1200)).toHaveLength(1);
    expect(h.events.some(event => event.type === "turn-finished")).toBe(false);
    await expect(h.driver.prompt("no retry")).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/prompt")).toHaveLength(1);
    await closeWith(h);
  });
  it("cancels a pending scoped approval when a process exit wins before the UI decision", async () => {
    const h = harness(); await started(h); permission(h.transport, 1201); await tick();
    const request = h.events.find(event => event.type === "permission-request");
    if (request?.type !== "permission-request") throw new Error("Missing permission fixture");
    h.transport.exit();
    await h.driver.resolvePermission({ requestId: request.request.requestId, optionId: "allow" }); await tick();
    expect(h.transport.sent.filter(frame => frame.id === 1201)).toEqual([
      { jsonrpc: "2.0", id: 1201, result: { outcome: { outcome: "cancelled" } } },
    ]);
    await closeWith(h);
  });
  it("keeps close timeout uncertain and kills without replaying or replacing the session", async () => {
    const h = harness(); await started(h); vi.useFakeTimers();
    try {
      const closing = h.driver.dispose();
      await vi.advanceTimersByTimeAsync(0); expect(h.transport.request("session/close")).toBeDefined();
      await vi.advanceTimersByTimeAsync(1001); await closing;
      expect(h.closed).toHaveBeenCalledWith("uncertain"); expect(h.transport.killed).toBe(true);
      expect(h.transport.sent.filter(frame => frame.method === "session/close")).toHaveLength(1);
      expect(h.transport.sent.filter(frame => frame.method === "session/new")).toHaveLength(1);
    } finally { vi.useRealTimers(); }
  });
  it("reuses a receipt-validated ACK across a transport-kill retry", async () => {
    const h = harness(); await started(h); h.transport.killFailures = 1;
    const closing = h.driver.dispose(); void closing.catch(() => {}); await tick();
    h.transport.result("session/close", { _meta: fullMeta() });
    await expect(closing).rejects.toThrow("Synthetic kill failure");
    expect(h.closed).toHaveBeenCalledOnce(); expect(h.closed).toHaveBeenCalledWith("acknowledged");
    await h.driver.dispose();
    expect(h.transport.sent.filter(frame => frame.method === "session/close")).toHaveLength(1);
    expect(h.closed).toHaveBeenCalledOnce(); expect(h.transport.killAttempts).toBe(2);
    expect(h.transport.killed).toBe(true);
  });
  it("retries only a failed durable close write while retaining the original ACK", async () => {
    const outcomes: string[] = [];
    const committed = vi.fn(async (outcome: "acknowledged" | "uncertain") => {
      outcomes.push(outcome);
      if (outcomes.length === 1) throw new Error("Synthetic close persistence failure");
    });
    const h = harness({ onCloseOutcome: committed }); await started(h);
    const closing = h.driver.dispose(); void closing.catch(() => {}); await tick();
    h.transport.result("session/close", { _meta: fullMeta() });
    await expect(closing).rejects.toThrow("Synthetic close persistence failure");
    await h.driver.dispose(); await h.driver.dispose();
    expect(outcomes).toEqual(["acknowledged", "acknowledged"]);
    expect(h.transport.sent.filter(frame => frame.method === "session/close")).toHaveLength(1);
    expect(h.transport.killAttempts).toBe(3);
  });
  it("shares the first close transaction across concurrent disposals", async () => {
    const h = harness(); await started(h);
    const first = h.driver.dispose(); const second = h.driver.dispose(); await tick();
    expect(h.transport.sent.filter(frame => frame.method === "session/close")).toHaveLength(1);
    h.transport.result("session/close", { _meta: fullMeta() }); await Promise.all([first, second]);
    expect(h.closed).toHaveBeenCalledOnce(); expect(h.closed).toHaveBeenCalledWith("acknowledged");
  });
  it("ignores disposed/late events and permissions even when their receipt matches", async () => {
    const h = harness(); await started(h); await closeWith(h); const count = h.events.length;
    update(h.transport, "late event"); permission(h.transport, 990); await tick();
    expect(h.events).toHaveLength(count);
    // A disposed client does not dispatch any late permission result or accept new prompts.
    await expect(h.driver.prompt("late prompt")).rejects.toThrow();
    expect(h.transport.sent.filter(frame => frame.method === "session/prompt")).toHaveLength(0);
  });
});


describe("passive execution receipt projection stays outside task-v1 authority", () => {
  const execution = (current = receipt, patch: Record<string, unknown> = {}) => ({
    version: 1, taskId: current.id, root: current.root, activationEpoch: current.activationEpoch,
    activationId: current.activationId, authorityId: null, policyId: "a".repeat(64),
    bashTarget: "host", bashExecutor: "local-process", nativeBackend: null,
    confinement: "none", osAuthority: "not-attested", approval: { mode: "default", yolo: false }, ...patch });
  const advertised = { ...init, _meta: { ...init._meta, "neko.executionProtocol": { version: 1 } } };
  function projected(h: ReturnType<typeof harness>) {
    return h.events.filter(event => event.type === "neko-execution-info");
  }
  async function admitExecution(h: ReturnType<typeof harness>, value: unknown = execution()) {
    const { starting } = await begin(h, advertised);
    h.transport.result("session/new", { ...newResult(), _meta: { ...fullMeta(), "neko.execution": value } });
    await starting;
  }
  function executionUpdate(h: ReturnType<typeof harness>, value: unknown, sessionId = backendId, current = receipt) {
    h.transport.inject({ jsonrpc: "2.0", method: "session/update", params: {
      sessionId, _meta: { "neko.task": current, "neko.execution": value },
      update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "safe transcript" } },
    } });
  }
  it("projects only after durable task admission, without execution opt-in or echo", async () => {
    let commit!: () => void;
    const persisted = new Promise<void>(resolve => { commit = resolve; });
    const h = harness({ onAdmitted: () => persisted });
    const { starting } = await begin(h, advertised);
    h.transport.result("session/new", { ...newResult(), _meta: { ...fullMeta(), "neko.execution": execution() } });
    await tick(); expect(projected(h)).toEqual([]);
    expect(h.transport.request("session/new").params._meta).toEqual(buildNekoTaskNewMeta(receipt.label));
    commit(); await starting;
    expect(projected(h)).toMatchObject([{ backendSessionId: backendId, projection: { status: "reported", bashTarget: "host" } }]);
    const prompting = h.driver.prompt("explicit synthetic prompt"); await tick();
    expect(h.transport.request("session/prompt").params._meta).toEqual(buildNekoTaskEchoMeta(receipt));
    h.transport.result("session/prompt", { stopReason: "end_turn", _meta: { ...fullMeta(), "neko.execution": execution() } });
    await prompting; await closeWith(h);
  });
  it("drops wrong-session and late-task projection before reading display data", async () => {
    const h = harness(); await admitExecution(h);
    const before = projected(h).length;
    executionUpdate(h, execution(receipt, { approval: { mode: "auto", yolo: true } }), "foreign-session");
    executionUpdate(h, execution(), backendId, { ...receipt, activationId: "retired" });
    expect(projected(h)).toHaveLength(before);
    await closeWith(h);
    executionUpdate(h, execution()); expect(projected(h)).toHaveLength(before);
  });
  it("rejects mismatched optional facts while preserving valid task transcript", async () => {
    const h = harness(); await admitExecution(h);
    executionUpdate(h, execution(receipt, { taskId: "foreign-task" }));
    expect(projected(h).at(-1)).toMatchObject({ projection: { status: "unverified" } });
    expect(h.events.at(-1)).toEqual({ type: "answer-delta", sessionId: "local-thread", text: "safe transcript" });
    await closeWith(h);
  });
  it("approval report updates independently, duplicate reports emit once", async () => {
    const h = harness(); await admitExecution(h);
    const current = execution(receipt, { approval: { mode: "auto", yolo: true } });
    executionUpdate(h, current); executionUpdate(h, current);
    expect(projected(h)).toHaveLength(2);
    expect(projected(h).at(-1)).toMatchObject({ projection: { status: "reported", bashTarget: "host", approvalMode: "auto", yolo: true } });
    await closeWith(h);
  });
  it("unknown execution metadata does not cancel a valid task-v1 permission", async () => {
    const h = harness(); await admitExecution(h);
    permission(h.transport, 1901); await tick();
    const event = h.events.find(event => event.type === "permission-request");
    if (!event || event.type !== "permission-request") throw new Error("missing permission");
    expect(projected(h).at(-1)).toMatchObject({ projection: { status: "unknown" } });
    await h.driver.resolvePermission({ requestId: event.request.requestId, optionId: "allow" });
    expect(h.transport.sent.filter(frame => frame.id === 1901)).toEqual([
      { jsonrpc: "2.0", id: 1901, result: { outcome: { outcome: "selected", optionId: "allow" } } },
    ]);
    await closeWith(h);
  });
});
