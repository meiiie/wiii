/**
 * Dependency-free Wiii ADE work ontology.
 *
 * These records describe product/work identity, not provider conversation
 * state. Keep them JSON-compatible so the same contract can later cross the
 * Neko Control boundary or be mapped to SQLite without UI dependencies.
 */

export interface AdeProject {
  id: string;
  name: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface AdeWorkspace {
  id: string;
  projectId: string;
  kind: "local" | "git" | "remote";
  roots: string[];
}

export type AdeTaskState =
  | "draft"
  | "ready"
  | "running"
  | "blocked"
  | "review"
  | "completed"
  | "cancelled";

export interface AdeTask {
  id: string;
  projectId: string;
  title: string;
  description?: string;
  state: AdeTaskState;
  /** Optional decomposition owned by Wiii, never by a provider session. */
  parentTaskId?: string;
  /** Task identities that must finish before this task can be dispatched. */
  dependencyTaskIds?: string[];
}

export interface AdeSpec {
  id: string;
  taskId: string;
  revision: number;
  requirements: string[];
  constraints: string[];
  acceptanceCriteria: string[];
}

export type AdeRunState =
  | "queued"
  | "starting"
  | "running"
  | "waiting"
  | "verifying"
  | "review"
  | "completed"
  | "failed"
  | "cancelled"
  | "unknown_outcome";

export type AdeRunStrategy =
  | "single"
  | "best_of_n"
  | "specialist"
  | "writer_reviewer"
  | "plan_implement_verify"
  | "provider_native";

export interface AdeRun {
  id: string;
  taskId: string;
  environmentId: string;
  state: AdeRunState;
  strategy: AdeRunStrategy;
}

export type AdeAgentRole =
  | "primary"
  | "planner"
  | "implementer"
  | "reviewer"
  | "specialist";

export interface AdeAgentSession {
  id: string;
  runId: string;
  providerId: string;
  /** Opaque provider-owned identity; never used as Task or Run identity. */
  providerSessionId: string | null;
  role: AdeAgentRole;
}

export type AdeEnvironmentKind =
  | "local_workspace"
  | "worktree"
  | "wsl"
  | "ssh"
  | "container"
  | "wiii_cloud"
  | "external_cloud";

export interface AdeEnvironment {
  id: string;
  projectId: string;
  workspaceId?: string;
  kind: AdeEnvironmentKind;
  state: "preparing" | "ready" | "busy" | "stopped" | "failed";
}

export interface AdeArtifact {
  id: string;
  runId: string;
  kind: "diff" | "log" | "report" | "screenshot" | "video" | "package" | "pr" | "other";
  uri: string;
  mediaType?: string;
  sha256?: string;
  byteSize?: number;
}

export interface AdeEvidence {
  id: string;
  runId: string;
  kind: "test" | "build" | "lint" | "typecheck" | "security" | "review" | "manual";
  outcome: "passed" | "failed" | "warning" | "not_run";
  summary: string;
  command?: string;
  artifactIds?: string[];
}

export interface AdeApproval {
  id: string;
  runId: string;
  agentSessionId?: string;
  request: string;
  risk: "low" | "medium" | "high" | "critical";
  state: "pending" | "approved" | "rejected" | "expired" | "cancelled";
}

export type AdeAttentionReason =
  | "approval"
  | "question"
  | "authentication"
  | "test_failure"
  | "ci_failure"
  | "conflict"
  | "stalled"
  | "budget"
  | "review_ready"
  | "unknown_outcome";

export interface AdeAttentionItem {
  id: string;
  projectId: string;
  taskId: string;
  runId?: string;
  agentSessionId?: string;
  reason: AdeAttentionReason;
  state: "open" | "resolved" | "dismissed";
}

export interface AdeGraph {
  projects: AdeProject[];
  workspaces: AdeWorkspace[];
  tasks: AdeTask[];
  specs: AdeSpec[];
  runs: AdeRun[];
  agentSessions: AdeAgentSession[];
  environments: AdeEnvironment[];
  artifacts: AdeArtifact[];
  evidence: AdeEvidence[];
  approvals: AdeApproval[];
  attentionItems: AdeAttentionItem[];
}

export type AdeGraphDiagnosticCode =
  | "duplicate_id"
  | "missing_project"
  | "missing_workspace"
  | "cross_project_workspace"
  | "missing_task"
  | "missing_environment"
  | "cross_project_environment"
  | "cross_project_task"
  | "task_cycle"
  | "duplicate_task_dependency"
  | "missing_run"
  | "multiple_active_task_runs"
  | "multiple_run_sessions"
  | "provider_subagent_not_top_level"
  | "missing_agent_session"
  | "missing_artifact"
  | "cross_run_artifact"
  | "inconsistent_approval_reference"
  | "inconsistent_attention_reference";

export interface AdeGraphDiagnostic {
  code: AdeGraphDiagnosticCode;
  entityKind: string;
  entityId: string;
  field: string;
  referenceId?: string;
}

function indexById<T extends { id: string }>(
  kind: string,
  values: T[],
  diagnostics: AdeGraphDiagnostic[],
): Map<string, T> {
  const index = new Map<string, T>();
  for (const value of values) {
    if (index.has(value.id)) {
      diagnostics.push({
        code: "duplicate_id",
        entityKind: kind,
        entityId: value.id,
        field: "id",
        referenceId: value.id,
      });
      continue;
    }
    index.set(value.id, value);
  }
  return index;
}

function missing(
  diagnostics: AdeGraphDiagnostic[],
  code: AdeGraphDiagnosticCode,
  entityKind: string,
  entityId: string,
  field: string,
  referenceId: string,
): void {
  diagnostics.push({ code, entityKind, entityId, field, referenceId });
}

const ACTIVE_RUN_STATES = new Set<AdeRunState>([
  "queued",
  "starting",
  "running",
  "waiting",
  "verifying",
  "review",
]);

const PARALLEL_RUN_STRATEGIES = new Set<AdeRunStrategy>([
  "best_of_n",
  "specialist",
]);

function taskEdges(task: AdeTask): string[] {
  return [
    ...(task.parentTaskId ? [task.parentTaskId] : []),
    ...(task.dependencyTaskIds ?? []),
  ];
}

function findTaskCycle(tasks: Map<string, AdeTask>): string[] | null {
  const visited = new Set<string>();
  const visiting = new Set<string>();
  const path: string[] = [];

  const visit = (taskId: string): string[] | null => {
    if (visiting.has(taskId)) {
      const start = path.indexOf(taskId);
      return [...path.slice(start), taskId];
    }
    if (visited.has(taskId)) return null;
    const task = tasks.get(taskId);
    if (!task) return null;
    visiting.add(taskId);
    path.push(taskId);
    for (const targetId of taskEdges(task)) {
      const cycle = visit(targetId);
      if (cycle) return cycle;
    }
    path.pop();
    visiting.delete(taskId);
    visited.add(taskId);
    return null;
  };

  for (const taskId of tasks.keys()) {
    const cycle = visit(taskId);
    if (cycle) return cycle;
  }
  return null;
}

/** Validate references without mutating or guessing repairs for the graph. */
export function validateAdeGraph(graph: AdeGraph): AdeGraphDiagnostic[] {
  const diagnostics: AdeGraphDiagnostic[] = [];
  const projects = indexById("project", graph.projects, diagnostics);
  const workspaces = indexById("workspace", graph.workspaces, diagnostics);
  const tasks = indexById("task", graph.tasks, diagnostics);
  indexById("spec", graph.specs, diagnostics);
  const environments = indexById("environment", graph.environments, diagnostics);
  const runs = indexById("run", graph.runs, diagnostics);
  const sessions = indexById("agent_session", graph.agentSessions, diagnostics);
  const artifacts = indexById("artifact", graph.artifacts, diagnostics);
  indexById("evidence", graph.evidence, diagnostics);
  indexById("approval", graph.approvals, diagnostics);
  indexById("attention_item", graph.attentionItems, diagnostics);

  for (const workspace of graph.workspaces) {
    if (!projects.has(workspace.projectId)) {
      missing(diagnostics, "missing_project", "workspace", workspace.id, "projectId", workspace.projectId);
    }
  }
  for (const task of graph.tasks) {
    if (!projects.has(task.projectId)) {
      missing(diagnostics, "missing_project", "task", task.id, "projectId", task.projectId);
    }
    const relatedTaskIds = [
      ...(task.parentTaskId ? [{ field: "parentTaskId", id: task.parentTaskId }] : []),
      ...(task.dependencyTaskIds ?? []).map((id) => ({ field: "dependencyTaskIds", id })),
    ];
    const seenDependencies = new Set<string>();
    for (const related of relatedTaskIds) {
      const target = tasks.get(related.id);
      if (!target) {
        missing(diagnostics, "missing_task", "task", task.id, related.field, related.id);
      } else if (target.projectId !== task.projectId) {
        missing(diagnostics, "cross_project_task", "task", task.id, related.field, related.id);
      }
      if (related.field === "dependencyTaskIds") {
        if (seenDependencies.has(related.id)) {
          diagnostics.push({
            code: "duplicate_task_dependency",
            entityKind: "task",
            entityId: task.id,
            field: related.field,
            referenceId: related.id,
          });
        }
        seenDependencies.add(related.id);
      }
    }
  }
  const taskCycle = findTaskCycle(tasks);
  if (taskCycle) {
    diagnostics.push({
      code: "task_cycle",
      entityKind: "task",
      entityId: taskCycle[0],
      field: "parentTaskId/dependencyTaskIds",
      referenceId: taskCycle.join(" -> "),
    });
  }
  for (const spec of graph.specs) {
    if (!tasks.has(spec.taskId)) {
      missing(diagnostics, "missing_task", "spec", spec.id, "taskId", spec.taskId);
    }
  }
  for (const environment of graph.environments) {
    if (!projects.has(environment.projectId)) {
      missing(diagnostics, "missing_project", "environment", environment.id, "projectId", environment.projectId);
    }
    if (environment.workspaceId && !workspaces.has(environment.workspaceId)) {
      missing(diagnostics, "missing_workspace", "environment", environment.id, "workspaceId", environment.workspaceId);
    } else if (
      environment.workspaceId &&
      workspaces.get(environment.workspaceId)?.projectId !== environment.projectId
    ) {
      missing(
        diagnostics,
        "cross_project_workspace",
        "environment",
        environment.id,
        "workspaceId",
        environment.workspaceId,
      );
    }
  }
  for (const run of graph.runs) {
    const task = tasks.get(run.taskId);
    const environment = environments.get(run.environmentId);
    if (!task) missing(diagnostics, "missing_task", "run", run.id, "taskId", run.taskId);
    if (!environment) {
      missing(diagnostics, "missing_environment", "run", run.id, "environmentId", run.environmentId);
    } else if (task && environment.projectId !== task.projectId) {
      missing(
        diagnostics,
        "cross_project_environment",
        "run",
        run.id,
        "environmentId",
        run.environmentId,
      );
    }
  }
  const activeRunsByTask = new Map<string, AdeRun[]>();
  for (const run of graph.runs) {
    if (!ACTIVE_RUN_STATES.has(run.state)) continue;
    const active = activeRunsByTask.get(run.taskId) ?? [];
    active.push(run);
    activeRunsByTask.set(run.taskId, active);
  }
  for (const [taskId, activeRuns] of activeRunsByTask) {
    if (
      activeRuns.length > 1 &&
      activeRuns.some((run) => !PARALLEL_RUN_STRATEGIES.has(run.strategy))
    ) {
      diagnostics.push({
        code: "multiple_active_task_runs",
        entityKind: "task",
        entityId: taskId,
        field: "runs",
      });
    }
  }
  const sessionsByRun = new Map<string, AdeAgentSession[]>();
  for (const session of graph.agentSessions) {
    if (!runs.has(session.runId)) {
      missing(diagnostics, "missing_run", "agent_session", session.id, "runId", session.runId);
    }
    const sessionsForRun = sessionsByRun.get(session.runId) ?? [];
    sessionsForRun.push(session);
    sessionsByRun.set(session.runId, sessionsForRun);
    if ((session.role as string) === "subagent") {
      diagnostics.push({
        code: "provider_subagent_not_top_level",
        entityKind: "agent_session",
        entityId: session.id,
        field: "role",
      });
    }
  }
  for (const [runId, runSessions] of sessionsByRun) {
    if (runSessions.length > 1) {
      diagnostics.push({
        code: "multiple_run_sessions",
        entityKind: "run",
        entityId: runId,
        field: "agentSessions",
      });
    }
  }
  for (const artifact of graph.artifacts) {
    if (!runs.has(artifact.runId)) {
      missing(diagnostics, "missing_run", "artifact", artifact.id, "runId", artifact.runId);
    }
  }
  for (const item of graph.evidence) {
    if (!runs.has(item.runId)) {
      missing(diagnostics, "missing_run", "evidence", item.id, "runId", item.runId);
    }
    for (const artifactId of item.artifactIds ?? []) {
      const artifact = artifacts.get(artifactId);
      if (!artifact) {
        missing(diagnostics, "missing_artifact", "evidence", item.id, "artifactIds", artifactId);
      } else if (artifact.runId !== item.runId) {
        missing(diagnostics, "cross_run_artifact", "evidence", item.id, "artifactIds", artifactId);
      }
    }
  }
  for (const approval of graph.approvals) {
    if (!runs.has(approval.runId)) {
      missing(diagnostics, "missing_run", "approval", approval.id, "runId", approval.runId);
    }
    if (approval.agentSessionId) {
      const session = sessions.get(approval.agentSessionId);
      if (!session) {
        missing(
          diagnostics,
          "missing_agent_session",
          "approval",
          approval.id,
          "agentSessionId",
          approval.agentSessionId,
        );
      } else if (session.runId !== approval.runId) {
        missing(
          diagnostics,
          "inconsistent_approval_reference",
          "approval",
          approval.id,
          "agentSessionId",
          approval.agentSessionId,
        );
      }
    }
  }
  for (const item of graph.attentionItems) {
    const task = tasks.get(item.taskId);
    const run = item.runId ? runs.get(item.runId) : undefined;
    const session = item.agentSessionId ? sessions.get(item.agentSessionId) : undefined;
    let inconsistent = false;

    if (!projects.has(item.projectId)) {
      missing(diagnostics, "missing_project", "attention_item", item.id, "projectId", item.projectId);
    }
    if (!task) {
      missing(diagnostics, "missing_task", "attention_item", item.id, "taskId", item.taskId);
    } else if (task.projectId !== item.projectId) {
      inconsistent = true;
    }
    if (item.runId && !run) {
      missing(diagnostics, "missing_run", "attention_item", item.id, "runId", item.runId);
    } else if (run && run.taskId !== item.taskId) {
      inconsistent = true;
    }
    if (item.agentSessionId && !session) {
      missing(
        diagnostics,
        "missing_agent_session",
        "attention_item",
        item.id,
        "agentSessionId",
        item.agentSessionId,
      );
    } else if (session && (!item.runId || session.runId !== item.runId)) {
      inconsistent = true;
    }
    if (inconsistent) {
      diagnostics.push({
        code: "inconsistent_attention_reference",
        entityKind: "attention_item",
        entityId: item.id,
        field: "references",
      });
    }
  }

  return diagnostics;
}
