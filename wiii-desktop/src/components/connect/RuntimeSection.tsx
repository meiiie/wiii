import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Info,
  Route,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type {
  RuntimeFlowDoctorHistoryReport,
  RuntimeFlowDoctorReport,
  RuntimeFlowSessionEventPruneReport,
  SemanticMemoryWriteDoctorHistoryReport,
  SemanticMemoryWriteDoctorReport,
  WiiiConnectDoctorReport,
} from "@/api/types";
import type { CapabilityStatusTone, RuntimePathSnapshot } from "@/lib/capability-status";
import type {
  RuntimeFlowLedgerViewModel,
  RuntimeFlowTraceViewModel,
} from "@/lib/runtime-flow-trace";
import {
  compactText,
  formatCount,
  formatDateTime,
  pathList,
  statusDotClasses,
  toolGroupSummary,
} from "./connect-display";
import { StatusPill } from "./ConnectStatus";
import { RecentRuntimeFlowDoctorPanel } from "./RecentRuntimeFlowDoctorPanel";
import {
  doctorMetric,
  doctorStatusTone,
  importantDoctorPaths,
  importantDoctorProviders,
  pathDoctorTone,
} from "./runtime-doctor-model";
import { SemanticMemoryDoctorPanel } from "./SemanticMemoryDoctorPanel";

function doctorStageLabel(key: string | undefined): string {
  const labels: Record<string, string> = {
    registry: "Registry",
    adapter: "Adapter",
    account: "Account",
    agent_policy: "Agent policy",
    gateway: "Gateway",
  };
  const normalized = String(key ?? "").trim();
  return labels[normalized] ?? compactText(normalized.replaceAll("_", " "));
}

function providerDoctorCountSummary(
  provider: NonNullable<WiiiConnectDoctorReport["provider_diagnostics"]>[number],
): string {
  return [
    formatCount(provider.connection_count, "kết nối"),
    formatCount(provider.active_connection_count, "active"),
    formatCount(provider.action_count, "action"),
    formatCount(provider.scope_count, "scope"),
  ]
    .filter(Boolean)
    .join(" · ") || "Không";
}

function providerStageTone(status: string | undefined): CapabilityStatusTone {
  if (status === "ready") return "ok";
  if (status === "pending") return "pending";
  if (status === "blocked") return "warn";
  return "off";
}

function DoctorProviderStages({
  provider,
}: {
  provider: NonNullable<WiiiConnectDoctorReport["provider_diagnostics"]>[number];
}) {
  const stages = provider.stages ?? [];
  if (stages.length === 0) {
    return <span className="text-text-tertiary">Chưa có lifecycle</span>;
  }
  return (
    <div className="grid min-w-[280px] gap-1.5">
      {stages.map((stage) => (
        <div
          key={`${provider.provider_slug}-${stage.key}`}
          className="rounded-md border border-[var(--border)] bg-surface-secondary px-2 py-1.5"
        >
          <div className="flex min-w-0 items-center justify-between gap-2">
            <span className="truncate text-xs font-medium text-text">
              {doctorStageLabel(stage.key)}
            </span>
            <StatusPill tone={providerStageTone(stage.status)}>
              {compactText(stage.status)}
            </StatusPill>
          </div>
          <div className="mt-1 truncate text-xs text-text-secondary">
            {compactText(stage.reason)}
          </div>
          {stage.required_next && stage.required_next.length > 0 && (
            <div className="mt-1 truncate text-[11px] text-text-tertiary">
              {pathList(stage.required_next)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function RuntimeSection({
  runtimePath,
  runtimeFlowLedger,
  runtimeFlowTrace,
  doctorReport,
  doctorError,
  recentRuntimeFlowDoctorReport,
  recentRuntimeFlowDoctorError,
  runtimeFlowDoctorHistoryReport,
  runtimeFlowDoctorHistoryError,
  recentSemanticMemoryDoctorReport,
  recentSemanticMemoryDoctorError,
  semanticMemoryDoctorHistoryReport,
  semanticMemoryDoctorHistoryError,
  runtimePruneReport,
  runtimePruneLoading,
  runtimePruneError,
  onRuntimePruneDryRun,
  onRuntimePruneApply,
}: {
  runtimePath: RuntimePathSnapshot | null;
  runtimeFlowLedger: RuntimeFlowLedgerViewModel;
  runtimeFlowTrace: RuntimeFlowTraceViewModel;
  doctorReport: WiiiConnectDoctorReport | null;
  doctorError?: string;
  recentRuntimeFlowDoctorReport: RuntimeFlowDoctorReport | null;
  recentRuntimeFlowDoctorError?: string;
  runtimeFlowDoctorHistoryReport: RuntimeFlowDoctorHistoryReport | null;
  runtimeFlowDoctorHistoryError?: string;
  recentSemanticMemoryDoctorReport: SemanticMemoryWriteDoctorReport | null;
  recentSemanticMemoryDoctorError?: string;
  semanticMemoryDoctorHistoryReport: SemanticMemoryWriteDoctorHistoryReport | null;
  semanticMemoryDoctorHistoryError?: string;
  runtimePruneReport: RuntimeFlowSessionEventPruneReport | null;
  runtimePruneLoading?: boolean;
  runtimePruneError?: string;
  onRuntimePruneDryRun?: () => void;
  onRuntimePruneApply?: () => void;
}) {
  const rows = [
    ["Path", compactText(runtimePath?.lane, "Chưa phân loại")],
    ["Pha", compactText(runtimePath?.phase)],
    ["Sự kiện", compactText(runtimePath?.eventName)],
    ["Trạng thái", compactText(runtimePath?.status)],
    ["Surface", compactText(runtimePath?.hostSurface, "Không")],
    ["Tool đã thấy", toolGroupSummary(runtimePath?.observedTools)],
    ["Tool bị chặn", toolGroupSummary(runtimePath?.suppressedTools)],
    ["Preview", runtimePath?.previewRequired ? "Cần preview" : "Không"],
    ["Apply", runtimePath?.approvalTokenPresent ? "Có approval evidence" : "Không"],
    ["Nhận lúc", runtimePath?.receivedAtMs != null ? formatDateTime(new Date(runtimePath.receivedAtMs).toISOString()) : "Chưa có"],
  ];
  const doctorPaths = importantDoctorPaths(doctorReport);
  const doctorProviders = importantDoctorProviders(doctorReport);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(300px,380px)]">
      <section className="rounded-lg border border-[var(--border)] bg-surface p-4">
        <div className="mb-3 flex items-center gap-2">
          <Route size={16} className="text-text-secondary" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-text">Lượt runtime gần nhất</h3>
        </div>
        <dl className="grid gap-2 sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div key={label} className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
              <dt className="text-xs text-text-tertiary">{label}</dt>
              <dd className="mt-0.5 truncate text-sm font-medium text-text">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="rounded-lg border border-[var(--border)] bg-surface p-4">
        <div className="mb-3 flex items-center gap-2">
          <Info size={16} className="text-text-secondary" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-text">Kỷ luật hiển thị</h3>
        </div>
        <ul className="space-y-2 text-sm text-text-secondary">
          <li className="flex gap-2">
            <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden="true" />
            Chỉ hiển thị snapshot đã sanitize từ runtime.
          </li>
          <li className="flex gap-2">
            <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden="true" />
            Không hiển thị token, payload provider, raw document hay approval_token.
          </li>
          <li className="flex gap-2">
            <XCircle size={16} className="mt-0.5 shrink-0 text-text-tertiary" aria-hidden="true" />
            Adapter bên ngoài chưa được bật nếu chưa có vault/policy/gate.
          </li>
        </ul>
      </section>

      <section
        className="rounded-lg border border-[var(--border)] bg-surface p-4 lg:col-span-2"
        data-testid="wiii-connect-runtime-flow-ledger"
      >
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Activity size={16} className="text-text-secondary" aria-hidden="true" />
              <h3 className="text-sm font-semibold text-text">Runtime flow ledger</h3>
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              {runtimeFlowLedger.summary}
            </p>
          </div>
          <StatusPill tone={runtimeFlowLedger.tone}>
            {runtimeFlowLedger.present ? runtimeFlowLedger.version : "Đang chờ"}
          </StatusPill>
        </div>

        <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {runtimeFlowLedger.rows.map((row) => (
            <div key={row.label} className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
              <dt className="flex items-center justify-between gap-2 text-xs text-text-tertiary">
                <span>{row.label}</span>
                {row.tone && <span className={`h-2 w-2 rounded-full ${statusDotClasses[row.tone]}`} />}
              </dt>
              <dd className="mt-0.5 break-words text-sm font-medium text-text" title={row.value}>
                {row.value}
              </dd>
            </div>
          ))}
        </dl>

        {runtimeFlowLedger.warnings.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            <div className="mb-1 flex items-center gap-2 font-medium">
              <AlertTriangle size={15} aria-hidden="true" />
              Cần kiểm tra ledger
            </div>
            <ul className="space-y-1 text-xs">
              {runtimeFlowLedger.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section
        className="rounded-lg border border-[var(--border)] bg-surface p-4 lg:col-span-2"
        data-testid="wiii-connect-runtime-flow-trace"
      >
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-text-secondary" aria-hidden="true" />
              <h3 className="text-sm font-semibold text-text">Runtime flow trace</h3>
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              {runtimeFlowTrace.summary}
            </p>
          </div>
          <StatusPill tone={runtimeFlowTrace.tone}>
            {runtimeFlowTrace.present ? runtimeFlowTrace.version : "Đang chờ"}
          </StatusPill>
        </div>

        <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {runtimeFlowTrace.rows.map((row) => (
            <div key={row.label} className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
              <dt className="flex items-center justify-between gap-2 text-xs text-text-tertiary">
                <span>{row.label}</span>
                {row.tone && <span className={`h-2 w-2 rounded-full ${statusDotClasses[row.tone]}`} />}
              </dt>
              <dd className="mt-0.5 break-words text-sm font-medium text-text" title={row.value}>
                {row.value}
              </dd>
            </div>
          ))}
        </dl>

        {runtimeFlowTrace.warnings.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            <div className="mb-1 flex items-center gap-2 font-medium">
              <AlertTriangle size={15} aria-hidden="true" />
              Cần kiểm tra trace
            </div>
            <ul className="space-y-1 text-xs">
              {runtimeFlowTrace.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section
        className="rounded-lg border border-[var(--border)] bg-surface p-4 lg:col-span-2"
        data-testid="wiii-connect-doctor-panel"
      >
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Activity size={16} className="text-text-secondary" aria-hidden="true" />
              <h3 className="text-sm font-semibold text-text">Runtime doctor</h3>
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              {doctorError
                ? "Chưa đọc được doctor report từ backend."
                : doctorReport
                  ? "Tóm tắt path, connection và blocker từ cùng snapshot runtime."
                  : "Đang chờ doctor report từ backend."}
            </p>
          </div>
          <StatusPill tone={doctorStatusTone(doctorReport?.status)}>
            {doctorReport?.status ?? "checking"}
          </StatusPill>
        </div>

        <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
            <dt className="text-xs text-text-tertiary">Path sẵn sàng</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {doctorMetric(doctorReport, "ready_paths")}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
            <dt className="text-xs text-text-tertiary">Path guarded</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {doctorMetric(doctorReport, "guarded_paths")}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
            <dt className="text-xs text-text-tertiary">Path bị chặn</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {doctorMetric(doctorReport, "blocked_paths")}
            </dd>
          </div>
          <div className="min-w-0 rounded-md bg-surface-secondary px-3 py-2">
            <dt className="text-xs text-text-tertiary">External ready</dt>
            <dd className="mt-0.5 truncate text-sm font-medium text-text">
              {doctorMetric(doctorReport, "external_agent_ready_connections")}
            </dd>
          </div>
        </dl>

        {doctorPaths.length > 0 && (
          <div className="mt-3 overflow-x-auto rounded-lg border border-[var(--border)]">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="border-b border-[var(--border)] bg-surface-secondary text-xs uppercase text-text-tertiary">
                <tr>
                  <th className="px-3 py-2 font-medium">Path</th>
                  <th className="px-3 py-2 font-medium">Trạng thái</th>
                  <th className="px-3 py-2 font-medium">Lý do</th>
                  <th className="px-3 py-2 font-medium">Thiếu</th>
                </tr>
              </thead>
              <tbody>
                {doctorPaths.map((path) => (
                  <tr key={path.path} className="border-b border-[var(--border)] last:border-b-0">
                    <td className="px-3 py-2 font-medium text-text">{path.path}</td>
                    <td className="px-3 py-2">
                      <StatusPill tone={pathDoctorTone(path.status)}>
                        {path.status}
                      </StatusPill>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {compactText(path.reason)}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {pathList(path.missing_connection_slugs)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {doctorProviders.length > 0 && (
          <div className="mt-3 overflow-x-auto rounded-lg border border-[var(--border)]">
            <table className="w-full min-w-[760px] text-left text-sm">
              <caption className="sr-only">Provider diagnostics</caption>
              <thead className="border-b border-[var(--border)] bg-surface-secondary text-xs uppercase text-text-tertiary">
                <tr>
                  <th className="px-3 py-2 font-medium">Provider</th>
                  <th className="px-3 py-2 font-medium">Kết nối</th>
                  <th className="px-3 py-2 font-medium">Agent</th>
                  <th className="px-3 py-2 font-medium">Vòng đời</th>
                  <th className="px-3 py-2 font-medium">Bước tiếp</th>
                </tr>
              </thead>
              <tbody>
                {doctorProviders.map((provider) => (
                  <tr key={provider.provider_slug} className="border-b border-[var(--border)] last:border-b-0">
                    <td className="px-3 py-2">
                      <div className="font-medium text-text">{provider.label}</div>
                      <div className="text-xs text-text-tertiary">
                        {provider.provider_slug} · {compactText(provider.provider_kind)}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      <div className="font-medium text-text">{compactText(provider.connection_status)}</div>
                      <div className="text-xs text-text-tertiary">
                        {providerDoctorCountSummary(provider)}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill tone={pathDoctorTone(provider.status)}>
                        {provider.status}
                      </StatusPill>
                      <div className="mt-1 text-xs text-text-secondary">
                        {compactText(provider.reason)}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      <DoctorProviderStages provider={provider} />
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {pathList(provider.required_next)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {doctorReport?.top_blockers && doctorReport.top_blockers.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            {pathList(doctorReport.top_blockers.slice(0, 4))}
          </div>
        )}
      </section>

      <RecentRuntimeFlowDoctorPanel
        report={recentRuntimeFlowDoctorReport}
        error={recentRuntimeFlowDoctorError}
        historyReport={runtimeFlowDoctorHistoryReport}
        historyError={runtimeFlowDoctorHistoryError}
        pruneReport={runtimePruneReport}
        pruneLoading={runtimePruneLoading}
        pruneError={runtimePruneError}
        onPruneDryRun={onRuntimePruneDryRun}
        onPruneApply={onRuntimePruneApply}
      />

      <SemanticMemoryDoctorPanel
        report={recentSemanticMemoryDoctorReport}
        error={recentSemanticMemoryDoctorError}
        historyReport={semanticMemoryDoctorHistoryReport}
        historyError={semanticMemoryDoctorHistoryError}
      />
    </div>
  );
}
