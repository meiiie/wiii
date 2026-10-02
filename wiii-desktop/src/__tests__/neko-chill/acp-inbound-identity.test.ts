import { describe, expect, it, vi } from "vitest";
import { AcpDriver, ACP_ADMISSION_MAX_BYTES, ACP_ADMISSION_MAX_UPDATES } from "@/neko-chill/drivers/acp/driver";
import type { AcpTransport } from "@/neko-chill/drivers/acp/client";
import type { DriverEvent } from "@/neko-chill/drivers/types";
import { WIII_SIGNAL_INBOX_AGENT_METHODS, type AgentComputerBridge } from "@/neko-computer/agent-bridge";

type Frame = Record<string, any>;
class Transport implements AcpTransport {
  sent: Frame[] = [];
  killed = false;
  lines: Array<(line: string) => void> = [];
  exits: Array<(code: number | null) => void> = [];
  async send(line: string) { this.sent.push(JSON.parse(line)); }
  onLine(handler: (line: string) => void) { this.lines.push(handler); }
  onExit(handler: (code: number | null) => void) { this.exits.push(handler); }
  async kill() { this.killed = true; }
  inject(frame: Frame) { this.lines.forEach(handler => handler(JSON.stringify(frame))); }
  exit() { this.exits.forEach(handler => handler(0)); }
}
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
function update(transport: Transport, sessionId: unknown, content: Record<string, unknown>) {
  transport.inject({ jsonrpc: "2.0", method: "session/update", params: { sessionId, update: content } });
}
function answer(transport: Transport, sessionId: unknown, text: string) {
  update(transport, sessionId, { sessionUpdate: "agent_message_chunk", content: { type: "text", text } });
}
function permission(transport: Transport, sessionId: unknown, id = "permission-rpc") {
  transport.inject({ jsonrpc: "2.0", id, method: "session/request_permission", params: {
    sessionId, toolCall: { toolCallId: "edit-1", title: "Edit synthetic file" },
    options: [{ optionId: "allow", name: "Allow once", kind: "allow_once" }],
  } });
}
async function pending(resumeSessionId?: string) {
  const transport = new Transport(); const events: DriverEvent[] = [];
  const driver = new AcpDriver({ sessionId: "visible-thread", cwd: "C:/synthetic", transport,
    ...(resumeSessionId ? { resumeSessionId } : {}), onEvent: event => events.push(event) });
  const starting = driver.start(); void starting.catch(() => {});
  await tick();
  transport.inject({ jsonrpc: "2.0", id: transport.sent[0].id, result: {
    protocolVersion: 1, agentCapabilities: { loadSession: true, sessionCapabilities: { resume: {}, close: {} } },
  } });
  await tick();
  const request = transport.sent.find(frame => frame.method === (resumeSessionId ? "session/resume" : "session/new"))!;
  return { driver, transport, events, starting, request };
}
async function admitted(id = "wire-session") {
  const state = await pending();
  state.transport.inject({ jsonrpc: "2.0", id: state.request.id, result: { sessionId: id } });
  await state.starting; state.events.length = 0;
  return state;
}
const invalidIds = [undefined, null, "", 7, {}, [], "other-session", "wire-session "];

describe("ACP inbound session identity and admission lifecycle", () => {
  it.each(invalidIds)("rejects invalid/foreign identity %j before any projection or cache write", async sessionId => {
    const { driver, transport, events } = await admitted();
    const capabilities = structuredClone(driver.runtime.observedProviderCapabilities);
    const variants = [
      { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "FOREIGN-ANSWER" } },
      { sessionUpdate: "agent_thought_chunk", content: { type: "text", text: "FOREIGN-THOUGHT" } },
      { sessionUpdate: "tool_call", toolCallId: "collision", title: "FOREIGN-TOOL", name: "evil" },
      { sessionUpdate: "tool_call_update", toolCallId: "collision", status: "completed" },
      { sessionUpdate: "plan", entries: [] },
      { sessionUpdate: "available_commands_update", availableCommands: [{ name: "foreign" }] },
      { sessionUpdate: "config_option_update", configOptions: [{ id: "foreign", name: "Foreign", type: "boolean", currentValue: true }] },
      { sessionUpdate: "current_mode_update", currentModeId: "foreign" },
      { sessionUpdate: "session_info_update", title: "FOREIGN-TITLE" },
    ];
    variants.forEach(value => update(transport, sessionId, value));
    expect(events).toEqual([]);
    expect(driver.runtime.observedProviderCapabilities).toEqual(capabilities);
    update(transport, "wire-session", { sessionUpdate: "tool_call_update", toolCallId: "collision", status: "in_progress" });
    const activity = events.find(event => event.type === "activity");
    expect(activity?.type === "activity" && activity.activity.title).toBe("Tool call");
    expect(activity?.type === "activity" && activity.activity.toolName).toBeUndefined();
  });

  it.each(invalidIds)("cancels invalid/foreign permission %j without UI or approval dispatch", async sessionId => {
    const { driver, transport, events } = await admitted();
    permission(transport, sessionId); await tick();
    expect(events).toEqual([]);
    expect(transport.sent.filter(frame => frame.id === "permission-rpc")).toEqual([
      { jsonrpc: "2.0", id: "permission-rpc", result: { outcome: { outcome: "cancelled" } } },
    ]);
    await driver.resolvePermission({ requestId: "perm-1", optionId: "allow" });
    expect(transport.sent.filter(frame => frame.id === "permission-rpc")).toHaveLength(1);
  });

  it("preserves exact opaque identity, offered options, and one decision for a valid permission", async () => {
    const { driver, transport, events } = await admitted("Case Sensitive ");
    answer(transport, "Case Sensitive ", "OWN");
    permission(transport, "Case Sensitive ");
    const event = events.find(event => event.type === "permission-request");
    expect(event?.type).toBe("permission-request");
    if (event?.type !== "permission-request") throw new Error("permission missing");
    await driver.resolvePermission({ requestId: event.request.requestId, optionId: "allow" });
    await driver.resolvePermission({ requestId: event.request.requestId, optionId: "allow" });
    await tick();
    expect(transport.sent.filter(frame => frame.id === "permission-rpc")).toEqual([
      { jsonrpc: "2.0", id: "permission-rpc", result: { outcome: { outcome: "selected", optionId: "allow" } } },
    ]);
    expect(events).toContainEqual({ type: "answer-delta", sessionId: "visible-thread", text: "OWN" });
  });

  it("holds bootstrap updates until response and flushes admitted identity only, in order", async () => {
    const { driver, transport, events, starting, request } = await pending();
    answer(transport, "wire-session", "FIRST"); answer(transport, "foreign", "FOREIGN");
    answer(transport, undefined, "MISSING"); answer(transport, "wire-session", "SECOND");
    permission(transport, "wire-session", "pre-admission"); await tick();
    expect(events).toEqual([]);
    expect(transport.sent.find(frame => frame.id === "pre-admission")?.result).toEqual({ outcome: { outcome: "cancelled" } });
    transport.inject({ jsonrpc: "2.0", id: request.id, result: { sessionId: "wire-session" } }); await starting;
    expect(events.filter(event => event.type === "answer-delta").map(event => event.text)).toEqual(["FIRST", "SECOND"]);
    expect(driver.backendSessionId).toBe("wire-session");
    expect(events.some(event => event.type === "permission-request")).toBe(false);
  });

  it("delays resume replay until success, supports omitted response ID and forbids replacement new", async () => {
    const { transport, events, starting, request } = await pending("saved-session");
    answer(transport, "saved-session", "SAVED"); answer(transport, "other", "FOREIGN"); expect(events).toEqual([]);
    transport.inject({ jsonrpc: "2.0", id: request.id, result: {} }); await starting;
    expect(events.filter(event => event.type === "answer-delta").map(event => event.text)).toEqual(["SAVED"]);
    expect(transport.sent.some(frame => frame.method === "session/new")).toBe(false);
  });

  it.each(["conflicting", "missing", "rpc-error"])("rejects %s admission without bootstrap leakage or fallback", async kind => {
    const { driver, transport, events, starting, request } = await pending(kind === "conflicting" ? "saved-session" : undefined);
    answer(transport, kind === "conflicting" ? "saved-session" : "wire-session", "UNADMITTED");
    transport.inject({ jsonrpc: "2.0", id: request.id, ...(kind === "rpc-error"
      ? { error: { code: -32603, message: "Synthetic fault" } }
      : { result: kind === "conflicting" ? { sessionId: "different" } : {} }) });
    await expect(starting).rejects.toThrow();
    expect(driver.backendSessionId).toBeNull(); expect(events).toEqual([]);
    answer(transport, "wire-session", "LATE"); permission(transport, "wire-session"); await tick();
    expect(events).toEqual([]);
    expect(transport.sent.filter(frame => frame.method === "session/new")).toHaveLength(kind === "conflicting" ? 0 : 1);
    expect(transport.sent.find(frame => frame.id === "permission-rpc")?.result).toEqual({ outcome: { outcome: "cancelled" } });
  });

  it("supports a replay at the explicit frame budget without truncation", async () => {
    const { transport, events, starting, request } = await pending();
    for (let n = 0; n < ACP_ADMISSION_MAX_UPDATES; n++) answer(transport, "wire-session", String(n));
    expect(events).toEqual([]);
    transport.inject({ jsonrpc: "2.0", id: request.id, result: { sessionId: "wire-session" } }); await starting;
    expect(events.filter(event => event.type === "answer-delta")).toHaveLength(ACP_ADMISSION_MAX_UPDATES);
  });

  it.each(["count", "utf8-bytes"])("fails the whole bootstrap on %s overflow, never prompts or silently truncates", async kind => {
    const { driver, transport, events, starting, request } = await pending();
    if (kind === "count") for (let n = 0; n <= ACP_ADMISSION_MAX_UPDATES; n++) answer(transport, "wire-session", "bounded");
    else answer(transport, "wire-session", "漢".repeat(Math.ceil(ACP_ADMISSION_MAX_BYTES / 3)));
    await expect(starting).rejects.toThrow(/vượt giới hạn/);
    transport.inject({ jsonrpc: "2.0", id: request.id, result: { sessionId: "wire-session" } }); await tick();
    expect(driver.backendSessionId).toBeNull(); expect(events.some(event => event.type === "answer-delta")).toBe(false);
    expect(events.filter(event => event.type === "error")).toHaveLength(1);
    await expect(driver.prompt("never replay")).rejects.toThrow();
    expect(transport.sent.some(frame => frame.method === "session/prompt")).toBe(false);
    await driver.dispose();
  });

  it.each(["dispose", "exit"])("fences synchronous %s after session response before its await continuation", async action => {
    const { driver, transport, events, starting, request } = await pending();
    answer(transport, "wire-session", "QUEUED");
    transport.inject({ jsonrpc: "2.0", id: request.id, result: { sessionId: "wire-session" } });
    if (action === "dispose") await driver.dispose(); else transport.exit();
    await expect(starting).rejects.toThrow();
    expect(driver.backendSessionId).toBeNull(); expect(events.some(event => event.type === "answer-delta" || event.type === "session-controls")).toBe(false);
  });

  it.each(["dispose", "exit"])("rejects admission promptly during never-settled preflight on %s", async action => {
    let finish!: (value: unknown) => void;
    const bridge: AgentComputerBridge = {
      handles: method => method === WIII_SIGNAL_INBOX_AGENT_METHODS.consult,
      handle: vi.fn(() => new Promise(resolve => { finish = resolve; })), dispose: vi.fn(async () => {}),
    };
    const transport = new Transport(); const events: DriverEvent[] = [];
    const driver = new AcpDriver({ sessionId: "visible-thread", cwd: "C:/synthetic", transport, computerBridge: bridge,
      onEvent: event => events.push(event) });
    const starting = driver.start(); void starting.catch(() => {});
    if (action === "dispose") await driver.dispose(); else transport.exit();
    await expect(starting).rejects.toThrow(/before session admission/);
    expect(transport.sent).toEqual([]);
    finish({}); await tick();
    expect(transport.sent).toEqual([]); expect(driver.backendSessionId).toBeNull();
  });

  it("keeps close ACK correlation while closing, and refuses all late presentation/permissions", async () => {
    const { driver, transport, events } = await admitted();
    const disposing = driver.dispose(); await tick();
    const close = transport.sent.find(frame => frame.method === "session/close")!; expect(close).toBeTruthy();
    answer(transport, "wire-session", "CLOSING"); permission(transport, "wire-session", "closing-permission"); await tick();
    expect(events).toEqual([]);
    expect(transport.sent.find(frame => frame.id === "closing-permission")?.result).toEqual({ outcome: { outcome: "cancelled" } });
    transport.inject({ jsonrpc: "2.0", id: close.id, result: {} }); await disposing;
    expect(transport.killed).toBe(true);
    answer(transport, "wire-session", "AFTER-DISPOSE"); expect(events).toEqual([]);
  });

  it("rejects a concurrent/repeated start instead of sending another initialize/new", async () => {
    const { driver, transport, starting, request } = await pending();
    await expect(driver.start()).rejects.toThrow(/not available/);
    expect(transport.sent.filter(frame => frame.method === "initialize")).toHaveLength(1);
    transport.inject({ jsonrpc: "2.0", id: request.id, result: { sessionId: "wire-session" } }); await starting;
    await expect(driver.start()).rejects.toThrow(/not available/);
  });

  it("cannot return a ready driver if it was disposed during the admission projection", async () => {
    const transport = new Transport(); let disposal: Promise<void> | undefined;
    const driver = new AcpDriver({ sessionId: "visible-thread", cwd: "C:/synthetic", transport,
      onEvent: event => { if (event.type === "session-controls") disposal = driver.dispose(); } });
    const starting = driver.start(); void starting.catch(() => {}); await tick();
    transport.inject({ jsonrpc: "2.0", id: transport.sent[0].id, result: { protocolVersion: 1,
      agentCapabilities: { sessionCapabilities: { close: {} } } } }); await tick();
    transport.inject({ jsonrpc: "2.0", id: transport.sent[1].id, result: { sessionId: "wire-session" } });
    await expect(starting).rejects.toThrow(/admission ended/); await tick();
    const close = transport.sent.find(frame => frame.method === "session/close")!;
    transport.inject({ jsonrpc: "2.0", id: close.id, result: {} }); await disposal;
    expect(driver.backendSessionId).toBeNull(); expect(transport.killed).toBe(true);
  });

  it("does not project disposed provider generation frames into a replacement sharing a visible thread", async () => {
    const old = await admitted("old-wire"); const next = await admitted("new-wire");
    const closing = old.driver.dispose(); await tick();
    const request = old.transport.sent.find(frame => frame.method === "session/close")!;
    old.transport.inject({ jsonrpc: "2.0", id: request.id, result: {} }); await closing;
    answer(old.transport, "old-wire", "STALE"); permission(old.transport, "old-wire");
    answer(next.transport, "old-wire", "CROSS-SESSION"); permission(next.transport, "old-wire"); await tick();
    expect(old.events).toEqual([]); expect(next.events).toEqual([]);
    answer(next.transport, "new-wire", "CURRENT");
    expect(next.events).toEqual([{ type: "answer-delta", sessionId: "visible-thread", text: "CURRENT" }]);
  });
});
