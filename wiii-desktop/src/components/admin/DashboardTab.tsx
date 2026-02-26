/**
 * Dashboard tab — 7 stat cards grid with refresh.
 * Sprint 179: "Quản Trị Toàn Diện"
 */
import { RefreshCw, Users, Activity, Building2, MessageSquare, Coins, DollarSign, Flag } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";

const CARDS = [
  { key: "total_users", label: "Người dùng", icon: Users, format: (v: number) => String(v) },
  { key: "active_users", label: "Đang hoạt động", icon: Activity, format: (v: number) => String(v) },
  { key: "total_organizations", label: "Tổ chức", icon: Building2, format: (v: number) => String(v) },
  { key: "total_chat_sessions_24h", label: "Phiên chat (24h)", icon: MessageSquare, format: (v: number) => String(v) },
  { key: "total_llm_tokens_24h", label: "Tokens (24h)", icon: Coins, format: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v) },
  { key: "estimated_cost_24h_usd", label: "Chi phí (24h)", icon: DollarSign, format: (v: number) => `$${v.toFixed(2)}` },
  { key: "feature_flags_active", label: "Flags bật", icon: Flag, format: (v: number) => String(v) },
] as const;

export function DashboardTab() {
  const { dashboard, loading, fetchDashboard, setActiveTab, selectOrg } = useAdminStore();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-text">Tổng quan hệ thống</div>
          <div className="text-xs text-text-tertiary">Dữ liệu thời gian thực</div>
        </div>
        <button
          onClick={() => fetchDashboard()}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-medium hover:bg-surface-tertiary transition-colors disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Làm mới
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {CARDS.map((card) => {
          const Icon = card.icon;
          const value = dashboard ? (dashboard as unknown as Record<string, number>)[card.key] : null;
          return (
            <div
              key={card.key}
              className="p-4 rounded-xl border border-border bg-surface-secondary"
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon size={14} className="text-text-tertiary" />
                <span className="text-xs text-text-tertiary">{card.label}</span>
              </div>
              <div className="text-2xl font-semibold text-text">
                {value !== null && value !== undefined ? card.format(value) : "—"}
              </div>
            </div>
          );
        })}
      </div>

      {/* Organization cards (Sprint 179b) */}
      {dashboard?.organizations && dashboard.organizations.length > 0 && (
        <div className="mt-6">
          <div className="text-sm font-medium text-text mb-3">Tổ chức</div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {dashboard.organizations.map((org) => (
              <button
                key={org.id}
                onClick={() => {
                  selectOrg(org.id);
                  setActiveTab("organizations");
                }}
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
      )}
    </div>
  );
}
