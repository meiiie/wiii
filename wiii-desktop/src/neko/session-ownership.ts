/**
 * Neko owns logical execution sessions; providers only create the native
 * conversation/process behind one of these records.
 *
 * This contract deliberately has no provider-level cardinality: one provider
 * may back any number of independent sessions. Provider-native subagents are
 * not top-level Neko sessions and therefore are not part of this vocabulary.
 */

export type NekoTopLevelSessionKind = "worker" | "coordinator" | "scratch";

export interface NekoSessionOwnershipFact {
  sessionId: string;
  providerId: string;
  kind: NekoTopLevelSessionKind;
  projectId: string | null;
  taskId: string | null;
  runId: string | null;
  active: boolean;
}

export type NekoSessionOwnershipDiagnosticCode =
  | "duplicate_session_id"
  | "invalid_session_scope"
  | "multiple_project_coordinators"
  | "multiple_task_workers";

export interface NekoSessionOwnershipDiagnostic {
  code: NekoSessionOwnershipDiagnosticCode;
  sessionId: string;
  referenceId?: string;
}

export function validateNekoSessionOwnership(
  facts: readonly NekoSessionOwnershipFact[],
): NekoSessionOwnershipDiagnostic[] {
  const diagnostics: NekoSessionOwnershipDiagnostic[] = [];
  const sessionIds = new Set<string>();
  const coordinators = new Map<string, string>();
  const workers = new Map<string, string>();

  for (const fact of facts) {
    if (sessionIds.has(fact.sessionId)) {
      diagnostics.push({
        code: "duplicate_session_id",
        sessionId: fact.sessionId,
        referenceId: fact.sessionId,
      });
    }
    sessionIds.add(fact.sessionId);

    const validScope = fact.kind === "scratch"
      ? fact.taskId === null && fact.runId === null
      : fact.kind === "coordinator"
        ? fact.projectId !== null && fact.taskId === null && fact.runId === null
        : fact.taskId !== null && fact.runId !== null;
    if (!validScope) {
      diagnostics.push({ code: "invalid_session_scope", sessionId: fact.sessionId });
      continue;
    }
    if (!fact.active) continue;

    if (fact.kind === "coordinator") {
      const owner = coordinators.get(fact.projectId!);
      if (owner) {
        diagnostics.push({
          code: "multiple_project_coordinators",
          sessionId: fact.sessionId,
          referenceId: owner,
        });
      } else {
        coordinators.set(fact.projectId!, fact.sessionId);
      }
    }

    if (fact.kind === "worker") {
      const owner = workers.get(fact.taskId!);
      if (owner) {
        diagnostics.push({
          code: "multiple_task_workers",
          sessionId: fact.sessionId,
          referenceId: owner,
        });
      } else {
        workers.set(fact.taskId!, fact.sessionId);
      }
    }
  }

  return diagnostics;
}
