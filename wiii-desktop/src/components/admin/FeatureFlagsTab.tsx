/**
 * Feature Flags tab — grouped by category with collapsible sections.
 * Sprint 179: "Quản Trị Toàn Diện"
 * Sprint 180: Category grouping (LaunchDarkly-style)
 */
import { useEffect, useState } from "react";
import { Search, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";
import type { AdminFeatureFlag } from "@/api/types";

// ---------------------------------------------------------------------------
// Flag categories (client-side classification by prefix)
// ---------------------------------------------------------------------------

interface FlagCategory {
  id: string;
  label: string;
  prefixes: string[];
}

const FLAG_CATEGORIES: FlagCategory[] = [
  { id: "core_ai", label: "Trí tuệ nhân tạo", prefixes: ["enable_corrective_rag", "enable_answer_verification", "rag_enable_reflection", "enable_structured_outputs", "enable_agentic_loop", "enable_hyde", "enable_adaptive_rag", "enable_graph_rag", "deep_reasoning"] },
  { id: "memory", label: "Bộ nhớ & Tính cách", prefixes: ["enable_core_memory", "enable_memory_", "enable_enhanced_extraction", "enable_semantic_fact", "enable_character_"] },
  { id: "search", label: "Tìm kiếm & Sản phẩm", prefixes: ["enable_product_search", "enable_tiktok_", "enable_browser_", "enable_network_", "enable_auto_group_", "enable_facebook_", "enable_deep_search"] },
  { id: "auth", label: "Xác thực & Bảo mật", prefixes: ["enable_google_oauth", "enable_lms_token_", "enable_auth_audit", "enable_oauth_", "enable_pkce"] },
  { id: "multi_tenant", label: "Đa tổ chức", prefixes: ["enable_multi_tenant", "enable_rls"] },
  { id: "channels", label: "Kênh giao tiếp", prefixes: ["enable_websocket", "enable_telegram", "enable_messenger_", "enable_zalo", "enable_cross_platform_"] },
  { id: "living_agent", label: "Linh hồn Wiii", prefixes: ["enable_living_agent", "living_agent_"] },
  { id: "emotion", label: "Cảm xúc & Tính cách", prefixes: ["enable_emotional_", "enable_personality_", "enable_soul_emotion", "default_personality"] },
  { id: "tools", label: "Công cụ & Mở rộng", prefixes: ["enable_mcp_", "enable_filesystem_", "enable_code_", "enable_skill_", "enable_unified_", "enable_tool_", "enable_thinking_"] },
  { id: "content_ui", label: "Nội dung & Giao diện", prefixes: ["enable_vision", "enable_chart_", "enable_visual_", "enable_preview", "enable_artifacts", "enable_text_"] },
  { id: "infra", label: "Hạ tầng", prefixes: ["enable_llm_failover", "enable_neo4j", "enable_subagent_", "enable_background_", "enable_scheduler", "enable_langsmith", "enable_evaluation"] },
  { id: "admin", label: "Quản trị", prefixes: ["enable_admin_"] },
  { id: "lms", label: "LMS & Đào tạo", prefixes: ["enable_lms_integration"] },
];

export function categorizeFlags(flags: AdminFeatureFlag[]): { category: FlagCategory; flags: AdminFeatureFlag[] }[] {
  const assigned = new Set<string>();
  const groups: { category: FlagCategory; flags: AdminFeatureFlag[] }[] = [];

  for (const cat of FLAG_CATEGORIES) {
    const matched = flags.filter(
      (f) => !assigned.has(f.key) && cat.prefixes.some((p) => f.key.startsWith(p))
    );
    matched.forEach((f) => assigned.add(f.key));
    if (matched.length > 0) {
      groups.push({ category: cat, flags: matched });
    }
  }

  // "Other" bucket for uncategorized flags
  const others = flags.filter((f) => !assigned.has(f.key));
  if (others.length > 0) {
    groups.push({
      category: { id: "other", label: "Khác", prefixes: [] },
      flags: others,
    });
  }

  return groups;
}

export function FeatureFlagsTab() {
  const {
    featureFlags, flagSearch, flagsOrgFilter, organizations, loading,
    fetchFeatureFlags, toggleFlag, deleteFlagOverride, setFlagSearch, setFlagsOrgFilter,
  } = useAdminStore();
  const [togglingKey, setTogglingKey] = useState<string | null>(null);
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchFeatureFlags();
  }, [fetchFeatureFlags]);

  const filtered = flagSearch
    ? featureFlags.filter((f) => f.key.toLowerCase().includes(flagSearch.toLowerCase()))
    : featureFlags;

  const groups = categorizeFlags(filtered);

  const handleToggle = async (key: string, currentValue: boolean) => {
    setTogglingKey(key);
    await toggleFlag(key, !currentValue);
    setTogglingKey(null);
  };

  const toggleCategory = (catId: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(catId)) next.delete(catId);
      else next.add(catId);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-text">Feature Flags</div>
          <div className="text-xs text-text-tertiary">
            {featureFlags.length} flags — {featureFlags.filter((f) => f.value).length} đang bật
          </div>
        </div>
      </div>

      {/* Org filter + Search */}
      <div className="flex gap-3">
        {organizations.length > 0 && (
          <select
            value={flagsOrgFilter ?? ""}
            onChange={(e) => {
              const val = e.target.value || null;
              setFlagsOrgFilter(val);
              fetchFeatureFlags(val ?? undefined);
            }}
            className="px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)] shrink-0"
            aria-label="Lọc theo tổ chức"
          >
            <option value="">Global (tất cả)</option>
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.display_name || org.name}
              </option>
            ))}
          </select>
        )}
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
          <input
            type="text"
            value={flagSearch}
            onChange={(e) => setFlagSearch(e.target.value)}
            placeholder="Tìm flag..."
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          />
        </div>
      </div>

      {/* Grouped flag list */}
      <div className="space-y-2">
        {groups.length === 0 && !loading && (
          <div className="text-center text-text-tertiary text-xs py-8">
            {flagSearch ? "Không tìm thấy flag" : "Không có feature flags"}
          </div>
        )}
        {groups.map(({ category, flags: catFlags }) => {
          const isCollapsed = collapsedCategories.has(category.id);
          const enabledCount = catFlags.filter((f) => f.value).length;

          return (
            <div key={category.id} className="rounded-lg border border-border overflow-hidden">
              {/* Category header */}
              <button
                onClick={() => toggleCategory(category.id)}
                className="w-full flex items-center gap-2 px-4 py-2.5 bg-surface-tertiary hover:bg-surface-secondary transition-colors text-left"
                aria-expanded={!isCollapsed}
                aria-label={`${category.label} — ${catFlags.length} flags`}
              >
                {isCollapsed ? <ChevronRight size={14} className="text-text-tertiary shrink-0" /> : <ChevronDown size={14} className="text-text-tertiary shrink-0" />}
                <span className="text-sm font-medium text-text flex-1">{category.label}</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[var(--accent-light)] text-[var(--accent)]">
                  {enabledCount}/{catFlags.length}
                </span>
              </button>

              {/* Flag rows */}
              {!isCollapsed && (
                <div className="divide-y divide-border">
                  {catFlags.map((flag) => (
                    <div
                      key={flag.key}
                      className="flex items-center gap-3 px-4 py-2.5 bg-surface-secondary group"
                    >
                      {/* Toggle switch */}
                      <button
                        role="switch"
                        aria-checked={flag.value}
                        aria-label={`Toggle ${flag.key}`}
                        disabled={togglingKey === flag.key}
                        onClick={() => handleToggle(flag.key, flag.value)}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0 ${
                          flag.value ? "bg-[var(--accent)]" : "bg-gray-300 dark:bg-gray-600"
                        } ${togglingKey === flag.key ? "opacity-50" : ""}`}
                      >
                        <span
                          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                            flag.value ? "translate-x-[18px]" : "translate-x-[3px]"
                          }`}
                        />
                      </button>

                      {/* Key + description */}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-text font-mono truncate">{flag.key}</div>
                        {flag.description && (
                          <div className="text-[11px] text-text-tertiary truncate">{flag.description}</div>
                        )}
                      </div>

                      {/* Source badge */}
                      <span
                        className={`shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          flag.source === "db_override"
                            ? "bg-[var(--accent-light)] text-[var(--accent)]"
                            : "bg-surface-tertiary text-text-tertiary"
                        }`}
                      >
                        {flag.source === "db_override" ? "override" : "config"}
                      </span>

                      {/* Delete override button */}
                      {flag.source === "db_override" && (
                        <button
                          onClick={() => deleteFlagOverride(flag.key)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-600 transition-all shrink-0"
                          title="Xoá override"
                          aria-label={`Xoá override cho ${flag.key}`}
                        >
                          <Trash2 size={12} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
