import { useState, useEffect } from "react";
import { Minus, Square, X, PanelLeftClose, PanelLeft } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { APP_NAME } from "@/lib/constants";

/**
 * Check if running inside Tauri webview.
 * Outside Tauri (plain browser), window.__TAURI_INTERNALS__ is undefined.
 */
function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function TitleBar() {
  const { sidebarOpen, toggleSidebar } = useUIStore();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [appWindow, setAppWindow] = useState<any>(null);

  useEffect(() => {
    if (isTauri()) {
      import("@tauri-apps/api/window")
        .then((mod) => setAppWindow(mod.getCurrentWindow()))
        .catch(() => {});
    }
  }, []);

  return (
    <div
      className="flex items-center h-10 bg-surface border-b border-border select-none"
      data-tauri-drag-region
    >
      {/* Left: Toggle sidebar + App name */}
      <div className="flex items-center gap-2 px-3">
        <button
          onClick={toggleSidebar}
          className="p-1 rounded hover:bg-surface-tertiary transition-colors"
          title={sidebarOpen ? "Ẩn sidebar" : "Hiện sidebar"}
        >
          {sidebarOpen ? (
            <PanelLeftClose size={16} className="text-text-secondary" />
          ) : (
            <PanelLeft size={16} className="text-text-secondary" />
          )}
        </button>
        <span
          className="text-sm font-semibold text-text-secondary"
          data-tauri-drag-region
        >
          {APP_NAME}
        </span>
      </div>

      {/* Center: Drag region */}
      <div className="flex-1" data-tauri-drag-region />

      {/* Right: Window controls (only in Tauri) */}
      {appWindow && (
        <div className="flex items-center">
          <button
            onClick={() => appWindow.minimize()}
            className="flex items-center justify-center w-11 h-10 hover:bg-surface-tertiary transition-colors"
          >
            <Minus size={14} className="text-text-secondary" />
          </button>
          <button
            onClick={() => appWindow.toggleMaximize()}
            className="flex items-center justify-center w-11 h-10 hover:bg-surface-tertiary transition-colors"
          >
            <Square size={12} className="text-text-secondary" />
          </button>
          <button
            onClick={() => appWindow.close()}
            className="flex items-center justify-center w-11 h-10 hover:bg-red-500 hover:text-white transition-colors"
          >
            <X size={14} className="text-text-secondary hover:text-white" />
          </button>
        </div>
      )}
    </div>
  );
}
