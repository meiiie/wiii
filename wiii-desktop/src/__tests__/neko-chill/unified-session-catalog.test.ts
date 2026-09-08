import { describe, expect, it } from "vitest";
import type { NekoProviderSessionRecord } from "@/neko/contracts";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import {
  createUnifiedSessionCatalog,
  filterUnifiedSessions,
  groupUnifiedSessions,
} from "@/neko-chill/unified-session-catalog";

function managed(id: string, overrides: Partial<NekoSession> = {}): NekoSession {
  return {
    id,
    agentId: "codex",
    agentName: "Codex",
    title: id,
    createdAt: 1,
    updatedAt: 1,
    workspace: { path: "E:\\Projects\\Wiii", name: "Wiii" },
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

function provider(overrides: Partial<NekoProviderSessionRecord> = {}): NekoProviderSessionRecord {
  return {
    providerId: "claude",
    nativeSessionId: "claude-native-1",
    title: "Claude review",
    workspacePath: "e:\\projects\\wiii\\",
    createdAt: null,
    updatedAt: "2026-08-25T10:00:00.000Z",
    model: "claude-sonnet",
    state: "saved",
    canResume: false,
    ...overrides,
  };
}

describe("unified Neko session catalog", () => {
  it("merges Wiii-managed and provider-owned sessions into one project projection", () => {
    const items = createUnifiedSessionCatalog(
      [managed("Fix auth")],
      [provider()],
      new Map([["claude", "Claude Code"]]),
    );
    const groups = groupUnifiedSessions(items, "projects");

    expect(groups).toHaveLength(1);
    expect(groups[0]?.name).toBe("Wiii");
    expect(groups[0]?.sessions.map((item) => item.source).sort()).toEqual(["provider", "wiii"]);
    expect(groups[0]?.harnessCounts).toEqual([
      { harnessId: "claude", name: "Claude Code", count: 1 },
      { harnessId: "codex", name: "Codex", count: 1 },
    ]);
  });

  it("selects preview candidates deterministically from durable attention and activity facts", () => {
    const items = createUnifiedSessionCatalog(
      [
        managed("ready", { updatedAt: 300, status: "idle" }),
        managed("working", { updatedAt: 100, status: "streaming" }),
        managed("attention", { updatedAt: 10, status: "error" }),
      ],
      [provider({ title: "newest saved", updatedAt: "2026-08-25T23:00:00.000Z" })],
      new Map([["claude", "Claude Code"]]),
    );

    expect(items.map((item) => item.title)).toEqual([
      "attention",
      "working",
      "ready",
      "newest saved",
    ]);
  });

  it("searches user intent and native identity while status remains a structured facet", () => {
    const items = createUnifiedSessionCatalog(
      [managed("Auth work", {
        messages: [{ id: "user-1", role: "user", text: "sửa refresh token" }],
      })],
      [provider()],
      new Map([["claude", "Claude Code"]]),
    );

    expect(filterUnifiedSessions(items, { query: "refresh token" })).toHaveLength(1);
    expect(filterUnifiedSessions(items, { query: "claude-native-1" })[0]?.source).toBe("provider");
    expect(filterUnifiedSessions(items, { state: "ready" })[0]?.title).toBe("Auth work");
    expect(filterUnifiedSessions(items, { state: "working" })).toHaveLength(0);
  });
});
