import { useEffect, useMemo, useRef } from "react";
import { useShallow } from "zustand/react/shallow";
import { ArrowUpRight, Bot, ChevronDown, Folder, FolderPlus, LoaderCircle, MessageSquare, Plus, Settings2 } from "lucide-react";
import { WiiiMark } from "@/components/common/WiiiMark";
import type { NekoProject } from "../stores/neko-project-store";
import type { NekoProviderSessionCatalog, NekoProviderSessionRecord } from "@/neko/contracts";
import { findProviderDefinition } from "@/neko/provider-registry";
import { useNekoAgentStore, type DetectedAgent } from "../stores/neko-agent-store";
import type { NekoSession } from "../stores/neko-session-store";
import { deriveSessionPresentation } from "../session-catalog";
import { providerSessionTimestamp } from "../provider-session-catalog";
import { ProviderSessionCatalogPanel } from "./ProviderSessionCatalogPanel";
import { HarnessSetupNotice } from "./HarnessSetupNotice";

interface HarnessSummary {
  id: string;
  name: string;
  version: string | null;
  found: boolean | null;
  availability: DetectedAgent["availability"] | null;
  detail: string | null;
  launchable: boolean;
  bundled: boolean;
  managedSessionCount: number;
  discoveredSessionCount: number;
}

function summarizeHarnesses(
  sessions: NekoSession[],
  agents: DetectedAgent[],
  catalogs: NekoProviderSessionCatalog[],
): HarnessSummary[] {
  const summaries = new Map<string, HarnessSummary>();
  for (const agent of agents) {
    summaries.set(agent.id, {
      id: agent.id,
      name: agent.name,
      version: agent.version,
      found: agent.found,
      availability: agent.availability,
      detail: agent.detail ?? null,
      bundled: agent.bundled === true,
      launchable: findProviderDefinition(agent.id)?.launchable !== false,
      managedSessionCount: 0,
      discoveredSessionCount: catalogs.find((catalog) => catalog.providerId === agent.id)?.sessions.length ?? 0,
    });
  }
  for (const session of sessions) {
    const summary = summaries.get(session.agentId) ?? {
      id: session.agentId,
      name: session.agentName,
      version: null,
      found: null,
      availability: null,
      detail: null,
      bundled: false,
      launchable: findProviderDefinition(session.agentId)?.launchable !== false,
      managedSessionCount: 0,
      discoveredSessionCount: 0,
    };
    summary.managedSessionCount += 1;
    summaries.set(session.agentId, summary);
  }
  return [...summaries.values()].sort((left, right) => {
    if (left.found !== right.found) return left.found ? -1 : 1;
    const leftCount = left.managedSessionCount + left.discoveredSessionCount;
    const rightCount = right.managedSessionCount + right.discoveredSessionCount;
    return rightCount - leftCount || left.name.localeCompare(right.name);
  });
}

function harnessDetail(summary: HarnessSummary): string {
  if (summary.found && !summary.launchable) {
    return summary.version ? `Đã phát hiện · ${summary.version} · chỉ mục read-only` : "Đã phát hiện · chỉ mục read-only";
  }
  if (summary.found && summary.bundled) return `Đi kèm Wiii · ${summary.version ?? "đã xác minh"}`;
  if (summary.found) return summary.version ? `Đã phát hiện · ${summary.version}` : "Đã phát hiện";
  if (summary.found === null) return "Chưa kiểm tra trên máy này";
  if (summary.availability === "probe_failed") return "Kiểm tra bị gián đoạn";
  if (summary.availability === "host_unsupported") return "Wiii chưa hỗ trợ chạy trên hệ điều hành này";
  return "Chưa tìm thấy trên máy này";
}

export function NekoOverview({
  sessions,
  agents,
  providerCatalogs,
  discoveryLoading,
  projectCount = 0,
  projects = [],
  onOpenProject,
  onQuickChat,
  quickChatPending = false,
  quickChatError,
  onNewSession,
  onCreateProject,
  onOpenSession,
  onRefreshDiscovery,
  onImportProviderSession,
  harnessFocusRequest = 0,
}: {
  sessions: NekoSession[];
  agents: DetectedAgent[];
  providerCatalogs: NekoProviderSessionCatalog[];
  discoveryLoading: boolean;
  projectCount?: number;
  projects?: NekoProject[];
  onOpenProject?: (projectId: string) => void;
  onQuickChat?: () => void;
  quickChatPending?: boolean;
  quickChatError?: string | null;
  onNewSession: () => void;
  onCreateProject?: () => void;
  onOpenSession: (sessionId: string) => void;
  onRefreshDiscovery: () => void;
  onImportProviderSession: (session: NekoProviderSessionRecord) => Promise<void>;
  harnessFocusRequest?: number;
}) {
  const harnessHeading = useRef<HTMLHeadingElement>(null);
  const harnessDetails = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (!harnessFocusRequest) return;
    if (harnessDetails.current) harnessDetails.current.open = true;
    harnessHeading.current?.scrollIntoView?.({ block: "start" });
    harnessHeading.current?.focus({ preventScroll: true });
  }, [harnessFocusRequest]);
  const { agentLoading, agentError, detectAgents } = useNekoAgentStore(useShallow((state) => ({
    agentLoading: state.isLoading, agentError: state.error, detectAgents: state.detect,
  })));
  const availableAgent = agents.find((agent) => agent.found && agent.availability === "available"
    && findProviderDefinition(agent.id)?.launchable === true) ?? null;
  const harnesses = useMemo(
    () => summarizeHarnesses(sessions, agents, providerCatalogs),
    [agents, providerCatalogs, sessions],
  );
  const discoveredSessions = useMemo(() => {
    const attached = new Set(sessions.flatMap((session) =>
      session.backendSessionId ? [`${session.agentId}:${session.backendSessionId}`] : [],
    ));
    return providerCatalogs
      .flatMap((catalog) => catalog.sessions)
      .filter((session) => !attached.has(`${session.providerId}:${session.nativeSessionId}`))
      .sort((left, right) => providerSessionTimestamp(right) - providerSessionTimestamp(left));
  }, [providerCatalogs, sessions]);
  const providerNames = useMemo(
    () => new Map(agents.map((agent) => [agent.id, agent.name])),
    [agents],
  );
  const working = sessions.filter((session) => deriveSessionPresentation(session).state === "working").length;
  const attention = sessions.filter((session) => deriveSessionPresentation(session).state === "needs-attention").length;
  const recentProjects = useMemo(() => projects
    .filter((project) => project.roots[0]?.kind !== "scratch")
    .sort((left, right) => right.updatedAt - left.updatedAt)
    .slice(0, 4), [projects]);

  return (
    <main className="nk-overview min-w-0 flex-1 overflow-y-auto" data-testid="neko-overview">
      <div className="mx-auto w-full max-w-[960px] px-6 pb-10 pt-10 sm:px-10">
        <div className="nk-home-welcome">
          <WiiiMark size={48} />
          <h1 className="mt-5 text-[30px] font-medium leading-tight tracking-[-0.035em] text-[var(--nk-text)]">Cùng bắt tay vào việc.</h1>
          <div className="nk-home-actions mt-7 grid gap-3">
            <button type="button" className="nk-home-action" onClick={onQuickChat ?? onNewSession} disabled={quickChatPending} data-testid="overview-quick-chat">
              <span className="nk-home-action-icon">{quickChatPending ? <LoaderCircle aria-hidden="true" size={20} className="animate-spin motion-reduce:animate-none" /> : <MessageSquare aria-hidden="true" size={20} />}</span>
              <span className="min-w-0 flex-1 text-[14px] font-medium">{quickChatPending ? "Đang mở chat…" : "Chat mới"}</span>
              <ArrowUpRight aria-hidden="true" size={16} className="text-[var(--nk-text-3)]" />
            </button>
            <button type="button" className="nk-home-action" onClick={projectCount === 0 ? onCreateProject ?? onNewSession : onNewSession} data-testid={projectCount === 0 ? "overview-create-first-project" : "overview-new-session"}>
              <span className="nk-home-action-icon"><FolderPlus aria-hidden="true" size={20} /></span>
              <span className="min-w-0 flex-1 text-[14px] font-medium">{projectCount === 0 ? "Tạo Project" : "Chat trong dự án"}</span>
              <ArrowUpRight aria-hidden="true" size={16} className="text-[var(--nk-text-3)]" />
            </button>
          </div>
          {quickChatError ? <p role="alert" className="mt-3 text-[12px] text-[var(--nk-danger)]">{quickChatError}</p> : null}
        </div>

        {recentProjects.length && onOpenProject ? <section className="mt-9" aria-label="Dự án gần đây">
          <div className="mb-3 flex items-center justify-between"><h2 className="text-[12px] font-medium text-[var(--nk-text-3)]">Dự án của bạn</h2><button type="button" onClick={onCreateProject} className="nk-chrome-button inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-[var(--nk-text-2)]"><Plus size={13} aria-hidden="true" />Tạo Project</button></div>
          <div className="nk-project-shortcuts grid gap-2">{recentProjects.map((project) => <button key={project.id} type="button" className="nk-project-shortcut" onClick={() => onOpenProject(project.id)}>
            <Folder size={17} aria-hidden="true" className="shrink-0 text-[var(--nk-text-3)]" /><span className="min-w-0 flex-1"><strong className="block truncate text-[12.5px] font-medium">{project.name}</strong><span className="mt-0.5 block truncate text-[11px] text-[var(--nk-text-3)]">{project.roots[0]?.path}</span></span><ArrowUpRight size={14} aria-hidden="true" className="shrink-0 text-[var(--nk-text-3)]" />
          </button>)}</div>
        </section> : null}

        {working || attention ? <div className="mt-6 flex flex-wrap gap-4 text-[12px] text-[var(--nk-text-2)]" aria-label="Tổng quan phiên">
          {working ? <span className="inline-flex items-center gap-2"><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[var(--nk-success)]" />{working} đang chạy</span> : null}
          {attention ? <span className="inline-flex items-center gap-2 text-[var(--nk-warning)]"><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />{attention} cần bạn</span> : null}
        </div> : null}

        <ProviderSessionCatalogPanel
          managedSessions={sessions}
          providerSessions={discoveredSessions}
          providerCatalogs={providerCatalogs}
          providerNames={providerNames}
          discoveryLoading={discoveryLoading}
          onRefresh={onRefreshDiscovery}
          onOpenManaged={onOpenSession}
          onImportProvider={onImportProviderSession}
        />

        <details ref={harnessDetails} className="nk-agent-details mt-7 border-t border-[var(--nk-border)]" data-testid="overview-agent-details">
          <summary className="flex cursor-pointer list-none items-center gap-2 py-4 text-[12px] text-[var(--nk-text-3)]"><Settings2 size={15} aria-hidden="true" /><span className="flex-1">Agent & cấu hình</span><span className="text-[11px]">{agentLoading ? "Đang kiểm tra…" : agentError ? "Kiểm tra thất bại" : availableAgent ? `${availableAgent.name} · Sẵn sàng` : "Cần thiết lập"}</span><ChevronDown size={14} aria-hidden="true" className="nk-details-chevron" /></summary>
          <section className="rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] p-2">
          <div className="flex flex-wrap items-end justify-between gap-3 px-3 pb-2 pt-1.5">
            <div>
              <h2 ref={harnessHeading} tabIndex={-1} id="neko-harness-management" className="scroll-mt-6 rounded text-[13px] font-medium text-[var(--nk-text)]">Quản lý agent</h2>
            </div>
            <button type="button" disabled={agentLoading}
              className="rounded-md border border-[var(--nk-border)] px-3 py-1.5 text-[11.5px] text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] disabled:opacity-50"
              onClick={() => { void detectAgents(); }}>{agentLoading ? "Đang kiểm tra…" : "Kiểm tra tất cả"}</button>
          </div>
          {harnesses.length ? (
            <div className="grid gap-0.5 lg:grid-cols-2">
              {harnesses.map((harness) => (
                <div key={harness.id} className="flex items-start gap-3 rounded-xl px-3 py-2.5">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--nk-inset)] text-[var(--nk-text-2)]"><Bot aria-hidden="true" className="h-3.5 w-3.5" /></span>
                  <span className="min-w-0 flex-1">
                    <strong className="block truncate text-[12.5px] font-medium text-[var(--nk-text)]">{harness.name}</strong>
                    <span className="block truncate text-[10.5px] text-[var(--nk-text-3)]">{harnessDetail(harness)}</span>
                    {harness.id !== "neko" && harness.detail && <details className="mt-1 text-[11px] text-[var(--nk-text-3)]">
                      <summary className="cursor-pointer">Chi tiết kiểm tra {harness.name}</summary>
                      <p className="mt-1 wrap-break-word">{harness.detail}</p>
                    </details>}
                  </span>
                  {harness.availability !== "host_unsupported" && (harness.id !== "neko" || harness.found) && <button type="button" disabled={agentLoading}
                    aria-label={`Kiểm tra ${harness.name}`}
                    className="shrink-0 rounded px-1 py-1 text-[11px] text-[var(--nk-text-2)] hover:underline disabled:opacity-50"
                    onClick={() => { void detectAgents(harness.id); }}>Kiểm tra</button>}
                  <span className="text-[10.5px] tabular-nums text-[var(--nk-ghost)]">
                    {harness.managedSessionCount} Wiii{harness.discoveredSessionCount ? ` · ${harness.discoveredSessionCount} ngoài Wiii` : ""}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
          <div className="px-3 pt-2">
            <HarnessSetupNotice agents={agents} loading={agentLoading} error={agentError}
              selectedAgent={availableAgent} onRetry={() => { void detectAgents("neko"); }} />
          </div>
          <div className="mx-3 mt-2 border-t border-[var(--nk-border)] py-3 text-[10.5px] leading-4 text-[var(--nk-text-3)]">
            <details>
              <summary className="cursor-pointer text-[var(--nk-text-2)]">Cài đặt, cập nhật và gỡ Neko Core</summary>
              <div className="mt-2 max-w-[720px] v3-space-y-2 text-[11.5px] leading-5">
                {agents.some((agent) => agent.id === "neko" && agent.found && agent.bundled) ? (
                  <p>Neko Core đi kèm bộ cài Wiii. Cập nhật hoặc cài lại Wiii để cập nhật hay sửa runtime này; không dùng lệnh tự cập nhật Neko cho bản đi kèm.</p>
                ) : (
                  <p>Bản Neko cài riêng do bạn quản lý. Wiii không tự tải, cập nhật hoặc gỡ bản cài riêng. Kiểm tra chỉ đọc phiên bản, không đăng nhập hay chạy công việc.</p>
                )}
              </div>
            </details>
          </div>
        </section>
        </details>
      </div>
    </main>
  );
}
