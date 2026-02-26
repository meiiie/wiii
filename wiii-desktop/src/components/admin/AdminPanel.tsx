/**
 * Admin Panel — Sprint 179: "Quản Trị Toàn Diện"
 *
 * Full-screen overlay with 6 tabs: Dashboard, Users, Feature Flags,
 * Analytics, Audit Logs, GDPR.
 */
import { useEffect, useRef } from "react";
import {
  X,
  LayoutDashboard,
  Users,
  Building2,
  Flag,
  BarChart3,
  ScrollText,
  Shield,
} from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useAdminStore } from "@/stores/admin-store";
import type { AdminTab } from "@/stores/admin-store";
import { DashboardTab } from "./DashboardTab";
import { UsersTab } from "./UsersTab";
import { OrganizationsTab } from "./OrganizationsTab";
import { FeatureFlagsTab } from "./FeatureFlagsTab";
import { AnalyticsTab } from "./AnalyticsTab";
import { AuditLogsTab } from "./AuditLogsTab";
import { GdprTab } from "./GdprTab";
import { AdminToast } from "./AdminToast";

const TABS: { id: AdminTab; label: string; icon: React.ReactNode }[] = [
  { id: "dashboard", label: "Tổng quan", icon: <LayoutDashboard size={16} /> },
  { id: "users", label: "Người dùng", icon: <Users size={16} /> },
  { id: "organizations", label: "Tổ chức", icon: <Building2 size={16} /> },
  { id: "flags", label: "Feature Flags", icon: <Flag size={16} /> },
  { id: "analytics", label: "Phân tích", icon: <BarChart3 size={16} /> },
  { id: "audit", label: "Nhật ký", icon: <ScrollText size={16} /> },
  { id: "gdpr", label: "GDPR", icon: <Shield size={16} /> },
];

export function AdminPanel() {
  const { closeAdminPanel } = useUIStore();
  const { activeTab, setActiveTab, fetchDashboard } = useAdminStore();
  const dialogRef = useRef<HTMLDivElement>(null);

  // Fetch dashboard on mount
  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Focus trap + Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeAdminPanel();
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
  }, [closeAdminPanel]);

  // Auto-focus on mount
  useEffect(() => {
    if (dialogRef.current) {
      const firstFocusable = dialogRef.current.querySelector<HTMLElement>(
        'button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      firstFocusable?.focus();
    }
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-panel-title"
    >
      <div
        ref={dialogRef}
        className="bg-surface rounded-2xl shadow-2xl w-[95%] max-w-5xl mx-4 max-h-[95vh] flex flex-col border border-border animate-scale-in"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2.5">
            <Shield size={20} className="text-[var(--accent)]" />
            <h2
              id="admin-panel-title"
              className="text-lg font-semibold text-text"
            >
              Quản trị hệ thống
            </h2>
          </div>
          <button
            onClick={closeAdminPanel}
            className="p-1.5 rounded-lg hover:bg-surface-tertiary transition-colors text-text-secondary"
            aria-label="Đóng bảng quản trị"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border px-5 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
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
        <div className="flex-1 overflow-y-auto p-5">
          {activeTab === "dashboard" && <DashboardTab />}
          {activeTab === "users" && <UsersTab />}
          {activeTab === "organizations" && <OrganizationsTab />}
          {activeTab === "flags" && <FeatureFlagsTab />}
          {activeTab === "analytics" && <AnalyticsTab />}
          {activeTab === "audit" && <AuditLogsTab />}
          {activeTab === "gdpr" && <GdprTab />}
        </div>
      </div>
      <AdminToast />
    </div>
  );
}
