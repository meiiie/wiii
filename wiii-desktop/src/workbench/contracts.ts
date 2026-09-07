export interface WorkspaceRef {
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
