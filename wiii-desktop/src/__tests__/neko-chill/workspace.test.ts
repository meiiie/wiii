import { open } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";
import { homeDir } from "@tauri-apps/api/path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  chooseWorkspaceFolder,
  folderPickerFallbackStartPath,
  isAbsoluteWorkspacePath,
  resolveFolderPickerStartPath,
  workspaceFromPath,
  workspaceName,
} from "@/neko-chill/workspace";

vi.mock("@tauri-apps/plugin-dialog", () => ({ open: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/path", () => ({ homeDir: vi.fn() }));

describe("Neko Chill workspace selection", () => {
  beforeEach(() => {
    vi.mocked(open).mockReset();
    vi.mocked(invoke).mockReset();
    vi.mocked(homeDir).mockReset().mockResolvedValue("/home/operator");
    Object.defineProperty(window, "__TAURI_INTERNALS__", {
      configurable: true,
      value: {},
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
  });

  it("preserves the exact selected path and derives a cross-platform label", () => {
    expect(workspaceFromPath("E:\\Sach\\Sua\\NekoChill\\wiii")).toEqual({
      path: "E:\\Sach\\Sua\\NekoChill\\wiii",
      name: "wiii",
    });
    expect(workspaceName("/tmp/neko-project/")).toBe("neko-project");
    expect(isAbsoluteWorkspacePath("E:\\work\\neko")).toBe(true);
    expect(isAbsoluteWorkspacePath("\\\\server\\share\\neko")).toBe(true);
    expect(isAbsoluteWorkspacePath("/tmp/neko")).toBe(true);
    expect(isAbsoluteWorkspacePath("relative/neko")).toBe(false);
  });

  it("opens a single-directory native dialog at HOME so GTK Open is not stuck on empty Recent", async () => {
    vi.mocked(open).mockResolvedValue("C:\\work\\neko" as never);
    vi.mocked(invoke).mockResolvedValue({ path: "C:\\work\\neko", name: "neko" });

    await expect(chooseWorkspaceFolder()).resolves.toEqual({
      path: "C:\\work\\neko",
      name: "neko",
    });
    expect(homeDir).toHaveBeenCalledOnce();
    expect(open).toHaveBeenCalledWith({
      directory: true,
      multiple: false,
      title: "Chọn thư mục dự án cho Neko Chill",
      defaultPath: "/home/operator",
    });
    expect(invoke).toHaveBeenCalledWith("neko_resolve_workspace", {
      workspace: "C:\\work\\neko",
    });
  });

  it("falls back to HOME/tmp when homeDir is unavailable", async () => {
    vi.mocked(homeDir).mockRejectedValue(new Error("path ipc unavailable"));
    await expect(resolveFolderPickerStartPath()).resolves.toBe(folderPickerFallbackStartPath());
  });

  it("preserves current UI state when the folder dialog is cancelled", async () => {
    vi.mocked(open).mockResolvedValue(null);
    await expect(chooseWorkspaceFolder()).resolves.toBeNull();
  });
});
