/**
 * Analytics tab — charts and metrics via recharts.
 * Sprint 179: "Quản Trị Toàn Diện"
 */
import { useEffect } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useAdminStore } from "@/stores/admin-store";
import type { DateRange } from "@/stores/admin-store";

const DATE_RANGES: { value: DateRange; label: string }[] = [
  { value: "7d", label: "7 ngày" },
  { value: "30d", label: "30 ngày" },
  { value: "90d", label: "90 ngày" },
  { value: "all", label: "Tất cả" },
];

function useThemeColors() {
  // Re-read CSS vars on every render so chart colors update on theme toggle
  if (typeof window === "undefined") return { accent: "#6366f1", text: "#374151", grid: "#e5e7eb" };
  const style = getComputedStyle(document.documentElement);
  return {
    accent: style.getPropertyValue("--accent").trim() || "#6366f1",
    text: style.getPropertyValue("--text-secondary").trim() || "#374151",
    grid: style.getPropertyValue("--border").trim() || "#e5e7eb",
  };
}

export function AnalyticsTab() {
  const {
    analyticsOverview,
    llmUsage,
    userAnalytics,
    analyticsDateRange,
    loading,
    fetchAnalyticsOverview,
    fetchLlmUsage,
    fetchUserAnalytics,
    setAnalyticsDateRange,
  } = useAdminStore();
  const colors = useThemeColors();

  useEffect(() => {
    fetchAnalyticsOverview();
    fetchLlmUsage();
    fetchUserAnalytics();
  }, [fetchAnalyticsOverview, fetchLlmUsage, fetchUserAnalytics]);

  const handleRangeChange = (range: DateRange) => {
    setAnalyticsDateRange(range);
    fetchAnalyticsOverview(range);
    fetchLlmUsage(range);
    fetchUserAnalytics(range);
  };

  return (
    <div className="space-y-6">
      {/* Date range */}
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-text">Phân tích hệ thống</div>
        <div className="flex gap-1.5">
          {DATE_RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => handleRangeChange(r.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                analyticsDateRange === r.value
                  ? "bg-[var(--accent)] text-white"
                  : "bg-surface-secondary text-text-secondary hover:text-text border border-border"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* DAU chart */}
      {analyticsOverview && analyticsOverview.daily_active_users.length > 0 && (
        <div className="p-4 rounded-xl border border-border bg-surface-secondary">
          <div className="text-xs font-medium text-text-secondary mb-3">
            Người dùng hoạt động hàng ngày (DAU)
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={analyticsOverview.daily_active_users}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: colors.text }} />
              <YAxis tick={{ fontSize: 10, fill: colors.text }} />
              <Tooltip
                contentStyle={{
                  fontSize: 12,
                  borderRadius: 8,
                  border: `1px solid ${colors.grid}`,
                }}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke={colors.accent}
                strokeWidth={2}
                dot={false}
                name="DAU"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Chat volume chart */}
      {analyticsOverview && analyticsOverview.chat_volume.length > 0 && (
        <div className="p-4 rounded-xl border border-border bg-surface-secondary">
          <div className="text-xs font-medium text-text-secondary mb-3">
            Lượng chat hàng ngày
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={analyticsOverview.chat_volume}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: colors.text }} />
              <YAxis tick={{ fontSize: 10, fill: colors.text }} />
              <Tooltip
                contentStyle={{
                  fontSize: 12,
                  borderRadius: 8,
                  border: `1px solid ${colors.grid}`,
                }}
              />
              <Bar dataKey="messages" fill={colors.accent} name="Tin nhắn" radius={[4, 4, 0, 0]} />
              <Bar dataKey="sessions" fill={`${colors.accent}80`} name="Phiên" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* LLM Usage summary */}
      {llmUsage && (
        <div className="p-4 rounded-xl border border-border bg-surface-secondary">
          <div className="text-xs font-medium text-text-secondary mb-3">
            Sử dụng LLM
          </div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <div className="text-xl font-semibold text-text">
                {llmUsage.total_tokens >= 1000000
                  ? `${(llmUsage.total_tokens / 1000000).toFixed(1)}M`
                  : llmUsage.total_tokens >= 1000
                    ? `${(llmUsage.total_tokens / 1000).toFixed(1)}k`
                    : String(llmUsage.total_tokens)}
              </div>
              <div className="text-[10px] text-text-tertiary">Tokens</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-text">
                ${llmUsage.total_cost_usd.toFixed(2)}
              </div>
              <div className="text-[10px] text-text-tertiary">Chi phí</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-text">
                {llmUsage.total_requests}
              </div>
              <div className="text-[10px] text-text-tertiary">Requests</div>
            </div>
          </div>

          {/* LLM breakdown chart */}
          {llmUsage.breakdown.length > 0 && (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={llmUsage.breakdown}>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                <XAxis dataKey="group" tick={{ fontSize: 10, fill: colors.text }} />
                <YAxis tick={{ fontSize: 10, fill: colors.text }} />
                <Tooltip
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: `1px solid ${colors.grid}`,
                  }}
                />
                <Bar dataKey="tokens" fill={colors.accent} name="Tokens" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}

          {/* Top models table */}
          {llmUsage.top_models.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] font-medium text-text-secondary mb-2">Top Models</div>
              <div className="space-y-1">
                {llmUsage.top_models.slice(0, 5).map((m, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-text font-mono truncate">{m.model}</span>
                    <span className="text-text-tertiary shrink-0 ml-2">
                      {m.tokens >= 1000 ? `${(m.tokens / 1000).toFixed(1)}k` : m.tokens} tokens
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top users table */}
          {llmUsage.top_users.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] font-medium text-text-secondary mb-2">Top Users</div>
              <div className="space-y-1">
                {llmUsage.top_users.slice(0, 5).map((u, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-text truncate">{u.user_id}</span>
                    <span className="text-text-tertiary shrink-0 ml-2">
                      {u.tokens >= 1000 ? `${(u.tokens / 1000).toFixed(1)}k` : u.tokens} tokens
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* User analytics */}
      {userAnalytics && (
        <div className="p-4 rounded-xl border border-border bg-surface-secondary">
          <div className="text-xs font-medium text-text-secondary mb-3">
            Người dùng
          </div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <div className="text-xl font-semibold text-text">{userAnalytics.total_users}</div>
              <div className="text-[10px] text-text-tertiary">Tổng</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-text">{userAnalytics.new_users_period}</div>
              <div className="text-[10px] text-text-tertiary">Mới</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-text">{userAnalytics.active_users_period}</div>
              <div className="text-[10px] text-text-tertiary">Hoạt động</div>
            </div>
          </div>

          {/* Role distribution */}
          {Object.keys(userAnalytics.role_distribution).length > 0 && (
            <div>
              <div className="text-[11px] font-medium text-text-secondary mb-2">Phân bố vai trò</div>
              <div className="flex gap-3">
                {Object.entries(userAnalytics.role_distribution).map(([role, count]) => (
                  <div key={role} className="flex items-center gap-1.5 text-xs">
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-surface-tertiary text-text-secondary">
                      {role}
                    </span>
                    <span className="text-text">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {loading && !analyticsOverview && (
        <div className="text-center text-text-tertiary text-xs py-8">Đang tải...</div>
      )}
    </div>
  );
}
