import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { Check, X } from "lucide-react";
import { APP_VERSION } from "@/lib/constants";
import { CompletionPreferences } from "./CompletionPreferences";
import { captureTextEditTarget, runTextEdit, type TextEditCommand, type TextEditTarget } from "../text-edit-target";

const MENUS = ["Tệp", "Sửa", "Xem", "Trợ giúp"];
const EDIT_ITEMS: [TextEditCommand, string, string][] = [
  ["undo", "Hoàn tác", "Z"], ["redo", "Làm lại", "Shift+Z"],
  ["cut", "Cắt", "X"], ["copy", "Sao chép", "C"],
  ["paste", "Dán", "V"], ["selectAll", "Chọn tất cả", "A"],
];

interface MenuAction {
  label: string;
  shortcut?: string;
  disabled?: boolean;
  checked?: boolean;
  run: () => void;
}

interface NekoMenuBarProps {
  ready: boolean;
  sidebarOpen: boolean;
  workspaceOpen: boolean;
  workspaceAvailable: boolean;
  onNewSession: () => void;
  onCreateProject: () => void;
  onSearch: () => void;
  onToggleSidebar: () => void;
  onToggleWorkspace: () => void;
  onConnections: () => void;
}

export function NekoMenuBar(props: NekoMenuBarProps) {
  const [open, setOpen] = useState<number | null>(null);
  const [active, setActive] = useState(0);
  const [left, setLeft] = useState(8);
  const [error, setError] = useState<string | null>(null);
  const [help, setHelp] = useState<"shortcuts" | "about" | "notifications" | null>(null);
  const root = useRef<HTMLElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const triggers = useRef<(HTMLButtonElement | null)[]>([]);
  const previousFocus = useRef<HTMLElement | null>(null);
  const editTarget = useRef<TextEditTarget | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const pendingEdit = useRef(false);
  const focusLastItem = useRef(false);
  const modifier = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl+";

  const capture = useCallback(() => {
    if (root.current?.contains(document.activeElement)) return;
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    editTarget.current = captureTextEditTarget(root.current?.closest(".nk-root") ?? null);
  }, []);
  const show = (index: number) => {
    setActive(index);
    setLeft(Math.max(8, Math.min(triggers.current[index]?.getBoundingClientRect().left ?? 8, innerWidth - 288)));
    setOpen(index);
    setError(null);
  };
  const close = useCallback((restore = false) => {
    setOpen(null);
    if (restore && previousFocus.current?.isConnected) previousFocus.current.focus({ preventScroll: true });
    else triggers.current[active]?.focus();
  }, [active]);
  const edit = async (command: TextEditCommand) => {
    if (!editTarget.current || pendingEdit.current) return;
    pendingEdit.current = true;
    setOpen(null);
    try {
      await runTextEdit(command, editTarget.current);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể sửa nội dung. Hãy dùng phím tắt trong ô nhập.");
    } finally {
      pendingEdit.current = false;
    }
  };

  const actions: MenuAction[][] = [
    [
      { label: "Phiên mới", disabled: !props.ready, run: props.onNewSession },
      { label: "Tạo Project…", disabled: !props.ready, run: props.onCreateProject },
      { label: "Tìm Project hoặc phiên…", shortcut: `${modifier}K`, disabled: !props.ready, run: props.onSearch },
      { label: "Tài khoản & ứng dụng…", run: props.onConnections },
      { label: "Thông báo & âm thanh…", run: () => setHelp("notifications") },
    ],
    EDIT_ITEMS.map(([command, label, key]) => ({
      label, shortcut: `${modifier}${key}`, disabled: !editTarget.current?.enabled[command],
      run: () => { void edit(command); },
    })),
    [
      { label: "Tìm kiếm và lệnh…", shortcut: `${modifier}K`, disabled: !props.ready, run: props.onSearch },
      { label: "Thanh bên", shortcut: `${modifier}B`, checked: props.sidebarOpen, run: props.onToggleSidebar },
      { label: "Công cụ dự án", shortcut: `${modifier}Alt+B`, checked: props.workspaceOpen, disabled: !props.workspaceAvailable, run: props.onToggleWorkspace },
    ],
    [
      { label: "Phím tắt", run: () => setHelp("shortcuts") },
      { label: "Giới thiệu Wiii", run: () => setHelp("about") },
    ],
  ];

  useLayoutEffect(() => {
    if (open === null) return;
    const items = popup.current?.querySelectorAll<HTMLElement>('[role^="menuitem"]');
    const index = focusLastItem.current ? (items?.length ?? 1) - 1 : 0;
    items?.[index]?.focus();
    focusLastItem.current = false;
  }, [open]);

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Tab" && !event.defaultPrevented && !event.isComposing) capture();
      if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey
        || event.key !== "F10" || document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return;
      event.preventDefault();
      if (root.current?.contains(document.activeElement)) close(true);
      else { capture(); setActive(0); triggers.current[0]?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [capture, close]);

  useEffect(() => {
    if (open === null) return;
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(null);
    };
    const onBlur = () => setOpen(null);
    window.addEventListener("pointerdown", dismiss);
    window.addEventListener("blur", onBlur);
    window.addEventListener("resize", onBlur);
    return () => {
      window.removeEventListener("pointerdown", dismiss);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("resize", onBlur);
    };
  }, [open]);

  useEffect(() => {
    if (help) dialog.current?.showModal();
  }, [help]);

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.nativeEvent.isComposing || event.defaultPrevented) return;
    const onTrigger = triggers.current.includes(document.activeElement as HTMLButtonElement);
    if (event.key === "Escape") {
      event.preventDefault(); event.stopPropagation(); close(onTrigger);
    } else if (event.key === "Tab") {
      setOpen(null);
      triggers.current[active]?.focus();
    } else if (["ArrowLeft", "ArrowRight"].includes(event.key)) {
      event.preventDefault();
      const next = (active + (event.key === "ArrowRight" ? 1 : -1) + MENUS.length) % MENUS.length;
      setActive(next);
      if (open !== null) show(next);
      else triggers.current[next]?.focus();
    } else if (onTrigger && ["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
      focusLastItem.current = event.key === "ArrowUp";
      event.preventDefault(); show(active);
    } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const items = onTrigger ? triggers.current.filter(Boolean) as HTMLElement[]
        : [...(popup.current?.querySelectorAll<HTMLElement>('[role^="menuitem"]') ?? [])];
      if (!items.length) return;
      const current = items.indexOf(document.activeElement as HTMLElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
        : (current + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      if (onTrigger) setActive(next);
      items[next].focus();
    }
  };

  return (
    <>
      <nav ref={root} role="menubar" aria-label="Menu ứng dụng" className="nk-menubar flex h-full items-center"
        onKeyDown={onKeyDown} onBlur={(event) => {
          if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) setOpen(null);
        }}>
        {MENUS.map((label, index) => (
          <button key={label} ref={(element) => { triggers.current[index] = element; }} type="button" role="menuitem"
            className="nk-menu-trigger nk-chrome-button h-8 rounded-md px-2 text-[12px]"
            tabIndex={index === active ? 0 : -1} aria-haspopup="menu" aria-expanded={open === index}
            aria-controls={open === index ? "wiii-app-menu" : undefined}
            onPointerDown={capture} onFocus={() => setActive(index)}
            onPointerEnter={() => { if (open !== null && open !== index) show(index); }}
            onClick={() => { if (open === index) close(); else show(index); }}>
            {label}
          </button>
        ))}
        {open !== null && (
          <div ref={popup} id="wiii-app-menu" role="menu" aria-label={MENUS[open]}
            className="nk-app-menu nk-chrome-popover fixed top-11 z-[70] max-h-[calc(100dvh-52px)] w-[280px] max-w-[calc(100vw-16px)] overflow-y-auto rounded-lg border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-1 shadow-lg"
            style={{ left }}>
            {actions[open].map((action) => (
              <button key={action.label} type="button" role={action.checked === undefined ? "menuitem" : "menuitemcheckbox"}
                tabIndex={-1} aria-disabled={action.disabled || undefined} aria-checked={action.checked}
                className="nk-menu-action flex min-h-8 w-full items-center gap-2 rounded px-2 text-left text-[12px]"
                onClick={() => {
                  if (action.disabled) return;
                  setOpen(null);
                  triggers.current[active]?.focus();
                  action.run();
                }}>
                <span className="w-3.5 shrink-0">{action.checked && <Check size={14} aria-hidden="true" />}</span>
                <span className="flex-1">{action.label}</span>
                {action.shortcut && <kbd className="text-[10px] text-[var(--nk-text-3)]">{action.shortcut}</kbd>}
              </button>
            ))}
            {open === 1 && <p className="border-t border-[var(--nk-border)] px-3 py-2 text-[11px] leading-4 text-[var(--nk-text-3)]">
              Sửa ô nhập trong Wiii. Trình sửa tệp và Computer dùng phím tắt trong vùng đó.
            </p>}
          </div>
        )}
      </nav>
      {error && <div role="alert" className="fixed left-3 top-14 z-[80] flex max-w-[min(420px,calc(100vw-24px))] gap-3 rounded-lg border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-3 text-[12px] shadow-lg">
        <span>{error}</span><button type="button" aria-label="Đóng thông báo" onClick={() => setError(null)}><X size={16} /></button>
      </div>}
      {help && <dialog ref={dialog} aria-labelledby="wiii-help-title" className="nk-help-dialog w-[420px] max-w-[calc(100vw-32px)] rounded-xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-6 text-[var(--nk-text)] shadow-lg"
        onClose={() => { setHelp(null); triggers.current[help === "notifications" ? 0 : 3]?.focus(); }}>
        <div className="mb-5 flex items-center justify-between"><h2 id="wiii-help-title" className="text-base font-semibold">{help === "shortcuts" ? "Phím tắt Wiii" : help === "notifications" ? "Thông báo & âm thanh" : "Giới thiệu Wiii"}</h2>
          <button type="button" aria-label={help === "notifications" ? "Đóng cài đặt thông báo" : "Đóng trợ giúp"} className="nk-chrome-button grid h-8 w-8 place-items-center rounded-md" onClick={() => dialog.current?.close()}><X size={16} /></button>
        </div>
        {help === "notifications" ? <CompletionPreferences /> : help === "shortcuts" ? <dl className="space-y-3 text-[13px]">
          {[["Tìm kiếm và lệnh", `${modifier}K`], ["Ẩn / hiện thanh bên", `${modifier}B`], ["Ẩn / hiện công cụ", `${modifier}Alt+B`], ["Chọn menu ứng dụng", "F10"], ["Điều hướng menu", "↑ ↓ ← →"], ["Đóng menu đang chọn", "Esc"]].map(([name, keys]) => <div key={name} className="flex justify-between gap-3"><dt>{name}</dt><dd><kbd>{keys}</kbd></dd></div>)}
        </dl> : <div className="space-y-3 text-[13px] leading-6"><p>Wiii — không gian làm việc cùng Neko.</p><p className="text-[var(--nk-text-2)]">Phiên bản mã nguồn: {APP_VERSION}{import.meta.env.DEV ? " · Bản phát triển cục bộ" : ""}</p><p className="text-[var(--nk-text-2)]">Project, phiên làm việc và công cụ trên máy. Wiii Service là kết nối tùy chọn.</p></div>}
      </dialog>}
    </>
  );
}
