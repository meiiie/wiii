import { useEffect, useMemo, useRef } from "react";
import { useShallow } from "zustand/react/shallow";
import { AlertCircle, Bot, Plus, Radio } from "lucide-react";
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
  if (summary.found) return summary.version ? `Đã phát hiện · ${summary.version}` : "Đã phát hiện";
  if (summary.found === null) return "Chưa kiểm tra trên máy này";
  if (summary.availability === "probe_failed") return "Chưa kiểm tra được · không có nghĩa là chưa cài";
  if (summary.availability === "host_unsupported") return "Wiii chưa hỗ trợ chạy trên hệ điều hành này";
  return "Chưa tìm thấy trên máy này";
}

export function NekoOverview({
  sessions,
  agents,
  providerCatalogs,
  discoveryLoading,
  onNewSession,
  onOpenSession,
  onRefreshDiscovery,
  onImportProviderSession,
  harnessFocusRequest = 0,
}: {
  sessions: NekoSession[];
  agents: DetectedAgent[];
  providerCatalogs: NekoProviderSessionCatalog[];
  discoveryLoading: boolean;
  onNewSession: () => void;
  onOpenSession: (sessionId: string) => void;
  onRefreshDiscovery: () => void;
  onImportProviderSession: (session: NekoProviderSessionRecord) => Promise<void>;
  harnessFocusRequest?: number;
}) {
  const harnessHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!harnessFocusRequest) return;
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

  return (
    <main className="min-w-0 flex-1 overflow-y-auto" data-testid="neko-overview">
      <div className="mx-auto w-full max-w-[1080px] px-7 pb-14 pt-[7vh]">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--nk-accent)]">Neko Chill · Agent sessions</p>
            <h1 className="text-[30px] font-normal tracking-[-0.03em] text-[var(--nk-text)]" style={{ fontFamily: "var(--font-serif)" }}>
              Mọi phiên agent, ở một nơi.
            </h1>
            <p className="mt-2 max-w-[650px] text-[13px] leading-5 text-[var(--nk-text-2)]">
              Tìm lại công việc theo dự án, tiếp tục các phiên đã lưu và quản lý agent trên máy.
            </p>
          </div>
          <button type="button" className="inline-flex h-9 items-center gap-2 rounded-lg bg-[var(--nk-inverse)] px-3.5 text-[12.5px] font-medium text-[var(--nk-on-inverse)] transition-opacity hover:opacity-90" onClick={onNewSession}>
            <Plus aria-hidden="true" className="h-3.5 w-3.5" /> Phiên mới
          </button>
        </div>

        <div className="mt-7 grid grid-cols-3 gap-2" aria-label="Tổng quan phiên">
          {[
            { label: "Phiên trên máy", value: sessions.length + discoveredSessions.length, icon: Bot },
            { label: "Đang hoạt động", value: working, icon: Radio },
            { label: "Cần bạn", value: attention, icon: AlertCircle },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.label} className="rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] px-4 py-3">
                <div className="flex items-center justify-between text-[11px] text-[var(--nk-text-3)]">{item.label}<Icon aria-hidden="true" className="h-3.5 w-3.5" /></div>
                <strong className="mt-1 block text-[22px] font-medium tabular-nums text-[var(--nk-text)]">{item.value}</strong>
              </div>
            );
          })}
        </div>

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

        <section className="mt-4 rounded-2xl border border-[var(--nk-border)] bg-[var(--nk-composer)] p-2">
          <div className="flex flex-wrap items-end justify-between gap-3 px-3 pb-2 pt-1.5">
            <div>
              <h2 ref={harnessHeading} tabIndex={-1} id="neko-harness-management" className="scroll-mt-6 rounded text-[13px] font-medium text-[var(--nk-text)]">Quản lý harness</h2>
              <p className="mt-0.5 text-[11.5px] text-[var(--nk-text-3)]">Neko Core là agent mặc định. Wiii dùng bản đã có trên máy nếu tìm thấy.</p>
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
                      <p className="mt-1 break-words">{harness.detail}</p>
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
              <div className="mt-2 max-w-[720px] space-y-2 text-[11.5px] leading-5">
                <p>Bản Wiii thử nghiệm này dùng Neko đã cài riêng; chưa tự tải, tự cập nhật hoặc tự gỡ Neko Core. Kiểm tra chỉ đọc phiên bản, không đăng nhập hay chạy công việc.</p>
                <p>Neko có bản Windows, macOS và Linux. Khả năng chạy trong Wiii còn phụ thuộc hỗ trợ của từng hệ điều hành; cài Neko không tự bổ sung hỗ trợ đó.</p>
                <p>Để cập nhật bản cài riêng, dùng <code>neko update</code> sau khi kết thúc các phiên Neko. Để gỡ, dùng cách tương ứng với bản bạn đã cài; Wiii không xóa chương trình dùng chung hoặc dữ liệu tài khoản của bạn.</p>
              </div>
            </details>
          </div>
        </section>
      </div>
    </main>
  );
}
