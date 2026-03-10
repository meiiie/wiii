/**
 * OrgFlagsSection — Sprint 179b + 219d: "Quản Trị Theo Tổ Chức"
 *
 * Per-org feature flag management with 3-layer cascade indicator:
 * config → global override → org override
 *
 * Sprint 219d: Reuses categorizeFlags() for grouped display (same as system-level).
 */
import { useState } from "react";
import { Search, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";
import { categorizeFlags } from "./FeatureFlagsTab";

interface OrgFlagsSectionProps {
  orgId: string;
}

export function OrgFlagsSection({ orgId }: OrgFlagsSectionProps) {
  const { orgFeatureFlags, loading, toggleOrgFlag, deleteOrgFlagOverride } =
    useAdminStore();
  const [togglingKey, setTogglingKey] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());

  const filtered = search
    ? orgFeatureFlags.filter((f) => f.key.toLowerCase().includes(search.toLowerCase()))
    : orgFeatureFlags;

  const groups = categorizeFlags(filtered);

  const handleToggle = async (key: string, currentValue: boolean) => {
    setTogglingKey(key);
    await toggleOrgFlag(key, !currentValue, orgId);
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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs text-text-tertiary px-1">
          Override flags riêng cho tổ chức này. Các flag không ghi đè sẽ kế thừa từ global.
        </div>
        <div className="text-xs text-text-tertiary shrink-0">
          {orgFeatureFlags.filter((f) => f.source === "db_override").length} override / {orgFeatureFlags.length} flags
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Tìm flag..."
          className="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
        />
      </div>

      {groups.length === 0 && !loading && (
        <div className="text-center text-text-tertiary text-xs py-8">
          {search ? "Không tìm thấy flag" : "Không có feature flags"}
        </div>
      )}

      {/* Grouped flag list */}
      <div className="space-y-2">
        {groups.map(({ category, flags: catFlags }) => {
          const isCollapsed = collapsedCategories.has(category.id);
          const overrideCount = catFlags.filter((f) => f.source === "db_override").length;
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
                {isCollapsed
                  ? <ChevronRight size={14} className="text-text-tertiary shrink-0" />
                  : <ChevronDown size={14} className="text-text-tertiary shrink-0" />}
                <span className="text-sm font-medium text-text flex-1">{category.label}</span>
                {overrideCount > 0 && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400">
                    {overrideCount} override
                  </span>
                )}
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
                          <div className="text-[11px] text-text-tertiary truncate">
                            {flag.description}
                          </div>
                        )}
                      </div>

                      {/* Source badge — 3-layer cascade indicator */}
                      <span
                        className={`shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          flag.source === "db_override"
                            ? "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                            : "bg-surface-tertiary text-text-tertiary"
                        }`}
                      >
                        {flag.source === "db_override" ? "org override" : "kế thừa"}
                      </span>

                      {/* Delete override button (only for db_override) */}
                      {flag.source === "db_override" && (
                        <button
                          onClick={() => deleteOrgFlagOverride(flag.key, orgId)}
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
