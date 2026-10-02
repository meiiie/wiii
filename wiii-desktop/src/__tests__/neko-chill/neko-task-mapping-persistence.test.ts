import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import {
  beginNekoTaskLoad,
  bindNekoTaskMapping,
  createPendingNekoTaskMapping,
  markNekoTaskRecovery,
  parseNekoTaskMapping,
  restoreNekoTaskMapping,
  type NekoTaskScopeState,
} from "@/neko-chill/task-scope-mapping";
import type { NekoTaskReceipt } from "@/neko-chill/drivers/acp/task-protocol";

const disk = vi.hoisted(() => ({ values: new Map<string, unknown>(), failSnapshotWrite: false }));
vi.mock("@/lib/storage", () => {
  const clone = <T,>(value: T): T => value === undefined ? value : JSON.parse(JSON.stringify(value));
  const read = async (store: string, key: string, fallback: unknown) => {
    const value = disk.values.get(`${store}:${key}`);
    return clone(value === undefined ? fallback : value);
  };
  const write = async (store: string, key: string, value: unknown) => {
    if (disk.failSnapshotWrite && store === "neko-chill-sessions.json" && key.startsWith("session:")) {
      throw new Error("synthetic snapshot write failure");
    }
    disk.values.set(`${store}:${key}`, clone(value));
  };
  return {
    loadStore: vi.fn(read), loadStoreStrict: vi.fn(read),
    saveStore: vi.fn(write), saveStoreStrict: vi.fn(write),
    deleteStoreStrict: vi.fn(async (store: string, key: string) => { disk.values.delete(`${store}:${key}`); }),
  };
});

const host = {
  threadId: "wiii-thread",
  providerId: "neko",
  projectId: "task:ade-run",
  execution: { taskId: "ade-task", runId: "ade-run", environmentId: "ade-environment" },
  workspacePath: "E:/workspace",
};
const receipt: NekoTaskReceipt = {
  version: 1, mode: "fixed-active-task", id: "neko-task", label: "Kiểm thử lưu phiên",
  root: "e:/workspace", activationEpoch: 1, activationId: "activation-1",
};
const pending = () => createPendingNekoTaskMapping(host, receipt.label)!;
const bound = () => bindNekoTaskMapping(pending(), receipt, "neko-coordinator", "E:/workspace");
const STORE = "neko-chill-sessions.json";
const entry = () => ({ v: 2, id: host.threadId, agentId: "neko", agentName: "Neko Core",
  title: receipt.label, createdAt: 1, updatedAt: 2,
  workspace: { path: host.workspacePath, name: "workspace" },
  projectId: host.projectId, execution: host.execution, backendSessionId: "neko-coordinator" });

function snapshot(metadata: unknown, version = 2) {
  return { v: version, messages: [], events: [], eventHighWaterMark: 0, entry: metadata };
}

function session(taskScope?: NekoTaskScopeState): NekoSession & { taskScope?: NekoTaskScopeState } {
  return {
    ...entry(), workspace: { path: host.workspacePath, name: "workspace" },
    launchProfile: null, kind: "worker", controls: [], commands: [], pendingControlId: null,
    lastActivityAt: 2, status: "connecting", messages: [], events: [], eventHighWaterMark: 0,
    runtime: null, pendingPermission: null, resolvingPermissionId: null,
    cancelPending: false, closePending: false, deletePending: false, taskScope,
  };
}

beforeEach(() => {
  vi.resetModules();
  disk.values.clear();
  disk.failSnapshotWrite = false;
});

describe("scoped task metadata at the persistence boundary", () => {
  it.each(["pending-new", "bound", "pending-load", "recovery-required", "invalid"] as const)(
    "preserves %s through strict authoritative snapshot and load", async (state) => {
      const mapping: NekoTaskScopeState = state === "pending-new" ? pending()
        : state === "bound" ? bound()
        : state === "pending-load" ? beginNekoTaskLoad(bound())
        : state === "recovery-required" ? markNekoTaskRecovery(bound(), "writer-unavailable")
        : { state: "invalid", reason: "host-binding-mismatch", retained: bound() };
      const api = await import("@/neko-chill/persistence");
      await api.persistSessionBeforeDispatch(session(mapping));
      const stored = disk.values.get(`${STORE}:session:${host.threadId}`) as { entry: { taskScope: unknown } };
      expect(stored.entry.taskScope).toEqual(mapping);
      const loaded = await api.loadSessionIndex();
      expect(loaded).toHaveLength(1);
      expect(loaded[0].taskScope).toEqual(mapping);
      expect(parseNekoTaskMapping(loaded[0].taskScope).kind).toBe(state === "invalid" ? "blocked" : "scoped");
    },
  );

  it.each([null, {}, "scope", { version: 2, state: "bound" }, { ...bound(), receipt: null }])(
    "keeps malformed embedded scope for explicit blocking rather than selecting legacy cache %#", async (raw) => {
      disk.values.set(`${STORE}:session-ids`, [host.threadId]);
      disk.values.set(`${STORE}:index`, [entry()]);
      disk.values.set(`${STORE}:session:${host.threadId}`, snapshot({ ...entry(), taskScope: raw }));
      const api = await import("@/neko-chill/persistence");
      const loaded = await api.loadSessionIndex();
      expect(loaded).toHaveLength(1);
      expect(Object.prototype.hasOwnProperty.call(loaded[0], "taskScope")).toBe(true);
      expect(loaded[0].taskScope).toEqual(raw);
      expect(restoreNekoTaskMapping(loaded[0].taskScope, host).kind).toBe("blocked");
      expect((await api.loadSessionSnapshot(host.threadId)).messages).toEqual([]);
    },
  );

  it("takes the receipt from the authoritative embedded entry over a stale index", async () => {
    const freshReceipt = { ...receipt, activationEpoch: 2, activationId: "activation-2" };
    const latest = bindNekoTaskMapping(beginNekoTaskLoad(bound()), freshReceipt, "neko-coordinator", "E:/workspace");
    disk.values.set(`${STORE}:session-ids`, [host.threadId]);
    disk.values.set(`${STORE}:index`, [{ ...entry(), taskScope: bound() }]);
    disk.values.set(`${STORE}:session:${host.threadId}`, snapshot({ ...entry(), taskScope: latest }));
    const loaded = await (await import("@/neko-chill/persistence")).loadSessionIndex();
    expect(loaded[0].taskScope).toEqual(latest);
    expect(restoreNekoTaskMapping(loaded[0].taskScope, host)).toMatchObject({ kind: "scoped",
      mapping: { state: "bound", receipt: freshReceipt } });
  });

  it("does not turn read-only restart persistence into an interrupted load", async () => {
    const api = await import("@/neko-chill/persistence");
    await api.persistSessionStrict(session(bound()));
    for (let restart = 0; restart < 3; restart++) {
      const loaded = await api.loadSessionIndex();
      const restored = restoreNekoTaskMapping(loaded[0].taskScope, host);
      expect(restored).toMatchObject({ kind: "scoped", mapping: { state: "bound", receipt } });
      if (restored.kind !== "scoped") throw new Error("unexpected blocked fixture");
      // Reconciliation may save the snapshot even though no input was sent.
      await api.persistSessionStrict({ ...session(restored.mapping), status: "exited" });
    }
    const intent = beginNekoTaskLoad(bound());
    expect(restoreNekoTaskMapping(intent, host)).toMatchObject({
      kind: "scoped", mapping: { state: "recovery-required", reason: "unfinished-load" },
    });
  });

  it("retains malformed scope from legacy cache metadata when a v1 snapshot lacks an entry", async () => {
    const raw = { state: "bound", receipt: "malformed" };
    disk.values.set(`${STORE}:index`, [{ ...entry(), taskScope: raw }]);
    disk.values.set(`${STORE}:session:${host.threadId}`, { v: 1, messages: [] });
    const loaded = await (await import("@/neko-chill/persistence")).loadSessionIndex();
    expect(loaded[0].taskScope).toEqual(raw);
    expect(parseNekoTaskMapping(loaded[0].taskScope).kind).toBe("blocked");
  });

  it("keeps existing legacy and other-provider metadata absent rather than creating an opt-in", async () => {
    const api = await import("@/neko-chill/persistence");
    await api.persistSessionStrict({ ...session(), agentId: "gemini", execution: null, projectId: null });
    const loaded = await api.loadSessionIndex();
    expect(loaded[0].agentId).toBe("gemini");
    expect(loaded[0].taskScope).toBeUndefined();
    expect(parseNekoTaskMapping(loaded[0].taskScope)).toEqual({ kind: "legacy" });
  });

  it("propagates a strict receipt save failure while preserving prior authoritative receipt bytes", async () => {
    const api = await import("@/neko-chill/persistence");
    await api.persistSessionStrict(session(bound()));
    const before = JSON.stringify(disk.values.get(`${STORE}:session:${host.threadId}`));
    disk.failSnapshotWrite = true;
    await expect(api.persistSessionBeforeDispatch(session(markNekoTaskRecovery(bound(), "close-unconfirmed"))))
      .rejects.toThrow("synthetic snapshot write failure");
    expect(JSON.stringify(disk.values.get(`${STORE}:session:${host.threadId}`))).toBe(before);
    expect((await api.loadSessionIndex())[0].taskScope).toEqual(bound());
  });
});
