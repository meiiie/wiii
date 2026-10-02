import { describe, expect, it } from "vitest";
import {
  beginNekoTaskLoad,
  bindNekoTaskMapping,
  createPendingNekoTaskMapping,
  isNekoTaskScopeMapping,
  isNekoTaskScopeState,
  markNekoTaskRecovery,
  NekoTaskMappingError,
  parseNekoTaskMapping,
  restoreNekoTaskMapping,
  type NekoTaskMappingHost,
  type NekoTaskScopeMapping,
} from "@/neko-chill/task-scope-mapping";
import type { NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";

const host: NekoTaskMappingHost = {
  threadId: "wiii-thread",
  providerId: "neko",
  projectId: "task:ade-run",
  execution: { taskId: "ade-task", runId: "ade-run", environmentId: "ade-environment" },
  workspacePath: "E:/workspace",
};
const receipt: NekoTaskReceipt = {
  version: 1,
  mode: "fixed-active-task",
  id: "neko-task",
  label: "Kiểm thử tác vụ",
  root: "e:/workspace",
  activationEpoch: 1,
  activationId: "activation-1",
};
const pending = () => createPendingNekoTaskMapping(host, receipt.label)!;
const bound = () => bindNekoTaskMapping(pending(), receipt, "neko-coordinator", "E:/workspace");
const nextReceipt = (): NekoTaskReceipt => ({ ...receipt, activationEpoch: 2, activationId: "activation-2" });

function expectMapping(raw: unknown): NekoTaskScopeMapping {
  const decision = parseNekoTaskMapping(raw);
  expect(decision.kind).toBe("scoped");
  if (decision.kind !== "scoped") throw new Error("fixture did not parse as scoped");
  return decision.mapping;
}

describe("explicit Neko work-item mapping", () => {
  it("opts in only an explicit Neko ADE execution and keeps the host task separate", () => {
    expect(pending()).toMatchObject({ state: "pending-new", threadId: host.threadId,
      projectId: "task:ade-run", execution: host.execution, backendSessionId: null, receipt: null });
    expect(bound().execution.taskId).toBe("ade-task");
    expect(bound().receipt?.id).toBe("neko-task");
    expect(createPendingNekoTaskMapping({ ...host, providerId: "gemini" }, receipt.label)).toBeUndefined();
    expect(createPendingNekoTaskMapping({ ...host, providerId: "codex" }, receipt.label)).toBeUndefined();
    expect(createPendingNekoTaskMapping({ ...host, execution: null }, receipt.label)).toBeUndefined();
  });

  it("preserves a null project rather than inventing a Computer capability grant", () => {
    expect(createPendingNekoTaskMapping({ ...host, projectId: null }, receipt.label)?.projectId).toBeNull();
  });

  it.each([
    { ...host, threadId: "" },
    { ...host, execution: { taskId: "", runId: "run", environmentId: "env" } },
    { ...host, projectId: "" },
    { ...host, workspacePath: "relative/path" },
  ])("rejects malformed explicit host identity %#", (context) => {
    expect(() => createPendingNekoTaskMapping(context, receipt.label)).toThrow(NekoTaskMappingError);
  });

  it("does not mutate or retain a mutable host execution object", () => {
    const source = { ...host.execution! };
    const mapping = createPendingNekoTaskMapping({ ...host, execution: source }, receipt.label)!;
    source.taskId = "changed-host-task";
    expect(mapping.execution.taskId).toBe("ade-task");
    expect(Object.isFrozen(mapping)).toBe(true);
    expect(Object.isFrozen(mapping.execution)).toBe(true);
  });

  it("requires a separately proven root for new admission, allowing a selected alias", () => {
    expect(() => bindNekoTaskMapping(pending(), receipt, "neko-coordinator")).toThrow(NekoTaskMappingError);
    const aliasHost = { ...host, workspacePath: "E:/alias" };
    const mapped = bindNekoTaskMapping(createPendingNekoTaskMapping(aliasHost, receipt.label)!,
      receipt, "neko-coordinator", "E:/workspace");
    expect(mapped.workspacePath).toBe("E:/alias");
    expect(mapped.authorizedRoot).toBe("E:/workspace");
    expect(restoreNekoTaskMapping(mapped, aliasHost)).toMatchObject({ kind: "scoped",
      mapping: { state: "bound", workspacePath: "E:/alias" } });
  });

  it.each([
    { ...receipt, root: "e:/other" },
    { ...receipt, label: "Other work" },
    { ...receipt, activationEpoch: 2 },
  ])("blocks an unrelated new receipt %#", (other) => {
    expect(() => bindNekoTaskMapping(pending(), other, "neko-coordinator", "E:/workspace"))
      .toThrow(NekoTaskMappingError);
  });

  it("keeps POSIX root case meaningful", () => {
    const linuxHost = { ...host, workspacePath: "/Project" };
    const linuxReceipt = { ...receipt, root: "/project" };
    expect(() => bindNekoTaskMapping(createPendingNekoTaskMapping(linuxHost, receipt.label)!,
      linuxReceipt, "neko-coordinator", "/Project")).toThrow(NekoTaskMappingError);
  });

  it("rejects coordinator identity collisions with task or activation IDs", () => {
    expect(() => bindNekoTaskMapping(pending(), receipt, receipt.id, "E:/workspace")).toThrow(NekoTaskMappingError);
    expect(() => bindNekoTaskMapping(pending(), receipt, receipt.activationId, "E:/workspace")).toThrow(NekoTaskMappingError);
  });
});

describe("persisted mapping validation and restart", () => {
  it("round-trips only supported fields for all mapping states", () => {
    const mappings = [pending(), bound(), beginNekoTaskLoad(bound()),
      markNekoTaskRecovery(bound(), "writer-unavailable"), markNekoTaskRecovery(pending(), "unfinished-new")];
    for (const mapping of mappings) {
      const decoded = expectMapping(JSON.parse(JSON.stringify({ ...mapping, ignored: "not retained" })));
      expect(decoded).toEqual(mapping);
      expect(decoded).not.toHaveProperty("ignored");
      expect(isNekoTaskScopeMapping(decoded)).toBe(true);
      expect(isNekoTaskScopeState(decoded)).toBe(true);
    }
  });

  it("only undefined means legacy; explicit null and malformed scoped data stay blocked", () => {
    expect(parseNekoTaskMapping(undefined)).toEqual({ kind: "legacy" });
    expect(restoreNekoTaskMapping(undefined, host)).toEqual({ kind: "legacy" });
    for (const raw of [null, [], {}, "scoped", { ...bound(), receipt: null },
      { ...pending(), backendSessionId: "neko-coordinator" }, { ...bound(), receipt: { ...receipt, activationEpoch: 0 } },
      { ...bound(), version: 2 }, { ...bound(), mode: "other-mode" },
      { ...bound(), authorizedRoot: "e:/other" }, { ...bound(), backendSessionId: receipt.id }]) {
      expect(parseNekoTaskMapping(raw)).toEqual({ kind: "blocked",
        mapping: { state: "invalid", reason: "invalid-mapping" } });
    }
  });

  it("persists the blocked marker without retaining untrusted diagnostic payload", () => {
    const blocked = parseNekoTaskMapping({ state: "invalid", reason: "Bearer private value", receipt: "unsafe payload" });
    expect(blocked).toEqual({ kind: "blocked", mapping: { state: "invalid", reason: "invalid-mapping" } });
    if (blocked.kind !== "blocked") throw new Error("fixture should be blocked");
    expect(parseNekoTaskMapping(JSON.parse(JSON.stringify(blocked.mapping)))).toEqual(blocked);
    expect(isNekoTaskScopeState(blocked.mapping)).toBe(true);
    expect(isNekoTaskScopeMapping(blocked.mapping)).toBe(false);
    expect(JSON.stringify(blocked)).not.toContain("private");
  });

  it("does not execute accessors while decoding untrusted metadata", () => {
    let reads = 0;
    const raw = Object.defineProperty({}, "state", { get: () => { reads++; return "bound"; } });
    expect(parseNekoTaskMapping(raw).kind).toBe("blocked");
    expect(reads).toBe(0);
  });

  it("restoring receipt bytes does not create load intent or live validated authority", () => {
    const saved = bound();
    const restored = restoreNekoTaskMapping(JSON.parse(JSON.stringify(saved)), host);
    expect(restored).toEqual({ kind: "scoped", mapping: saved });
    expect(saved.state).toBe("bound");
    if (restored.kind === "scoped") expect(restored.mapping).not.toHaveProperty("validated");
  });

  it.each(["pending-new", "pending-load"] as const)("retains an interrupted %s without scheduling recovery", (state) => {
    const saved = state === "pending-new" ? pending() : beginNekoTaskLoad(bound());
    const restored = restoreNekoTaskMapping(saved, host);
    expect(restored).toEqual({ kind: "scoped", mapping: { ...saved, state: "recovery-required",
      reason: state === "pending-new" ? "unfinished-new" : "unfinished-load" } });
  });

  it("retains a known receipt and backend identity through recovery and restart", () => {
    const recovery = markNekoTaskRecovery(bound(), "close-unconfirmed");
    const restored = restoreNekoTaskMapping(recovery, host);
    expect(restored).toEqual({ kind: "scoped", mapping: recovery });
    expect(recovery.receipt).toEqual(receipt);
    expect(recovery.backendSessionId).toBe("neko-coordinator");
    expect(() => beginNekoTaskLoad(recovery)).toThrow(NekoTaskMappingError);
    expect(() => bindNekoTaskMapping(recovery, nextReceipt(), "neko-coordinator", "E:/workspace"))
      .toThrow(NekoTaskMappingError);
  });

  it.each([
    { ...host, threadId: "different-thread" },
    { ...host, providerId: "gemini" },
    { ...host, execution: null },
    { ...host, execution: { ...host.execution!, taskId: "different-work" } },
    { ...host, execution: { ...host.execution!, runId: "different-run" } },
    { ...host, execution: { ...host.execution!, environmentId: "different-environment" } },
    { ...host, projectId: "different-project" },
    { ...host, workspacePath: "E:/other" },
  ])("blocks a changed host correlation on restore %#", (otherHost) => {
    const saved = bound();
    const decision = restoreNekoTaskMapping(saved, otherHost);
    expect(decision).toEqual({ kind: "blocked",
      mapping: { state: "invalid", reason: "host-binding-mismatch", retained: saved } });
    if (decision.kind !== "blocked") throw new Error("fixture should stay blocked");
    expect(parseNekoTaskMapping(JSON.parse(JSON.stringify(decision.mapping)))).toEqual(decision);
    expect(decision.mapping.retained?.receipt).toEqual(receipt);
  });
});

describe("explicit load binding", () => {
  it("uses the saved receipt until one fresh ordinary load is validated", () => {
    const saved = bound();
    const loading = beginNekoTaskLoad(saved);
    expect(loading).toEqual({ ...saved, state: "pending-load" });
    const loaded = bindNekoTaskMapping(loading, nextReceipt(), "neko-coordinator", "E:/workspace");
    expect(loaded).toMatchObject({ state: "bound", backendSessionId: "neko-coordinator", receipt: nextReceipt() });
    expect(loading.receipt).toEqual(receipt);
    expect(bindNekoTaskMapping(loaded, nextReceipt(), "neko-coordinator", "E:/workspace")).toEqual(loaded);
  });

  it.each([
    { ...nextReceipt(), id: "other-task" },
    { ...nextReceipt(), root: "e:/other" },
    { ...nextReceipt(), label: "Other label" },
    { ...nextReceipt(), activationEpoch: 1 },
    { ...nextReceipt(), activationEpoch: 3 },
    { ...nextReceipt(), activationId: receipt.activationId },
  ])("does not admit an unrelated, stale or implicitly retried load receipt %#", (other) => {
    expect(() => bindNekoTaskMapping(beginNekoTaskLoad(bound()), other, "neko-coordinator", "E:/workspace"))
      .toThrow(NekoTaskMappingError);
  });

  it("does not change the durable coordinator or proven canonical root during load", () => {
    const loading = beginNekoTaskLoad(bound());
    expect(() => bindNekoTaskMapping(loading, nextReceipt(), "other-coordinator", "E:/workspace"))
      .toThrow(NekoTaskMappingError);
    expect(() => bindNekoTaskMapping(loading, nextReceipt(), "neko-coordinator", "E:/other"))
      .toThrow(NekoTaskMappingError);
  });
});
