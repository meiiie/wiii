import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Bot, ChevronRight, Folder, History, Layers3, Link2, LoaderCircle, RefreshCw, Search } from "lucide-react";
import type { NekoProviderSessionCatalog, NekoProviderSessionRecord } from "@/neko/contracts";
import type { NekoSession } from "../stores/neko-session-store";
import {
  createUnifiedSessionCatalog,
  filterUnifiedSessions,
  groupUnifiedSessions,
  type UnifiedSessionGroup,
  type UnifiedSessionItem,
  type UnifiedSessionState,
} from "../unified-session-catalog";

type CatalogView = "projects" | "recent" | "harnesses";

const INITIAL_GROUP_LIMIT = 12;
const PREVIEW_LIMIT = 6;
const PAGE_SIZE = 50;

function timeLabel(timestamp: number): string {
  if (!timestamp) return "Đã lưu";
  return new Intl.DateTimeFormat("vi", { dateStyle: "short", timeStyle: "short" }).format(timestamp);
}

function stateDotClass(state: UnifiedSessionState): string {
  if (state === "needs-attention") return "bg-[var(--nk-danger)]";
  if (state === "working") return "bg-[var(--nk-accent)] nk-status-pulse";
  if (state === "ready") return "bg-[var(--nk-success)]";
  return "bg-[var(--nk-ghost)]";
}

function SessionRow({ item, showProject, importing, onOpenManaged, onImportProvider }: {
  item: UnifiedSessionItem;
  showProject: boolean;
  importing: boolean;
  onOpenManaged: (sessionId: string) => void;
  onImportProvider: (item: UnifiedSessionItem) => void;
}) {
  const actionable = Boolean(item.managedSessionId || item.providerSession?.canResume);
  return (
    <div className="group flex min-w-0 items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-[var(--nk-overlay)]">
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${stateDotClass(item.state)}`} />
      <span className="min-w-0 flex-1">
        <strong className="block truncate text-[12px] font-medium text-[var(--nk-text)]">{item.title}</strong>
        <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-[10.5px] text-[var(--nk-text-3)]">
          {showProject ? <><span className="truncate">{item.projectName}</span><span aria-hidden="true">›</span></> : null}
          <span className="shrink-0">{item.harnessName}</span><span aria-hidden="true">·</span>
          <span className="shrink-0">{item.stateLabel}</span><span aria-hidden="true">·</span>
          <span className="shrink-0">{timeLabel(item.updatedAt)}</span>
          {item.model ? <><span aria-hidden="true">·</span><span className="truncate">{item.model}</span></> : null}
        </span>
      </span>
      {actionable ? (
        <button
          type="button"
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-[var(--nk-border)] bg-[var(--nk-raised)] px-2.5 text-[11px] font-medium text-[var(--nk-text-2)] opacity-0 transition-opacity hover:border-[var(--nk-border-strong)] hover:text-[var(--nk-text)] group-hover:opacity-100 focus:opacity-100 disabled:opacity-50"
          disabled={importing}
          aria-label={`${item.managedSessionId ? "Mở phiên" : "Gắn phiên vào Wiii"} ${item.title}`}
          onClick={() => item.managedSessionId ? onOpenManaged(item.managedSessionId) : onImportProvider(item)}
        >
          {importing ? <LoaderCircle aria-hidden="true" className="h-3 w-3 animate-spin" />
            : item.managedSessionId ? <ChevronRight aria-hidden="true" className="h-3 w-3" />
              : <Link2 aria-hidden="true" className="h-3 w-3" />}
          {item.managedSessionId ? "Mở" : "Gắn vào Wiii"}
        </button>
      ) : (
        <span className="shrink-0 rounded-md bg-[var(--nk-inset)] px-2 py-1 text-[10px] text-[var(--nk-ghost)]" title="Wiii chỉ đọc metadata; harness chưa cung cấp continuation chính thức">
          Ngoài Wiii
        </span>
      )}
    </div>
  );
}

export function ProviderSessionCatalogPanel({
  managedSessions,
  providerSessions,
  providerCatalogs,
  providerNames,
  discoveryLoading,
  onRefresh,
  onOpenManaged,
  onImportProvider,
}: {
  managedSessions: NekoSession[];
  providerSessions: NekoProviderSessionRecord[];
  providerCatalogs: NekoProviderSessionCatalog[];
  providerNames: ReadonlyMap<string, string>;
  discoveryLoading: boolean;
  onRefresh: () => void;
  onOpenManaged: (sessionId: string) => void;
  onImportProvider: (session: NekoProviderSessionRecord) => Promise<void>;
}) {
  const [view, setView] = useState<CatalogView>("projects");
  const [query, setQuery] = useState("");
  const [state, setState] = useState<"" | UnifiedSessionState>("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [groupLimit, setGroupLimit] = useState(INITIAL_GROUP_LIMIT);
  const [sessionLimits, setSessionLimits] = useState<Record<string, number>>({});
  const [groupHarness, setGroupHarness] = useState<Record<string, string>>({});
  const [showAllHarnesses, setShowAllHarnesses] = useState<Set<string>>(new Set());
  const [flatLimit, setFlatLimit] = useState(PAGE_SIZE);
  const [importingKey, setImportingKey] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);

  const items = useMemo(
    () => createUnifiedSessionCatalog(managedSessions, providerSessions, providerNames),
    [managedSessions, providerNames, providerSessions],
  );
  const stateFiltered = useMemo(
    () => filterUnifiedSessions(items, { state: state || undefined }),
    [items, state],
  );
  const searchResults = useMemo(
    () => filterUnifiedSessions(items, { query: deferredQuery, state: state || undefined }),
    [deferredQuery, items, state],
  );
  const groups = useMemo(
    () => groupUnifiedSessions(stateFiltered, view === "harnesses" ? "harnesses" : "projects"),
    [stateFiltered, view],
  );
  const firstGroupKey = groups[0]?.key ?? null;
  const searching = deferredQuery.trim().length > 0;

  useEffect(() => {
    setGroupLimit(INITIAL_GROUP_LIMIT);
    setFlatLimit(PAGE_SIZE);
    if (!firstGroupKey) return;
    setExpanded((current) => current.has(firstGroupKey) ? current : new Set([firstGroupKey]));
  }, [firstGroupKey, view]);

  const importProvider = async (item: UnifiedSessionItem) => {
    if (!item.providerSession) return;
    setImportError(null);
    setImportingKey(item.key);
    try {
      await onImportProvider(item.providerSession);
    } catch (error) {
      setImportError(error instanceof Error ? error.message : String(error));
    } finally {
      setImportingKey(null);
    }
  };

  const renderRow = (item: UnifiedSessionItem, showProject: boolean) => (
    <SessionRow
      key={item.key}
      item={item}
      showProject={showProject}
      importing={importingKey === item.key}
      onOpenManaged={onOpenManaged}
      onImportProvider={(next) => void importProvider(next)}
    />
  );

  const renderGroup = (group: UnifiedSessionGroup) => {
    const isOpen = expanded.has(group.key);
    const selectedHarness = groupHarness[group.key] ?? "";
    const groupSessions = selectedHarness ? group.sessions.filter((item) => item.harnessId === selectedHarness) : group.sessions;
    const sessionLimit = sessionLimits[group.key] ?? PREVIEW_LIMIT;
    const visibleSessions = groupSessions.slice(0, sessionLimit);
    const visibleHarnesses = showAllHarnesses.has(group.key) ? group.harnessCounts : group.harnessCounts.slice(0, 3);
    const hiddenHarnessCount = group.harnessCounts.length - visibleHarnesses.length;

    return (
      <div key={group.key} className="border-b border-[var(--nk-border)] last:border-b-0">
        <button
          type="button"
          className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-[var(--nk-overlay)]"
          aria-expanded={isOpen}
          onClick={() => setExpanded((current) => {
            const next = new Set(current);
            if (next.has(group.key)) next.delete(group.key); else next.add(group.key);
            return next;
          })}
        >
          <ChevronRight aria-hidden="true" className={`h-3.5 w-3.5 shrink-0 text-[var(--nk-ghost)] transition-transform ${isOpen ? "rotate-90" : ""}`} />
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--nk-inset)] text-[var(--nk-text-2)]">
            {view === "harnesses" ? <Bot aria-hidden="true" className="h-3.5 w-3.5" /> : <Folder aria-hidden="true" className="h-3.5 w-3.5" />}
          </span>
          <span className="min-w-0 flex-1">
            <strong className="block truncate text-[12.5px] font-medium text-[var(--nk-text)]">{group.name}</strong>
            <span className="block truncate text-[10.5px] text-[var(--nk-text-3)]">
              {group.attentionCount ? `${group.attentionCount} cần bạn · ` : ""}
              {group.workingCount ? `${group.workingCount} đang chạy` : "Không có phiên đang chạy"}
              {group.detail ? ` · ${group.detail}` : ""}
            </span>
          </span>
          <span className="w-10 shrink-0 text-right text-[11px] tabular-nums text-[var(--nk-ghost)]">{group.sessions.length}</span>
        </button>

        {isOpen ? (
          <div className="mb-2 ml-6 border-l border-[var(--nk-border)] pl-2">
            {view === "projects" && group.harnessCounts.length ? (
              <div className="flex flex-wrap items-center gap-1.5 px-3 pb-1.5 pt-1">
                <button type="button" aria-pressed={!selectedHarness} className={`rounded-md px-2 py-1 text-[10px] ${!selectedHarness ? "bg-[var(--nk-overlay)] text-[var(--nk-text)]" : "bg-[var(--nk-inset)] text-[var(--nk-text-3)]"}`} onClick={() => setGroupHarness((current) => ({ ...current, [group.key]: "" }))}>
                  Tất cả {group.sessions.length}
                </button>
                {visibleHarnesses.map((harness) => (
                  <button key={harness.harnessId} type="button" aria-pressed={selectedHarness === harness.harnessId} className={`rounded-md px-2 py-1 text-[10px] ${selectedHarness === harness.harnessId ? "bg-[var(--nk-overlay)] text-[var(--nk-text)]" : "bg-[var(--nk-inset)] text-[var(--nk-text-3)]"}`} onClick={() => setGroupHarness((current) => ({ ...current, [group.key]: harness.harnessId }))}>
                    {harness.name} {harness.count}
                  </button>
                ))}
                {hiddenHarnessCount > 0 ? (
                  <button type="button" className="rounded-md bg-[var(--nk-inset)] px-2 py-1 text-[10px] text-[var(--nk-text-3)] hover:text-[var(--nk-text)]" onClick={() => setShowAllHarnesses((current) => new Set(current).add(group.key))}>
                    +{hiddenHarnessCount}
                  </button>
                ) : null}
              </div>
            ) : null}
            {visibleSessions.map((item) => renderRow(item, view === "harnesses"))}
            {groupSessions.length > visibleSessions.length ? (
              <button
                type="button"
                className="ml-3 mt-1 rounded-md px-2 py-1.5 text-[10.5px] font-medium text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
                onClick={() => setSessionLimits((current) => ({ ...current, [group.key]: sessionLimit === PREVIEW_LIMIT ? Math.min(PAGE_SIZE, groupSessions.length) : sessionLimit + PAGE_SIZE }))}
              >
                {sessionLimit === PREVIEW_LIMIT ? `Xem tất cả ${groupSessions.length} phiên` : `Hiện thêm ${Math.min(PAGE_SIZE, groupSessions.length - visibleSessions.length)} phiên`}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  };

  const flatItems = searching ? searchResults : stateFiltered;
  const showFlat = searching || view === "recent";

  return (
    <section className="mt-4 overflow-hidden rounded-2xl border border-[var(--nk-border)] bg-[var(--nk-composer)]">
      <div className="flex flex-wrap items-start justify-between gap-4 px-5 pb-3 pt-4">
        <div>
          <h2 className="text-[13px] font-medium text-[var(--nk-text)]">Phiên</h2>
          <p className="mt-0.5 max-w-[700px] text-[10.5px] leading-4 text-[var(--nk-text-3)]">Dự án là chiều điều hướng chính. Harness và trạng thái là bộ lọc trên cùng một catalog.</p>
        </div>
        <button type="button" className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-2.5 text-[11.5px] text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)] disabled:opacity-50" onClick={onRefresh} disabled={discoveryLoading}>
          {discoveryLoading ? <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />} Quét lại
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-y border-[var(--nk-border)] bg-[var(--nk-raised)]/40 px-4 py-2.5">
        <label className="relative min-w-[220px] flex-1">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--nk-ghost)]" />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm mọi phiên…" aria-label="Tìm mọi phiên" aria-busy={query !== deferredQuery} className="h-9 w-full rounded-lg border border-[var(--nk-border)] bg-[var(--nk-composer)] pl-9 pr-3 text-[12px] text-[var(--nk-text)] outline-none placeholder:text-[var(--nk-ghost)] focus:border-[var(--nk-border-strong)]" />
        </label>
        <select value={state} onChange={(event) => setState(event.target.value as "" | UnifiedSessionState)} aria-label="Lọc theo trạng thái" className="h-9 min-w-[135px] rounded-lg border border-[var(--nk-border)] bg-[var(--nk-composer)] px-2.5 text-[11.5px] text-[var(--nk-text-2)] outline-none focus:border-[var(--nk-border-strong)]">
          <option value="">Mọi trạng thái</option><option value="needs-attention">Cần bạn</option><option value="working">Đang chạy</option><option value="ready">Sẵn sàng</option><option value="stopped">Đã lưu / dừng</option>
        </select>
        <div className="flex h-9 items-center rounded-lg border border-[var(--nk-border)] bg-[var(--nk-composer)] p-0.5" aria-label="Cách xem phiên">
          {(["projects", "recent", "harnesses"] as const).map((value) => {
            const label = value === "projects" ? "Dự án" : value === "recent" ? "Gần đây" : "Harness";
            const Icon = value === "projects" ? Folder : value === "recent" ? History : Layers3;
            return <button key={value} type="button" aria-pressed={view === value} onClick={() => setView(value)} className={`inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[11px] transition-colors ${view === value ? "bg-[var(--nk-overlay)] text-[var(--nk-text)] shadow-sm" : "text-[var(--nk-text-3)] hover:text-[var(--nk-text-2)]"}`}><Icon aria-hidden="true" className="h-3 w-3" />{label}</button>;
          })}
        </div>
      </div>

      {importError ? <p role="alert" className="mx-4 mt-3 rounded-lg bg-[var(--nk-danger-soft)] px-3 py-2 text-[11px] text-[var(--nk-danger)]">{importError}</p> : null}

      {showFlat ? (
        flatItems.length ? (
          <div className="px-2 py-2" data-testid={searching ? "flat-session-search" : "recent-session-list"}>
            {flatItems.slice(0, flatLimit).map((item) => renderRow(item, true))}
            {flatItems.length > flatLimit ? <button type="button" className="mx-auto mt-2 block rounded-lg px-3 py-2 text-[11px] font-medium text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]" onClick={() => setFlatLimit((current) => current + PAGE_SIZE)}>Hiện thêm {Math.min(PAGE_SIZE, flatItems.length - flatLimit)} phiên</button> : null}
          </div>
        ) : <div className="grid min-h-28 place-items-center px-6 text-center text-[11.5px] text-[var(--nk-text-3)]">Không có phiên nào khớp tìm kiếm hoặc bộ lọc.</div>
      ) : groups.length ? (
        <div className="px-2 py-2" data-testid="unified-session-groups">
          {groups.slice(0, groupLimit).map(renderGroup)}
          {groups.length > groupLimit ? <button type="button" className="mx-auto mt-2 block rounded-lg px-3 py-2 text-[11px] font-medium text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]" onClick={() => setGroupLimit((current) => current + INITIAL_GROUP_LIMIT)}>Hiện thêm {Math.min(INITIAL_GROUP_LIMIT, groups.length - groupLimit)} nhóm</button> : null}
        </div>
      ) : (
        <div className="grid min-h-28 place-items-center px-6 text-center text-[11.5px] text-[var(--nk-text-3)]">{discoveryLoading ? "Đang hỏi từng harness về các phiên đã lưu…" : items.length ? "Không có phiên nào khớp bộ lọc." : "Chưa có phiên Wiii hoặc phiên ngoài Wiii nào được phát hiện."}</div>
      )}

      <div className="flex items-center justify-between border-t border-[var(--nk-border)] px-5 py-2.5 text-[10px] text-[var(--nk-ghost)]">
        <span>{items.length} phiên · {managedSessions.length} do Wiii quản lý</span>
        {providerCatalogs.some((catalog) => catalog.detail) ? (
          <details className="max-w-[70%] text-right"><summary className="cursor-pointer select-none hover:text-[var(--nk-text-3)]">Nguồn & giới hạn</summary><div className="mt-2 space-y-1 text-left leading-4">{providerCatalogs.flatMap((catalog) => catalog.detail ? [<p key={catalog.providerId}><strong>{providerNames.get(catalog.providerId) ?? catalog.providerId}:</strong> {catalog.detail}</p>] : [])}</div></details>
        ) : null}
      </div>
    </section>
  );
}
