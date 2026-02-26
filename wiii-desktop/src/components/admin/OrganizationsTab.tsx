/**
 * Organizations tab — Sprint 179b: "Quản Trị Theo Tổ Chức"
 *
 * Org card grid (list) or detail drill-down (when selectedOrgId is set).
 */
import { Building2, Users } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";
import { OrgDetailView } from "./OrgDetailView";

export function OrganizationsTab() {
  const { organizations, selectedOrgId, selectOrg, loading } = useAdminStore();

  // Drill-down: show detail view
  if (selectedOrgId) {
    return <OrgDetailView />;
  }

  // List view
  return (
    <div className="space-y-4">
      <div>
        <div className="text-sm font-medium text-text">Tổ chức</div>
        <div className="text-xs text-text-tertiary">
          {organizations.length} tổ chức đã đăng ký
        </div>
      </div>

      {organizations.length === 0 && !loading && (
        <div className="text-center text-text-tertiary text-xs py-12">
          Chưa có tổ chức nào. Hãy tạo tổ chức từ API hoặc bật multi-tenant.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {organizations.map((org) => (
          <button
            key={org.id}
            onClick={() => selectOrg(org.id)}
            className="flex items-start gap-3 p-4 rounded-xl border border-border bg-surface-secondary hover:border-[var(--accent)] hover:bg-surface-tertiary transition-colors text-left group"
          >
            <Building2
              size={16}
              className="mt-0.5 text-text-tertiary group-hover:text-[var(--accent)] shrink-0"
            />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-text truncate">
                {org.display_name || org.name}
              </div>
              <div className="text-[11px] text-text-tertiary font-mono truncate">
                {org.name}
              </div>
              <div className="flex items-center gap-2 mt-1.5">
                <Users size={10} className="text-text-tertiary" />
                <span className="text-[10px] text-text-tertiary">
                  {org.member_count} thành viên
                </span>
                <span
                  className={`inline-block w-1.5 h-1.5 rounded-full ${
                    org.is_active ? "bg-green-500" : "bg-gray-400"
                  }`}
                />
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
