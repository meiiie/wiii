/** Shared presentation helpers, including connector-secret redaction. */
import type { WiiiConnectRuntimeConnection, WiiiConnectRuntimeSnapshot } from "@/api/types";
import type { CapabilityStatusTone } from "@/lib/capability-status";

export const statusToneClasses: Record<CapabilityStatusTone, string> = {
  ok: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warn: "border-amber-200 bg-amber-50 text-amber-800",
  pending: "border-sky-200 bg-sky-50 text-sky-700",
  off: "border-[var(--border)] bg-surface-secondary text-text-tertiary",
};

export const statusDotClasses: Record<CapabilityStatusTone, string> = {
  ok: "bg-emerald-500",
  warn: "bg-amber-500",
  pending: "bg-sky-500",
  off: "bg-zinc-400",
};

export const providerKindLabels: Record<string, string> = {
  wiii_native: "Wiii native",
  composio: "Composio",
  mcp: "MCP",
  custom_oauth: "OAuth riêng",
  workflow: "Workflow",
  channels: "Channels",
};

export const mutationPolicyLabels: Record<string, string> = {
  none: "Không ghi dữ liệu",
  preview_only: "Chỉ preview",
  approval_token_required: "Cần approval_token",
  explicit_user_confirmation_required: "Cần xác nhận",
};

export const delegationPolicyLabels: Record<string, string> = {
  direct_only: "Trực tiếp",
  delegate_to_path_agent: "Path agent",
  delegate_to_integration_agent: "Integration agent",
};

export function isEmbeddedWindow(): boolean {
  if (typeof window === "undefined") return false;
  return window.parent !== window;
}

export function connectionTone(connection: WiiiConnectRuntimeConnection): CapabilityStatusTone {
  if (connection.status === "error" || connection.status === "expired") return "warn";
  if (connection.status === "pending" || connection.status === "preview") return "pending";
  if (connection.status === "disabled" || connection.status === "not_connected") return "off";
  return connection.agent_ready || connection.active || connection.status === "connected"
    ? "ok"
    : "warn";
}

export function statusLabel(status: string | undefined): string {
  if (status === "connected") return "Đã kết nối";
  if (status === "authorizing") return "Đang xác thực";
  if (status === "waiting") return "Đang chờ";
  if (status === "disconnected") return "Chưa nối";
  if (status === "preview") return "Preview";
  if (status === "pending") return "Đang chờ";
  if (status === "expired") return "Hết hạn";
  if (status === "error") return "Lỗi";
  if (status === "disabled") return "Tắt";
  if (status === "not_connected") return "Chưa nối";
  return compactText(status, "Không rõ");
}

const sensitiveDisplayKeyMarkers = [
  "access_token",
  "api_key",
  "approval_token",
  "authorization",
  "bearer",
  "code=",
  "connection_id",
  "connection_ref",
  "credential",
  "password",
  "page_id",
  "provider_payload",
  "raw_payload",
  "refresh_token",
  "secret",
  "scheduled_publish_time",
  "token=",
  "vault",
];

function looksSensitiveDisplayText(value: string): boolean {
  const text = value.trim();
  const lower = text.toLowerCase();
  if (!text) return false;
  if (sensitiveDisplayKeyMarkers.some((marker) => lower.includes(marker))) return true;
  if (lower.startsWith("bearer ")) return true;
  if (/^(sk-|ak_|tp-|wcn_|ca_)/i.test(text)) return true;
  if (/^eyJ[\w-]*\.[\w-]*\.[\w-]*$/.test(text)) return true;
  return false;
}

function safeConnectorText(value: unknown, fallback = "Chưa có"): string {
  const text = String(value ?? "").trim();
  if (!text) return fallback;
  return looksSensitiveDisplayText(text) ? "[đã ẩn]" : text;
}

export function compactText(value: unknown, fallback = "Chưa có"): string {
  const text = safeConnectorText(value, fallback);
  if (!text) return fallback;
  return text.length > 72 ? `${text.slice(0, 69)}...` : text;
}

export function formatCount(value: unknown, label: string): string | null {
  if (typeof value !== "number") return null;
  return `${value} ${label}`;
}

export function formatDateTime(value: string | undefined | null): string {
  if (!value) return "Chưa có";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return compactText(value);
  return date.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    day: "2-digit",
    month: "2-digit",
  });
}

export function scopeSummary(scopes: WiiiConnectRuntimeConnection["scopes"]): string {
  if (!scopes) return "Không";
  const enabled = Object.entries(scopes)
    .filter(([, value]) => value)
    .map(([key]) => safeConnectorText(key, "scope"));
  return enabled.length > 0 ? enabled.join(", ") : "Không";
}

export function pathList(value: string[] | undefined): string {
  if (!value || value.length === 0) return "Không";
  return value.map((item) => compactText(item)).join(", ");
}

export function capabilityCount(connection: WiiiConnectRuntimeConnection): string {
  const count = connection.capabilities?.length ?? 0;
  return count > 0 ? `${count} capability` : "Không";
}

export function connectionCounts(connection: WiiiConnectRuntimeConnection): string {
  return [
    formatCount(connection.attachment_count, "file"),
    formatCount(connection.document_count, "doc"),
    formatCount(connection.source_ref_count, "nguồn"),
    formatCount(connection.target_count, "target"),
    formatCount(connection.tool_count, "tool"),
  ]
    .filter(Boolean)
    .join(" · ");
}

export function toolGroupSummary(names: string[] | undefined): string {
  if (!names || names.length === 0) return "Không";
  const groups = new Set(
    names.map((name) => {
      const lower = name.toLowerCase();
      if (lower.includes("authoring") || lower.includes("lms")) return "LMS";
      if (lower.includes("host")) return "Host";
      if (lower.startsWith("ui.") || lower.includes("pointy")) return "UI";
      if (lower.includes("web") || lower.includes("search")) return "Web";
      if (lower.includes("memory")) return "Memory";
      if (lower.includes("visual")) return "Visual";
      if (lower.includes("code")) return "Code";
      return "Khác";
    }),
  );
  return `${names.length} nhóm (${Array.from(groups).join(", ")})`;
}

export function snapshotStats(snapshot: WiiiConnectRuntimeSnapshot | null) {
  const connections = snapshot?.connections ?? [];
  const pathReadiness = snapshot?.capability_summary?.path_readiness ?? [];
  const readyCount = connections.filter((item) => item.agent_ready).length;
  const warningCount =
    (snapshot?.warnings?.length ?? 0) +
    connections.reduce((total, item) => total + (item.warnings?.length ?? 0), 0);
  return {
    total: connections.length,
    ready: readyCount,
    warningCount,
    pathCount: snapshot?.path_capabilities?.length ?? pathReadiness.length,
    readyPathCount: pathReadiness.filter((item) => item.status === "ready").length,
    guardedPathCount: pathReadiness.filter((item) => item.status === "guarded").length,
    blockedPathCount: pathReadiness.filter((item) => item.status === "blocked").length,
  };
}

export function capabilityPathStatusSummary(
  snapshot: WiiiConnectRuntimeSnapshot | null,
): string {
  const paths = snapshot?.capability_summary?.path_readiness ?? [];
  if (paths.length === 0) return "Chưa có";
  const ready = paths.filter((path) => path.status === "ready").length;
  const guarded = paths.filter((path) => path.status === "guarded").length;
  const blocked = paths.filter((path) => path.status === "blocked").length;
  return `${ready}/${paths.length} ready · ${guarded} guarded · ${blocked} blocked`;
}

export function capabilityAttentionPath(
  snapshot: WiiiConnectRuntimeSnapshot | null,
): string {
  const paths = snapshot?.capability_summary?.path_readiness ?? [];
  const path = paths.find((item) => item.status !== "ready") ?? paths[0];
  if (!path) return "Không";
  return `${compactText(path.path)}: ${compactText(path.status)} (${compactText(path.reason)})`;
}
