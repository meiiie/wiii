/**
 * OrgManagerDashboard — Sprint 181: Simple stats for org managers.
 *
 * Shows member count, org status, and basic info.
 * No technical jargon — designed for non-IT managers.
 */
import { Users, CheckCircle, ShieldCheck, FileText } from "lucide-react";
import { useOrgAdminStore } from "@/stores/org-admin-store";

export function OrgManagerDashboard() {
  const { orgDetail, members, documents, loading } = useOrgAdminStore();

  if (loading || !orgDetail) {
    return (
      <div className="text-center text-text-tertiary py-12 text-sm">
        Đang tải...
      </div>
    );
  }

  const memberCount = members.length;
  const adminCount = members.filter((m) => m.role === "admin" || m.role === "owner").length;

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Users size={20} />}
          label="Thành viên"
          value={memberCount}
          color="blue"
        />
        <StatCard
          icon={<FileText size={20} />}
          label="Tài liệu"
          value={documents.filter((d) => d.status === "ready").length}
          color="purple"
        />
        <StatCard
          icon={<CheckCircle size={20} />}
          label="Trạng thái"
          value={orgDetail.is_active ? "Hoạt động" : "Tạm dừng"}
          color={orgDetail.is_active ? "green" : "gray"}
        />
        <StatCard
          icon={<ShieldCheck size={20} />}
          label="Quản trị viên"
          value={adminCount}
          color="amber"
        />
      </div>

      {/* Org info */}
      <div className="bg-surface-secondary rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold text-text">Thông tin tổ chức</h3>
        <div className="grid grid-cols-2 gap-y-2 text-sm">
          <span className="text-text-tertiary">Tên</span>
          <span className="text-text">{orgDetail.display_name || orgDetail.name}</span>
          <span className="text-text-tertiary">Mã</span>
          <code className="text-xs text-text-secondary bg-surface-tertiary px-1.5 py-0.5 rounded w-fit">
            {orgDetail.id}
          </code>
          {orgDetail.description && (
            <>
              <span className="text-text-tertiary">Mô tả</span>
              <span className="text-text truncate">{orgDetail.description}</span>
            </>
          )}
          {orgDetail.allowed_domains.length > 0 && (
            <>
              <span className="text-text-tertiary">Lĩnh vực</span>
              <span className="text-text">{orgDetail.allowed_domains.join(", ")}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40",
    green: "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/40",
    amber: "text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40",
    gray: "text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/40",
    purple: "text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40",
  };

  return (
    <div className="bg-surface-secondary rounded-xl p-4 flex items-center gap-3">
      <div className={`p-2.5 rounded-lg ${colorMap[color] || colorMap.blue}`}>
        {icon}
      </div>
      <div>
        <div className="text-xs text-text-tertiary">{label}</div>
        <div className="text-lg font-bold text-text">{value}</div>
      </div>
    </div>
  );
}
