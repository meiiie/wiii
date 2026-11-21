import { Database } from "lucide-react";
import type {
  SemanticMemoryWriteDoctorHistoryReport,
  SemanticMemoryWriteDoctorReport,
} from "@/api/types/runtime-diagnostics";
import { formatDateTime } from "./connect-display";
import { StatusPill } from "./ConnectStatus";
import {
  countMapEntries,
  doctorStatusTone,
  safeRuntimeDoctorCounterLabel,
  semanticMemoryDoctorMetric,
} from "./runtime-doctor-model";

export function SemanticMemoryDoctorPanel({
  report,
  error,
  historyReport,
  historyError,
}: {
  report: SemanticMemoryWriteDoctorReport | null;
  error?: string;
  historyReport: SemanticMemoryWriteDoctorHistoryReport | null;
  historyError?: string;
}) {
  const writeKindEntries = countMapEntries(report?.write_kinds, 4);
  const statusEntries = countMapEntries(report?.write_statuses, 4);
  const orgContextEntries = countMapEntries(report?.organization_contexts, 4);
  const warningEntries = countMapEntries(report?.warnings, 4);
  const historyBuckets = historyReport?.buckets?.slice(0, 8) ?? [];
  const backend = safeRuntimeDoctorCounterLabel(report?.runtime_config?.session_event_log_backend);
  const privacyStrategy = safeRuntimeDoctorCounterLabel(report?.privacy?.identifier_strategy);
  const historyPrivacyStrategy = safeRuntimeDoctorCounterLabel(
    historyReport?.privacy?.identifier_strategy,
  );

  return (
    <section
      className="rounded-lg border border-[var(--border)] bg-surface p-4 lg:col-span-2"
      data-testid="wiii-connect-semantic-memory-doctor-panel"
    >
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Database size={16} className="text-text-secondary" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-text">Semantic memory doctor</h3>
          </div>
          <p className="mt-1 text-xs text-text-secondary">
            {error
              ? "Backend semantic-memory doctor is unavailable."
              : report
                ? "Post-turn memory write audits, aggregate counts only."
                : "Waiting for semantic-memory doctor report."}
          </p>
        </div>
        <StatusPill tone={doctorStatusTone(report?.status)}>
          {report?.status ?? (error ? "unavailable" : "checking")}
        </StatusPill>
      </div>

      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Writes</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {semanticMemoryDoctorMetric(report, "write_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Facts</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {semanticMemoryDoctorMetric(report, "stored_fact_total")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Insights</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {semanticMemoryDoctorMetric(report, "stored_insight_total")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Blocked</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {semanticMemoryDoctorMetric(report, "blocked_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Warnings</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {semanticMemoryDoctorMetric(report, "warning_count")}
          </dd>
        </div>
        <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
          <dt className="text-xs text-text-tertiary">Raw flags</dt>
          <dd className="mt-0.5 truncate text-sm font-medium text-text">
            {semanticMemoryDoctorMetric(report, "raw_content_flag_count")}
          </dd>
        </div>
      </dl>

      <div className="mt-3 grid gap-3 lg:grid-cols-4">
        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Write kinds</div>
          <ul className="v3-space-y-1 text-sm text-text-secondary">
            {writeKindEntries.length > 0 ? writeKindEntries.map(([label, count], index) => (
              <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                <span className="truncate">{label}</span>
                <span className="font-medium text-text">{count}</span>
              </li>
            )) : <li>None</li>}
          </ul>
        </div>

        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Statuses</div>
          <ul className="v3-space-y-1 text-sm text-text-secondary">
            {statusEntries.length > 0 ? statusEntries.map(([label, count], index) => (
              <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                <span className="truncate">{label}</span>
                <span className="font-medium text-text">{count}</span>
              </li>
            )) : <li>None</li>}
          </ul>
        </div>

        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Org context</div>
          <ul className="v3-space-y-1 text-sm text-text-secondary">
            {orgContextEntries.length > 0 ? orgContextEntries.map(([label, count], index) => (
              <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                <span className="truncate">{label}</span>
                <span className="font-medium text-text">{count}</span>
              </li>
            )) : <li>None</li>}
          </ul>
        </div>

        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="mb-2 text-xs font-medium uppercase text-text-tertiary">Warnings</div>
          <ul className="v3-space-y-1 text-sm text-text-secondary">
            {warningEntries.length > 0 ? warningEntries.map(([label, count], index) => (
              <li key={`${label}-${index}`} className="flex min-w-0 justify-between gap-3">
                <span className="truncate">{label}</span>
                <span className="font-medium text-text">{count}</span>
              </li>
            )) : <li>None</li>}
          </ul>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-[var(--border)] bg-surface-secondary p-3">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-text">Memory write history</div>
            <p className="mt-1 text-xs text-text-secondary">
              Recent write doctor buckets grouped by event hour.
            </p>
          </div>
          <StatusPill tone={historyError ? "warn" : historyBuckets.length > 0 ? "ok" : "off"}>
            {historyError ? "unavailable" : `${historyBuckets.length} buckets`}
          </StatusPill>
        </div>

        <div
          className="mt-3 overflow-x-auto rounded-lg border border-[var(--border)] bg-surface"
          data-testid="wiii-connect-semantic-memory-doctor-history"
        >
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-[var(--border)] bg-surface-secondary text-xs uppercase text-text-tertiary">
              <tr>
                <th className="px-3 py-2 font-medium">Bucket</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Writes</th>
                <th className="px-3 py-2 font-medium">Facts</th>
                <th className="px-3 py-2 font-medium">Insights</th>
                <th className="px-3 py-2 font-medium">Blocked</th>
                <th className="px-3 py-2 font-medium">Top kind</th>
                <th className="px-3 py-2 font-medium">Warnings</th>
              </tr>
            </thead>
            <tbody>
              {historyBuckets.length > 0 ? historyBuckets.map((bucket) => {
                const topKind = countMapEntries(bucket.write_kinds, 1)[0];
                const warnings = countMapEntries(bucket.warnings, 2)
                  .map(([label, count]) => `${label} ${count}`)
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
                      {bucket.summary?.write_count ?? 0}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {bucket.summary?.stored_fact_total ?? 0}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {bucket.summary?.stored_insight_total ?? 0}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {bucket.summary?.blocked_count ?? 0}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {topKind ? `${topKind[0]} ${topKind[1]}` : "None"}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {warnings || "None"}
                    </td>
                  </tr>
                );
              }) : (
                <tr>
                  <td className="px-3 py-3 text-text-secondary" colSpan={8}>
                    {historyError
                      ? "Backend semantic-memory history is unavailable."
                      : "No semantic-memory doctor history."}
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
            Events: {historyReport?.source?.semantic_memory_write_event_count ?? 0}/
            {historyReport?.source?.session_event_count ?? 0}
          </div>
          <div>Privacy: {historyPrivacyStrategy}</div>
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-xs text-text-tertiary sm:grid-cols-3">
        <div>Backend: {backend}</div>
        <div>Privacy: {privacyStrategy}</div>
        <div>
          Events: {report?.source?.semantic_memory_write_event_count ?? 0}/
          {report?.source?.session_event_count ?? 0}
        </div>
      </div>
    </section>
  );
}
