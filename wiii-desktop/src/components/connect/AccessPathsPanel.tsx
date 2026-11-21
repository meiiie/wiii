import type { WiiiConnectRuntimePathCapability, WiiiConnectRuntimeSnapshot } from "@/api/types";
import {
  capabilityAttentionPath,
  capabilityPathStatusSummary,
  compactText,
  delegationPolicyLabels,
  mutationPolicyLabels,
  pathList,
} from "./connect-display";
import { StatusPill } from "./ConnectStatus";

export function CapabilitySummaryPanel({
  snapshot,
}: {
  snapshot: WiiiConnectRuntimeSnapshot | null;
}) {
  const summary = snapshot?.capability_summary;
  if (!summary) return null;

  const rows: Array<[string, string]> = [
    ["Provider đã nối", pathList(summary.connected_provider_slugs)],
    ["Provider agent-ready", pathList(summary.agent_ready_provider_slugs)],
    ["Scope đã cấp", pathList(summary.connected_scope_names)],
    ["Path readiness", capabilityPathStatusSummary(snapshot)],
    ["Path cần chú ý", capabilityAttentionPath(snapshot)],
    ["Tool group bị chặn", pathList(summary.suppressed_tool_groups)],
  ];

  return (
    <section
      className="mb-4 rounded-lg border border-[var(--border)] bg-surface p-4"
      data-testid="wiii-connect-capability-summary"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text">Capability snapshot</h3>
          <p className="mt-0.5 truncate text-xs text-text-tertiary">
            Connection, scope, path-ready và tool suppression do backend snapshot sở hữu.
          </p>
        </div>
        <StatusPill
          tone={
            (summary.path_readiness ?? []).some((path) => path.status === "blocked")
              ? "warn"
              : "ok"
          }
        >
          {capabilityPathStatusSummary(snapshot)}
        </StatusPill>
      </div>
      <dl className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
            <dt className="text-xs text-text-tertiary">{label}</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function PathPolicyTable({
  paths,
}: {
  paths: WiiiConnectRuntimePathCapability[];
}) {
  if (paths.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-surface-secondary px-4 py-8 text-sm text-text-secondary">
        Chưa có path policy trong snapshot runtime.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-surface">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-[var(--border)] bg-surface-secondary text-xs uppercase text-text-tertiary">
          <tr>
            <th className="px-3 py-2 font-medium">Path</th>
            <th className="px-3 py-2 font-medium">Kết nối bắt buộc</th>
            <th className="px-3 py-2 font-medium">Tool group được phép</th>
            <th className="px-3 py-2 font-medium">Tool group bị chặn</th>
            <th className="px-3 py-2 font-medium">Mutation</th>
            <th className="px-3 py-2 font-medium">Delegation</th>
          </tr>
        </thead>
        <tbody>
          {paths.map((path) => (
            <tr key={path.path} className="border-b border-[var(--border)] last:border-b-0">
              <td className="px-3 py-3 font-medium text-text">{path.path}</td>
              <td className="px-3 py-3 text-text-secondary">
                {pathList(path.required_connection_slugs)}
              </td>
              <td className="px-3 py-3 text-text-secondary">
                {pathList(path.allowed_tool_groups)}
              </td>
              <td className="px-3 py-3 text-text-secondary">
                {pathList(path.forbidden_tool_groups)}
              </td>
              <td className="px-3 py-3">
                <StatusPill
                  tone={
                    path.mutation_policy === "approval_token_required" ||
                    path.mutation_policy === "explicit_user_confirmation_required"
                      ? "warn"
                      : path.mutation_policy === "preview_only"
                        ? "pending"
                        : "ok"
                  }
                >
                  {mutationPolicyLabels[path.mutation_policy ?? "none"] ?? compactText(path.mutation_policy)}
                </StatusPill>
              </td>
              <td className="px-3 py-3 text-text-secondary">
                {delegationPolicyLabels[path.delegation_policy ?? "direct_only"] ?? compactText(path.delegation_policy)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
