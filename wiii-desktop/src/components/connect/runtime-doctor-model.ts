/** Aggregate-only diagnostic labels and counts for runtime doctor panels. */
import type {
  RuntimeFlowDoctorReport,
  RuntimeFlowDoctorSubagentSummary,
  SemanticMemoryWriteDoctorReport,
  WiiiConnectDoctorReport,
} from "@/api/types";
import type { CapabilityStatusTone } from "@/lib/capability-status";
import { compactText } from "./connect-display";

const safeRuntimeDoctorCounterToken = /^[A-Za-z0-9_.:/-]{1,96}$/;

export function safeRuntimeDoctorCounterLabel(value: unknown): string {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (!text) return "unknown";
  if (!safeRuntimeDoctorCounterToken.test(text)) return "[Ä‘Ã£ áº©n]";
  return compactText(text);
}

export function countMapEntries(
  value: Record<string, number> | undefined,
  limit = 5,
): Array<[string, number]> {
  if (!value) return [];
  return Object.entries(value)
    .filter(([, count]) => typeof count === "number" && Number.isFinite(count))
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([label, count]) => [safeRuntimeDoctorCounterLabel(label), count]);
}

export function doctorStatusTone(status: string | undefined): CapabilityStatusTone {
  if (status === "ready") return "ok";
  if (status === "degraded" || status === "blocked") return "warn";
  return "pending";
}

export function pathDoctorTone(status: string | undefined): CapabilityStatusTone {
  if (status === "ready") return "ok";
  if (status === "guarded") return "pending";
  if (status === "blocked") return "warn";
  return "off";
}

export function doctorMetric(report: WiiiConnectDoctorReport | null, key: string): string {
  const value = report?.summary?.[key];
  return typeof value === "number" ? String(value) : "0";
}

export function runtimeDoctorMetric(report: RuntimeFlowDoctorReport | null, key: string): string {
  const value = report?.summary?.[key];
  return typeof value === "number" ? String(value) : "0";
}

export function runtimeDoctorConfigNumber(
  report: { runtime_config?: Record<string, string | number | boolean> } | null | undefined,
  key: string,
): number | undefined {
  const value = report?.runtime_config?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function semanticMemoryDoctorMetric(
  report: SemanticMemoryWriteDoctorReport | null,
  key: string,
): string {
  const value = report?.summary?.[key];
  return typeof value === "number" ? String(value) : "0";
}

export function runtimeDoctorCorrelationMetric(
  report: RuntimeFlowDoctorReport | null,
  key: string,
): string {
  const value = report?.request_correlation?.[key];
  return typeof value === "number" ? String(value) : "0";
}

export function runtimeDoctorSubagentMetric(
  report: RuntimeFlowDoctorReport | null,
  key: keyof RuntimeFlowDoctorSubagentSummary,
): string {
  const value = report?.subagents?.[key];
  return typeof value === "number" ? String(value) : "0";
}

export function runtimeDoctorAlertTone(
  severity: string | undefined,
): CapabilityStatusTone {
  if (severity === "critical" || severity === "error") return "warn";
  if (severity === "warning") return "pending";
  return "off";
}

export function importantDoctorPaths(report: WiiiConnectDoctorReport | null) {
  return (report?.path_diagnostics ?? [])
    .filter((path) => path.status !== "ready")
    .slice(0, 6);
}

export function importantDoctorProviders(report: WiiiConnectDoctorReport | null) {
  return (report?.provider_diagnostics ?? [])
    .filter((provider) => provider.provider_kind !== "wiii_native" || provider.status !== "ready")
    .slice(0, 8);
}
