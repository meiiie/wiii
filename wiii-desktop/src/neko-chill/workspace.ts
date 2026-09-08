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

/** Opens Tauri's native directory chooser. Browser/test environments return null. */
export async function chooseWorkspaceFolder(): Promise<WorkspaceRef | null> {
  if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({
    directory: true,
    multiple: false,
    title: "Chọn thư mục dự án cho Neko Chill",
  });
  return typeof selected === "string" && selected
    ? await resolveWorkspaceFolder(selected)
    : null;
}
