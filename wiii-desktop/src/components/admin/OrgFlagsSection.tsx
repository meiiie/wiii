/**
 * OrgFlagsSection — Sprint 179b: "Quản Trị Theo Tổ Chức"
 *
 * Per-org feature flag management with 3-layer cascade indicator:
 * config → global override → org override
 */
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";

interface OrgFlagsSectionProps {
  orgId: string;
}

export function OrgFlagsSection({ orgId }: OrgFlagsSectionProps) {
  const { orgFeatureFlags, loading, toggleOrgFlag, deleteOrgFlagOverride } =
    useAdminStore();
  const [togglingKey, setTogglingKey] = useState<string | null>(null);

  const handleToggle = async (key: string, currentValue: boolean) => {
    setTogglingKey(key);
    await toggleOrgFlag(key, !currentValue, orgId);
    setTogglingKey(null);
  };

  return (
    <div className="space-y-3">
      <div className="text-xs text-text-tertiary px-1">
        Override flags riêng cho tổ chức này. Các flag không ghi đè sẽ kế thừa từ global.
      </div>

      {orgFeatureFlags.length === 0 && !loading && (
        <div className="text-center text-text-tertiary text-xs py-8">
          Không có feature flags
        </div>
      )}

      <div className="space-y-1.5">
        {orgFeatureFlags.map((flag) => (
          <div
            key={flag.key}
            className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border bg-surface-secondary group"
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
    </div>
  );
}
