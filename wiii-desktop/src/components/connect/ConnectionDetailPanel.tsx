import { ExternalLink, Loader2, Lock, RefreshCw, Unplug } from "lucide-react";
import type {
  WiiiConnectAuthorizationUrlDecision,
  WiiiConnectProviderConnectionRecord,
  WiiiConnectSessionStartDecision,
} from "@/api/types";
import { compactText, formatDateTime, statusLabel } from "./connect-display";
import type {
  CatalogCard,
  ProviderActionInventoryState,
  ProviderActivationReadinessState,
  ProviderConnectionListState,
  ProviderDisconnectState,
} from "./connect-types";
import { StatusPill } from "./ConnectStatus";
import { EffectiveActionInventoryPanel } from "./EffectiveActionInventoryPanel";
import { FacebookPostComposer } from "./FacebookPostComposer";
import {
  activationReadinessTone,
  cardDefaultActionIsReadonly,
  disconnectResultTone,
  primaryProviderConnection,
  providerConnectionRef,
  providerConnectionSummary,
  providerConnectionTone,
  readinessActionMutation,
  readinessBooleanLabel,
  readinessGateLabel,
  readinessGateTone,
  readinessReadyForAction,
  readinessReadyForReadonly,
  sessionDecisionTone,
} from "./provider-readiness";
import { ProviderLifecyclePanel } from "./ProviderLifecyclePanel";

export function ConnectionDetailPanel({
  card,
  readinessState,
  sessionDecision,
  authorizationDecision,
  sessionLoading,
  readinessLoading,
  authorizationLoading,
  disconnectState,
  actionInventoryState,
  readinessError,
  actionInventoryError,
  sessionError,
  authorizationError,
  connectionList,
  onRefreshReadiness,
  onRequestSession,
  onRequestAuthorization,
  onRefreshConnections,
  onRefreshActionInventory,
  onDisconnectConnection,
}: {
  card: CatalogCard | null;
  readinessState?: ProviderActivationReadinessState;
  sessionDecision?: WiiiConnectSessionStartDecision;
  authorizationDecision?: WiiiConnectAuthorizationUrlDecision;
  sessionLoading?: boolean;
  readinessLoading?: boolean;
  authorizationLoading?: boolean;
  disconnectState?: ProviderDisconnectState;
  actionInventoryState?: ProviderActionInventoryState;
  readinessError?: string;
  actionInventoryError?: string;
  sessionError?: string;
  authorizationError?: string;
  connectionList?: ProviderConnectionListState;
  onRefreshReadiness?: (card: CatalogCard) => Promise<unknown>;
  onRequestSession?: (card: CatalogCard) => Promise<void>;
  onRequestAuthorization?: (card: CatalogCard) => Promise<void>;
  onRefreshConnections?: (card: CatalogCard) => Promise<unknown>;
  onRefreshActionInventory?: (card: CatalogCard) => Promise<unknown>;
  onDisconnectConnection?: (
    card: CatalogCard,
    connection: WiiiConnectProviderConnectionRecord,
  ) => Promise<void>;
}) {
  if (!card) {
    return (
      <aside className="rounded-lg border border-dashed border-[var(--border)] bg-surface-secondary p-4 text-sm text-text-secondary">
        Chọn một tài khoản hoặc ứng dụng để xem trạng thái và quyền của Neko.
      </aside>
    );
  }

  const Icon = card.icon;
  const canRequestSession =
    card.provider !== "wiii_native" &&
    card.registrySource === "backend" &&
    Boolean(onRequestSession);
  const canRequestAuthorization =
    card.provider !== "wiii_native" &&
    card.registrySource === "backend" &&
    Boolean(onRequestAuthorization);
  const canRefreshConnections =
    card.provider !== "wiii_native" &&
    card.registrySource === "backend" &&
    Boolean(onRefreshConnections);
  const canRefreshReadiness =
    card.provider !== "wiii_native" &&
    card.registrySource === "backend" &&
    Boolean(onRefreshReadiness);
  const canRefreshActionInventory =
    card.provider !== "wiii_native" &&
    card.registrySource === "backend" &&
    Boolean(onRefreshActionInventory);
  const providerConnection = primaryProviderConnection(connectionList?.response);
  const readiness = readinessState?.response;
  const canDisconnectConnection =
    card.provider !== "wiii_native" &&
    card.registrySource === "backend" &&
    Boolean(providerConnectionRef(providerConnection)) &&
    providerConnection?.state !== "disabled" &&
    Boolean(onDisconnectConnection);

  return (
    <aside className="rounded-lg border border-[var(--border)] bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-surface-secondary text-text-secondary">
            <Icon size={19} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold text-text">{card.label}</h3>
            <p className="mt-1 text-sm text-text-secondary">{card.description}</p>
          </div>
        </div>
        <StatusPill tone={card.tone}>{card.status}</StatusPill>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!canRequestAuthorization || authorizationLoading}
          onClick={() => {
            if (canRequestAuthorization) void onRequestAuthorization?.(card);
          }}
          className={`inline-flex h-10 items-center justify-center gap-2 rounded-md border px-4 text-sm font-semibold ${
            canRequestAuthorization
              ? "border-primary/30 bg-primary text-primary-foreground hover:opacity-90"
              : "border-[var(--border)] bg-surface-secondary text-text-tertiary"
          }`}
        >
          {authorizationLoading ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <ExternalLink size={14} aria-hidden="true" />
          )}
          {card.provider === "wiii_native"
            ? "Có sẵn trong Wiii"
            : canRequestAuthorization
              ? authorizationLoading
                ? "Đang mở..."
                : "Kết nối qua Wiii"
              : "Chưa thể kết nối"}
        </button>
        <span className="self-center text-xs text-text-tertiary">
          {card.disabledReason ?? card.statusDetail}
        </span>
      </div>

      <details className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-2">
        <summary className="cursor-pointer text-sm font-medium text-text-secondary">
          Chi tiết kỹ thuật
        </summary>
        <dl className="mt-3 grid gap-2 text-xs">
          {card.detailRows.map(([label, value]) => (
            <div key={`${card.id}-${label}`} className="min-w-0 rounded-md bg-surface px-3 py-2">
              <dt className="text-text-tertiary">{label}</dt>
              <dd className="mt-0.5 break-words font-medium text-text">{value}</dd>
            </div>
          ))}
        </dl>
      </details>

      <ProviderLifecyclePanel
        card={card}
        readiness={readiness}
        providerConnection={providerConnection}
        connectionList={connectionList}
        authorizationDecision={authorizationDecision}
        authorizationLoading={authorizationLoading}
        authorizationError={authorizationError}
        disconnectState={disconnectState}
      />

      {(actionInventoryState || canRefreshActionInventory) && (
        <EffectiveActionInventoryPanel inventoryState={actionInventoryState} />
      )}

      {card.requirements && card.requirements.length > 0 && (
        <details className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3">
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-text-secondary">
            <Lock size={13} aria-hidden="true" />
            Yêu cầu kỹ thuật
          </summary>
          <ul className="mt-3 space-y-1.5 text-sm text-text-secondary">
            {card.requirements.map((requirement) => (
              <li key={`${card.id}-${requirement}`} className="flex gap-2">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-400" aria-hidden="true" />
                <span>{requirement}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {(readinessState || canRefreshReadiness) && (
        <div
          className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3"
          data-testid="wiii-connect-readiness-panel"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase text-text-tertiary">
              Activation readiness
            </div>
            <StatusPill tone={activationReadinessTone(readiness)}>
              {readiness?.status ?? (readinessState?.loading ? "đang đọc" : "chưa đọc")}
            </StatusPill>
          </div>

          <dl className="grid gap-2 text-xs sm:grid-cols-2">
            <div className="rounded-md bg-surface px-2 py-2">
              <dt className="text-text-tertiary">Connect-ready</dt>
              <dd className="mt-0.5 font-medium text-text">
                {readinessBooleanLabel(readiness?.ready_to_connect)}
              </dd>
            </div>
            <div className="rounded-md bg-surface px-2 py-2">
              <dt className="text-text-tertiary">
                {readinessReadyForReadonly(readiness) ||
                readinessActionMutation(readiness) === "read" ||
                cardDefaultActionIsReadonly(card)
                  ? "Agent read-only"
                  : "Agent action"}
              </dt>
              <dd className="mt-0.5 font-medium text-text">
                {readinessBooleanLabel(readinessReadyForAction(readiness))}
              </dd>
            </div>
            <div className="rounded-md bg-surface px-2 py-2">
              <dt className="text-text-tertiary">Connection</dt>
              <dd className="mt-0.5 font-medium text-text">
                {readiness?.connection?.present
                  ? statusLabel(readiness.connection.state)
                  : "Chưa có account"}
              </dd>
            </div>
            <div className="rounded-md bg-surface px-2 py-2">
              <dt className="text-text-tertiary">Gateway</dt>
              <dd className="mt-0.5 font-medium text-text">
                {compactText(readiness?.execution_gateway?.status, "Chưa đánh giá")}
              </dd>
            </div>
          </dl>

          {readiness?.gates && readiness.gates.length > 0 && (
            <ul className="mt-3 grid gap-2">
              {readiness.gates.map((gate) => (
                <li
                  key={`${card.id}-readiness-${gate.key}`}
                  className="rounded-md border border-[var(--border)] bg-surface px-2 py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate text-sm font-medium text-text">
                      {readinessGateLabel(gate.key)}
                    </span>
                    <StatusPill tone={readinessGateTone(gate)}>
                      {gate.ready ? "ok" : "blocked"}
                    </StatusPill>
                  </div>
                  <div className="mt-1 break-words text-xs text-text-tertiary">
                    {compactText(gate.reason)}
                  </div>
                  {gate.required_next && gate.required_next.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {gate.required_next.slice(0, 3).map((item) => (
                        <span
                          key={`${card.id}-readiness-${gate.key}-${item}`}
                          className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-text-secondary"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {readinessState?.lastFetchedAt && (
            <p className="mt-2 text-xs text-text-tertiary">
              Cập nhật {formatDateTime(readinessState.lastFetchedAt)}
            </p>
          )}
        </div>
      )}

      {sessionDecision && (
        <div className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase text-text-tertiary">
              Quyết định backend
            </div>
            <StatusPill tone={sessionDecisionTone(sessionDecision)}>
              {sessionDecision.status}
            </StatusPill>
          </div>
          <dl className="grid gap-2 text-xs">
            <div>
              <dt className="text-text-tertiary">Lý do</dt>
              <dd className="mt-0.5 font-medium text-text">{sessionDecision.reason}</dd>
            </div>
            <div>
              <dt className="text-text-tertiary">Authorization URL</dt>
              <dd className="mt-0.5 font-medium text-text">
                {sessionDecision.authorization_url ? "Sẵn sàng từ backend" : "Không phát hành"}
              </dd>
            </div>
          </dl>
          {sessionDecision.required_next && sessionDecision.required_next.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {sessionDecision.required_next.map((requirement) => (
                <span
                  key={`${card.id}-decision-${requirement}`}
                  className="rounded-md border border-[var(--border)] bg-surface px-2 py-1 text-xs text-text-secondary"
                >
                  {requirement}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {authorizationDecision && (
        <div className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase text-text-tertiary">
              Connect Link backend
            </div>
            <StatusPill tone={sessionDecisionTone(authorizationDecision)}>
              {authorizationDecision.status}
            </StatusPill>
          </div>
          <dl className="grid gap-2 text-xs">
            <div>
              <dt className="text-text-tertiary">Lý do</dt>
              <dd className="mt-0.5 font-medium text-text">{authorizationDecision.reason}</dd>
            </div>
            <div>
              <dt className="text-text-tertiary">URL</dt>
              <dd className="mt-0.5 font-medium text-text">
                {authorizationDecision.authorization_url ? "Backend đã cấp URL" : "Không phát hành"}
              </dd>
            </div>
          </dl>
          {authorizationDecision.required_next && authorizationDecision.required_next.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {authorizationDecision.required_next.map((requirement) => (
                <span
                  key={`${card.id}-auth-${requirement}`}
                  className="rounded-md border border-[var(--border)] bg-surface px-2 py-1 text-xs text-text-secondary"
                >
                  {requirement}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {connectionList && (
        <div className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase text-text-tertiary">
              Connection thật
            </div>
            <StatusPill tone={providerConnectionTone(providerConnection, connectionList.response)}>
              {providerConnection ? statusLabel(providerConnection.state) : connectionList.response?.status ?? "chưa đọc"}
            </StatusPill>
          </div>
          <dl className="grid gap-2 text-xs">
            <div>
              <dt className="text-text-tertiary">Account</dt>
              <dd className="mt-0.5 font-medium text-text">
                {providerConnectionSummary(providerConnection)}
              </dd>
            </div>
            <div>
              <dt className="text-text-tertiary">Lý do</dt>
              <dd className="mt-0.5 font-medium text-text">
                {connectionList.response?.reason ?? connectionList.error ?? "Chưa có"}
              </dd>
            </div>
            {connectionList.lastFetchedAt && (
              <div>
                <dt className="text-text-tertiary">Làm mới</dt>
                <dd className="mt-0.5 font-medium text-text">
                  {formatDateTime(connectionList.lastFetchedAt)}
                </dd>
              </div>
            )}
          </dl>
          {providerConnection?.warnings && providerConnection.warnings.length > 0 && (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-xs text-amber-800">
              {providerConnection.warnings.length} cảnh báo trong connection này.
            </div>
          )}
        </div>
      )}

      <FacebookPostComposer
        card={card}
        providerConnection={providerConnection}
        readiness={readiness}
        onRefreshConnections={onRefreshConnections}
      />

      {sessionError && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {sessionError}
        </div>
      )}

      {authorizationError && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {authorizationError}
        </div>
      )}

      {connectionList?.error && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {connectionList.error}
        </div>
      )}

      {readinessError && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {readinessError}
        </div>
      )}

      {actionInventoryError && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {actionInventoryError}
        </div>
      )}

      {disconnectState?.response && (
        <div className="mt-4 rounded-md border border-[var(--border)] bg-surface-secondary px-3 py-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase text-text-tertiary">
              Ngắt kết nối
            </div>
            <span data-testid="wiii-connect-disconnect-status">
              <StatusPill tone={disconnectResultTone(disconnectState.response)}>
                {disconnectState.response.local_disabled ? "Đã khóa local" : disconnectState.response.status}
              </StatusPill>
            </span>
          </div>
          <dl className="grid gap-2 text-xs">
            <div>
              <dt className="text-text-tertiary">Lý do</dt>
              <dd className="mt-0.5 font-medium text-text">
                {disconnectState.response.reason}
              </dd>
            </div>
            <div>
              <dt className="text-text-tertiary">Provider cleanup</dt>
              <dd className="mt-0.5 font-medium text-text">
                {disconnectState.response.status === "succeeded" ? "Đã gửi yêu cầu" : "Chờ xử lý"}
              </dd>
            </div>
            {disconnectState.lastUpdatedAt && (
              <div>
                <dt className="text-text-tertiary">Cập nhật</dt>
                <dd className="mt-0.5 font-medium text-text">
                  {formatDateTime(disconnectState.lastUpdatedAt)}
                </dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {disconnectState?.error && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {disconnectState.error}
        </div>
      )}

      {(canRefreshReadiness ||
        canRefreshConnections ||
        canDisconnectConnection ||
        canRequestSession ||
        canRefreshActionInventory) && (
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!canRefreshReadiness || readinessLoading}
          onClick={() => {
            if (canRefreshReadiness) void onRefreshReadiness?.(card);
          }}
          className={`inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium ${
            canRefreshReadiness
              ? "border-[var(--border)] bg-surface-secondary text-text-secondary hover:text-text"
              : "border-[var(--border)] bg-surface-secondary text-text-tertiary"
          }`}
        >
          <RefreshCw
            size={14}
            className={readinessLoading ? "animate-spin" : ""}
            aria-hidden="true"
          />
          Kiểm tra readiness
        </button>

        <button
          type="button"
          disabled={!canRefreshConnections || connectionList?.loading}
          onClick={() => {
            if (canRefreshConnections) void onRefreshConnections?.(card);
          }}
          className={`inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium ${
            canRefreshConnections
              ? "border-[var(--border)] bg-surface-secondary text-text-secondary hover:text-text"
              : "border-[var(--border)] bg-surface-secondary text-text-tertiary"
          }`}
        >
          <RefreshCw
            size={14}
            className={connectionList?.loading ? "animate-spin" : ""}
            aria-hidden="true"
          />
          Làm mới trạng thái
        </button>

        <button
          type="button"
          data-testid="wiii-connect-disconnect-button"
          disabled={!canDisconnectConnection || disconnectState?.loading}
          onClick={() => {
            if (canDisconnectConnection && providerConnection) {
              void onDisconnectConnection?.(card, providerConnection);
            }
          }}
          className={`inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium ${
            canDisconnectConnection
              ? "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
              : "border-[var(--border)] bg-surface-secondary text-text-tertiary"
          }`}
        >
          {disconnectState?.loading ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <Unplug size={14} aria-hidden="true" />
          )}
          {disconnectState?.loading
            ? "Đang ngắt..."
            : providerConnection?.state === "disabled"
              ? "Đã ngắt"
              : "Ngắt kết nối"}
        </button>

        <button
          type="button"
          disabled={!canRequestSession || sessionLoading}
          onClick={() => {
            if (canRequestSession) void onRequestSession?.(card);
          }}
          className={`inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium ${
            canRequestSession
              ? "border-[var(--border)] bg-surface-secondary text-text-secondary hover:text-text"
              : "border-[var(--border)] bg-surface-secondary text-text-tertiary"
          }`}
        >
          {sessionLoading ? "Đang kiểm tra..." : "Kiểm tra policy"}
        </button>

        <button
          type="button"
          disabled={!canRefreshActionInventory || actionInventoryState?.loading}
          onClick={() => {
            if (canRefreshActionInventory) void onRefreshActionInventory?.(card);
          }}
          className={`inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium ${
            canRefreshActionInventory
              ? "border-[var(--border)] bg-surface-secondary text-text-secondary hover:text-text"
              : "border-[var(--border)] bg-surface-secondary text-text-tertiary"
          }`}
        >
          <RefreshCw
            size={14}
            className={actionInventoryState?.loading ? "animate-spin" : ""}
            aria-hidden="true"
          />
          Đồng bộ actions
        </button>
      </div>
      )}
    </aside>
  );
}
