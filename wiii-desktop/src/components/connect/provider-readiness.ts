/** Fail-closed provider readiness and safe connection-state updates. */
import type {
  WiiiConnectActivationGate,
  WiiiConnectActivationReadinessResponse,
  WiiiConnectProviderConnectionListResponse,
  WiiiConnectProviderConnectionRecord,
  WiiiConnectProviderDisconnectResponse,
  WiiiConnectSessionStartDecision,
} from "@/api/types/wiii-connect";
import type { CapabilityStatusTone } from "@/lib/capability-status";
import { compactText } from "./connect-display";
import type { CatalogCard } from "./connect-types";

export function providerConnectionTone(
  connection: WiiiConnectProviderConnectionRecord | undefined,
  response?: WiiiConnectProviderConnectionListResponse,
): CapabilityStatusTone {
  if (connection) {
    if (connection.state === "connected" || connection.active) return "ok";
    if (connection.state === "authorizing" || connection.state === "waiting") return "pending";
    if (connection.state === "expired" || connection.state === "error") return "warn";
    return "off";
  }
  if (response?.status === "blocked") return response.reason === "provider_disabled" ? "off" : "warn";
  if (response?.status === "ready") return "off";
  return "off";
}

export function primaryProviderConnection(
  response: WiiiConnectProviderConnectionListResponse | undefined,
): WiiiConnectProviderConnectionRecord | undefined {
  return response?.connections?.[0];
}

export function providerConnectionSummary(
  connection: WiiiConnectProviderConnectionRecord | undefined,
): string {
  if (!connection) return "Chưa có account";
  return compactText(
    connection.account_label ||
      (connection.external_account_ref_present ? "Provider account" : "") ||
      connection.reason,
    "Đã có connection",
  );
}

export function disconnectResultTone(
  response: WiiiConnectProviderDisconnectResponse | undefined,
): CapabilityStatusTone {
  if (!response) return "off";
  if (response.local_disabled) return "ok";
  if (response.status === "blocked") return "warn";
  return response.status === "failed" ? "warn" : "off";
}

export function locallyDisabledConnection(
  connection: WiiiConnectProviderConnectionRecord,
  reason = "user_disconnect_requested",
): WiiiConnectProviderConnectionRecord {
  return {
    ...connection,
    state: "disabled",
    active: false,
    scopes: {},
    reason,
    warnings: Array.from(new Set([...(connection.warnings ?? []), "disconnected_by_user"])),
  };
}

export function responseWithLocallyDisabledConnection(
  response: WiiiConnectProviderConnectionListResponse | undefined,
  connection: WiiiConnectProviderConnectionRecord,
  reason = "user_disconnect_requested",
): WiiiConnectProviderConnectionListResponse {
  const disabled = locallyDisabledConnection(connection, reason);
  if (!response) {
    return {
      version: "wiii_connect_connection_list.v1",
      status: "ready",
      reason,
      provider_slug: connection.provider_slug,
      provider_kind: "composio",
      connection_count: 1,
      connections: [disabled],
    };
  }
  return {
    ...response,
    status: "ready",
    reason,
    connection_count: Math.max(response.connection_count, 1),
    connections: response.connections.map((item) =>
      providerConnectionRef(item) === providerConnectionRef(connection) ? disabled : item,
    ),
  };
}

export function providerConnectionRef(
  connection: WiiiConnectProviderConnectionRecord | null | undefined,
): string {
  return connection?.connection_ref || connection?.connection_id || "";
}

export function defaultActivationActionSlug(card: CatalogCard): string {
  if (card.providerSlug === "facebook") return "FACEBOOK_LIST_MANAGED_PAGES";
  if (card.providerSlug === "gmail") return "GMAIL_FETCH_EMAILS";
  return "";
}

export function sessionDecisionTone(
  decision: WiiiConnectSessionStartDecision | undefined,
): CapabilityStatusTone {
  if (!decision) return "off";
  return decision.status === "ready" ? "ok" : "warn";
}

export function activationReadinessTone(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): CapabilityStatusTone {
  if (!readiness) return "off";
  if (readinessReadyForAction(readiness)) return "ok";
  if (readiness.ready_to_connect) return "pending";
  return "warn";
}

export function readinessReadyForAction(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): boolean {
  return Boolean(readiness?.ready_to_execute_action ?? readiness?.ready_to_execute_readonly);
}

export function readinessReadyForReadonly(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): boolean {
  return Boolean(readiness?.ready_to_execute_readonly);
}

export function readinessActionMutation(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): string {
  const value = readiness?.action?.mutation;
  return typeof value === "string" ? value : "";
}

export function cardDefaultActionIsReadonly(card: CatalogCard): boolean {
  return ["FACEBOOK_LIST_MANAGED_PAGES", "GMAIL_FETCH_EMAILS"].includes(
    defaultActivationActionSlug(card),
  );
}

export function readinessBooleanLabel(value: boolean | undefined): string {
  return value ? "Sẵn sàng" : "Chưa sẵn sàng";
}

function readinessGateReady(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
  key: string,
): boolean {
  return Boolean(readiness?.gates?.some((gate) => gate.key === key && gate.ready));
}

export function readinessGatewayStatus(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): string {
  return compactText(readiness?.execution_gateway?.status, "Chưa đánh giá");
}

export function externalActionSummary(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
  actionCount: number | undefined,
): string {
  if (
    readinessReadyForReadonly(readiness) ||
    readinessGateReady(readiness, "curated_readonly_action")
  ) {
    return "Read-only sẵn sàng";
  }
  if (readinessReadyForAction(readiness) || readinessGateReady(readiness, "curated_action")) {
    return "Action sẵn sàng";
  }
  if (actionCount != null) return `${actionCount}`;
  return "Chưa khai báo";
}

export function externalAgentStatusDetail(
  fromBackend: boolean,
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): string {
  if (!fromBackend) {
    return "Wiii chưa có adapter, vault và permission gate cho kết nối này.";
  }
  if (readinessReadyForReadonly(readiness)) {
    return "Read-only action đã qua scope policy và execution gateway; mutation/write vẫn bị chặn ngoài allowlist.";
  }
  if (readinessReadyForAction(readiness)) {
    return "Action đã qua scope policy và execution gateway; mutation vẫn phải đúng preview/approval.";
  }
  if (readiness?.ready_to_connect) {
    return "Backend đã sẵn sàng cấp Connect Link; agent action vẫn chờ account, scope policy và execution gateway.";
  }
  return "Backend registry đã khai báo provider này; agent action vẫn bị khóa cho đến khi có scope, policy và audit.";
}

export function externalControlLabel(card: CatalogCard): string {
  if (card.agentReady) return "Sẵn sàng";
  if (card.connected) return "Chờ cấp quyền";
  return "Đang khóa an toàn";
}

export function readinessGateLabel(key: string): string {
  const labels: Record<string, string> = {
    provider_registered: "Provider registry",
    provider_adapter: "Adapter",
    vault: "Vault",
    persistent_storage: "Storage",
    audit_ledger: "Audit ledger",
    connect_policy: "Connect policy",
    curated_action: "Curated action",
    curated_readonly_action: "Read-only action",
    local_connection: "Connection",
    execution_gateway: "Execution gateway",
  };
  return labels[key] ?? compactText(key.replaceAll("_", " "));
}

export function readinessGateTone(gate: WiiiConnectActivationGate): CapabilityStatusTone {
  return gate.ready ? "ok" : "warn";
}

export function requirementDisplayLabel(value: string): string {
  const labels: Record<string, string> = {
    audit_ledger: "Bật audit ledger",
    complete_provider_oauth: "Hoàn tất OAuth/Connect Link",
    connect_policy: "Bật connect policy",
    connect_provider_account: "Kết nối account provider",
    curate_action: "Khai báo action đã kiểm duyệt",
    curate_readonly_action: "Khai báo action read-only đã kiểm duyệt",
    curated_action_catalog: "Khai báo catalog action đã kiểm duyệt",
    curated_readonly_action: "Khai báo action read-only đã kiểm duyệt",
    durable_audit_ledger: "Bật audit ledger bền vững",
    enable_curated_action_catalog: "Bật catalog action đã kiểm duyệt",
    enable_action_allowlist: "Bật action allowlist đã kiểm duyệt",
    enable_provider_agent_policy: "Bật policy agent cho provider",
    encrypted_vault_ref: "Cấu hình vault/token ref",
    execution_gateway: "Mở execution gateway read-only",
    provider_adapter: "Bind adapter provider",
    provider_managed_vault_ref: "Dùng vault ref do provider quản lý",
    provider_registered: "Khai báo provider trong registry",
    scope_policy: "Bật scope policy",
    vault: "Cấu hình vault",
  };
  return labels[value] ?? compactText(value.replaceAll("_", " "));
}

function blockedReadinessGates(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): WiiiConnectActivationGate[] {
  return (readiness?.gates ?? []).filter((gate) => !gate.ready);
}

export function readableRequiredNext(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): string[] {
  const values = blockedReadinessGates(readiness).flatMap((gate) =>
    gate.required_next && gate.required_next.length > 0
      ? gate.required_next
      : [gate.key],
  );
  return Array.from(new Set(values.map(requirementDisplayLabel)));
}

function readinessConnectionPresent(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): boolean {
  const state = readiness?.connection?.state;
  return Boolean(
    readiness?.connection?.present &&
      state !== "disabled" &&
      state !== "not_connected" &&
      state !== "missing",
  );
}

export function providerHasUsableConnection(
  connection: WiiiConnectProviderConnectionRecord | undefined,
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): boolean {
  if (connection) {
    return Boolean(
      (connection.active || connection.state === "connected") &&
        connection.state !== "disabled",
    );
  }
  return readinessConnectionPresent(readiness);
}

export function gatewayLifecycleTone(
  readiness: WiiiConnectActivationReadinessResponse | undefined,
): CapabilityStatusTone {
  if (readinessReadyForAction(readiness)) return "ok";
  const status = String(readiness?.execution_gateway?.status ?? "").toLowerCase();
  if (!status) return "off";
  if (["allowed", "ready", "ok", "enabled"].includes(status)) return "ok";
  if (["blocked", "denied", "disabled", "error", "missing"].includes(status)) return "warn";
  return "pending";
}
