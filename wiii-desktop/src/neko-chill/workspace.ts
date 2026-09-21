/** Workspace selection helpers for the local-only Neko Chill shell. */

import type { WorkspaceRef } from "@/workbench/contracts";

export type { WorkspaceRef } from "@/workbench/contracts";

/** Accept Windows drive/UNC paths and POSIX roots without touching the filesystem. */
export function isAbsoluteWorkspacePath(path: string): boolean {
  return /^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+(?:\\|$)|\/)/.test(path);
}

export function workspaceName(path: string): string {
  const parts = path.replace(/[\\/]+$/, "").split(/[\\/]/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : path;
}

export function workspaceFromPath(path: string): WorkspaceRef {
  return { path, name: workspaceName(path) };
}

export async function resolveWorkspaceFolder(path: string): Promise<WorkspaceRef> {
  if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) {
    return workspaceFromPath(path);
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<WorkspaceRef>("neko_resolve_workspace", { workspace: path });
}

/** VI title when folder picker is unavailable (browser chill preview). */
export const BROWSER_FOLDER_PICKER_UNAVAILABLE_VI =
  "Bản xem trước trình duyệt không chọn được thư mục trên máy. Hãy dùng app desktop Wiii.";

/**
 * VI helper for native GTK/rfd: Open stays disabled on empty Recent / inside an
 * empty directory until a directory row is selected (product honesty).
 */
export const NATIVE_FOLDER_PICKER_SELECT_HINT_VI =
  "Trong hộp chọn thư mục: hãy chọn một thư mục trong danh sách — nút Mở tắt khi Gần đây trống hoặc đang đứng trong thư mục rỗng.";

/** True only in the native desktop shell — browser preview cannot open a folder picker. */
export function canChooseWorkspaceFolder(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/** Prefer HOME so GTK does not land on empty Recent (Open stays disabled). */
export function folderPickerFallbackStartPath(): string {
  if (typeof process !== "undefined") {
    const home = process.env.HOME || process.env.USERPROFILE;
    if (home) return home;
  }
  return "/tmp";
}

/** Resolve a usable start directory for the native folder chooser. */
export async function resolveFolderPickerStartPath(): Promise<string> {
  if (canChooseWorkspaceFolder()) {
    try {
      const { homeDir } = await import("@tauri-apps/api/path");
      const home = await homeDir();
      if (home) return home;
    } catch {
      /* fall through to env /tmp */
    }
  }
  return folderPickerFallbackStartPath();
}

/** Opens Tauri's native directory chooser. Browser/test environments return null. */
export async function chooseWorkspaceFolder(): Promise<WorkspaceRef | null> {
  if (!canChooseWorkspaceFolder()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const defaultPath = await resolveFolderPickerStartPath();
  const selected = await open({
    directory: true,
    multiple: false,
    title: "Chọn thư mục dự án cho Neko Chill",
    defaultPath,
  });
  return typeof selected === "string" && selected
    ? await resolveWorkspaceFolder(selected)
    : null;
}
