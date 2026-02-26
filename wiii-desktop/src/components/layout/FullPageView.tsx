/**
 * FullPageView — Sprint 192: Shared layout for full-page admin/settings views.
 *
 * Section sidebar (220px) + content area pattern.
 * Used by SystemAdminView, OrgAdminView, SettingsView.
 */
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft } from "lucide-react";
import { viewEnter } from "@/lib/animations";
import { useReducedMotion, motionSafe } from "@/hooks/useReducedMotion";

export interface FullPageTab {
  id: string;
  label: string;
  icon: React.ReactNode;
}

interface FullPageViewProps {
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  tabs: FullPageTab[];
  activeTab: string;
  onTabChange: (id: string) => void;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export function FullPageView({
  title,
  subtitle,
  icon,
  tabs,
  activeTab,
  onTabChange,
  onClose,
  children,
  footer,
}: FullPageViewProps) {
  const reduced = useReducedMotion();

  return (
    <div className="flex h-full">
      {/* Section Sidebar */}
      <div className="shrink-0 w-[220px] bg-surface-secondary border-r border-border flex flex-col">
        {/* Header */}
        <div className="px-4 pt-5 pb-4">
          <div className="flex items-center gap-2.5">
            <span className="text-[var(--accent)]">{icon}</span>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-text truncate">{title}</h2>
              {subtitle && (
                <p className="text-xs text-text-tertiary truncate mt-0.5">{subtitle}</p>
              )}
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 space-y-0.5 overflow-y-auto" aria-label={title}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm transition-colors ${
                activeTab === tab.id
                  ? "bg-[var(--accent)]/10 text-[var(--accent)] font-medium border-l-2 border-[var(--accent)] -ml-[2px] pl-[calc(0.75rem+2px)]"
                  : "text-text-secondary hover:bg-surface-tertiary hover:text-text"
              }`}
              aria-current={activeTab === tab.id ? "page" : undefined}
            >
              {tab.icon}
              <span className="truncate">{tab.label}</span>
            </button>
          ))}
        </nav>

        {/* Footer: Back to chat */}
        <div className="p-3 border-t border-border">
          {footer}
          <button
            onClick={onClose}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-text-secondary hover:bg-surface-tertiary hover:text-text transition-colors"
          >
            <ArrowLeft size={14} />
            Quay lại trò chuyện
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            variants={motionSafe(reduced, viewEnter)}
            initial={reduced ? false : "hidden"}
            animate="visible"
            exit={reduced ? undefined : "exit"}
            className="p-6 max-w-7xl"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
