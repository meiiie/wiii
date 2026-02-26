/**
 * OrgManagerPanel — Sprint 181: "Hai Tầng Quyền Lực"
 *
 * Simplified admin panel for org admins/owners (non-IT managers).
 * 4 tabs: Dashboard, Members, Analytics, Settings
 * Separated from AdminPanel (7 tabs, system admin only).
 */
import { useEffect, useRef } from "react";
import { X, Building2, LayoutDashboard, Users, BarChart3, Settings, BookOpen } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useOrgAdminStore } from "@/stores/org-admin-store";
import type { OrgManagerTab } from "@/stores/org-admin-store";
import { OrgManagerDashboard } from "./OrgManagerDashboard";
import { OrgManagerMembers } from "./OrgManagerMembers";
import { OrgManagerSettings } from "./OrgManagerSettings";
import { OrgManagerKnowledge } from "./OrgManagerKnowledge";

const TABS: { id: OrgManagerTab; label: string; icon: React.ReactNode }[] = [
  { id: "dashboard", label: "Tổng quan", icon: <LayoutDashboard size={16} /> },
  { id: "members", label: "Thành viên", icon: <Users size={16} /> },
  { id: "analytics", label: "Hoạt động", icon: <BarChart3 size={16} /> },
  { id: "settings", label: "Cài đặt", icon: <Settings size={16} /> },
  { id: "knowledge", label: "Tri thức", icon: <BookOpen size={16} /> },
];

export function OrgManagerPanel() {
  const { closeOrgManagerPanel, orgManagerTargetOrgId } = useUIStore();
  const { activeTab, setActiveTab, fetchOrgDetail, fetchMembers, fetchDocuments, orgDetail, reset } = useOrgAdminStore();
  const dialogRef = useRef<HTMLDivElement>(null);
  const toast = useOrgAdminStore((s) => s.toast);

  // Fetch org detail on mount
  useEffect(() => {
    if (orgManagerTargetOrgId) {
      fetchOrgDetail(orgManagerTargetOrgId);
      fetchMembers(orgManagerTargetOrgId);
      fetchDocuments(orgManagerTargetOrgId);
    }
  }, [orgManagerTargetOrgId, fetchOrgDetail, fetchMembers, fetchDocuments]);

  // Reset store on unmount (prevent stale data flash)
  useEffect(() => {
    return () => reset();
  }, [reset]);

  // Focus trap + Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeOrgManagerPanel();
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeOrgManagerPanel]);

  // Auto-focus on mount + restore focus on unmount
  const previousFocusRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    if (dialogRef.current) {
      const firstFocusable = dialogRef.current.querySelector<HTMLElement>(
        'button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      firstFocusable?.focus();
    }
    return () => {
      previousFocusRef.current?.focus();
    };
  }, []);

  const orgName = orgDetail?.display_name || orgDetail?.name || orgManagerTargetOrgId || "";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="org-manager-panel-title"
      onClick={closeOrgManagerPanel}
    >
      <div
        ref={dialogRef}
        className="bg-surface rounded-2xl shadow-2xl w-[95%] max-w-4xl mx-4 max-h-[95vh] flex flex-col border border-border animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2.5">
            <Building2 size={20} className="text-[var(--accent)]" />
            <h2
              id="org-manager-panel-title"
              className="text-lg font-semibold text-text"
            >
              Quản lý tổ chức: {orgName}
            </h2>
          </div>
          <button
            onClick={closeOrgManagerPanel}
            className="p-1.5 rounded-lg hover:bg-surface-tertiary transition-colors text-text-secondary"
            aria-label="Đóng bảng quản lý"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border px-5 overflow-x-auto" role="tablist" aria-label="Các tab quản lý tổ chức">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              id={`org-tab-${tab.id}`}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`org-tabpanel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-transparent text-text-secondary hover:text-text"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5" role="tabpanel" id={`org-tabpanel-${activeTab}`} aria-labelledby={`org-tab-${activeTab}`}>
          {activeTab === "dashboard" && <OrgManagerDashboard />}
          {activeTab === "members" && orgManagerTargetOrgId && (
            <OrgManagerMembers orgId={orgManagerTargetOrgId} />
          )}
          {activeTab === "analytics" && (
            <div className="text-center text-text-tertiary py-12 text-sm">
              Tính năng phân tích hoạt động sẽ sớm ra mắt.
            </div>
          )}
          {activeTab === "settings" && orgManagerTargetOrgId && (
            <OrgManagerSettings orgId={orgManagerTargetOrgId} />
          )}
          {activeTab === "knowledge" && orgManagerTargetOrgId && (
            <OrgManagerKnowledge orgId={orgManagerTargetOrgId} />
          )}
        </div>
      </div>

      {/* Reuse admin toast for feedback */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[80] animate-fade-in">
          <div
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-lg border text-sm font-medium ${
              toast.type === "success"
                ? "bg-green-50 dark:bg-green-950/60 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300"
                : "bg-red-50 dark:bg-red-950/60 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300"
            }`}
            role="status"
            aria-live="polite"
          >
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
}
