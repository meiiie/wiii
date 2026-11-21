import { Activity, AlertTriangle, Lock, Network } from "lucide-react";
import type { WiiiConnectRuntimeConnection, WiiiConnectRuntimeSnapshot } from "@/api/types";
import type { CapabilityDashboardSection } from "@/lib/capability-status";
import { connectionIconBySlug } from "./catalog-data";
import {
  capabilityCount,
  compactText,
  connectionCounts,
  connectionTone,
  formatDateTime,
  pathList,
  providerKindLabels,
  scopeSummary,
  statusLabel,
} from "./connect-display";
import { StatusPill } from "./ConnectStatus";

const externalProviderRows = [
  {
    provider: "Composio",
    kind: "composio",
    state: "Adapter chưa bật",
    note: "Dùng cho Facebook, Gmail, Notion, Slack khi có policy/vault.",
  },
  {
    provider: "MCP",
    kind: "mcp",
    state: "Adapter chưa bật",
    note: "Dùng cho server local/remote sau khi có permission gate.",
  },
  {
    provider: "OAuth riêng",
    kind: "custom_oauth",
    state: "Chưa triển khai",
    note: "Dùng khi Wiii tự sở hữu app, review quyền và token vault.",
  },
  {
    provider: "Workflow",
    kind: "workflow",
    state: "Chưa triển khai",
    note: "Dùng cho Activepieces, n8n, Windmill, Pipedream-like bridge.",
  },
];

export function ConnectionsGrid({
  connections,
  snapshot,
}: {
  connections: WiiiConnectRuntimeConnection[];
  snapshot: WiiiConnectRuntimeSnapshot | null;
}) {
  if (connections.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-surface-secondary px-4 py-8 text-sm text-text-secondary">
        Chưa có snapshot Wiii Connect từ backend. Trang đang chờ lượt chat runtime tiếp theo.
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {connections.map((connection) => {
        const Icon = connectionIconBySlug[connection.slug] ?? Network;
        const tone = connectionTone(connection);
        const counts = connectionCounts(connection);
        return (
          <article
            key={`${connection.provider_kind ?? "provider"}-${connection.slug}`}
            className="min-w-0 rounded-lg border border-[var(--border)] bg-surface p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-surface-secondary text-text-secondary">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-text">
                    {connection.label || connection.slug}
                  </h3>
                  <p className="mt-0.5 truncate text-xs text-text-tertiary">
                    {providerKindLabels[connection.provider_kind ?? ""] ?? compactText(connection.provider_kind, "Provider")}
                  </p>
                </div>
              </div>
              <StatusPill tone={tone}>{statusLabel(connection.status)}</StatusPill>
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <div className="min-w-0 rounded-md bg-surface-secondary px-2 py-2">
                <dt className="text-text-tertiary">Agent-ready</dt>
                <dd className="mt-0.5 truncate font-medium text-text">
                  {connection.agent_ready ? "Có" : "Chưa"}
                </dd>
              </div>
              <div className="min-w-0 rounded-md bg-surface-secondary px-2 py-2">
                <dt className="text-text-tertiary">Scope</dt>
                <dd className="mt-0.5 truncate font-medium text-text">
                  {scopeSummary(connection.scopes)}
                </dd>
              </div>
              <div className="min-w-0 rounded-md bg-surface-secondary px-2 py-2">
                <dt className="text-text-tertiary">Capability</dt>
                <dd className="mt-0.5 truncate font-medium text-text">
                  {capabilityCount(connection)}
                </dd>
              </div>
              <div className="min-w-0 rounded-md bg-surface-secondary px-2 py-2">
                <dt className="text-text-tertiary">Path dùng</dt>
                <dd className="mt-0.5 truncate font-medium text-text">
                  {pathList(connection.required_for_paths)}
                </dd>
              </div>
            </dl>

            <div className="mt-3 space-y-1.5 text-xs text-text-secondary">
              <div className="flex min-w-0 justify-between gap-3">
                <span className="shrink-0 text-text-tertiary">Nguồn</span>
                <span className="truncate">{compactText(connection.source)}</span>
              </div>
              <div className="flex min-w-0 justify-between gap-3">
                <span className="shrink-0 text-text-tertiary">Kiểm tra</span>
                <span className="truncate">{formatDateTime(connection.last_checked_at)}</span>
              </div>
              {counts && (
                <div className="flex min-w-0 justify-between gap-3">
                  <span className="shrink-0 text-text-tertiary">Tài nguyên</span>
                  <span className="truncate">{counts}</span>
                </div>
              )}
              {connection.reason && (
                <div className="flex min-w-0 justify-between gap-3">
                  <span className="shrink-0 text-text-tertiary">Lý do</span>
                  <span className="truncate">{compactText(connection.reason)}</span>
                </div>
              )}
            </div>

            {connection.warnings && connection.warnings.length > 0 && (
              <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-xs text-amber-800">
                {connection.warnings.length} cảnh báo trong connection này.
              </div>
            )}
          </article>
        );
      })}

      {snapshot?.warnings && snapshot.warnings.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 md:col-span-2 xl:col-span-3">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle size={16} aria-hidden="true" />
            Snapshot có {snapshot.warnings.length} cảnh báo cần kiểm tra.
          </div>
        </div>
      )}
    </div>
  );
}

export function ProviderRoadmap() {
  return (
    <section className="mt-6">
      <div className="mb-3 flex items-center gap-2">
        <Lock size={16} className="text-text-secondary" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-text">Provider adapter chưa bật</h3>
      </div>
      <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-surface">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-[var(--border)] bg-surface-secondary text-xs uppercase text-text-tertiary">
            <tr>
              <th className="px-3 py-2 font-medium">Provider</th>
              <th className="px-3 py-2 font-medium">Kind</th>
              <th className="px-3 py-2 font-medium">Trạng thái</th>
              <th className="px-3 py-2 font-medium">Ghi chú</th>
            </tr>
          </thead>
          <tbody>
            {externalProviderRows.map((row) => (
              <tr key={row.provider} className="border-b border-[var(--border)] last:border-b-0">
                <td className="px-3 py-3 font-medium text-text">{row.provider}</td>
                <td className="px-3 py-3 text-text-secondary">
                  {providerKindLabels[row.kind] ?? row.kind}
                </td>
                <td className="px-3 py-3">
                  <StatusPill tone="off">{row.state}</StatusPill>
                </td>
                <td className="px-3 py-3 text-text-secondary">{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function LocalRuntimeFallback({
  sections,
}: {
  sections: CapabilityDashboardSection[];
}) {
  return (
    <section className="mt-6">
      <div className="mb-3 flex items-center gap-2">
        <Activity size={16} className="text-text-secondary" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-text">Fallback cục bộ</h3>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {sections.slice(0, 5).map((section) => (
          <article
            key={section.id}
            className="min-w-0 rounded-lg border border-[var(--border)] bg-surface p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h4 className="truncate text-sm font-semibold text-text">
                  {section.title}
                </h4>
                <p className="mt-0.5 truncate text-xs text-text-tertiary">
                  {section.summary}
                </p>
              </div>
              <StatusPill tone={section.tone}>{section.summary}</StatusPill>
            </div>
            <dl className="mt-3 grid gap-2 text-xs">
              {section.metrics.slice(0, 4).map((metric, index) => (
                <div
                  key={`${section.id}-${metric.label}-${index}`}
                  className="min-w-0 rounded-md bg-surface-secondary px-2 py-2"
                >
                  <dt className="text-text-tertiary">{metric.label}</dt>
                  <dd className="mt-0.5 truncate font-medium text-text">
                    {metric.value}
                  </dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
