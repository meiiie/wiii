import type {
  WiiiConnectEffectiveActionInventoryResponse,
  WiiiConnectEffectiveActionRecord,
} from "@/api/types/wiii-connect";
import type { CapabilityStatusTone } from "@/lib/capability-status";
import { compactText, formatDateTime, pathList } from "./connect-display";
import type { ProviderActionInventoryState } from "./connect-types";
import { StatusPill } from "./ConnectStatus";

function actionInventoryTone(
  inventory: WiiiConnectEffectiveActionInventoryResponse | undefined,
): CapabilityStatusTone {
  const status = String(inventory?.status ?? "").toLowerCase();
  if (status === "ready") return "ok";
  if (status === "guarded") return "pending";
  if (status === "blocked") return "warn";
  return "off";
}

function actionRecordTone(action: WiiiConnectEffectiveActionRecord): CapabilityStatusTone {
  if (action.executable_now || action.status === "ready") return "ok";
  if (action.visible_to_agent || action.status === "guarded") return "pending";
  return "off";
}

function actionStageLabel(key: string | undefined): string {
  const labels: Record<string, string> = {
    catalog: "Catalog",
    runtime_enablement: "Runtime",
    account: "Account",
    agent_policy: "Agent policy",
    gateway: "Gateway",
  };
  const normalized = String(key ?? "").trim();
  return labels[normalized] ?? compactText(normalized.replaceAll("_", " "));
}

function actionInventorySummary(
  inventory: WiiiConnectEffectiveActionInventoryResponse | undefined,
): string {
  if (!inventory) return "Chưa đồng bộ effective inventory";
  return `${inventory.visible_action_count}/${inventory.runtime_enabled_action_count} action agent-visible · ${inventory.executable_action_count} executable`;
}

function actionModelArgumentSummary(action: WiiiConnectEffectiveActionRecord): string {
  const keys = action.model_argument_keys ?? [];
  const safeKeys = keys
    .map((key) => compactText(key, ""))
    .filter((key) => key && key !== "[đã ẩn]");
  return safeKeys.length > 0 ? safeKeys.join(", ") : "Không";
}

function hiddenArgumentSummary(action: WiiiConnectEffectiveActionRecord): string {
  const count = action.hidden_argument_count ?? 0;
  return count > 0 ? `${count} backend-owned` : "Không";
}

export function EffectiveActionInventoryPanel({
  inventoryState,
}: {
  inventoryState?: ProviderActionInventoryState;
}) {
  const inventory = inventoryState?.response;
  const actions = inventory?.actions ?? [];
  return (
    <section
      className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3"
      data-testid="wiii-connect-action-inventory-panel"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="text-xs font-semibold uppercase text-text-tertiary">
          Effective actions
        </div>
        <StatusPill tone={actionInventoryTone(inventory)}>
          {inventory?.status ?? (inventoryState?.loading ? "đang đọc" : "chưa đọc")}
        </StatusPill>
      </div>
      <p className="text-xs leading-relaxed text-text-secondary">
        {inventory
          ? `${actionInventorySummary(inventory)}. Gateway: ${compactText(inventory.reason)}.`
          : "Danh sách action agent thật sự được thấy sẽ lấy từ backend policy, không lấy từ catalog tĩnh của UI."}
      </p>

      {actions.length > 0 && (
        <ul className="mt-3 space-y-2">
          {actions.slice(0, 6).map((action) => (
            <li
              key={`${action.provider_slug}-${action.slug}`}
              className="rounded-md border border-[var(--border)] bg-surface px-2 py-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-text">
                    {action.label || action.slug}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-text-tertiary">
                    {action.slug} · {action.mutation}
                  </div>
                </div>
                <StatusPill tone={actionRecordTone(action)}>
                  {action.executable_now
                    ? "execute"
                    : action.visible_to_agent
                      ? "agent-visible"
                      : action.status}
                </StatusPill>
              </div>
              <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
                <div>
                  <span className="text-text-tertiary">Runtime</span>
                  <div className="font-medium text-text">
                    {action.runtime_enabled ? "Bật" : "Tắt"}
                  </div>
                </div>
                <div>
                  <span className="text-text-tertiary">Gateway</span>
                  <div className="font-medium text-text">{compactText(action.reason)}</div>
                </div>
                <div>
                  <span className="text-text-tertiary">Scope</span>
                  <div className="font-medium text-text">
                    {action.required_scopes?.join(", ") || "read"}
                  </div>
                </div>
                <div>
                  <span className="text-text-tertiary">Model args</span>
                  <div className="font-medium text-text">
                    {actionModelArgumentSummary(action)}
                  </div>
                </div>
                <div>
                  <span className="text-text-tertiary">Runtime-owned</span>
                  <div className="font-medium text-text">
                    {hiddenArgumentSummary(action)}
                  </div>
                </div>
              </div>
              {action.stages && action.stages.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {action.stages.slice(0, 5).map((stage) => (
                    <span
                      key={`${action.slug}-${stage.key}`}
                      className="max-w-full rounded-md border border-[var(--border)] px-2 py-1 text-xs text-text-secondary"
                    >
                      <span className="font-medium text-text">
                        {actionStageLabel(stage.key)}:
                      </span>{" "}
                      {compactText(stage.status)}
                      {stage.reason ? <> · {compactText(stage.reason)}</> : null}
                      {stage.required_next && stage.required_next.length > 0 ? (
                        <> · Tiếp: {pathList(stage.required_next.slice(0, 2))}</>
                      ) : null}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {inventoryState?.error && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-xs text-amber-800">
          {inventoryState.error}
        </div>
      )}
      {inventoryState?.lastFetchedAt && (
        <p className="mt-2 text-xs text-text-tertiary">
          Cập nhật {formatDateTime(inventoryState.lastFetchedAt)}
        </p>
      )}
    </section>
  );
}
