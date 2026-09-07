import { describe, expect, it } from "vitest";
import type { NekoProviderSessionRecord } from "@/neko/contracts";
import { groupProviderSessions } from "@/neko-chill/provider-session-catalog";

function providerSession(
  providerId: string,
  id: string,
  workspacePath: string | null,
  title: string,
  updatedAt: string,
): NekoProviderSessionRecord {
  return {
    providerId,
    nativeSessionId: id,
    title,
    workspacePath,
    createdAt: null,
    updatedAt,
    model: null,
    state: "saved",
    canResume: providerId !== "claude",
  };
}

const providerNames = new Map([
  ["codex", "Codex"],
  ["claude", "Claude Code"],
  ["neko", "Neko Core"],
]);

describe("provider-owned session catalog", () => {
  const sessions = [
    providerSession("codex", "c1", "E:\\Projects\\Wiii", "Fix auth", "2026-08-24T10:00:00Z"),
    providerSession("claude", "a1", "e:\\projects\\wiii", "Security review", "2026-08-24T09:00:00Z"),
    providerSession("neko", "n1", "E:\\Projects\\Video", "Timeline", "2026-08-23T10:00:00Z"),
    providerSession("claude", "a2", null, "Scratch", "2026-08-22T10:00:00Z"),
  ];

  it("groups Windows paths case-insensitively and keeps unassigned last", () => {
    const groups = groupProviderSessions(sessions, "projects", providerNames);
    expect(groups.map((group) => [group.name, group.sessions.length])).toEqual([
      ["Wiii", 2],
      ["Video", 1],
      ["Chưa xác định folder", 1],
    ]);
    expect(groups[0].providerCounts).toEqual([
      { providerId: "claude", name: "Claude Code", count: 1 },
      { providerId: "codex", name: "Codex", count: 1 },
    ]);
  });

  it("searches title, folder and harness without creating another data source", () => {
    expect(groupProviderSessions(sessions, "projects", providerNames, { query: "security" })
      .flatMap((group) => group.sessions).map((session) => session.nativeSessionId)).toEqual(["a1"]);
    expect(groupProviderSessions(sessions, "projects", providerNames, { query: "video" })
      .flatMap((group) => group.sessions).map((session) => session.nativeSessionId)).toEqual(["n1"]);
    expect(groupProviderSessions(sessions, "harnesses", providerNames, { query: "claude code" })
      .flatMap((group) => group.sessions)).toHaveLength(2);
  });

  it("filters one harness before projecting its sessions", () => {
    const groups = groupProviderSessions(sessions, "harnesses", providerNames, {
      providerId: "claude",
    });
    expect(groups).toHaveLength(1);
    expect(groups[0].name).toBe("Claude Code");
    expect(groups[0].sessions).toHaveLength(2);
  });
});
