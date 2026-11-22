import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { tryCloseOrphanAcpSession } from "@/neko/control-recovery";

const native = vi.hoisted(() => ({ invoke: vi.fn(), listen: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: native.invoke }));
vi.mock("@tauri-apps/api/event", () => ({ listen: native.listen }));
let deliver: (event: { payload: string }) => void;
let detach: ReturnType<typeof vi.fn>;
beforeEach(() => {
  detach = vi.fn();
  native.invoke.mockReset().mockResolvedValue(undefined);
  native.listen.mockReset().mockImplementation(async (_event, callback) => { deliver = callback; return detach; });
});
afterEach(() => vi.useRealTimers());

it("closes only the bound backend through the existing native identity, never initializes or prompts", async () => {
  const params = { sessionId: "saved-backend", _meta: { "neko.task": { task_id: "task" } } };
  native.invoke.mockImplementation(async (command, payload) => {
    expect(command).toBe("neko_control_session_write");
    expect(native.listen).toHaveBeenCalledWith("neko-session://line/orphan", expect.any(Function));
    expect(payload.request.agentSessionId).toBe("orphan");
    const frame = JSON.parse(payload.request.line);
    expect(frame).toMatchObject({ jsonrpc: "2.0", method: "session/close", params });
    deliver({ payload: JSON.stringify({ jsonrpc: "2.0", id: frame.id, result: {} }) });
  });
  await expect(tryCloseOrphanAcpSession("orphan", params)).resolves.toBe(true);
  expect(native.invoke).toHaveBeenCalledOnce();
  expect(detach).toHaveBeenCalledOnce();
});

it("ignores unrelated, malformed and oversized traffic before the correlated close result", async () => {
  native.invoke.mockImplementation(async (_command, payload) => {
    const { id } = JSON.parse(payload.request.line);
    for (const line of ["not json", "x".repeat(65_537), JSON.stringify({ jsonrpc: "2.0", id: "foreign", result: {} })]) deliver({ payload: line });
    expect(detach).not.toHaveBeenCalled();
    deliver({ payload: JSON.stringify({ jsonrpc: "2.0", id, result: {} }) });
  });
  await expect(tryCloseOrphanAcpSession("orphan", { sessionId: "backend" })).resolves.toBe(true);
});

it.each(["rejected", "write-failed", "bad-result", "detach-failed"])("does not strand native cleanup when close is %s", async mode => {
  if (mode === "detach-failed") detach.mockImplementation(() => { throw new Error("detached bridge"); });
  native.invoke.mockImplementation(async (_command, payload) => {
    if (mode === "write-failed") throw new Error("IPC disconnected");
    const { id } = JSON.parse(payload.request.line);
    deliver({ payload: JSON.stringify({ jsonrpc: "2.0", id, ...(mode === "rejected"
      ? { error: { code: -32601 } } : { result: mode === "bad-result" ? false : {} }) }) });
  });
  await expect(tryCloseOrphanAcpSession("orphan", { sessionId: "backend" })).resolves.toBe(mode === "detach-failed");
  expect(detach).toHaveBeenCalledOnce();
});

it("bounds an unresponsive peer and detaches its temporary listener", async () => {
  vi.useFakeTimers();
  const result = tryCloseOrphanAcpSession("orphan", { sessionId: "backend" });
  await vi.waitFor(() => expect(native.invoke).toHaveBeenCalledOnce());
  await vi.advanceTimersByTimeAsync(1_500);
  await expect(result).resolves.toBe(false);
  expect(detach).toHaveBeenCalledOnce();
});

it("detaches a late subscription without writing after the deadline", async () => {
  vi.useFakeTimers();
  let subscribe!: (detach: () => void) => void;
  native.listen.mockImplementation(() => new Promise(resolve => { subscribe = resolve; }));
  const result = tryCloseOrphanAcpSession("orphan", { sessionId: "backend" });
  await vi.waitFor(() => expect(native.listen).toHaveBeenCalledOnce());
  await vi.advanceTimersByTimeAsync(1_500);
  await expect(result).resolves.toBe(false);
  subscribe(detach);
  await vi.waitFor(() => expect(detach).toHaveBeenCalledOnce());
  expect(native.invoke).not.toHaveBeenCalled();
});
