/**
 * Searchable co-located catalog picker for Neko Chill composers.
 * ADE ModelSelector patterns (search, groups, empty, disabled titles) with --nk-* tokens.
 * Keyboard: ↑↓ · Enter/Tab select · Esc close.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { ChevronDown, Search } from "lucide-react";

export interface ChillCatalogItem {
  id: string;
  label: string;
  group?: string;
  description?: string;
  disabled?: boolean;
  title?: string;
}

export interface ChillCatalogPickerProps {
  items: readonly ChillCatalogItem[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel: string;
  disabled?: boolean;
  pending?: boolean;
  triggerTitle?: string;
  searchPlaceholder?: string;
  emptyLabel?: string;
  icon?: ReactNode;
  testId?: string;
  className?: string;
}

function itemMatches(item: ChillCatalogItem, query: string): boolean {
  if (!query) return true;
  const haystack = [item.id, item.label, item.group, item.description]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase("vi");
  return haystack.includes(query);
}

export function ChillCatalogPicker({
  items,
  value,
  onChange,
  ariaLabel,
  disabled = false,
  pending = false,
  triggerTitle,
  searchPlaceholder = "Tìm…",
  emptyLabel = "Không tìm thấy mục phù hợp.",
  icon,
  testId,
  className = "",
}: ChillCatalogPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const blocked = disabled;

  const filtered = useMemo(
    () => items.filter((item) => itemMatches(item, query.trim().toLocaleLowerCase("vi"))),
    [items, query],
  );

  const selected = items.find((item) => item.id === value);
  const triggerLabel = pending
    ? "Đang đổi…"
    : selected?.label ?? (items.length ? "Chọn…" : "Chưa có mục");

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setHighlight(0);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close();
    };
    // Defer so the opening click does not immediately dismiss the menu (jsdom/RTL).
    const timer = window.setTimeout(() => {
      window.addEventListener("pointerdown", onPointer);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("pointerdown", onPointer);
    };
  }, [close, open]);

  useEffect(() => {
    if (!open) return;
    requestAnimationFrame(() => searchRef.current?.focus());
  }, [open]);

  useEffect(() => {
    setHighlight(0);
  }, [query]);

  const pick = (item: ChillCatalogItem) => {
    if (item.disabled || blocked) return;
    onChange(item.id);
    close();
  };

  const onTriggerKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (blocked) return;
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setOpen(true);
    }
  };

  const onPanelKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (!filtered.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((current) => (current + 1) % filtered.length);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((current) => (current - 1 + filtered.length) % filtered.length);
      return;
    }
    if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      const item = filtered[Math.min(highlight, filtered.length - 1)];
      if (item) pick(item);
    }
  };

  const groups = useMemo(() => {
    const seen = new Set<string>();
    const order: string[] = [];
    for (const item of filtered) {
      const group = item.group ?? "";
      if (!seen.has(group)) {
        seen.add(group);
        order.push(group);
      }
    }
    return order;
  }, [filtered]);

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        className="flex h-8 max-w-[210px] items-center gap-1.5 rounded-md px-1.5 text-[12px] text-[var(--nk-text-2)] transition-colors hover:bg-[var(--nk-overlay)] disabled:cursor-not-allowed disabled:opacity-60"
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-haspopup="listbox"
        disabled={blocked}
        title={triggerTitle ?? selected?.title ?? selected?.description}
        data-testid={testId}
        onClick={() => {
          if (blocked) return;
          setOpen((current) => !current);
          setQuery("");
        }}
        onKeyDown={onTriggerKey}
      >
        {icon}
        <span className="min-w-0 flex-1 truncate text-left">{triggerLabel}</span>
        <ChevronDown aria-hidden="true" className="h-3 w-3 shrink-0 text-[var(--nk-ghost)]" />
      </button>

      {open ? (
        <div
          className="absolute bottom-[calc(100%+4px)] left-0 z-40 w-[min(320px,calc(100vw-2rem))] overflow-hidden rounded-xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] shadow-[0_14px_35px_rgba(0,0,0,0.12)]"
          role="listbox"
          aria-label={ariaLabel}
          data-testid={testId ? `${testId}-menu` : "chill-catalog-picker-menu"}
          onKeyDown={onPanelKey}
        >
          <div className="sticky top-0 z-10 border-b border-[var(--nk-border)] bg-[var(--nk-composer)] p-2">
            <div className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--nk-ghost)]"
              />
              <input
                ref={searchRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={searchPlaceholder}
                className="h-8 w-full rounded-lg border border-[var(--nk-border)] bg-[var(--nk-sidebar)] pl-8 pr-2 text-[12px] text-[var(--nk-text)] outline-none placeholder:text-[var(--nk-ghost)] focus:border-[var(--nk-accent)]"
                aria-label={searchPlaceholder}
              />
            </div>
            <p className="mt-1.5 px-0.5 text-[10px] text-[var(--nk-ghost)]">↑↓ chọn · Enter · Esc</p>
          </div>

          <div className="max-h-[260px] overflow-y-auto p-1.5">
            {filtered.length === 0 ? (
              <p className="px-3 py-5 text-center text-[11.5px] text-[var(--nk-text-3)]">{emptyLabel}</p>
            ) : (
              groups.map((group) => {
                const groupItems = filtered.filter((item) => (item.group ?? "") === group);
                return (
                  <div key={group || "__ungrouped"}>
                    {group ? (
                      <div className="px-2 pb-1 pt-1.5 text-[10px] font-medium uppercase tracking-wide text-[var(--nk-ghost)]">
                        {group}
                      </div>
                    ) : null}
                    {groupItems.map((item) => {
                      const index = filtered.indexOf(item);
                      const active = item.id === value;
                      const highlighted = index === highlight;
                      return (
                        <button
                          key={item.id}
                          type="button"
                          role="option"
                          aria-selected={active}
                          aria-disabled={item.disabled || undefined}
                          disabled={item.disabled}
                          title={item.disabled ? item.title : item.description}
                          className={`flex min-h-9 w-full flex-col rounded-lg px-2.5 py-1.5 text-left ${
                            highlighted ? "bg-[var(--nk-item-active)]" : "hover:bg-[var(--nk-overlay)]"
                          } ${item.disabled ? "cursor-not-allowed opacity-60" : ""} ${
                            active ? "text-[var(--nk-accent)]" : "text-[var(--nk-text)]"
                          }`}
                          onMouseEnter={() => setHighlight(index)}
                          onClick={() => pick(item)}
                        >
                          <span className="truncate text-[12px]">{item.label}</span>
                          {item.description ? (
                            <span className="truncate text-[10.5px] text-[var(--nk-text-3)]">{item.description}</span>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
