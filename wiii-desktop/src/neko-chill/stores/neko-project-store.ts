import { v4 as uuidv4 } from "uuid";
import { create } from "zustand";
import { loadStoreStrict, saveStore, saveStoreStrict } from "@/lib/storage";
import type { NekoProject } from "@/workbench/contracts";
import {
  isAbsoluteWorkspacePath,
  type WorkspaceRef,
} from "../workspace";

export type { NekoProject } from "@/workbench/contracts";

const STORE = "neko-chill-projects.json";
const PROJECTS_KEY = "projects";
const SCHEMA_VERSION = 1;

interface PersistedProjects {
  v: typeof SCHEMA_VERSION;
  projects: NekoProject[];
}

interface NekoProjectState {
  projects: NekoProject[];
  hydrated: boolean;
  hydrating: boolean;
  error: string | null;
  hydrate: () => Promise<void>;
  ensureWorkspaceProjects: (workspaces: WorkspaceRef[]) => Promise<void>;
  createProject: (name: string, roots: WorkspaceRef[]) => Promise<string>;
  updateProject: (id: string, name: string, roots: WorkspaceRef[]) => Promise<void>;
  setPreferredHarness: (id: string, harnessId: string) => Promise<void>;
}

export function workspaceKey(path: string): string {
  let normalized = path.trim().replace(/\\/g, "/");
  if (/^\/\/\?\/unc\//i.test(normalized)) normalized = `//${normalized.slice(8)}`;
  else if (/^\/\/\?\//.test(normalized)) normalized = normalized.slice(4);

  const isUnc = normalized.startsWith("//");
  const isWindows = isUnc || /^[A-Za-z]:\//.test(normalized);
  const prefix = isUnc ? "//" : normalized.startsWith("/") ? "/" : "";
  const segments = normalized
    .slice(prefix.length)
    .split(/\/+/)
    .filter((segment) => segment && segment !== ".");
  const settled: string[] = [];
  for (const segment of segments) {
    if (segment === "..") settled.pop();
    else settled.push(segment);
  }
  const key = `${prefix}${settled.join("/")}`.replace(/\/$/, "");
  return isWindows ? key.toLocaleLowerCase("en-US") : key;
}

function uniqueRoots(roots: WorkspaceRef[]): WorkspaceRef[] {
  const seen = new Set<string>();
  return roots.flatMap((root) => {
    if (!root.name.trim() || !isAbsoluteWorkspacePath(root.path)) return [];
    const key = workspaceKey(root.path);
    if (seen.has(key)) return [];
    seen.add(key);
    return [{ path: root.path, name: root.name.trim() }];
  });
}

function isWorkspace(value: unknown): value is WorkspaceRef {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const workspace = value as Partial<WorkspaceRef>;
  return typeof workspace.name === "string"
    && workspace.name.trim().length > 0
    && typeof workspace.path === "string"
    && isAbsoluteWorkspacePath(workspace.path);
}

function isProject(value: unknown): value is NekoProject {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const project = value as Partial<NekoProject>;
  return typeof project.id === "string"
    && project.id.length > 0
    && typeof project.name === "string"
    && project.name.trim().length > 0
    && Array.isArray(project.roots)
    && project.roots.length > 0
    && project.roots.every(isWorkspace)
    && (project.preferredHarnessId === null || typeof project.preferredHarnessId === "string")
    && typeof project.createdAt === "number"
    && Number.isFinite(project.createdAt)
    && typeof project.updatedAt === "number"
    && Number.isFinite(project.updatedAt);
}

function parseProjects(value: unknown): NekoProject[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Danh mục Project có schema không hợp lệ.");
  }
  const snapshot = value as Partial<PersistedProjects>;
  if (
    snapshot.v !== SCHEMA_VERSION
    || !Array.isArray(snapshot.projects)
    || !snapshot.projects.every(isProject)
  ) {
    throw new Error("Danh mục Project có schema không hợp lệ.");
  }
  return snapshot.projects.map((project) => ({
    ...project,
    roots: uniqueRoots(project.roots),
  }));
}

async function persistProjects(projects: NekoProject[], strict: boolean): Promise<void> {
  const snapshot: PersistedProjects = { v: SCHEMA_VERSION, projects };
  if (strict) await saveStoreStrict(STORE, PROJECTS_KEY, snapshot);
  else await saveStore(STORE, PROJECTS_KEY, snapshot);
}

export function projectForWorkspace(
  projects: readonly NekoProject[],
  workspacePath: string | null | undefined,
): NekoProject | null {
  if (!workspacePath) return null;
  const key = workspaceKey(workspacePath);
  return projects.find((project) =>
    project.roots.some((root) => workspaceKey(root.path) === key),
  ) ?? null;
}

export function projectForSession(
  projects: readonly NekoProject[],
  session: {
    projectId?: string | null;
    workspace?: { path: string } | null;
  },
): NekoProject | null {
  if (session.projectId) {
    const explicit = projects.find((project) => project.id === session.projectId);
    if (explicit) return explicit;
  }
  return projectForWorkspace(projects, session.workspace?.path);
}

function assertProjectInput(name: string, roots: WorkspaceRef[]): WorkspaceRef[] {
  const normalizedRoots = uniqueRoots(roots);
  if (!name.trim()) throw new Error("Hãy đặt tên cho Project.");
  if (!normalizedRoots.length) throw new Error("Project cần ít nhất một thư mục nguồn.");
  return normalizedRoots;
}

function conflictingProject(
  projects: readonly NekoProject[],
  roots: readonly WorkspaceRef[],
  exceptId?: string,
): NekoProject | null {
  const keys = new Set(roots.map((root) => workspaceKey(root.path)));
  return projects.find((project) =>
    project.id !== exceptId
    && project.roots.some((root) => keys.has(workspaceKey(root.path))),
  ) ?? null;
}

export const useNekoProjectStore = create<NekoProjectState>((set, get) => ({
  projects: [],
  hydrated: false,
  hydrating: false,
  error: null,

  hydrate: async () => {
    if (get().hydrating || get().hydrated) return;
    set({ hydrating: true, error: null });
    try {
      const raw = await loadStoreStrict<unknown>(STORE, PROJECTS_KEY, {
        v: SCHEMA_VERSION,
        projects: [],
      });
      set({ projects: parseProjects(raw), hydrated: true, error: null });
    } catch (cause) {
      set({
        projects: [],
        hydrated: true,
        error: cause instanceof Error ? cause.message : String(cause),
      });
    } finally {
      set({ hydrating: false });
    }
  },

  ensureWorkspaceProjects: async (workspaces) => {
    const current = get().projects;
    const next = [...current];
    for (const workspace of uniqueRoots(workspaces)) {
      if (projectForWorkspace(next, workspace.path)) continue;
      const now = Date.now();
      next.push({
        id: uuidv4(),
        name: workspace.name,
        roots: [workspace],
        preferredHarnessId: null,
        createdAt: now,
        updatedAt: now,
      });
    }
    if (next.length === current.length) return;
    set({ projects: next });
    await persistProjects(next, false);
  },

  createProject: async (name, roots) => {
    const normalizedRoots = assertProjectInput(name, roots);
    const current = get().projects;
    const conflict = conflictingProject(current, normalizedRoots);
    if (conflict) {
      throw new Error(`Thư mục này đã thuộc Project “${conflict.name}”.`);
    }
    const now = Date.now();
    const project: NekoProject = {
      id: uuidv4(),
      name: name.trim(),
      roots: normalizedRoots,
      preferredHarnessId: null,
      createdAt: now,
      updatedAt: now,
    };
    const next = [project, ...current];
    await persistProjects(next, true);
    set({ projects: next, error: null });
    return project.id;
  },

  updateProject: async (id, name, roots) => {
    const normalizedRoots = assertProjectInput(name, roots);
    const current = get().projects;
    const conflict = conflictingProject(current, normalizedRoots, id);
    if (conflict) {
      throw new Error(`Thư mục này đã thuộc Project “${conflict.name}”.`);
    }
    const project = current.find((item) => item.id === id);
    if (!project) throw new Error("Project không còn tồn tại.");
    const next = current.map((item) => item.id === id ? {
      ...item,
      name: name.trim(),
      roots: normalizedRoots,
      updatedAt: Date.now(),
    } : item);
    await persistProjects(next, true);
    set({ projects: next, error: null });
  },

  setPreferredHarness: async (id, harnessId) => {
    const current = get().projects;
    const next = current.map((item) => item.id === id ? {
      ...item,
      preferredHarnessId: harnessId,
      updatedAt: Date.now(),
    } : item);
    set({ projects: next });
    await persistProjects(next, false);
  },
}));
