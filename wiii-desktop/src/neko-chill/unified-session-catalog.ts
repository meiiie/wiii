import type { NekoProviderSessionRecord } from "@/neko/contracts";
import { deriveSessionPresentation } from "./session-catalog";
import type { NekoSession } from "./stores/neko-session-store";

export type UnifiedSessionProjection = "projects" | "harnesses";
export type UnifiedSessionState = "needs-attention" | "working" | "ready" | "stopped";

export interface UnifiedSessionItem {
  key: string;
  source: "wiii" | "provider";
  title: string;
  projectKey: string;
  projectName: string;
  projectPath: string | null;
  harnessId: string;
  harnessName: string;
  updatedAt: number;
  model: string | null;
  state: UnifiedSessionState;
  stateLabel: string;
  searchableDetail: string;
  managedSessionId: string | null;
  providerSession: NekoProviderSessionRecord | null;
}

export interface UnifiedSessionGroup {
  key: string;
  name: string;
  detail: string | null;
  kind: UnifiedSessionProjection | "unassigned";
  updatedAt: number;
  workingCount: number;
  attentionCount: number;
  harnessCounts: Array<{ harnessId: string; name: string; count: number }>;
  sessions: UnifiedSessionItem[];
}

export interface UnifiedSessionFilters {
  query?: string;
  harnessId?: string;
  state?: "needs-attention" | "working" | "ready" | "stopped";
}

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("vi")
    .trim();
}

function normalizeProjectKey(path: string): string {
  const normalized = path.replace(/[\\/]+$/, "");
  return /^(?:[A-Za-z]:[\\/]|\\\\)/.test(normalized)
    ? normalized.toLocaleLowerCase("en-US")
    : normalized;
}

function projectName(path: string): string {
  const segments = path.replace(/[\\/]+$/, "").split(/[\\/]+/).filter(Boolean);
  return segments[segments.length - 1] ?? path;
}

function timestamp(value: string | null): number {
  const parsed = Date.parse(value ?? "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function stateRank(state: UnifiedSessionState): number {
  if (state === "needs-attention") return 0;
  if (state === "working") return 1;
  if (state === "ready") return 2;
  return 3;
}

export function compareUnifiedSessions(left: UnifiedSessionItem, right: UnifiedSessionItem): number {
  return stateRank(left.state) - stateRank(right.state)
    || right.updatedAt - left.updatedAt
    || left.title.localeCompare(right.title);
}

function managedSearchDetail(session: NekoSession): string {
  const latestUserText = [...session.messages]
    .reverse()
    .find((message) => message.role === "user" && message.text?.trim())
    ?.text ?? "";
  return [session.id, session.backendSessionId ?? "", latestUserText].join(" ");
}

export function createUnifiedSessionCatalog(
  managedSessions: NekoSession[],
  providerSessions: NekoProviderSessionRecord[],
  providerNames: ReadonlyMap<string, string>,
): UnifiedSessionItem[] {
  const items: UnifiedSessionItem[] = [];
  for (const session of managedSessions) {
    const presentation = deriveSessionPresentation(session);
    const path = session.workspace?.path?.trim() || null;
    items.push({
      key: `wiii:${session.id}`,
      source: "wiii",
      title: session.title,
      projectKey: path ? normalizeProjectKey(path) : "__unassigned__",
      projectName: session.workspace?.name ?? (path ? projectName(path) : "Dự án chưa xác định"),
      projectPath: path,
      harnessId: session.agentId,
      harnessName: session.agentName,
      updatedAt: session.updatedAt,
      model: session.launchProfile?.model ?? null,
      state: presentation.state,
      stateLabel: presentation.label,
      searchableDetail: managedSearchDetail(session),
      managedSessionId: session.id,
      providerSession: null,
    });
  }
  for (const session of providerSessions) {
    const path = session.workspacePath?.trim() || null;
    const updatedAt = timestamp(session.updatedAt ?? session.createdAt);
    items.push({
      key: `provider:${session.providerId}:${session.nativeSessionId}`,
      source: "provider",
      title: session.title,
      projectKey: path ? normalizeProjectKey(path) : "__unassigned__",
      projectName: path ? projectName(path) : "Dự án chưa xác định",
      projectPath: path,
      harnessId: session.providerId,
      harnessName: providerNames.get(session.providerId) ?? session.providerId,
      updatedAt,
      model: session.model,
      state: "stopped",
      stateLabel: "Đã lưu",
      searchableDetail: session.nativeSessionId,
      managedSessionId: null,
      providerSession: session,
    });
  }
  return items.sort(compareUnifiedSessions);
}

function searchableText(item: UnifiedSessionItem): string {
  return normalizeText([
    item.title,
    item.projectName,
    item.projectPath ?? "",
    item.harnessName,
    item.harnessId,
    item.model ?? "",
    item.searchableDetail,
  ].join(" "));
}

export function filterUnifiedSessions(
  items: UnifiedSessionItem[],
  filters: UnifiedSessionFilters = {},
): UnifiedSessionItem[] {
  const query = normalizeText(filters.query ?? "");
  return items
    .filter((item) => !filters.harnessId || item.harnessId === filters.harnessId)
    .filter((item) => !filters.state || item.state === filters.state)
    .filter((item) => !query || searchableText(item).includes(query))
    .sort(compareUnifiedSessions);
}

export function groupUnifiedSessions(
  items: UnifiedSessionItem[],
  projection: UnifiedSessionProjection,
): UnifiedSessionGroup[] {
  const groups = new Map<string, Omit<UnifiedSessionGroup, "harnessCounts"> & {
    harnessCounts: Map<string, { name: string; count: number }>;
  }>();
  for (const item of items) {
    const unassigned = item.projectKey === "__unassigned__";
    const key = projection === "projects"
      ? `project:${item.projectKey}`
      : `harness:${item.harnessId}`;
    const existing = groups.get(key) ?? {
      key,
      name: projection === "projects" ? item.projectName : item.harnessName,
      detail: projection === "projects" ? item.projectPath : item.harnessId,
      kind: projection === "projects"
        ? unassigned ? "unassigned" as const : "projects" as const
        : "harnesses" as const,
      updatedAt: 0,
      workingCount: 0,
      attentionCount: 0,
      harnessCounts: new Map<string, { name: string; count: number }>(),
      sessions: [],
    };
    existing.sessions.push(item);
    existing.updatedAt = Math.max(existing.updatedAt, item.updatedAt);
    if (item.state === "working") existing.workingCount += 1;
    if (item.state === "needs-attention") existing.attentionCount += 1;
    const harness = existing.harnessCounts.get(item.harnessId) ?? {
      name: item.harnessName,
      count: 0,
    };
    harness.count += 1;
    existing.harnessCounts.set(item.harnessId, harness);
    groups.set(key, existing);
  }
  return [...groups.values()]
    .map((group): UnifiedSessionGroup => ({
      ...group,
      sessions: [...group.sessions].sort(compareUnifiedSessions),
      harnessCounts: [...group.harnessCounts.entries()]
        .map(([harnessId, value]) => ({ harnessId, ...value }))
        .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name)),
    }))
    .sort((left, right) => {
      if (left.kind === "unassigned") return 1;
      if (right.kind === "unassigned") return -1;
      if (left.attentionCount !== right.attentionCount) return right.attentionCount - left.attentionCount;
      if (left.workingCount !== right.workingCount) return right.workingCount - left.workingCount;
      return right.updatedAt - left.updatedAt || left.name.localeCompare(right.name);
    });
}
