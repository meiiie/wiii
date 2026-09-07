import {
  memo,
  useDeferredValue,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Command,
  FolderOpen,
  Info,
  MessageSquare,
  PanelLeft,
  Plus,
  Search,
} from "lucide-react";
import {
  buildNekoCommandItems,
  filterNekoCommandMetadata,
  filterNekoCommandItems,
  type NekoCommandItem,
  type WorkbenchActionName,
} from "../command-items";
import type { NekoSession } from "../stores/neko-session-store";
import { measureWiiiPerformance } from "@/lib/performance-telemetry";

interface NekoCommandCenterProps {
  open: boolean;
  sessions: NekoSession[];
  activeSession: NekoSession | null;
  sidebarOpen: boolean;
  onClose: () => void;
  onAction: (action: WorkbenchActionName) => void;
  onSelectSession: (sessionId: string) => void;
  onInsertCommand: (text: string) => void;
}

const COMMAND_RESULT_LIMIT = 32;
const COMMAND_RECENT_RESULT_LIMIT = 8;

const GROUP_LABELS: Record<NekoCommandItem["kind"], string> = {
  action: "Thao tác",
  command: "Lệnh của agent",
  session: "Phiên cục bộ",
};

function ItemIcon({ item }: { item: NekoCommandItem }) {
  if (item.kind === "command") return <Command aria-hidden="true" className="h-4 w-4" />;
  if (item.kind === "session") return <MessageSquare aria-hidden="true" className="h-4 w-4" />;
  if (item.action === "new") return <Plus aria-hidden="true" className="h-4 w-4" />;
  if (item.action === "project") return <FolderOpen aria-hidden="true" className="h-4 w-4" />;
  if (item.action === "info") return <Info aria-hidden="true" className="h-4 w-4" />;
  return <PanelLeft aria-hidden="true" className="h-4 w-4" />;
}

function statusClass(status: NekoSession["status"]): string {
  if (status === "streaming") return "bg-[var(--nk-accent)] nk-status-pulse";
  if (status === "idle") return "bg-[var(--nk-success)]";
  if (status === "error") return "bg-[var(--nk-danger)]";
  return "bg-[var(--nk-ghost)]";
}

function NekoCommandCenterComponent({
  open,
  sessions,
  activeSession,
  sidebarOpen,
  onClose,
  onAction,
  onSelectSession,
  onInsertCommand,
}: NekoCommandCenterProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const wasOpenRef = useRef(false);
  const items = useMemo(
    () => buildNekoCommandItems(sessions, activeSession, sidebarOpen),
    [activeSession, sessions, sidebarOpen],
  );
  const metadataMatches = useMemo(
    () => filterNekoCommandMetadata(items, query),
    [items, query],
  );
  const transcriptQuery = metadataMatches.length === 0 && query.trim() ? query : "";
  const deferredTranscriptQuery = useDeferredValue(transcriptQuery);
  const deferredMatches = useMemo(
    () => deferredTranscriptQuery
      ? filterNekoCommandItems(items, deferredTranscriptQuery)
      : [],
    [deferredTranscriptQuery, items],
  );
  const filtered = metadataMatches.length > 0 || !query.trim()
    ? metadataMatches
    : deferredTranscriptQuery === transcriptQuery
      ? deferredMatches
      : [];
  const searchPending = Boolean(transcriptQuery)
    && deferredTranscriptQuery !== transcriptQuery;
  const visibleItems = useMemo(
    () => filtered.slice(
      0,
      query.trim() ? COMMAND_RESULT_LIMIT : COMMAND_RECENT_RESULT_LIMIT,
    ),
    [filtered, query],
  );

  useEffect(() => {
    if (open) {
      if (!wasOpenRef.current && document.activeElement instanceof HTMLElement) {
        returnFocusRef.current = document.activeElement;
      }
      wasOpenRef.current = true;
      setQuery("");
      setSelectedIndex(0);
      const frame = requestAnimationFrame(() => inputRef.current?.focus());
      return () => cancelAnimationFrame(frame);
    }
    if (wasOpenRef.current) {
      wasOpenRef.current = false;
      const frame = requestAnimationFrame(() => returnFocusRef.current?.focus());
      return () => cancelAnimationFrame(frame);
    }
  }, [open]);

  useLayoutEffect(() => {
    if (open) {
      measureWiiiPerformance("wiii:command:ready", "wiii:command:open-start");
    }
  }, [open]);

  useEffect(() => {
    if (selectedIndex >= visibleItems.length) {
      setSelectedIndex(Math.max(0, visibleItems.length - 1));
    }
  }, [selectedIndex, visibleItems.length]);

  useEffect(() => {
    listRef.current
      ?.querySelector<HTMLElement>("[data-selected='true']")
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  if (!open) return null;

  const execute = (item: NekoCommandItem | undefined) => {
    if (!item) return;
    if (item.kind === "action") onAction(item.action);
    else if (item.kind === "command") onInsertCommand(item.commandText);
    else onSelectSession(item.sessionId);
    onClose();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelectedIndex((current) => Math.min(current + 1, visibleItems.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelectedIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      execute(visibleItems[selectedIndex]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
  };

  let globalIndex = 0;
  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/30 px-4 pt-[12vh] backdrop-blur-[1px]"
      role="dialog"
      aria-modal="true"
      aria-label="Trung tâm lệnh Neko Chill"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="w-full max-w-[620px] overflow-hidden rounded-2xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] shadow-[0_24px_70px_rgba(20,20,20,0.22)]"
        onKeyDown={(event) => {
          if (event.key !== "Tab") return;
          const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
            'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
          );
          if (!focusable?.length) return;
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }}
      >
        <div className="nk-input-field flex h-14 items-center gap-3 rounded-t-xl border-b border-[var(--nk-border)] px-4">
          <Search aria-hidden="true" className="h-4 w-4 shrink-0 text-[var(--nk-text-3)]" />
          <input
            ref={inputRef}
            type="search"
            role="searchbox"
            aria-label="Tìm phiên hoặc lệnh"
            aria-controls="neko-command-results"
            aria-activedescendant={visibleItems[selectedIndex]?.id}
            aria-busy={searchPending}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Tìm phiên, dự án, nội dung hoặc lệnh…"
            className="min-w-0 flex-1 bg-transparent text-[14px] text-[var(--nk-text)] placeholder:text-[var(--nk-ghost)] focus:outline-none"
          />
          <kbd className="rounded-md border border-[var(--nk-border)] bg-[var(--nk-raised)] px-1.5 py-0.5 text-[10px] text-[var(--nk-text-3)]">
            Esc
          </kbd>
        </div>

        <div id="neko-command-results" ref={listRef} role="listbox" className="nk-scroll-surface max-h-[430px] overflow-y-auto p-2">
          {visibleItems.length === 0 ? (
            <div className="px-4 py-10 text-center text-[12.5px] text-[var(--nk-text-3)]">
              {searchPending
                ? "Đang tìm trong nội dung phiên…"
                : "Không tìm thấy phiên hoặc lệnh phù hợp."}
            </div>
          ) : (["action", "command", "session"] as const).map((kind) => {
            const groupItems = visibleItems.filter((item) => item.kind === kind);
            if (!groupItems.length) return null;
            return (
              <section key={kind} aria-label={GROUP_LABELS[kind]} className="mb-1 last:mb-0">
                <h2 className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--nk-ghost)]">
                  {GROUP_LABELS[kind]}
                </h2>
                {groupItems.map((item) => {
                  const index = globalIndex++;
                  const selected = index === selectedIndex;
                  return (
                    <button
                      key={item.id}
                      id={item.id}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      data-selected={selected}
                      className={`flex min-h-[46px] w-full items-center gap-3 rounded-xl px-3 text-left transition-colors ${
                        selected ? "bg-[var(--nk-item-active)]" : "hover:bg-[var(--nk-overlay)]"
                      }`}
                      onMouseEnter={() => setSelectedIndex(index)}
                      onClick={() => execute(item)}
                    >
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--nk-inset)] text-[var(--nk-text-3)]">
                        <ItemIcon item={item} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2">
                          {item.kind === "session" ? (
                            <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${statusClass(item.status)}`} />
                          ) : null}
                          <strong className="truncate text-[13px] font-medium text-[var(--nk-text)]">
                            {item.label}
                          </strong>
                        </span>
                        <span className="block truncate text-[11px] text-[var(--nk-text-3)]">
                          {item.description}
                        </span>
                      </span>
                      {item.kind === "command" ? (
                        <span className="rounded-md bg-[var(--nk-inset)] px-1.5 py-0.5 text-[9.5px] text-[var(--nk-ghost)]">
                          {item.source}
                        </span>
                      ) : item.kind === "session" && item.active ? (
                        <span className="text-[10px] text-[var(--nk-accent)]">Đang mở</span>
                      ) : null}
                    </button>
                  );
                })}
              </section>
            );
          })}
        </div>

        <footer className="flex items-center gap-4 border-t border-[var(--nk-border)] px-4 py-2 text-[10px] text-[var(--nk-ghost)]">
          <span>↑↓ di chuyển</span>
          <span>Enter chọn</span>
          <span>Esc đóng</span>
          <span className="ml-auto">
            {filtered.length > visibleItems.length
              ? `${visibleItems.length}/${filtered.length} kết quả · nhập thêm để thu hẹp`
              : "Lệnh agent được chèn để bạn xem lại trước khi gửi"}
          </span>
        </footer>
      </div>
    </div>
  );
}

export const NekoCommandCenter = memo(
  NekoCommandCenterComponent,
  (previous, next) => !previous.open && !next.open,
);
