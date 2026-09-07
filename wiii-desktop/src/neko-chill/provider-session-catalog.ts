import type { NekoProviderSessionRecord } from "@/neko/contracts";

export type ProviderSessionProjection = "projects" | "harnesses";

export interface ProviderSessionGroup {
  key: string;
  name: string;
  detail: string | null;
  kind: ProviderSessionProjection | "unassigned";
  updatedAt: number;
  providerCounts: Array<{ providerId: string; name: string; count: number }>;
  sessions: NekoProviderSessionRecord[];
}

export function providerSessionTimestamp(session: NekoProviderSessionRecord): number {
  const parsed = Date.parse(session.updatedAt ?? session.createdAt ?? "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeSearchValue(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("vi")
    .trim();
}

function normalizeWorkspaceKey(path: string): string {
  const normalized = path.replace(/[\\/]+$/, "");
  return /^(?:[A-Za-z]:[\\/]|\\\\)/.test(normalized)
    ? normalized.toLocaleLowerCase("en-US")
    : normalized;
}

function workspaceName(path: string): string {
  const segments = path.replace(/[\\/]+$/, "").split(/[\\/]+/).filter(Boolean);
  return segments[segments.length - 1] ?? path;
}

function searchableText(
  session: NekoProviderSessionRecord,
  providerName: string,
): string {
  return normalizeSearchValue([
    session.title,
    session.workspacePath ?? "",
    providerName,
    session.providerId,
    session.nativeSessionId,
    session.model ?? "",
  ].join(" "));
}

export function groupProviderSessions(
  sessions: NekoProviderSessionRecord[],
  projection: ProviderSessionProjection,
  providerNames: ReadonlyMap<string, string>,
  options: { query?: string; providerId?: string } = {},
): ProviderSessionGroup[] {
  const query = normalizeSearchValue(options.query ?? "");
  const filtered = sessions.filter((session) => {
    if (options.providerId && session.providerId !== options.providerId) return false;
    const providerName = providerNames.get(session.providerId) ?? session.providerId;
    return !query || searchableText(session, providerName).includes(query);
  });

  const groups = new Map<string, Omit<ProviderSessionGroup, "providerCounts"> & {
    providerCounts: Map<string, number>;
  }>();
  for (const session of filtered) {
    const providerName = providerNames.get(session.providerId) ?? session.providerId;
    const workspace = session.workspacePath?.trim() || null;
    const projectKey = workspace ? normalizeWorkspaceKey(workspace) : "__unassigned__";
    const key = projection === "projects" ? `project:${projectKey}` : `harness:${session.providerId}`;
    const existing = groups.get(key) ?? {
      key,
      name: projection === "projects"
        ? workspace ? workspaceName(workspace) : "Chưa xác định folder"
        : providerName,
      detail: projection === "projects" ? workspace : session.providerId,
      kind: projection === "projects"
        ? workspace ? "projects" as const : "unassigned" as const
        : "harnesses" as const,
      updatedAt: 0,
      providerCounts: new Map<string, number>(),
      sessions: [],
    };
    existing.sessions.push(session);
    existing.updatedAt = Math.max(existing.updatedAt, providerSessionTimestamp(session));
    existing.providerCounts.set(
      session.providerId,
      (existing.providerCounts.get(session.providerId) ?? 0) + 1,
    );
    groups.set(key, existing);
  }

  return [...groups.values()]
    .map((group): ProviderSessionGroup => ({
      ...group,
      sessions: [...group.sessions].sort(
        (left, right) => providerSessionTimestamp(right) - providerSessionTimestamp(left),
      ),
      providerCounts: [...group.providerCounts.entries()]
        .map(([providerId, count]) => ({
          providerId,
          name: providerNames.get(providerId) ?? providerId,
          count,
        }))
        .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name)),
    }))
    .sort((left, right) => {
      if (left.kind === "unassigned") return 1;
      if (right.kind === "unassigned") return -1;
      return right.updatedAt - left.updatedAt || left.name.localeCompare(right.name);
    });
}
