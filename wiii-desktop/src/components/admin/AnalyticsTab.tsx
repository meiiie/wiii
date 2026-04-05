/**
 * Analytics tab - charts and admin metrics via recharts.
 * The canonical Wiii view is account-type first; legacy roles remain visible
 * only as compatibility data.
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
  { value: "7d", label: "7 ngay" },
  { value: "30d", label: "30 ngay" },
  { value: "90d", label: "90 ngay" },
  { value: "all", label: "Tat ca" },
];

const PLATFORM_ROLE_LABELS: Record<string, string> = {
  user: "Wiii User",
  platform_admin: "Platform Admin",
};

const LEGACY_ROLE_LABELS: Record<string, string> = {
  student: "student",
  teacher: "teacher",
  admin: "admin",
};

const ORG_ROLE_LABELS: Record<string, string> = {
  member: "Thanh vien to chuc",
  org_admin: "Quan tri to chuc",
  owner: "Chu so huu to chuc",
  admin: "Quan tri to chuc",
};

function useThemeColors() {
  if (typeof window === "undefined") {
    return { accent: "#6366f1", text: "#374151", grid: "#e5e7eb" };
  }
  const style = getComputedStyle(document.documentElement);
  return {
    accent: style.getPropertyValue("--accent").trim() || "#6366f1",
    text: style.getPropertyValue("--text-secondary").trim() || "#374151",
    grid: style.getPropertyValue("--border").trim() || "#e5e7eb",
  };
}

function DistributionRow({
  title,
  values,
  labels,
}: {
  title: string;
  values?: Record<string, number>;
  labels?: Record<string, string>;
}) {
  if (!values || Object.keys(values).length === 0) return null;
  return (
    <div>
      <div className="text-[11px] font-medium text-text-secondary mb-2">{title}</div>
      <div className="flex flex-wrap gap-3">
        {Object.entries(values).map(([key, count]) => (
          <div key={key} className="flex items-center gap-1.5 text-xs">
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-surface-tertiary text-text-secondary">
              {labels?.[key] || key}
            </span>
            <span className="text-text">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function derivePlatformRoleDistribution(
  values?: Record<string, number>,
): Record<string, number> | undefined {
  if (!values || Object.keys(values).length === 0) return undefined;
  return {
    platform_admin: values.admin || 0,
    user: Object.entries(values).reduce(
      (total, [role, count]) => total + (role === "admin" ? 0 : count),
      0,
    ),
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

  const platformRoleDistribution =
    userAnalytics?.platform_role_distribution
    || derivePlatformRoleDistribution(userAnalytics?.role_distribution);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-text">Phan tich he thong</div>
        <div className="flex gap-1.5">
          {DATE_RANGES.map((range) => (
            <button
              key={range.value}
              onClick={() => handleRangeChange(range.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                analyticsDateRange === range.value
                  ? "bg-[var(--accent)] text-white"
                  : "bg-surface-secondary text-text-secondary hover:text-text border border-border"
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {analyticsOverview && analyticsOverview.daily_active_users.length > 0 && (
        <div className="p-4 rounded-xl border border-border bg-surface-secondary">
          <div className="text-xs font-medium text-text-secondary mb-3">
            Nguoi dung hoat dong hang ngay
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

      {analyticsOverview && analyticsOverview.chat_volume.length > 0 && (
        <div className="p-4 rounded-xl border border-border bg-surface-secondary">
          <div className="text-xs font-medium text-text-secondary mb-3">
            Luong chat hang ngay
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
              <Bar dataKey="messages" fill={colors.accent} name="Tin nhan" radius={[4, 4, 0, 0]} />
              <Bar dataKey="sessions" fill={`${colors.accent}80`} name="Phien" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {llmUsage && (
        <div className="p-4 rounded-xl border border-border bg-surface-secondary">
          <div className="text-xs font-medium text-text-secondary mb-3">
            Su dung LLM
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
              <div className="text-[10px] text-text-tertiary">Chi phi</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-text">
                {llmUsage.total_requests}
              </div>
              <div className="text-[10px] text-text-tertiary">Requests</div>
            </div>
          </div>

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

          {llmUsage.top_models.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] font-medium text-text-secondary mb-2">Top Models</div>
              <div className="space-y-1">
                {llmUsage.top_models.slice(0, 5).map((model, index) => (
                  <div key={index} className="flex items-center justify-between text-xs">
                    <span className="text-text font-mono truncate">{model.model}</span>
                    <span className="text-text-tertiary shrink-0 ml-2">
                      {model.tokens >= 1000 ? `${(model.tokens / 1000).toFixed(1)}k` : model.tokens} tokens
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {llmUsage.top_users.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] font-medium text-text-secondary mb-2">Top Users</div>
              <div className="space-y-1">
                {llmUsage.top_users.slice(0, 5).map((user, index) => (
                  <div key={index} className="flex items-center justify-between text-xs">
                    <span className="text-text truncate">{user.user_id}</span>
                    <span className="text-text-tertiary shrink-0 ml-2">
                      {user.tokens >= 1000 ? `${(user.tokens / 1000).toFixed(1)}k` : user.tokens} tokens
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {userAnalytics && (
        <div className="p-4 rounded-xl border border-border bg-surface-secondary">
          <div className="text-xs font-medium text-text-secondary mb-3">
            Nguoi dung
          </div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <div className="text-xl font-semibold text-text">{userAnalytics.total_users}</div>
              <div className="text-[10px] text-text-tertiary">Tong</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-text">{userAnalytics.new_users_period}</div>
              <div className="text-[10px] text-text-tertiary">Moi</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-text">{userAnalytics.active_users_period}</div>
              <div className="text-[10px] text-text-tertiary">Hoat dong</div>
            </div>
          </div>

          <div className="space-y-3">
            <DistributionRow
              title="Loai tai khoan Wiii"
              values={platformRoleDistribution}
              labels={PLATFORM_ROLE_LABELS}
            />
            <DistributionRow
              title="Vai tro tuong thich (legacy)"
              values={userAnalytics.legacy_role_distribution || userAnalytics.role_distribution}
              labels={LEGACY_ROLE_LABELS}
            />
            <DistributionRow
              title="Vai tro trong to chuc dang loc"
              values={userAnalytics.organization_role_distribution}
              labels={ORG_ROLE_LABELS}
            />
          </div>
        </div>
      )}

      {loading && !analyticsOverview && (
        <div className="text-center text-text-tertiary text-xs py-8">Dang tai...</div>
      )}
    </div>
  );
}
