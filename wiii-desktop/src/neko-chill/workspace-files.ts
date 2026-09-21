import { invoke } from "@tauri-apps/api/core";

export interface WorkspaceEntry {
  path: string;
  name: string;
  size: number;
  modifiedAt: number | null;
  language: string;
}

export interface WorkspaceListing {
  entries: WorkspaceEntry[];
  truncated: boolean;
}

export interface WorkspaceFile {
  path: string;
  name: string;
  kind: "text" | "image" | "pdf";
  language: string;
  mimeType: string;
  size: number;
  modifiedAt: number | null;
  content: string | null;
  dataUrl: string | null;
}

export interface WorkspaceChange {
  path: string;
  status: "added" | "modified" | "deleted" | "renamed" | "untracked";
  staged: boolean;
}

export interface WorkspaceChanges {
  isGit: boolean;
  changes: WorkspaceChange[];
}

export interface WorkspaceDiff {
  path: string;
  status: WorkspaceChange["status"];
  language: string;
  original: string;
  modified: string;
  binary: boolean;
}

/** VI honesty when Vite browser preview has no Tauri workspace IPC. */
export const NATIVE_WORKSPACE_UNAVAILABLE_VI =
  "Bản xem trước trong trình duyệt không đọc được workspace trên máy. Hãy dùng app desktop Wiii để mở tệp Project.";

export function hasNativeWorkspaceAuthority(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function assertNativeWorkspaceAuthority(): void {
  if (!hasNativeWorkspaceAuthority()) {
    throw new Error(NATIVE_WORKSPACE_UNAVAILABLE_VI);
  }
}

export async function listWorkspaceFiles(workspace: string): Promise<WorkspaceListing> {
  assertNativeWorkspaceAuthority();
  return invoke("neko_list_workspace_files", { workspace });
}

export async function readWorkspaceFile(workspace: string, path: string): Promise<WorkspaceFile> {
  assertNativeWorkspaceAuthority();
  return invoke("neko_read_workspace_file", { workspace, path });
}

export async function listWorkspaceChanges(workspace: string): Promise<WorkspaceChanges> {
  assertNativeWorkspaceAuthority();
  return invoke("neko_workspace_changes", { workspace });
}

export async function readWorkspaceDiff(workspace: string, path: string): Promise<WorkspaceDiff> {
  assertNativeWorkspaceAuthority();
  return invoke("neko_workspace_diff", { workspace, path });
}
