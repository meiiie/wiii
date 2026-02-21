/**
 * AppShell — root layout: TitleBar + Sidebar + main + StatusBar.
 * Sprint 106: Disconnected banner above main content.
 * Sprint 107: SourcesPanel side panel.
 */
import { AnimatePresence, motion } from "motion/react";
import { WifiOff, RefreshCw } from "lucide-react";
import { TitleBar } from "./TitleBar";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";
import { ContextPanel } from "./ContextPanel";
import { CharacterPanel } from "./CharacterPanel";
import { SourcesPanel } from "./SourcesPanel";
import { ToastContainer } from "@/components/common/Toast";
import { useUIStore } from "@/stores/ui-store";
import { useConnectionStore } from "@/stores/connection-store";
import { slideDown } from "@/lib/animations";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { sidebarOpen } = useUIStore();
  const { status, checkHealth } = useConnectionStore();

  const showDisconnected = status === "disconnected";

  return (
    <div className="flex flex-col h-screen">
      <TitleBar />
      <div className="flex flex-1 overflow-hidden">
        <div
          className={`shrink-0 sidebar-slide ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}
        >
          <Sidebar />
        </div>
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
          {children}
        </main>
      </div>
      <ContextPanel />
      <CharacterPanel />
      <SourcesPanel />
      <StatusBar />
      <ToastContainer />
    </div>
  );
}
