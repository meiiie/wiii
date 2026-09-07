import { sessionSearchableText } from "./command-items";
import type { NekoSession } from "./stores/neko-session-store";

export type SessionProjection = "projects" | "harnesses";
export type SessionGroupKind = "project" | "harness" | "legacy";
export type SessionAttentionState = "working" | "ready" | "needs-attention" | "stopped";

export interface SessionGroup {
  key: string;
  name: string;
  detail: string | null;
  kind: SessionGroupKind;
  updatedAt: number;
  sessions: NekoSession[];
}

export interface SessionPresentation {
  state: SessionAttentionState;
  label: string;
}

function visibleSessions(sessions: NekoSession[], query: string): NekoSession[] {
  const normalized = query.trim().toLocaleLowerCase("vi");
  return normalized
    ? sessions.filter((session) => sessionSearchableText(session).includes(normalized))
    : sessions;
}

function sortGroups(groups: Map<string, SessionGroup>): SessionGroup[] {
  return [...groups.values()]
    .map((group) => ({
      ...group,
      sessions: [...group.sessions].sort((a, b) => b.updatedAt - a.updatedAt),
    }))
    .sort((a, b) => {
      if (a.kind === "legacy") return 1;
      if (b.kind === "legacy") return -1;
      return b.updatedAt - a.updatedAt;
    });
}

export function groupSessionsByProject(
  sessions: NekoSession[],
  query = "",
): SessionGroup[] {
  const groups = new Map<string, SessionGroup>();
  for (const session of visibleSessions(sessions, query)) {
    const workspacePath = session.workspace?.path;
    const key = workspacePath
      ? (/^(?:[A-Za-z]:[\\/]|\\\\)/.test(workspacePath)
          ? workspacePath.toLocaleLowerCase("en-US")
          : workspacePath)
      : "__legacy__";
    const existing = groups.get(key) ?? {
      key,
      name: session.workspace?.name ?? "Legacy · Phiên chưa gắn dự án",
      detail: session.workspace?.path ?? null,
      kind: workspacePath ? "project" : "legacy",
      updatedAt: 0,
      sessions: [],
    };
    existing.sessions.push(session);
    existing.updatedAt = Math.max(existing.updatedAt, session.updatedAt);
    groups.set(key, existing);
  }
  return sortGroups(groups);
}

export function groupSessionsByHarness(
  sessions: NekoSession[],
  query = "",
): SessionGroup[] {
  const groups = new Map<string, SessionGroup>();
  for (const session of visibleSessions(sessions, query)) {
    const key = `harness:${session.agentId}`;
    const existing = groups.get(key) ?? {
      key,
      name: session.agentName,
      detail: session.agentId,
      kind: "harness" as const,
      updatedAt: 0,
      sessions: [],
    };
    existing.sessions.push(session);
    existing.updatedAt = Math.max(existing.updatedAt, session.updatedAt);
    groups.set(key, existing);
  }
  return sortGroups(groups);
}

/**
 * A display status is a projection of durable lifecycle facts. It is never
 * persisted as another source of truth.
 */
export function deriveSessionPresentation(session: NekoSession): SessionPresentation {
  if (session.pendingPermission) {
    return { state: "needs-attention", label: "Cần bạn" };
  }
  if (session.status === "error") {
    return { state: "needs-attention", label: "Cần kiểm tra" };
  }
  if (["connecting", "dispatching", "streaming", "stopping"].includes(session.status)) {
    const labels = {
      connecting: "Đang kết nối",
      dispatching: "Đang gửi",
      streaming: "Đang làm việc",
      stopping: "Đang dừng",
    } as const;
    return {
      state: "working",
      label: labels[session.status as keyof typeof labels],
    };
  }
  if (session.status === "idle") {
    return { state: "ready", label: "Sẵn sàng" };
  }
  return { state: "stopped", label: "Đã dừng" };
}

export function sessionStatusDotClass(session: NekoSession): string {
  const state = deriveSessionPresentation(session).state;
  if (state === "working") return "bg-[var(--nk-accent)] animate-pulse";
  if (state === "ready") return "bg-[var(--nk-success)]";
  if (state === "needs-attention") return "bg-[var(--nk-danger)]";
  return "bg-[var(--nk-ghost)]";
}
