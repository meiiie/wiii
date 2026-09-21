import { afterEach, describe, expect, it, vi } from "vitest";

const tauri = vi.hoisted(() => ({ invoke: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({ invoke: tauri.invoke }));

import {
  assertNativeWorkspaceAuthority,
  listWorkspaceChanges,
  listWorkspaceFiles,
  NATIVE_WORKSPACE_UNAVAILABLE_VI,
  readWorkspaceDiff,
  readWorkspaceFile,
} from "@/neko-chill/workspace-files";

describe("workspace files native authority honesty", () => {
  afterEach(() => {
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
    tauri.invoke.mockReset();
  });

  it("throws VI honesty instead of a raw invoke TypeError", async () => {
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
    expect(() => assertNativeWorkspaceAuthority()).toThrow(NATIVE_WORKSPACE_UNAVAILABLE_VI);
    await expect(listWorkspaceFiles("/tmp/project")).rejects.toThrow(/trình duyệt|desktop Wiii/i);
    await expect(listWorkspaceChanges("/tmp/project")).rejects.toThrow(/trình duyệt|desktop Wiii/i);
    await expect(readWorkspaceFile("/tmp/project", "a.ts")).rejects.toThrow(/trình duyệt|desktop Wiii/i);
    await expect(readWorkspaceDiff("/tmp/project", "a.ts")).rejects.toThrow(/trình duyệt|desktop Wiii/i);
    expect(tauri.invoke).not.toHaveBeenCalled();
  });

  it("invokes when Tauri internals are present", async () => {
    Object.defineProperty(window, "__TAURI_INTERNALS__", {
      configurable: true,
      value: {},
    });
    tauri.invoke.mockResolvedValue({ entries: [], truncated: false });
    await expect(listWorkspaceFiles("/tmp/project")).resolves.toEqual({
      entries: [],
      truncated: false,
    });
    expect(tauri.invoke).toHaveBeenCalledWith("neko_list_workspace_files", {
      workspace: "/tmp/project",
    });
  });
});
