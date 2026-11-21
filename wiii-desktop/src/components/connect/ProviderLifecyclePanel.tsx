import type {
  WiiiConnectActivationReadinessResponse,
  WiiiConnectAuthorizationUrlDecision,
  WiiiConnectProviderConnectionRecord,
} from "@/api/types";
import { statusDotClasses, statusToneClasses } from "./connect-display";
import type {
  CatalogCard,
  ProviderConnectionListState,
  ProviderDisconnectState,
} from "./connect-types";
import { StatusPill } from "./ConnectStatus";
import {
  providerConnectionFlow,
  providerLifecycleStages,
  providerNextAction,
} from "./provider-lifecycle";

export function ProviderLifecyclePanel({
  card,
  readiness,
  providerConnection,
  connectionList,
  authorizationDecision,
  authorizationLoading,
  authorizationError,
  disconnectState,
}: {
  card: CatalogCard;
  readiness: WiiiConnectActivationReadinessResponse | undefined;
  providerConnection: WiiiConnectProviderConnectionRecord | undefined;
  connectionList?: ProviderConnectionListState;
  authorizationDecision?: WiiiConnectAuthorizationUrlDecision;
  authorizationLoading?: boolean;
  authorizationError?: string;
  disconnectState?: ProviderDisconnectState;
}) {
  const flow = providerConnectionFlow({
    card,
    readiness,
    providerConnection,
    connectionList,
    authorizationDecision,
    authorizationLoading,
    authorizationError,
    disconnectState,
  });
  const stages = providerLifecycleStages({
    card,
    readiness,
    providerConnection,
    connectionList,
  });
  const nextAction = providerNextAction({
    card,
    readiness,
    providerConnection,
    connectionList,
    authorizationDecision,
    authorizationLoading,
    authorizationError,
    disconnectState,
  });

  return (
    <details
      className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3"
      data-testid="wiii-connect-lifecycle-panel"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-medium text-text-secondary">
        <span>Trạng thái kết nối nâng cao</span>
        <StatusPill tone={nextAction.tone}>
          {nextAction.tone === "ok"
            ? "sẵn sàng"
            : nextAction.tone === "pending"
              ? "đang chờ"
              : nextAction.tone === "warn"
                ? "đang bị chặn"
                : "chưa bật"}
        </StatusPill>
      </summary>

      <div
        className="mb-3 mt-3 rounded-md border border-[var(--border)] bg-surface px-3 py-2"
        data-state={flow.status}
        data-testid="wiii-connect-connection-flow-state"
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase text-text-tertiary">
              Tiến trình
            </div>
            <div className="mt-1 truncate text-sm font-semibold text-text">
              {flow.label}
            </div>
          </div>
          <StatusPill tone={flow.tone}>{flow.status}</StatusPill>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-text-secondary">
          {flow.detail}
        </p>
      </div>

      <ol className="grid gap-2 sm:grid-cols-2">
        {stages.map((stage, index) => (
          <li
            key={`${card.id}-lifecycle-${stage.id}`}
            className="min-w-0 rounded-md border border-[var(--border)] bg-surface px-2 py-2"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-xs font-medium text-text-tertiary">
                {index + 1}. {stage.label}
              </span>
              <span className={`h-2 w-2 shrink-0 rounded-full ${statusDotClasses[stage.tone]}`} />
            </div>
            <div className="mt-1 truncate text-sm font-semibold text-text">
              {stage.value}
            </div>
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-secondary">
              {stage.detail}
            </p>
          </li>
        ))}
      </ol>

      <div
        className={`mt-3 rounded-md border px-3 py-2 ${statusToneClasses[nextAction.tone]}`}
        data-testid="wiii-connect-next-action"
      >
        <div className="text-xs font-semibold uppercase">Bước tiếp theo</div>
        <div className="mt-1 text-sm font-semibold">{nextAction.title}</div>
        <p className="mt-1 text-xs leading-relaxed">{nextAction.detail}</p>
        {nextAction.items.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {nextAction.items.slice(0, 4).map((item) => (
              <span
                key={`${card.id}-next-${item}`}
                className="rounded-md border border-current/20 bg-white/45 px-2 py-1 text-xs"
              >
                {item}
              </span>
            ))}
          </div>
        )}
      </div>

      <p className="mt-2 text-xs text-text-tertiary">
        Agent không tự cấp quyền. Scope/write/admin phải đến từ policy hoặc approval riêng.
      </p>
    </details>
  );
}
