import { describe, expect, it } from "vitest";
import {
  deriveSessionPresentation,
  groupSessionsByHarness,
  groupSessionsByProject,
} from "@/neko-chill/session-catalog";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";

function session(
  id: string,
  overrides: Partial<NekoSession> = {},
): NekoSession {
  return {
    id,
    agentId: "codex",
    agentName: "Codex",
    title: id,
    createdAt: 1,
    updatedAt: 1,
    workspace: { path: "C:/work/Wiii", name: "Wiii" },
    launchProfile: null,
    backendSessionId: null,
    controls: [],
    commands: [],
    pendingControlId: null,
    lastActivityAt: 1,
    status: "idle",
    messages: [],
    events: [],
    eventHighWaterMark: 0,
    runtime: null,
    pendingPermission: null,
    resolvingPermissionId: null,
    cancelPending: false,
    closePending: false,
    deletePending: false,
    ...overrides,
  };
}

describe("Neko session catalog", () => {
  it("projects one catalog by project or harness without duplicating sessions", () => {
    const sessions = [
      session("codex-wiii"),
      session("neko-wiii", { agentId: "neko", agentName: "Neko Core" }),
      session("codex-video", {
        workspace: { path: "C:/work/video", name: "Video" },
      }),
    ];

    const projects = groupSessionsByProject(sessions);
    const harnesses = groupSessionsByHarness(sessions);

    expect(projects.map((group) => [group.name, group.sessions.length])).toEqual([
      ["Wiii", 2],
      ["Video", 1],
    ]);
    expect(harnesses.map((group) => [group.name, group.sessions.length])).toEqual([
      ["Codex", 2],
      ["Neko Core", 1],
    ]);
    expect(projects.flatMap((group) => group.sessions)).toHaveLength(sessions.length);
    expect(harnesses.flatMap((group) => group.sessions)).toHaveLength(sessions.length);
  });

  it("derives attention from lifecycle facts instead of persisting another status", () => {
    expect(deriveSessionPresentation(session("working", { status: "streaming" })))
      .toEqual({ state: "working", label: "Đang làm việc" });
    expect(deriveSessionPresentation(session("approval", {
      status: "idle",
      pendingPermission: {
        requestId: "permission-1",
        title: "Write(config.json)",
        options: [],
      },
    }))).toEqual({ state: "needs-attention", label: "Cần bạn" });
    expect(deriveSessionPresentation(session("failed", { status: "error" })))
      .toEqual({ state: "needs-attention", label: "Cần kiểm tra" });
  });
});
