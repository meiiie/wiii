import { describe, expect, it } from "vitest";
import {
  validateNekoSessionOwnership,
  type NekoSessionOwnershipFact,
} from "@/neko/session-ownership";

function session(
  sessionId: string,
  overrides: Partial<NekoSessionOwnershipFact> = {},
): NekoSessionOwnershipFact {
  return {
    sessionId,
    providerId: "codex",
    kind: "scratch",
    projectId: null,
    taskId: null,
    runId: null,
    active: true,
    ...overrides,
  };
}

describe("Neko top-level session ownership", () => {
  it("allows one provider to back many independent sessions", () => {
    expect(validateNekoSessionOwnership([
      session("codex-1"),
      session("codex-2"),
      session("codex-3"),
    ])).toEqual([]);
  });

  it("allows a scratch session to carry an optional Project facet", () => {
    expect(validateNekoSessionOwnership([
      session("project-scratch", { projectId: "project-wiii" }),
    ])).toEqual([]);
  });

  it("allows only one active coordinator for a project", () => {
    const diagnostics = validateNekoSessionOwnership([
      session("coordinator-1", {
        kind: "coordinator",
        projectId: "project-wiii",
      }),
      session("coordinator-2", {
        kind: "coordinator",
        projectId: "project-wiii",
      }),
    ]);

    expect(diagnostics).toContainEqual({
      code: "multiple_project_coordinators",
      sessionId: "coordinator-2",
      referenceId: "coordinator-1",
    });
  });

  it("gives a focused task one active worker while allowing a later retry", () => {
    const activeConflict = validateNekoSessionOwnership([
      session("worker-1", {
        kind: "worker",
        taskId: "task-auth",
        runId: "run-1",
      }),
      session("worker-2", {
        kind: "worker",
        taskId: "task-auth",
        runId: "run-2",
      }),
    ]);
    const afterExit = validateNekoSessionOwnership([
      session("worker-1", {
        kind: "worker",
        taskId: "task-auth",
        runId: "run-1",
        active: false,
      }),
      session("worker-2", {
        kind: "worker",
        taskId: "task-auth",
        runId: "run-2",
      }),
    ]);

    expect(activeConflict.map((item) => item.code)).toContain("multiple_task_workers");
    expect(afterExit).toEqual([]);
  });

  it("rejects worker, coordinator, and scratch identities with mixed ownership", () => {
    expect(validateNekoSessionOwnership([
      session("scratch", { taskId: "task-leak" }),
      session("coordinator", {
        kind: "coordinator",
        projectId: null,
      }),
      session("worker", {
        kind: "worker",
        taskId: "task-auth",
        runId: null,
      }),
    ]).map((item) => item.sessionId)).toEqual([
      "scratch",
      "coordinator",
      "worker",
    ]);
  });
});
