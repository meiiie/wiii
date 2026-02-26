/**
 * OrgDetailView — Sprint 179b: "Quản Trị Theo Tổ Chức"
 * Sprint 180: Add/remove members in Members sub-tab
 *
 * Drill-down view for a single organization with 5 sub-tabs:
 * Overview / Members / Feature Flags / Analytics / Settings
 */
import { useEffect, useState } from "react";
import { ArrowLeft, Users, Flag, BarChart3, Settings, Info, Trash2, Plus } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";
import type { OrgSubView } from "@/stores/admin-store";
import { OrgFlagsSection } from "./OrgFlagsSection";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";

const SUB_TABS: { id: OrgSubView; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Tổng quan", icon: <Info size={14} /> },
  { id: "members", label: "Thành viên", icon: <Users size={14} /> },
  { id: "flags", label: "Feature Flags", icon: <Flag size={14} /> },
  { id: "analytics", label: "Phân tích", icon: <BarChart3 size={14} /> },
  { id: "settings", label: "Cài đặt", icon: <Settings size={14} /> },
];

export function OrgDetailView() {
  const {
    selectedOrgId,
    selectedOrgDetail,
    selectedOrgMembers,
    orgAnalytics,
    orgLlmUsage,
    orgSubView,
    loading,
    selectOrg,
    fetchOrgDetail,
    fetchOrgMembers,
    fetchOrgFeatureFlags,
    fetchOrgAnalytics,
    fetchOrgLlmUsage,
    setOrgSubView,
  } = useAdminStore();

  // Fetch detail on mount
  useEffect(() => {
    if (selectedOrgId) {
      fetchOrgDetail(selectedOrgId);
    }
  }, [selectedOrgId, fetchOrgDetail]);

  // Fetch sub-tab data on sub-tab change
  useEffect(() => {
    if (!selectedOrgId) return;
    if (orgSubView === "members") fetchOrgMembers(selectedOrgId);
    if (orgSubView === "flags") fetchOrgFeatureFlags(selectedOrgId);
    if (orgSubView === "analytics") {
      fetchOrgAnalytics(selectedOrgId);
      fetchOrgLlmUsage(selectedOrgId);
    }
  }, [selectedOrgId, orgSubView, fetchOrgMembers, fetchOrgFeatureFlags, fetchOrgAnalytics, fetchOrgLlmUsage]);

  const detail = selectedOrgDetail;

  return (
    <div className="space-y-4">
      {/* Back button + header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => selectOrg(null)}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-[var(--accent)] transition-colors"
        >
          <ArrowLeft size={14} />
          Danh sách tổ chức
        </button>
      </div>

      {detail && (
        <div className="flex items-center gap-3">
          <div>
            <h3 className="text-base font-semibold text-text">
              {detail.display_name || detail.name}
            </h3>
            <div className="flex items-center gap-2 mt-0.5">
              <code className="text-[11px] text-text-tertiary bg-surface-tertiary px-1.5 py-0.5 rounded">
                {detail.name}
              </code>
              <span
                className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                  detail.is_active
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                }`}
              >
                {detail.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-1 p-1 bg-surface-tertiary rounded-lg w-fit">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setOrgSubView(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              orgSubView === tab.id
                ? "bg-surface text-[var(--accent)] shadow-sm"
                : "text-text-secondary hover:text-text"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sub-tab content */}
      <div className="min-h-[200px]">
        {orgSubView === "overview" && detail && (
          <OverviewSection detail={detail} />
        )}
        {orgSubView === "members" && selectedOrgId && (
          <MembersSection
            orgId={selectedOrgId}
            members={selectedOrgMembers}
            loading={loading}
          />
        )}
        {orgSubView === "flags" && selectedOrgId && (
          <OrgFlagsSection orgId={selectedOrgId} />
        )}
        {orgSubView === "analytics" && (
          <AnalyticsSection
            analytics={orgAnalytics}
            llmUsage={orgLlmUsage}
            loading={loading}
          />
        )}
        {orgSubView === "settings" && detail && (
          <SettingsSection detail={detail} />
        )}
      </div>
    </div>
  );
}

// --- Sub-sections ---

function OverviewSection({ detail }: { detail: NonNullable<ReturnType<typeof useAdminStore.getState>["selectedOrgDetail"]> }) {
  const fields = [
    { label: "ID", value: detail.id },
    { label: "Tên", value: detail.name },
    { label: "Tên hiển thị", value: detail.display_name ?? "\u2014" },
    { label: "Mô tả", value: detail.description ?? "\u2014" },
    { label: "Domain mặc định", value: detail.default_domain ?? "\u2014" },
    { label: "Ngày tạo", value: detail.created_at ?? "\u2014" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {fields.map((f) => (
          <div key={f.label} className="px-4 py-3 rounded-lg border border-border bg-surface-secondary">
            <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">{f.label}</div>
            <div className="text-sm text-text break-all">{f.value}</div>
          </div>
        ))}
      </div>
      {detail.allowed_domains && detail.allowed_domains.length > 0 && (
        <div className="px-4 py-3 rounded-lg border border-border bg-surface-secondary">
          <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-2">Domains được phép</div>
          <div className="flex flex-wrap gap-1.5">
            {detail.allowed_domains.map((d) => (
              <span key={d} className="text-xs px-2 py-0.5 rounded-full bg-[var(--accent-light)] text-[var(--accent)]">
                {d}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MembersSection({ orgId, members, loading }: {
  orgId: string;
  members: ReturnType<typeof useAdminStore.getState>["selectedOrgMembers"];
  loading: boolean;
}) {
  const { addOrgMember, removeOrgMember } = useAdminStore();
  const [showAddForm, setShowAddForm] = useState(false);
  const [newUserId, setNewUserId] = useState("");
  const [newRole, setNewRole] = useState("student");
  const [removingMember, setRemovingMember] = useState<{ userId: string } | null>(null);

  const handleAdd = async () => {
    if (!newUserId.trim()) return;
    await addOrgMember(orgId, newUserId.trim(), newRole);
    setNewUserId("");
    setNewRole("student");
    setShowAddForm(false);
  };

  const handleConfirmRemove = async () => {
    if (!removingMember) return;
    await removeOrgMember(orgId, removingMember.userId);
    setRemovingMember(null);
  };

  return (
    <div className="space-y-3">
      {/* Add member button / form */}
      <div>
        {!showAddForm ? (
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-dashed border-border text-sm text-text-secondary hover:text-[var(--accent)] hover:border-[var(--accent)] transition-colors"
          >
            <Plus size={14} />
            Thêm thành viên
          </button>
        ) : (
          <div className="flex items-center gap-2 p-3 rounded-lg border border-border bg-surface-secondary">
            <input
              type="text"
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
              placeholder="User ID..."
              className="flex-1 px-3 py-1.5 rounded-lg border border-border bg-surface text-text text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              aria-label="User ID cần thêm"
            />
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-surface text-text text-sm focus:outline-none"
              aria-label="Vai trò"
            >
              <option value="student">Sinh viên</option>
              <option value="teacher">Giảng viên</option>
              <option value="admin">Quản trị</option>
            </select>
            <button
              onClick={handleAdd}
              disabled={!newUserId.trim()}
              className="px-3 py-1.5 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] disabled:opacity-40 transition-colors"
            >
              Thêm
            </button>
            <button
              onClick={() => { setShowAddForm(false); setNewUserId(""); }}
              className="px-3 py-1.5 rounded-lg border border-border text-sm text-text-secondary hover:bg-surface-tertiary transition-colors"
            >
              Huỷ
            </button>
          </div>
        )}
      </div>

      {loading && (
        <div className="text-center text-text-tertiary text-xs py-8">Đang tải...</div>
      )}

      {!loading && members.length === 0 && (
        <div className="text-center text-text-tertiary text-xs py-8">Chưa có thành viên nào</div>
      )}

      {!loading && members.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-tertiary text-text-tertiary text-[11px] uppercase tracking-wide">
                <th className="text-left px-4 py-2.5">User ID</th>
                <th className="text-left px-4 py-2.5">Vai trò</th>
                <th className="text-left px-4 py-2.5">Ngày tham gia</th>
                <th className="text-right px-4 py-2.5 w-[60px]"></th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.user_id} className="border-t border-border group">
                  <td className="px-4 py-2.5 text-text font-mono text-xs truncate max-w-[200px]">
                    {m.user_id}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                      m.role === "admin"
                        ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                        : m.role === "teacher"
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                        : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                    }`}>
                      {m.role}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-text-tertiary text-xs">
                    {m.joined_at ? new Date(m.joined_at).toLocaleDateString("vi-VN") : "\u2014"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => setRemovingMember({ userId: m.user_id })}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-600 transition-all"
                      title="Xoá thành viên"
                      aria-label={`Xoá thành viên ${m.user_id}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Confirm dialog for remove */}
      <ConfirmDialog
        open={!!removingMember}
        title="Xoá thành viên"
        message={`Bạn có chắc chắn muốn xoá thành viên "${removingMember?.userId}" khỏi tổ chức?`}
        confirmLabel="Xoá"
        variant="danger"
        onConfirm={handleConfirmRemove}
        onCancel={() => setRemovingMember(null)}
      />
    </div>
  );
}

function AnalyticsSection({ analytics, llmUsage, loading }: {
  analytics: ReturnType<typeof useAdminStore.getState>["orgAnalytics"];
  llmUsage: ReturnType<typeof useAdminStore.getState>["orgLlmUsage"];
  loading: boolean;
}) {
  if (loading) {
    return <div className="text-center text-text-tertiary text-xs py-8">Đang tải...</div>;
  }

  return (
    <div className="space-y-4">
      {analytics && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div className="p-4 rounded-xl border border-border bg-surface-secondary">
            <div className="text-[10px] text-text-tertiary uppercase mb-1">DAU (trung bình)</div>
            <div className="text-xl font-semibold text-text">
              {analytics.daily_active_users.length > 0
                ? Math.round(analytics.daily_active_users.reduce((a, b) => a + b.count, 0) / analytics.daily_active_users.length)
                : 0}
            </div>
          </div>
          <div className="p-4 rounded-xl border border-border bg-surface-secondary">
            <div className="text-[10px] text-text-tertiary uppercase mb-1">Chat sessions</div>
            <div className="text-xl font-semibold text-text">
              {analytics.chat_volume.reduce((a, b) => a + b.sessions, 0)}
            </div>
          </div>
          <div className="p-4 rounded-xl border border-border bg-surface-secondary">
            <div className="text-[10px] text-text-tertiary uppercase mb-1">Messages</div>
            <div className="text-xl font-semibold text-text">
              {analytics.chat_volume.reduce((a, b) => a + b.messages, 0)}
            </div>
          </div>
        </div>
      )}
      {llmUsage && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div className="p-4 rounded-xl border border-border bg-surface-secondary">
            <div className="text-[10px] text-text-tertiary uppercase mb-1">Tokens</div>
            <div className="text-xl font-semibold text-text">
              {llmUsage.total_tokens >= 1000
                ? `${(llmUsage.total_tokens / 1000).toFixed(1)}k`
                : llmUsage.total_tokens}
            </div>
          </div>
          <div className="p-4 rounded-xl border border-border bg-surface-secondary">
            <div className="text-[10px] text-text-tertiary uppercase mb-1">Chi phí</div>
            <div className="text-xl font-semibold text-text">
              ${llmUsage.total_cost_usd.toFixed(2)}
            </div>
          </div>
          <div className="p-4 rounded-xl border border-border bg-surface-secondary">
            <div className="text-[10px] text-text-tertiary uppercase mb-1">Requests</div>
            <div className="text-xl font-semibold text-text">
              {llmUsage.total_requests}
            </div>
          </div>
        </div>
      )}
      {!analytics && !llmUsage && (
        <div className="text-center text-text-tertiary text-xs py-8">
          Chưa có dữ liệu phân tích cho tổ chức này
        </div>
      )}
    </div>
  );
}

function SettingsSection({ detail }: { detail: NonNullable<ReturnType<typeof useAdminStore.getState>["selectedOrgDetail"]> }) {
  if (!detail.settings) {
    return (
      <div className="text-center text-text-tertiary text-xs py-8">
        Chưa có cài đặt tuỳ chỉnh
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-surface-secondary p-4">
      <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-2">
        Org Settings (JSON)
      </div>
      <pre className="text-xs text-text font-mono overflow-x-auto whitespace-pre-wrap max-h-[400px] overflow-y-auto">
        {JSON.stringify(detail.settings, null, 2)}
      </pre>
    </div>
  );
}
