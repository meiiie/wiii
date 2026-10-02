export interface WorkspaceRef {
  /** Presentation metadata only; never grants filesystem authority. */
  kind?: "scratch";
  path: string;
  name: string;
}

export interface NekoProject {
  id: string;
  name: string;
  roots: WorkspaceRef[];
  preferredHarnessId: string | null;
  createdAt: number;
  updatedAt: number;
}
