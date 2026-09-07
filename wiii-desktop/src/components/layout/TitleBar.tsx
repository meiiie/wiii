import { useEffect, useState, type ReactNode } from "react";
import { useShallow } from "zustand/react/shallow";
import type { Window as TauriWindow } from "@tauri-apps/api/window";
import {
  Minus,
  PanelLeft,
  PanelLeftClose,
  Search,
  Square,
  X,
} from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { APP_NAME } from "@/lib/constants";
import { WiiiMark } from "@/components/common/WiiiMark";

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export interface TitleBarCommandCenter {
  label: string;
  onClick: () => void;
}

interface TitleBarProps {
  browserVisible?: boolean;
  /** Hide Wiii-owned sidebar and command controls on standalone surfaces. */
  minimal?: boolean;
  /** Optional product/mode control. Interactive children never become drag regions. */
  leading?: ReactNode;
  /** `undefined` uses Wiii's palette outside minimal mode; `false` hides it. */
  commandCenter?: TitleBarCommandCenter | false;
  /** Surface-specific controls rendered before the native caption buttons. */
  trailing?: ReactNode;
}

function RestoreIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-3 w-3"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
    >
      <path d="M5.25 5.25h6.5v6.5h-6.5z" />
      <path d="M4.25 10.75h-1V3.25h7.5v1" />
    </svg>
  );
}

function reportWindowFailure(message: string, error: unknown) {
  console.error(`[TitleBar] ${message}`, error);
}

export function TitleBar({
  browserVisible = false,
  minimal = false,
  leading,
  commandCenter,
  trailing,
}: TitleBarProps) {
  const { sidebarOpen, toggleSidebar, toggleCommandPalette } = useUIStore(useShallow((state) => ({
    sidebarOpen: state.sidebarOpen,
    toggleSidebar: state.toggleSidebar,
    toggleCommandPalette: state.toggleCommandPalette,
  })));
  const [appWindow, setAppWindow] = useState<TauriWindow | null>(null);
  const [maximized, setMaximized] = useState(false);
  const [tauri] = useState(isTauri);

  useEffect(() => {
    if (!tauri) return;

    let disposed = false;
    let unlisten: (() => void) | undefined;

    const initialize = async () => {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      const currentWindow = getCurrentWindow();
      if (disposed) return;
      setAppWindow(currentWindow);

      const refreshMaximized = async () => {
        try {
          const value = await currentWindow.isMaximized();
          if (!disposed) setMaximized(value);
        } catch (error) {
          reportWindowFailure("Không thể đọc trạng thái cửa sổ", error);
        }
      };

      await refreshMaximized();
      unlisten = await currentWindow.onResized(() => {
        void refreshMaximized();
      });
    };

    void initialize().catch((error) => {
      reportWindowFailure("Không thể khởi tạo điều khiển cửa sổ", error);
    });

    return () => {
      disposed = true;
      unlisten?.();
    };
  }, [tauri]);

  if (!tauri && !browserVisible) return null;

  const resolvedCommandCenter = commandCenter === undefined && !minimal
    ? {
        label: "Tìm cuộc trò chuyện hoặc chạy lệnh",
        onClick: toggleCommandPalette,
      }
    : commandCenter || null;

  const runWindowAction = async (
    failureMessage: string,
    action: (currentWindow: TauriWindow) => Promise<void>,
    refreshMaximized = false,
  ) => {
    if (!appWindow) return;
    try {
      await action(appWindow);
      if (refreshMaximized) setMaximized(await appWindow.isMaximized());
    } catch (error) {
      reportWindowFailure(failureMessage, error);
    }
  };

  return (
    <div
      className={`wiii-titlebar grid h-11 shrink-0 select-none items-center border-b border-border bg-surface text-text-secondary ${resolvedCommandCenter ? "[grid-template-columns:minmax(max-content,1fr)_minmax(32px,340px)_minmax(max-content,1fr)]" : "[grid-template-columns:auto_minmax(0,1fr)_auto]"}`}
      data-tauri-drag-region={tauri || undefined}
      data-testid="desktop-titlebar"
      onDoubleClick={(event) => {
        if (!(event.target instanceof HTMLElement) || !event.target.hasAttribute("data-tauri-drag-region")) return;
        void runWindowAction(
          maximized ? "Không thể khôi phục cửa sổ" : "Không thể phóng to cửa sổ",
          (currentWindow) => currentWindow.toggleMaximize(),
          true,
        );
      }}
    >
      <div className="flex h-full w-max items-center gap-1.5 px-2 [-webkit-app-region:no-drag]">
        {leading ?? (
          <>
            {!minimal ? (
              <button
                type="button"
                onClick={toggleSidebar}
                className="grid h-8 w-8 place-items-center rounded-md text-text-tertiary transition-colors hover:bg-surface-tertiary hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40"
                title={sidebarOpen ? "Ẩn thanh bên" : "Hiện thanh bên"}
                aria-label={sidebarOpen ? "Ẩn thanh bên" : "Hiện thanh bên"}
                aria-pressed={!sidebarOpen}
              >
                {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
              </button>
            ) : null}
            <WiiiMark className="ml-0.5 shrink-0" size={19} />
            <span className="px-0.5 text-[13px] font-semibold text-text-secondary">
              {APP_NAME}
            </span>
          </>
        )}
      </div>

      <div
        className="flex h-full min-w-0 items-center justify-center px-1 sm:px-3"
        data-tauri-drag-region={tauri || undefined}
        data-testid="titlebar-drag-region"
      >
        {resolvedCommandCenter ? (
          <button
            type="button"
            aria-label={resolvedCommandCenter.label}
            title={`${resolvedCommandCenter.label} (Ctrl+K)`}
            aria-keyshortcuts="Control+K Meta+K"
            onClick={resolvedCommandCenter.onClick}
            className="wiii-titlebar-search flex h-8 min-w-8 w-full items-center justify-center gap-2 rounded-md border border-border bg-surface-secondary px-2 text-[12px] text-text-secondary transition-colors duration-100 hover:border-[var(--border-secondary)] hover:bg-surface-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40 [-webkit-app-region:no-drag] sm:justify-start sm:px-2.5"
          >
            <Search aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
            <span className="hidden min-w-0 truncate sm:block">
              {resolvedCommandCenter.label}
            </span>
            <kbd className="ml-auto hidden shrink-0 rounded border border-border px-1 py-px text-[10px] text-text-tertiary lg:inline">
              Ctrl K
            </kbd>
          </button>
        ) : null}
      </div>

      <div className="flex h-full items-center justify-end" data-tauri-drag-region={tauri || undefined}>
      {trailing ? <div className="flex h-full shrink-0 items-center px-2">{trailing}</div> : null}

      {tauri && (appWindow ? (
        <div className="flex h-full shrink-0 items-stretch" aria-label="Điều khiển cửa sổ">
          <button
            type="button"
            onClick={() => void runWindowAction(
              "Không thể thu nhỏ cửa sổ",
              (currentWindow) => currentWindow.minimize(),
            )}
            className="grid h-11 w-[46px] place-items-center text-text-secondary transition-colors hover:bg-surface-tertiary active:bg-surface-tertiary/70 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--accent)]/50"
            aria-label="Thu nhỏ cửa sổ"
            title="Thu nhỏ"
          >
            <Minus aria-hidden="true" className="h-3.5 w-3.5" strokeWidth={1.5} />
          </button>
          <button
            type="button"
            onClick={() => void runWindowAction(
              maximized ? "Không thể khôi phục cửa sổ" : "Không thể phóng to cửa sổ",
              (currentWindow) => currentWindow.toggleMaximize(),
              true,
            )}
            className="grid h-11 w-[46px] place-items-center text-text-secondary transition-colors hover:bg-surface-tertiary active:bg-surface-tertiary/70 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--accent)]/50"
            aria-label={maximized ? "Khôi phục cửa sổ" : "Phóng to cửa sổ"}
            aria-pressed={maximized}
            title={maximized ? "Khôi phục" : "Phóng to"}
          >
            {maximized ? <RestoreIcon /> : <Square aria-hidden="true" className="h-3 w-3" strokeWidth={1.4} />}
          </button>
          <button
            type="button"
            onClick={() => void runWindowAction(
              "Không thể đóng cửa sổ",
              (currentWindow) => currentWindow.close(),
            )}
            className="grid h-11 w-[48px] place-items-center text-text-secondary transition-colors hover:bg-[#c42b1c] hover:text-white active:bg-[#a92318] active:text-white focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white/80"
            aria-label="Đóng cửa sổ"
            title="Đóng"
          >
            <X aria-hidden="true" className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>
      ) : (
        <div className="h-11 w-[140px] shrink-0" aria-hidden="true" />
      ))}
      </div>
    </div>
  );
}
