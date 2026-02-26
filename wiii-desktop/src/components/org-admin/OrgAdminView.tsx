/**
 * OrgAdminView — Sprint 192: Full-page org admin.
 *
 * Replaces OrgManagerPanel modal. Reuses all existing tab components
 * inside the FullPageView layout.
 */
import { useEffect } from "react";
import { LayoutDashboard, Users, BarChart3, Settings, BookOpen, Building2 } from "lucide-react";
import { useUIStore } from "@/stores/ui-store";
import { useOrgAdminStore } from "@/stores/org-admin-store";
import type { OrgManagerTab } from "@/stores/org-admin-store";
import { FullPageView } from "@/components/layout/FullPageView";
import type { FullPageTab } from "@/components/layout/FullPageView";
import { OrgManagerDashboard } from "./OrgManagerDashboard";
import { OrgManagerMembers } from "./OrgManagerMembers";
import { OrgManagerSettings } from "./OrgManagerSettings";
import { OrgManagerKnowledge } from "./OrgManagerKnowledge";

const TABS: (FullPageTab & { id: OrgManagerTab })[] = [
  { id: "dashboard", label: "Tổng quan", icon: <LayoutDashboard size={16} /> },
  { id: "members", label: "Thành viên", icon: <Users size={16} /> },
  { id: "analytics", label: "Hoạt động", icon: <BarChart3 size={16} /> },
  { id: "settings", label: "Cài đặt", icon: <Settings size={16} /> },
  { id: "knowledge", label: "Tri thức", icon: <BookOpen size={16} /> },
];

export function OrgAdminView() {
  const { navigateToChat, orgManagerTargetOrgId } = useUIStore();
  const { activeTab, setActiveTab, fetchOrgDetail, fetchMembers, fetchDocuments, orgDetail, reset } = useOrgAdminStore();
  const toast = useOrgAdminStore((s) => s.toast);

  useEffect(() => {
    if (orgManagerTargetOrgId) {
      fetchOrgDetail(orgManagerTargetOrgId);
      fetchMembers(orgManagerTargetOrgId);
      fetchDocuments(orgManagerTargetOrgId);
    }
  }, [orgManagerTargetOrgId, fetchOrgDetail, fetchMembers, fetchDocuments]);

  useEffect(() => {
    return () => reset();
  }, [reset]);

  const orgName = orgDetail?.display_name || orgDetail?.name || orgManagerTargetOrgId || "";

  return (
    <>
      <FullPageView
        title="Quản lý tổ chức"
        subtitle={orgName}
        icon={<Building2 size={20} />}
        tabs={TABS}
        activeTab={activeTab}
        onTabChange={(id) => setActiveTab(id as OrgManagerTab)}
        onClose={navigateToChat}
      >
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
      </FullPageView>
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
    </>
  );
}
