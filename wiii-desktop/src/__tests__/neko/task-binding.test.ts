import { describe, expect, it, vi } from "vitest";
import type { AdeGraph } from "@/ade/domain";
import {
  validateNekoTaskBinding,
  validateNekoTaskWorkItem,
  assertNekoTaskBindingCurrent,
  type NekoTaskBindingInput,
} from "@/neko/task-binding";

function input(): NekoTaskBindingInput {
  const graph: AdeGraph = {
    projects: [{ id: "project-1", name: "Synthetic task fixture" }],
    workspaces: [{ id: "workspace-1", projectId: "project-1", kind: "local", roots: ["E:/Project"] }],
    tasks: [{ id: "task-1", projectId: "project-1", title: "Explicit work item", state: "running" }],
    specs: [],
    environments: [{ id: "environment-1", projectId: "project-1", workspaceId: "workspace-1", kind: "local_workspace", state: "busy" }],
    runs: [{ id: "run-1", taskId: "task-1", environmentId: "environment-1", state: "starting", strategy: "single" }],
    agentSessions: [], artifacts: [], evidence: [], approvals: [], attentionItems: [],
  };
  return {
    hydrated: true, graph,
    execution: { taskId: "task-1", runId: "run-1", environmentId: "environment-1" },
    projectId: "project-1", workspacePath: "E:/Project", threadId: "thread-1", generationId: "generation-1",
  };
}

const sameNativeRoot = vi.fn(async () => ({ path: "E:\\Project" }));

describe("native Neko task work-item binding", () => {
  it("freezes an explicit work item and copies only the approved execution identities", () => {
    const value = input();
    const execution = { ...value.execution, untrustedExtra: "not-an-authority-field" };
    const work = validateNekoTaskWorkItem({ ...value, execution });
    expect(work.execution).toEqual({ taskId: "task-1", runId: "run-1", environmentId: "environment-1" });
    expect(Object.isFrozen(work)).toBe(true);
    expect(Object.isFrozen(work.execution)).toBe(true);
    expect(Object.isFrozen(work.authorizedRoots)).toBe(true);
    expect(work.threadId).toBe("thread-1");
    expect(work.generationId).toBe("generation-1");
  });

  it("blocks an unhydrated graph before requesting any physical root", async () => {
    const resolve = vi.fn(async () => ({ path: "E:/Project" }));
    await expect(validateNekoTaskBinding({ ...input(), hydrated: false }, resolve))
      .rejects.toMatchObject({ code: "work-not-hydrated" });
    expect(resolve).not.toHaveBeenCalled();
  });

  it.each(["taskId", "runId", "environmentId"] as const)("rejects a forged execution %s", async (field) => {
    const value = input();
    await expect(validateNekoTaskBinding({ ...value, execution: { ...value.execution, [field]: "foreign-id" } }, sameNativeRoot))
      .rejects.toMatchObject({ code: "work-item-mismatch" });
  });

  it("rejects the launcher's synthetic Project ID as an ADE project grant", () => {
    expect(() => validateNekoTaskWorkItem({ ...input(), projectId: "task:run-1" }))
      .toThrow("work-item-mismatch");
  });

  it("rejects a cross-project environment even if all three execution IDs exist", () => {
    const value = input();
    value.graph.projects.push({ id: "project-2", name: "Other project" });
    value.graph.environments[0].projectId = "project-2";
    expect(() => validateNekoTaskWorkItem(value)).toThrow("invalid-work-graph");
  });

  it.each(["worktree", "wsl", "ssh", "container", "wiii_cloud", "external_cloud"] as const)(
    "blocks %s until that environment's effective-root mapping is defined", (kind) => {
      const value = input();
      value.graph.environments[0].kind = kind;
      expect(() => validateNekoTaskWorkItem(value)).toThrow("unsupported-environment");
    },
  );

  it("rejects duplicated graph IDs instead of picking the first matching task", () => {
    const value = input();
    value.graph.tasks.push({ ...value.graph.tasks[0], title: "Conflicting duplicate" });
    expect(() => validateNekoTaskWorkItem(value)).toThrow("invalid-work-graph");
  });

  it("accepts a native-resolved alias and retains physical cwd spelling", async () => {
    const value = { ...input(), workspacePath: "E:/Alias" };
    const resolve = vi.fn(async (_path: string) => ({ path: "E:\\Project" }));
    const result = await validateNekoTaskBinding(value, resolve);
    expect(result.canonicalWorkspacePath).toBe("E:\\Project");
    expect(result.canonicalRoot).toBe("e:\\project");
    expect(resolve.mock.calls.map(([path]) => path)).toEqual(["E:/Alias", "E:/Project"]);
  });

  it("requires exact chosen-root membership rather than accepting an arbitrary child directory", async () => {
    const value = { ...input(), workspacePath: "E:/Project/Other" };
    const resolve = vi.fn(async (path: string) => ({ path }));
    await expect(validateNekoTaskBinding(value, resolve)).rejects.toMatchObject({ code: "root-not-authorized" });
  });

  it("does not authorize a different case-sensitive native root via a folded protocol key", async () => {
    const value = { ...input(), workspacePath: "E:/project" };
    const resolve = vi.fn(async (path: string) => ({
      path: path === "E:/project" ? "E:\\project" : "E:\\Project",
    }));
    await expect(validateNekoTaskBinding(value, resolve))
      .rejects.toMatchObject({ code: "root-not-authorized" });
  });

  it("does not block an authorized root merely because a different multi-root entry is offline", async () => {
    const value = input();
    value.graph.workspaces[0].roots = ["E:/Unavailable", "E:/Project"];
    const resolve = vi.fn(async (path: string) => {
      if (path === "E:/Unavailable") throw new Error("untrusted OS diagnostic");
      return { path: "E:/Project" };
    });
    const result = await validateNekoTaskBinding(value, resolve);
    expect(result.workspaceId).toBe("workspace-1");
  });

  it("never substitutes lexical paths after native resolution fails", async () => {
    const resolve = vi.fn(async () => { throw new Error("private resolver detail"); });
    await expect(validateNekoTaskBinding(input(), resolve)).rejects.toMatchObject({ code: "root-unavailable" });
    await expect(validateNekoTaskBinding(input(), resolve)).rejects.not.toThrow("private resolver detail");
  });

  it("rejects malformed native root results", async () => {
    await expect(validateNekoTaskBinding(input(), async () => ({ path: "relative/project" })))
      .rejects.toMatchObject({ code: "root-unavailable" });
  });

  it("does not carry a stale authorized-root snapshot across asynchronous graph changes", async () => {
    const value = input();
    let finish!: (value: { path: string }) => void;
    const pending = new Promise<{ path: string }>((resolve) => { finish = resolve; });
    const resolve = vi.fn().mockImplementationOnce(() => pending).mockResolvedValue({ path: "E:/Project" });
    const operation = validateNekoTaskBinding(value, resolve);
    value.graph.workspaces[0].roots = ["E:/Replacement"];
    finish({ path: "E:/Project" });
    await expect(operation).rejects.toMatchObject({ code: "binding-changed" });
  });

  it("rechecks the intended generation before returning the admitted work item", async () => {
    const mutable = { ...input() };
    const resolve = vi.fn(async () => {
      mutable.generationId = "new-generation";
      return { path: "E:/Project" };
    });
    await expect(validateNekoTaskBinding(mutable, resolve)).rejects.toMatchObject({ code: "binding-changed" });
  });

  it("rejects a replaced Immer graph that differs from the captured admission graph", async () => {
    const original = input();
    const binding = await validateNekoTaskBinding(original, sameNativeRoot);
    const next = { ...original, graph: structuredClone(original.graph) };
    next.graph.workspaces[0].roots = ["E:/Replacement"];
    expect(() => assertNekoTaskBindingCurrent(binding, next)).toThrow("binding-changed");
  });
});
