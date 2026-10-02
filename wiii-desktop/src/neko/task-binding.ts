/**
 * Host work-item admission for Neko's opt-in fixed-task lane.
 * This binds Wiii work identity and a native-resolved root; it grants no tool,
 * Computer, filesystem or provider authority and owns no agent memory.
 */
import { validateAdeGraph, type AdeGraph } from "@/ade/domain";
import type { NekoExecutionBinding } from "./control-client";
import { canonicalRootIdentity } from "@/neko-chill/drivers/acp/task-protocol";

export interface NekoTaskBindingInput {
  readonly hydrated: boolean;
  readonly graph: AdeGraph;
  readonly execution: NekoExecutionBinding;
  /** ADE Project ID, never the Neko launcher's synthetic `task:<run>` ID. */
  readonly projectId: string;
  readonly workspacePath: string;
  readonly threadId: string;
  /** Fresh RuntimeRegistry instance ID for this native preparation. */
  readonly generationId: string;
}

export type NekoCanonicalWorkspaceResolver = (
  path: string,
) => Promise<{ readonly path: string; readonly name?: string }>;

export interface NekoTaskWorkItem {
  readonly execution: Readonly<NekoExecutionBinding>;
  readonly projectId: string;
  readonly workspaceId: string;
  readonly workspacePath: string;
  readonly authorizedRoots: readonly string[];
  readonly threadId: string;
  readonly generationId: string;
}

export interface NekoTrustedTaskBinding extends NekoTaskWorkItem {
  /** Native physical path spelling used for process cwd, without case folding. */
  readonly canonicalWorkspacePath: string;
  /** Protocol root identity, normalized exactly like the Neko receipt codec. */
  readonly canonicalRoot: string;
}

export type NekoTaskBindingFailure =
  | "work-not-hydrated"
  | "invalid-identity"
  | "invalid-work-graph"
  | "work-item-mismatch"
  | "unsupported-environment"
  | "root-unavailable"
  | "root-not-authorized"
  | "binding-changed";

export class NekoTaskBindingError extends Error {
  constructor(readonly code: NekoTaskBindingFailure) {
    super(`Chưa thể gắn phạm vi task Neko: ${code}. Phiên scoped chưa được phép gửi prompt.`);
    this.name = "NekoTaskBindingError";
  }
}

function fail(code: NekoTaskBindingFailure): never {
  throw new NekoTaskBindingError(code);
}

function validIdentity(value: string): boolean {
  return typeof value === "string" && value.length > 0 && value.length <= 256
    && !/[\u0000-\u001f\u007f]/.test(value);
}

function absoluteRoot(value: string): boolean {
  return typeof value === "string" && value.length > 0 && value.length <= 4096
    && !/[\u0000-\u001f\u007f]/.test(value)
    && /^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+(?:\\|$)|\/)/.test(value);
}

/** Pure graph/identity check, performed again after asynchronous root reads. */
export function validateNekoTaskWorkItem(input: NekoTaskBindingInput): NekoTaskWorkItem {
  if (!input.hydrated) fail("work-not-hydrated");
  if (![input.execution.taskId, input.execution.runId, input.execution.environmentId,
    input.projectId, input.threadId, input.generationId].every(validIdentity)) {
    fail("invalid-identity");
  }
  if (validateAdeGraph(input.graph).length > 0) fail("invalid-work-graph");

  const run = input.graph.runs.find((item) => item.id === input.execution.runId);
  const task = input.graph.tasks.find((item) => item.id === input.execution.taskId);
  const environment = input.graph.environments.find((item) => item.id === input.execution.environmentId);
  if (!run || !task || !environment
    || run.taskId !== task.id || run.environmentId !== environment.id
    || task.projectId !== input.projectId || environment.projectId !== input.projectId) {
    fail("work-item-mismatch");
  }
  if (environment.kind !== "local_workspace") fail("unsupported-environment");
  const workspace = input.graph.workspaces.find((item) => item.id === environment.workspaceId);
  if (!workspace || workspace.projectId !== input.projectId || workspace.kind === "remote"
    || !input.graph.projects.some((item) => item.id === input.projectId)
    || workspace.roots.length === 0 || !workspace.roots.every(absoluteRoot)
    || !absoluteRoot(input.workspacePath)) {
    fail("work-item-mismatch");
  }
  return Object.freeze({
    execution: Object.freeze({
      taskId: input.execution.taskId,
      runId: input.execution.runId,
      environmentId: input.execution.environmentId,
    }),
    projectId: input.projectId,
    workspaceId: workspace.id,
    workspacePath: input.workspacePath,
    authorizedRoots: Object.freeze([...workspace.roots]),
    threadId: input.threadId,
    generationId: input.generationId,
  });
}

function sameWorkItem(left: NekoTaskWorkItem, right: NekoTaskWorkItem): boolean {
  return left.execution.taskId === right.execution.taskId
    && left.execution.runId === right.execution.runId
    && left.execution.environmentId === right.execution.environmentId
    && left.projectId === right.projectId && left.workspaceId === right.workspaceId
    && left.workspacePath === right.workspacePath
    && left.threadId === right.threadId && left.generationId === right.generationId
    && left.authorizedRoots.length === right.authorizedRoots.length
    && left.authorizedRoots.every((root, index) => root === right.authorizedRoots[index]);
}

/** Fresh-store check: callers must not reuse a captured Immer graph snapshot. */
export function assertNekoTaskBindingCurrent(
  binding: NekoTaskWorkItem,
  input: NekoTaskBindingInput,
): void {
  if (!sameWorkItem(binding, validateNekoTaskWorkItem(input))) fail("binding-changed");
}

/**
 * Resolver must be a host-native canonicalizer. There is deliberately no
 * browser/lexical fallback. The factory owns availability and generation
 * checks before it supplies the native resolver and before it commits a driver.
 */
export async function validateNekoTaskBinding(
  input: NekoTaskBindingInput,
  resolveCanonicalWorkspace: NekoCanonicalWorkspaceResolver,
): Promise<NekoTrustedTaskBinding> {
  const workItem = validateNekoTaskWorkItem(input);
  const chosenPath = input.workspacePath;
  let canonicalWorkspacePath: string;
  try {
    const resolved = await resolveCanonicalWorkspace(chosenPath);
    if (!absoluteRoot(resolved.path)) fail("root-unavailable");
    canonicalWorkspacePath = resolved.path;
  } catch {
    // Untrusted resolver/OS diagnostic payload is not displayed or persisted.
    fail("root-unavailable");
  }
  const canonicalRoot = canonicalRootIdentity(canonicalWorkspacePath);
  let authorized = false;
  let unavailableRoot = false;
  for (const declaredRoot of workItem.authorizedRoots) {
    try {
      const resolved = await resolveCanonicalWorkspace(declaredRoot);
      if (!absoluteRoot(resolved.path)) {
        unavailableRoot = true;
        continue;
      }
      // Both values come from the same native canonicalizer. Protocol case
      // folding is receipt correlation, not host authority: distinct Windows
      // directories may be case-sensitive even though Neko's v1 key is folded.
      if (resolved.path === canonicalWorkspacePath) {
        authorized = true;
        break;
      }
    } catch {
      unavailableRoot = true;
    }
  }
  if (!authorized) fail(unavailableRoot ? "root-unavailable" : "root-not-authorized");
  const currentWorkItem = validateNekoTaskWorkItem(input);
  if (input.workspacePath !== chosenPath || !sameWorkItem(workItem, currentWorkItem)) {
    fail("binding-changed");
  }
  return Object.freeze({ ...workItem, canonicalWorkspacePath, canonicalRoot });
}
