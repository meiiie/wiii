import { Activity, AlertTriangle, Database, Loader2, RefreshCw } from "lucide-react";
import type {
  RuntimeFlowDoctorHistoryReport,
  RuntimeFlowDoctorReport,
  RuntimeFlowSessionEventPruneReport,
} from "@/api/types/runtime-diagnostics";
import type { CapabilityStatusTone } from "@/lib/capability-status";
import { formatDateTime } from "./connect-display";
import { StatusPill } from "./ConnectStatus";
import {
  countMapEntries,
  doctorStatusTone,
  runtimeDoctorAlertTone,
  runtimeDoctorConfigNumber,
  runtimeDoctorCorrelationMetric,
  runtimeDoctorMetric,
  runtimeDoctorSubagentMetric,
  safeRuntimeDoctorCounterLabel,
} from "./runtime-doctor-model";

const RUNTIME_POST_TURN_LIFECYCLE_METRICS_SCHEMA = "wiii.post_turn_lifecycle_metrics.v1";

const RUNTIME_POST_TURN_LIFECYCLE_LEDGER_SCHEMA = "wiii.post_turn_lifecycle_ledger.v1";

export function RecentRuntimeFlowDoctorPanel({
  report,
  error,
  historyReport,
  historyError,
  pruneReport,
  pruneLoading,
  pruneError,
  onPruneDryRun,
  onPruneApply,
}: {
  report: RuntimeFlowDoctorReport | null;
  error?: string;
  historyReport: RuntimeFlowDoctorHistoryReport | null;
  historyError?: string;
  pruneReport: RuntimeFlowSessionEventPruneReport | null;
  pruneLoading?: boolean;
  pruneError?: string;
  onPruneDryRun?: () => void;
  onPruneApply?: () => void;
}) {
  const alerts = report?.alerts?.slice(0, 4) ?? [];
  const routeEntries = countMapEntries(report?.routes);
  const finalizationEntries = countMapEntries(report?.finalization_statuses, 4);
  const warningEntries = countMapEntries(report?.context_warnings, 4);
  const subagentWarningEntries = countMapEntries(report?.subagents?.warnings, 4);
  const latestBuckets = report?.alert_trend?.buckets?.slice(0, 3) ?? [];
  const historyBuckets = historyReport?.buckets?.slice(0, 8) ?? [];
  const backend = safeRuntimeDoctorCounterLabel(report?.runtime_config?.session_event_log_backend);
  const lifecycle = report?.lifecycle_registrations;
  const postTurnLifecycle = report?.post_turn_lifecycle;
  const postTurnLifecycleLedger = report?.post_turn_lifecycle_ledger;
  const postTurnStatusEntries = countMapEntries(postTurnLifecycle?.post_turn?.status_counts, 4);
  const postTurnReasonEntries = countMapEntries(postTurnLifecycle?.post_turn?.reason_counts, 4);
  const postTurnPolicyEntries = countMapEntries(
    postTurnLifecycle?.post_turn?.semantic_memory_policy_counts,
    4,
  );
  const backgroundGroupEntries = countMapEntries(
    postTurnLifecycle?.background_tasks?.group_counts,
    4,
  );
  const backgroundStatusEntries = countMapEntries(
    postTurnLifecycle?.background_tasks?.status_counts,
    4,
  );
  const ledgerBackgroundGroupEntries = countMapEntries(
    postTurnLifecycleLedger?.background_schedule?.group_counts,
    4,
  );
  const ledgerBackgroundStatusEntries = countMapEntries(
    postTurnLifecycleLedger?.background_schedule?.status_counts,
    4,
  );
  const lifecycleOwnerFallback = Object.values(lifecycle?.owner_counts ?? {}).filter(
    (count) => typeof count === "number" && Number.isFinite(count),
  ).length;
  const lifecycleHookTotal =
    runtimeDoctorConfigNumber(report, "lifecycle_hook_total") ??
    lifecycle?.registration_count ??
    0;
  const lifecycleOwnerCount =
    runtimeDoctorConfigNumber(report, "lifecycle_hook_owner_count") ??
    lifecycleOwnerFallback;
  const lifecycleRunEndCount =
    runtimeDoctorConfigNumber(report, "lifecycle_on_run_end_hook_count") ??
    lifecycle?.point_counts?.["on_run_end"] ??
    0;
  const lifecycleRunErrorCount =
    runtimeDoctorConfigNumber(report, "lifecycle_on_run_error_hook_count") ??
    lifecycle?.point_counts?.["on_run_error"] ??
    0;
  const lifecycleDefaultStatus = lifecycle?.default_runtime_hooks?.installed
    ? "installed"
    : lifecycle
      ? "missing"
      : "unknown";
  const lifecycleDefaultTone: CapabilityStatusTone =
    lifecycleDefaultStatus === "installed" ? "ok" : lifecycle ? "warn" : "off";
  const lifecyclePrivacyStrategy = safeRuntimeDoctorCounterLabel(
    lifecycle?.privacy?.identifier_strategy,
  );
  const postTurnPrivacyStrategy = safeRuntimeDoctorCounterLabel(
    postTurnLifecycle?.privacy?.identifier_strategy,
  );
  const postTurnSchema = safeRuntimeDoctorCounterLabel(
    postTurnLifecycle?.version ?? RUNTIME_POST_TURN_LIFECYCLE_METRICS_SCHEMA,
  );
  const postTurnLedgerSchema = safeRuntimeDoctorCounterLabel(
    postTurnLifecycleLedger?.version ?? RUNTIME_POST_TURN_LIFECYCLE_LEDGER_SCHEMA,
  );
  const postTurnWindow = safeRuntimeDoctorCounterLabel(postTurnLifecycle?.source?.window);
  const postTurnScope = postTurnLifecycle?.source?.org_scoped ? "org-scoped" : "process-wide";
  const postTurnLedgerWindow =
    postTurnLifecycleLedger?.source?.window === "runtime_flow_ledger_events"
      ? "ledger_events"
      : safeRuntimeDoctorCounterLabel(postTurnLifecycleLedger?.source?.window);
  const postTurnLedgerPrivacyStrategy = safeRuntimeDoctorCounterLabel(
    postTurnLifecycleLedger?.privacy?.identifier_strategy,
  );
  const privacyStrategy = safeRuntimeDoctorCounterLabel(report?.privacy?.identifier_strategy);
  const historyPrivacyStrategy = safeRuntimeDoctorCounterLabel(
    historyReport?.privacy?.identifier_strategy,
  );
  const matchedCount = pruneReport?.matched_count ?? 0;
  const deletedCount = pruneReport?.deleted_count ?? 0;
  const canApplyPrune =
    Boolean(pruneReport?.dry_run) &&
    matchedCount > 0 &&
    !pruneLoading &&
    !error &&
    Boolean(report);
  const pruneStatus = pruneError
    ? "unavailable"
    : pruneReport?.status ?? "not_checked";
  const pruneTone: CapabilityStatusTone = pruneError
    ? "warn"
    : pruneReport?.status === "pruned"
      ? "ok"
      : pruneReport?.dry_run
        ? "pending"
        : "off";

  return (
    <section
      className="rounded-lg border border-[var(--border)] bg-surface p-4 lg:col-span-2"
      data-testid="wiii-connect-runtime-flow-doctor-panel"
    >
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-text-secondary" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-text">Aggregate runtime doctor</h3>
          </div>
          <p className="mt-1 text-xs text-text-secondary">
            {error
              ? "Chưa đọc được aggregate doctor report từ backend."
              : report
                ? "Recent runtime-flow ledger events, aggregate counts only."
                : "Đang chờ aggregate doctor report từ backend."}
          </p>
        </div>
        <StatusPill tone={doctorStatusTone(report?.status)}>
          {report?.status ?? (error ? "unavailable" : "checking")}
        </StatusPill>
      </div>

      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Turns</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {runtimeDoctorMetric(report, "turn_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Done seen</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {runtimeDoctorMetric(report, "done_seen_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Missing request ID</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {runtimeDoctorCorrelationMetric(report, "missing_request_id_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Raw content flags</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {runtimeDoctorMetric(report, "raw_content_flag_count")}
          </dd>
        </div>
      </dl>

      <dl className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Subagent reports</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {runtimeDoctorSubagentMetric(report, "report_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Dropped keys</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {runtimeDoctorSubagentMetric(report, "state_dropped_key_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Thinking dropped</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {runtimeDoctorSubagentMetric(report, "thinking_dropped_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Subagent raw flags</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {runtimeDoctorSubagentMetric(report, "raw_content_flag_count")}
          </dd>
        </div>
      </dl>

      <dl
        className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4"
        data-testid="wiii-connect-runtime-lifecycle-hooks"
      >
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Lifecycle hooks</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {lifecycleHookTotal} hooks / {lifecycleOwnerCount} owners
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Default hooks</dt>
          <dd className="mt-0.5">
            <StatusPill tone={lifecycleDefaultTone}>{lifecycleDefaultStatus}</StatusPill>
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Run hooks</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            end {lifecycleRunEndCount} / error {lifecycleRunErrorCount}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Hook privacy</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {lifecyclePrivacyStrategy}
          </dd>
        </div>
      </dl>

      <div
        className="mt-3 rounded-lg border border-[var(--border)] bg-surface-secondary p-3"
        data-testid="wiii-connect-runtime-post-turn-lifecycle"
      >
        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-text">Post-turn lifecycle</div>
            <p className="mt-1 text-xs text-text-secondary">
              Metrics {postTurnSchema} / ledger {postTurnLedgerSchema}
            </p>
          </div>
          <StatusPill tone={postTurnLifecycle ? "ok" : "off"}>
            {postTurnLifecycle ? "metrics" : "missing"}
          </StatusPill>
        </div>

        <dl className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="min-w-0 rounded-md bg-surface px-3 py-2">
            <dt className="text-xs text-text-tertiary">Post-turn events</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {postTurnLifecycle?.post_turn?.event_count ?? 0}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface px-3 py-2">
            <dt className="text-xs text-text-tertiary">Background events</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {postTurnLifecycle?.background_tasks?.event_count ?? 0}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface px-3 py-2">
            <dt className="text-xs text-text-tertiary">Metric window</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {postTurnWindow}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface px-3 py-2">
            <dt className="text-xs text-text-tertiary">Metric scope</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {postTurnScope}
            </dd>
          </div>
        </dl>

        <dl className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="min-w-0 rounded-md bg-surface px-3 py-2">
            <dt className="text-xs text-text-tertiary">Durable events</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {postTurnLifecycleLedger?.event_count ?? 0}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface px-3 py-2">
            <dt className="text-xs text-text-tertiary">Missing ledger</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {postTurnLifecycleLedger?.missing_count ?? 0}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface px-3 py-2">
            <dt className="text-xs text-text-tertiary">Scheduled turns</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {postTurnLifecycleLedger?.background_tasks_scheduled_count ?? 0}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface px-3 py-2">
            <dt className="text-xs text-text-tertiary">Durable task count</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {postTurnLifecycleLedger?.background_schedule?.task_count ?? 0}
            </dd>
          </div>
        </dl>

        <div className="mt-3 grid gap-3 lg:grid-cols-5">
          <div className="rounded-md bg-surface p-3">
            <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Status</div>
            <ul className="space-y-1 text-sm text-text-secondary">
              {postTurnStatusEntries.length > 0 ? postTurnStatusEntries.map(([label, count], index) => (
                <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                  <span className="truncate">{label}</span>
                  <span className="font-medium text-text">{count}</span>
                </li>
              )) : <li>KhÃ´ng</li>}
            </ul>
          </div>
          <div className="rounded-md bg-surface p-3">
            <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Reasons</div>
            <ul className="space-y-1 text-sm text-text-secondary">
              {postTurnReasonEntries.length > 0 ? postTurnReasonEntries.map(([label, count], index) => (
                <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                  <span className="truncate">{label}</span>
                  <span className="font-medium text-text">{count}</span>
                </li>
              )) : <li>KhÃ´ng</li>}
            </ul>
          </div>
          <div className="rounded-md bg-surface p-3">
            <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Memory policy</div>
            <ul className="space-y-1 text-sm text-text-secondary">
              {postTurnPolicyEntries.length > 0 ? postTurnPolicyEntries.map(([label, count], index) => (
                <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                  <span className="truncate">{label}</span>
                  <span className="font-medium text-text">{count}</span>
                </li>
              )) : <li>KhÃ´ng</li>}
            </ul>
          </div>
          <div className="rounded-md bg-surface p-3">
            <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Task groups</div>
            <ul className="space-y-1 text-sm text-text-secondary">
              {backgroundGroupEntries.length > 0 ? backgroundGroupEntries.map(([label, count], index) => (
                <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                  <span className="truncate">{label}</span>
                  <span className="font-medium text-text">{count}</span>
                </li>
              )) : <li>KhÃ´ng</li>}
            </ul>
          </div>
          <div className="rounded-md bg-surface p-3">
            <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Task status</div>
            <ul className="space-y-1 text-sm text-text-secondary">
              {backgroundStatusEntries.length > 0 ? backgroundStatusEntries.map(([label, count], index) => (
                <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                  <span className="truncate">{label}</span>
                  <span className="font-medium text-text">{count}</span>
                </li>
              )) : <li>KhÃ´ng</li>}
            </ul>
          </div>
        </div>

        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <div className="rounded-md bg-surface p-3">
            <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Durable task groups</div>
            <ul className="space-y-1 text-sm text-text-secondary">
              {ledgerBackgroundGroupEntries.length > 0 ? ledgerBackgroundGroupEntries.map(([label, count], index) => (
                <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                  <span className="truncate">{label}</span>
                  <span className="font-medium text-text">{count}</span>
                </li>
              )) : <li>KhÃƒÂ´ng</li>}
            </ul>
          </div>
          <div className="rounded-md bg-surface p-3">
            <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Durable task status</div>
            <ul className="space-y-1 text-sm text-text-secondary">
              {ledgerBackgroundStatusEntries.length > 0 ? ledgerBackgroundStatusEntries.map(([label, count], index) => (
                <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                  <span className="truncate">{label}</span>
                  <span className="font-medium text-text">{count}</span>
                </li>
              )) : <li>KhÃƒÂ´ng</li>}
            </ul>
          </div>
        </div>

        <div className="mt-2 grid gap-2 text-xs text-text-tertiary sm:grid-cols-3">
          <div>
            Backend: {safeRuntimeDoctorCounterLabel(postTurnLifecycle?.source?.metrics_backend)}
          </div>
          <div>Privacy: {postTurnPrivacyStrategy}</div>
          <div>
            Raw content: {postTurnLifecycle?.privacy?.raw_content_included ? "true" : "false"}
          </div>
          <div>Ledger window: {postTurnLedgerWindow}</div>
          <div>Ledger privacy: {postTurnLedgerPrivacyStrategy}</div>
          <div>
            Ledger raw content: {postTurnLifecycleLedger?.privacy?.raw_content_included ? "true" : "false"}
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-4">
        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Routes</div>
          <ul className="space-y-1 text-sm text-text-secondary">
            {routeEntries.length > 0 ? routeEntries.map(([label, count], index) => (
              <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                <span className="truncate">{label}</span>
                <span className="font-medium text-text">{count}</span>
              </li>
            )) : <li>Không</li>}
          </ul>
        </div>

        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Finalization</div>
          <ul className="space-y-1 text-sm text-text-secondary">
            {finalizationEntries.length > 0 ? finalizationEntries.map(([label, count], index) => (
              <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                <span className="truncate">{label}</span>
                <span className="font-medium text-text">{count}</span>
              </li>
            )) : <li>Không</li>}
          </ul>
        </div>

        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Context warnings</div>
          <ul className="space-y-1 text-sm text-text-secondary">
            {warningEntries.length > 0 ? warningEntries.map(([label, count], index) => (
              <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                <span className="truncate">{label}</span>
                <span className="font-medium text-text">{count}</span>
              </li>
            )) : <li>Không</li>}
          </ul>
        </div>

        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Subagent warnings</div>
          <ul className="space-y-1 text-sm text-text-secondary">
            {subagentWarningEntries.length > 0 ? subagentWarningEntries.map(([label, count], index) => (
              <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                <span className="truncate">{label}</span>
                <span className="font-medium text-text">{count}</span>
              </li>
            )) : <li>KhÃ´ng</li>}
          </ul>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {alerts.map((alert, index) => (
            <div
              key={`${alert.code}-${index}`}
              className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
            >
              <div className="flex min-w-0 items-center justify-between gap-2">
                <span className="truncate font-medium">
                  {safeRuntimeDoctorCounterLabel(alert.code)}
                </span>
                <StatusPill tone={runtimeDoctorAlertTone(alert.severity)}>
                  {safeRuntimeDoctorCounterLabel(alert.severity)}
                </StatusPill>
              </div>
              <div className="mt-1 text-xs">
                count {typeof alert.count === "number" ? alert.count : 0}
              </div>
            </div>
          ))}
        </div>
      )}

      {latestBuckets.length > 0 && (
        <div className="mt-3 overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="border-b border-[var(--border)] bg-surface-secondary text-xs uppercase text-text-tertiary">
              <tr>
                <th className="px-3 py-2 font-medium">Bucket</th>
                <th className="px-3 py-2 font-medium">Turns</th>
                <th className="px-3 py-2 font-medium">Alerts</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {latestBuckets.map((bucket) => (
                <tr key={bucket.bucket_start} className="border-b border-[var(--border)] last:border-b-0">
                  <td className="px-3 py-2 font-medium text-text">
                    {formatDateTime(bucket.bucket_start)}
                  </td>
                  <td className="px-3 py-2 text-text-secondary">{bucket.turn_count}</td>
                  <td className="px-3 py-2 text-text-secondary">
                    {countMapEntries(bucket.alert_counts, 3)
                      .map(([label, count]) => `${label} ${count}`)
                      .join(", ") || "Không"}
                  </td>
                  <td className="px-3 py-2 text-text-secondary">
                    {countMapEntries(bucket.status_counts, 3)
                      .map(([label, count]) => `${label} ${count}`)
                      .join(", ") || "Không"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 rounded-lg border border-[var(--border)] bg-surface-secondary p-3">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-text">Doctor history</div>
            <p className="mt-1 text-xs text-text-secondary">
              Recent aggregate doctor reports grouped by event hour.
            </p>
          </div>
          <StatusPill tone={historyError ? "warn" : historyBuckets.length > 0 ? "ok" : "off"}>
            {historyError ? "unavailable" : `${historyBuckets.length} buckets`}
          </StatusPill>
        </div>

        <div
          className="mt-3 overflow-x-auto rounded-lg border border-[var(--border)] bg-surface"
          data-testid="wiii-connect-runtime-flow-doctor-history"
        >
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="border-b border-[var(--border)] bg-surface-secondary text-xs uppercase text-text-tertiary">
              <tr>
                <th className="px-3 py-2 font-medium">Bucket</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Turns</th>
                <th className="px-3 py-2 font-medium">Missing request</th>
                <th className="px-3 py-2 font-medium">Subagents</th>
                <th className="px-3 py-2 font-medium">Alerts</th>
                <th className="px-3 py-2 font-medium">Top route</th>
              </tr>
            </thead>
            <tbody>
              {historyBuckets.length > 0 ? historyBuckets.map((bucket) => {
                const topRoute = countMapEntries(bucket.routes, 1)[0];
                const alertSummary = (bucket.alerts ?? [])
                  .slice(0, 2)
                  .map((alert) => `${safeRuntimeDoctorCounterLabel(alert.code)} ${alert.count ?? 0}`)
                  .join(", ");
                return (
                  <tr
                    key={bucket.bucket_start}
                    className="border-b border-[var(--border)] last:border-b-0"
                  >
                    <td className="px-3 py-2 font-medium text-text">
                      {formatDateTime(bucket.bucket_start)}
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill tone={doctorStatusTone(bucket.status)}>
                        {safeRuntimeDoctorCounterLabel(bucket.status)}
                      </StatusPill>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {bucket.summary?.turn_count ?? 0}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {typeof bucket.request_correlation?.missing_request_id_count === "number"
                        ? bucket.request_correlation.missing_request_id_count
                        : 0}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {`${bucket.subagents?.report_count ?? 0} reports / ${bucket.subagents?.warning_count ?? 0} warnings`}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {alertSummary || "KhÃ´ng"}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {topRoute ? `${topRoute[0]} ${topRoute[1]}` : "KhÃ´ng"}
                    </td>
                  </tr>
                );
              }) : (
                <tr>
                  <td className="px-3 py-3 text-text-secondary" colSpan={7}>
                    {historyError
                      ? "ChÆ°a Ä‘á»c Ä‘Æ°á»£c history report tá»« backend."
                      : "ChÆ°a cÃ³ doctor history."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-2 grid gap-2 text-xs text-text-tertiary sm:grid-cols-3">
          <div>
            Buckets: {historyReport?.source?.bucket_count ?? historyBuckets.length}/
            {historyReport?.source?.bucket_limit ?? 0}
          </div>
          <div>
            Events: {historyReport?.source?.runtime_flow_ledger_event_count ?? 0}/
            {historyReport?.source?.session_event_count ?? 0}
          </div>
          <div>Privacy: {historyPrivacyStrategy}</div>
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-xs text-text-tertiary sm:grid-cols-3">
        <div>Backend: {backend}</div>
        <div>Privacy: {privacyStrategy}</div>
        <div>
          Events: {report?.source?.runtime_flow_ledger_event_count ?? 0}/
          {report?.source?.session_event_count ?? 0}
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-[var(--border)] bg-surface-secondary p-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-semibold text-text">
              <Database size={15} className="text-text-secondary" aria-hidden="true" />
              <span>Session event retention</span>
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              Chạy dry-run trước khi prune ledger cũ; kết quả chỉ là aggregate counts.
            </p>
          </div>
          <StatusPill tone={pruneTone}>{pruneStatus}</StatusPill>
        </div>

        <dl
          className="mt-3 grid gap-2 text-xs sm:grid-cols-4"
          data-testid="wiii-connect-runtime-prune-report"
        >
          <div className="rounded-md bg-surface px-2 py-2">
            <dt className="text-text-tertiary">Matched</dt>
            <dd className="mt-0.5 font-medium text-text">{matchedCount}</dd>
          </div>
          <div className="rounded-md bg-surface px-2 py-2">
            <dt className="text-text-tertiary">Deleted</dt>
            <dd className="mt-0.5 font-medium text-text">{deletedCount}</dd>
          </div>
          <div className="rounded-md bg-surface px-2 py-2">
            <dt className="text-text-tertiary">Retention</dt>
            <dd className="mt-0.5 font-medium text-text">
              {pruneReport?.retention_days ?? "--"} days
            </dd>
          </div>
          <div className="rounded-md bg-surface px-2 py-2">
            <dt className="text-text-tertiary">Scope</dt>
            <dd className="mt-0.5 font-medium text-text">
              {pruneReport?.org_scoped ? "org-scoped" : "aggregate"}
            </dd>
          </div>
        </dl>

        <div className="mt-2 grid gap-2 text-xs text-text-tertiary sm:grid-cols-3">
          <div>
            Cutoff: {pruneReport?.cutoff ? formatDateTime(pruneReport.cutoff) : "Chưa có"}
          </div>
          <div>
            Event filter: {pruneReport?.event_type_filter_applied ? "applied" : "not applied"}
          </div>
          <div>
            Privacy: {safeRuntimeDoctorCounterLabel(pruneReport?.privacy?.identifier_strategy)}
          </div>
        </div>

        {pruneError && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Không thể chạy retention control từ backend.
          </div>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            data-testid="wiii-connect-runtime-prune-dry-run"
            disabled={pruneLoading || Boolean(error) || !report}
            onClick={() => onPruneDryRun?.()}
            className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-[var(--border)] bg-surface px-3 text-sm font-medium text-text-secondary disabled:text-text-tertiary"
          >
            <RefreshCw
              size={14}
              className={pruneLoading ? "animate-spin" : ""}
              aria-hidden="true"
            />
            Dry-run retention
          </button>
          <button
            type="button"
            data-testid="wiii-connect-runtime-prune-apply"
            disabled={!canApplyPrune}
            onClick={() => onPruneApply?.()}
            className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 text-sm font-medium text-rose-700 disabled:border-[var(--border)] disabled:bg-surface disabled:text-text-tertiary"
          >
            {pruneLoading && canApplyPrune ? (
              <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            ) : (
              <AlertTriangle size={14} aria-hidden="true" />
            )}
            Prune matched events
          </button>
        </div>
      </div>
    </section>
  );
}
