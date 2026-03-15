/**
 * AppShell — root layout: TitleBar + Sidebar + main + StatusBar.
 * Sprint 106: Disconnected banner above main content.
 * Sprint 107: SourcesPanel side panel.
 * Sprint 192: View routing — chat, system-admin, org-admin, settings.
 */
import { lazy, Suspense, useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { WifiOff, RefreshCw, Menu } from "lucide-react";
import { TitleBar } from "./TitleBar";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";
import { ToastContainer } from "@/components/common/Toast";
import { useUIStore } from "@/stores/ui-store";
import { useConnectionStore } from "@/stores/connection-store";
import { slideDown } from "@/lib/animations";

const ChatView = lazy(async () => {
  const mod = await import("@/components/chat/ChatView");
  return { default: mod.ChatView };
});

const ContextPanel = lazy(async () => {
  const mod = await import("./ContextPanel");
  return { default: mod.ContextPanel };
});

const CharacterPanel = lazy(async () => {
  const mod = await import("./CharacterPanel");
  return { default: mod.CharacterPanel };
});

const SourcesPanel = lazy(async () => {
  const mod = await import("./SourcesPanel");
  return { default: mod.SourcesPanel };
});

const PreviewPanel = lazy(async () => {
  const mod = await import("./PreviewPanel");
  return { default: mod.PreviewPanel };
});

const ArtifactPanel = lazy(async () => {
  const mod = await import("./ArtifactPanel");
  return { default: mod.ArtifactPanel };
});

const SystemAdminView = lazy(async () => {
  const mod = await import("@/components/admin/SystemAdminView");
  return { default: mod.SystemAdminView };
});

const OrgAdminView = lazy(async () => {
  const mod = await import("@/components/org-admin/OrgAdminView");
  return { default: mod.OrgAdminView };
});

const SettingsView = lazy(async () => {
  const mod = await import("@/components/settings/SettingsView");
  return { default: mod.SettingsView };
});

const SoulBridgePanel = lazy(async () => {
  const mod = await import("@/components/soul-bridge/SoulBridgePanel");
  return { default: mod.SoulBridgePanel };
});

function ViewFallback({ label }: { label: string }) {
  return (
    <div className="flex flex-1 items-center justify-center bg-surface px-6 text-sm text-text-tertiary">
      {label}
    </div>
  );
}

export function AppShell() {
  const { sidebarOpen, activeView, setSidebarOpen, toggleSidebar } = useUIStore();
  const { status, checkHealth } = useConnectionStore();

  const showDisconnected = status === "disconnected";

  // Sprint 192b: Hide main sidebar entirely when not in chat view (Claude.ai pattern)
  const isInChat = activeView === "chat";

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }

    const mediaQuery = window.matchMedia("(max-width: 767px)");
    const closeForMobile = (matches: boolean) => {
      if (matches) {
        setSidebarOpen(false);
      }
    };

    closeForMobile(mediaQuery.matches);

    const handleChange = (event: MediaQueryListEvent) => {
      closeForMobile(event.matches);
    };

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }

    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, [setSidebarOpen]);

  return (
    <div className="flex flex-col h-screen">
      <TitleBar />
      <div className="flex flex-1 overflow-hidden">
        <div
          className={`shrink-0 sidebar-slide ${!isInChat ? "sidebar-hidden" : sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}
        >
          <Sidebar />
        </div>
        {/* Sprint 231: Mobile backdrop overlay when sidebar is open */}
        <div
          className={`sidebar-backdrop ${!sidebarOpen || !isInChat ? "hidden" : ""}`}
          onClick={toggleSidebar}
          aria-hidden="true"
        />
        {/* Sprint 231: Mobile menu button (only visible <768px when sidebar closed) */}
        {isInChat && !sidebarOpen && (
          <button
            className="mobile-menu-btn hidden"
            onClick={toggleSidebar}
            aria-label="Menu"
          >
            <Menu size={18} />
          </button>
        )}
        <main className="flex-1 flex flex-col overflow-hidden transition-all duration-200">
          {/* Disconnected banner */}
          <AnimatePresence>
            {showDisconnected && (
              <motion.div
                variants={slideDown}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-950/30 border-b border-red-200 dark:border-red-800 text-sm"
                role="alert"
                aria-live="assertive"
              >
                <WifiOff size={14} className="shrink-0 text-red-500" />
                <span className="flex-1 text-red-700 dark:text-red-300">
                  Mình mất liên lạc với server rồi.
                </span>
                <button
                  onClick={checkHealth}
                  className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"
                >
                  <RefreshCw size={12} />
                  Thử lại nhé
                </button>
              </motion.div>
            )}
          </AnimatePresence>
          {/* Sprint 192: View routing */}
          {/* Sprint 211: SourcesPanel push-aside — chat compresses when panel opens (Claude.ai/ChatGPT pattern) */}
          {activeView === "chat" ? (
            <div className="flex-1 flex overflow-hidden min-h-0">
              <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                <Suspense fallback={<ViewFallback label="Wiii dang mo cuoc tro chuyen..." />}>
                  <ChatView />
                </Suspense>
              </div>
              <Suspense fallback={null}>
                <SourcesPanel />
              </Suspense>
            </div>
          ) : (
            <Suspense fallback={<ViewFallback label="Wiii dang mo khong gian nay..." />}>
              {activeView === "system-admin" && <SystemAdminView />}
              {activeView === "org-admin" && <OrgAdminView />}
              {activeView === "settings" && <SettingsView />}
              {activeView === "soul-bridge" && <SoulBridgePanel />}
            </Suspense>
          )}
        </main>
      </div>
      {/* Side panels — chat-only (fixed overlays for non-push-aside panels) */}
      {activeView === "chat" && (
        <Suspense fallback={null}>
          <ContextPanel />
          <CharacterPanel />
          <PreviewPanel />
          <ArtifactPanel />
        </Suspense>
      )}
      <StatusBar />
      <ToastContainer />
    </div>
  );
}
