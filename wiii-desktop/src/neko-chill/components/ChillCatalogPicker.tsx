/** Searchable catalog: arrows explore, Enter commits, Tab leaves unchanged. */
import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Check, ChevronDown, LoaderCircle, Search, X } from "lucide-react";

export interface ChillCatalogItem {
  id: string; label: string; group?: string; description?: string; disabled?: boolean; title?: string;
}
export interface ChillCatalogPickerProps {
  items: readonly ChillCatalogItem[]; value: string; onChange: (id: string) => void; ariaLabel: string;
  disabled?: boolean; pending?: boolean; triggerTitle?: string; searchPlaceholder?: string;
  emptyLabel?: string; icon?: ReactNode; testId?: string; className?: string;
}
function itemMatches(item: ChillCatalogItem, query: string): boolean {
  return !query || [item.id, item.label, item.group, item.description].filter(Boolean).join(" ").toLocaleLowerCase("vi").includes(query);
}
export function ChillCatalogPicker({ items, value, onChange, ariaLabel, disabled = false, pending = false,
  triggerTitle, searchPlaceholder = "Tìm…", emptyLabel = "Không tìm thấy mục phù hợp.", icon, testId, className = "",
}: ChillCatalogPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [placement, setPlacement] = useState({ left: 0, width: 320, height: 340, below: false });
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef(new Map<string, HTMLButtonElement>());
  const listId = useId();
  // Loading feedback is distinct from admission: callers may allow an alternative while discovery runs.
  const blocked = disabled;
  const visible = open && !blocked;
  const filtered = useMemo(() => {
    const groups = new Map<string, ChillCatalogItem[]>();
    for (const item of items.filter(item => itemMatches(item, query.trim().toLocaleLowerCase("vi")))) {
      const key = item.group ?? "";
      const group = groups.get(key) ?? [];
      group.push(item); groups.set(key, group);
    }
    return [...groups.values()].flat();
  }, [items, query]);
  const enabled = useMemo(() => filtered.filter(item => !item.disabled), [filtered]);
  const selected = items.find(item => item.id === value);
  const activeId = enabled.some(item => item.id === highlightId) ? highlightId
    : enabled.find(item => item.id === value)?.id ?? enabled[0]?.id ?? null;
  const optionId = (id: string) => `${listId}-${items.findIndex(item => item.id === id)}`;
  const close = useCallback(() => { setOpen(false); setQuery(""); setHighlightId(null); }, []);

  useEffect(() => { if (blocked) close(); }, [blocked, close]);
  useLayoutEffect(() => {
    if (!visible) return;
    const place = () => {
      const rect = rootRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(320, Math.max(0, window.innerWidth - 24));
      const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)) - rect.left;
      const above = rect.top - 12;
      const below = window.innerHeight - rect.bottom - 12;
      const useBelow = above < 200 && below > above;
      setPlacement({ left, width, height: Math.max(80, Math.min(340, (useBelow ? below : above) - 4)), below: useBelow });
    };
    place(); searchRef.current?.focus();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [visible]);
  useEffect(() => {
    if (!visible) return;
    const outside = (event: PointerEvent) => { if (!rootRef.current?.contains(event.target as Node)) close(); };
    window.addEventListener("pointerdown", outside);
    return () => window.removeEventListener("pointerdown", outside);
  }, [visible, close]);
  useEffect(() => {
    if (visible && activeId) optionRefs.current.get(activeId)?.scrollIntoView?.({ block: "nearest" });
  }, [visible, activeId]);

  function pick(item: ChillCatalogItem) {
    if (item.disabled || blocked) return;
    close(); triggerRef.current?.focus();
    onChange(item.id);
  }
  function onPanelKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (event.key === "Escape") {
      event.preventDefault(); event.stopPropagation(); close(); triggerRef.current?.focus(); return;
    }
    if (event.key === "Tab") {
      // Restore the trigger before native traversal: the next control receives focus.
      close(); triggerRef.current?.focus(); return;
    }
    if (!enabled.length) return;
    const index = enabled.findIndex(item => item.id === activeId);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? enabled.length - 1
        : (index + (event.key === "ArrowDown" ? 1 : -1) + enabled.length) % enabled.length;
      setHighlightId(enabled[next].id); return;
    }
    if (event.key === "Enter") { event.preventDefault(); const item = enabled[index]; if (item) pick(item); }
  }
  const groups = [...new Set(filtered.map(item => item.group ?? ""))];
  return <div ref={rootRef} className={`relative ${className}`} onBlur={event => {
    if (visible && !event.currentTarget.contains(event.relatedTarget as Node | null)) close();
  }}>
    <button ref={triggerRef} type="button" className="flex h-8 w-full max-w-[210px] items-center gap-1.5 rounded-md px-1.5 text-[12px] text-[var(--nk-text-2)] transition-colors hover:bg-[var(--nk-overlay)] disabled:cursor-not-allowed disabled:opacity-60"
      aria-label={ariaLabel} aria-expanded={visible} aria-haspopup="listbox" aria-controls={visible ? listId : undefined} aria-busy={pending}
      disabled={blocked} title={triggerTitle ?? selected?.title ?? selected?.description} data-testid={testId}
      onClick={() => { if (!blocked) { setOpen(current => !current); setQuery(""); setHighlightId(null); } }}
      onKeyDown={event => {
        if (blocked || event.nativeEvent.isComposing || event.keyCode === 229) return;
        if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) { event.preventDefault(); setOpen(true); }
      }}>
      {pending ? <LoaderCircle size={14} aria-hidden="true" className="animate-spin motion-reduce:animate-none" /> : icon}
      <span className="min-w-0 flex-1 truncate text-left">{pending ? "Đang đổi…" : selected?.label ?? (items.length ? "Chọn…" : "Chưa có mục")}</span>
      <ChevronDown aria-hidden="true" className={`h-3 w-3 shrink-0 text-[var(--nk-ghost)] transition-transform motion-reduce:transition-none ${visible ? "rotate-180" : ""}`} />
    </button>
    {visible && <div className="nk-catalog-popover absolute z-40 flex flex-col overflow-hidden rounded-xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] shadow-[0_14px_35px_rgba(0,0,0,0.12)]"
      style={{ left: placement.left, width: placement.width, maxHeight: placement.height, ...(placement.below ? { top: "calc(100% + 4px)" } : { bottom: "calc(100% + 4px)" }) }}
      data-testid={testId ? `${testId}-menu` : "chill-catalog-picker-menu"} onKeyDown={onPanelKey}>
      <div className="shrink-0 border-b border-[var(--nk-border)] p-2">
        <div className="relative">
          <Search aria-hidden="true" className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--nk-ghost)]" />
          <input ref={searchRef} role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls={listId}
            aria-activedescendant={activeId ? optionId(activeId) : undefined} value={query}
            onChange={event => { setQuery(event.target.value); setHighlightId(null); }} placeholder={searchPlaceholder} aria-label={searchPlaceholder}
            className="h-8 w-full rounded-lg border border-[var(--nk-border)] bg-[var(--nk-sidebar)] pl-8 pr-8 text-[12px] text-[var(--nk-text)] outline-none placeholder:text-[var(--nk-ghost)] focus:border-[var(--nk-accent)]" />
          {query && <button type="button" tabIndex={-1} aria-label="Xóa bộ lọc" title="Xóa bộ lọc" onMouseDown={event => event.preventDefault()}
            onClick={() => { setQuery(""); setHighlightId(null); searchRef.current?.focus(); }} className="absolute right-0 top-0 grid h-8 w-8 place-items-center text-[var(--nk-text-2)]"><X size={13} aria-hidden="true" /></button>}
        </div>
        <p className="mt-1.5 px-0.5 text-[10px] text-[var(--nk-ghost)]">↑↓ chọn · Enter xác nhận · Esc đóng</p>
      </div>
      <div id={listId} role="listbox" aria-label={ariaLabel} className="min-h-0 overflow-y-auto overscroll-contain p-1.5">
        {filtered.length === 0 ? <p role="status" className="px-3 py-5 text-center text-[11.5px] text-[var(--nk-text-3)]">{emptyLabel}</p> : groups.map(group => <div key={group || "__ungrouped"}>
          {group && <div className="px-2 pb-1 pt-1.5 text-[10px] font-medium uppercase tracking-wide text-[var(--nk-ghost)]">{group}</div>}
          {filtered.filter(item => (item.group ?? "") === group).map(item => <button key={item.id} id={optionId(item.id)}
            ref={node => { if (node) optionRefs.current.set(item.id, node); else optionRefs.current.delete(item.id); }}
            type="button" role="option" tabIndex={-1} aria-selected={item.id === value} aria-disabled={item.disabled || undefined} disabled={item.disabled}
            title={item.disabled ? item.title : item.description} onMouseDown={event => event.preventDefault()}
            className={`flex min-h-9 w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left ${activeId === item.id ? "bg-[var(--nk-item-active)]" : "hover:bg-[var(--nk-overlay)]"} ${item.disabled ? "cursor-not-allowed opacity-60" : ""}`}
            onMouseEnter={() => { if (!item.disabled) setHighlightId(item.id); }} onClick={() => pick(item)}>
            <span className="min-w-0 flex-1"><span className="block truncate text-[12px]">{item.label}</span>{item.description && <span className="block truncate text-[10.5px] text-[var(--nk-text-3)]">{item.description}</span>}</span>
            {item.id === value && <Check size={14} aria-hidden="true" className="shrink-0 text-[var(--nk-accent)]" />}
          </button>)}
        </div>)}
      </div>
    </div>}
  </div>;
}
