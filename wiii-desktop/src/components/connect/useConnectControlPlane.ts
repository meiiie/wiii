/** Backend registry, diagnostics, polling and retention actions for Connect. */
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  RuntimeFlowDoctorHistoryReport,
  RuntimeFlowDoctorReport,
  RuntimeFlowSessionEventPruneReport,
  SemanticMemoryWriteDoctorHistoryReport,
  SemanticMemoryWriteDoctorReport,
  WiiiConnectDoctorReport,
  WiiiConnectProviderRegistryEntry,
  WiiiConnectRuntimeSnapshot,
} from "@/api/types";
import {
  fetchRecentRuntimeFlowDoctor,
  fetchRecentSemanticMemoryDoctor,
  fetchRuntimeFlowDoctorHistory,
  fetchSemanticMemoryDoctorHistory,
  fetchWiiiConnectDoctor,
  fetchWiiiConnectProviders,
  fetchWiiiConnectSnapshot,
  pruneRuntimeFlowSessionEvents,
} from "@/api/wiii-connect";
import { useAuthStore } from "@/stores/auth-store";

const WIII_CONNECT_RUNTIME_REFRESH_MS = 5_000;

export function useConnectControlPlane(isEmbedded: boolean) {
  const [providerRegistry, setProviderRegistry] = useState<WiiiConnectProviderRegistryEntry[] | null>(null);
  const [providerRegistryLoaded, setProviderRegistryLoaded] = useState(false);
  const [runtimeSnapshot, setRuntimeSnapshot] = useState<WiiiConnectRuntimeSnapshot | null>(null);
  const [runtimeSnapshotError, setRuntimeSnapshotError] = useState<string | undefined>();
  const [runtimeRefreshing, setRuntimeRefreshing] = useState(false);
  const [lastRuntimeRefreshAt, setLastRuntimeRefreshAt] = useState<string | null>(null);
  const [doctorReport, setDoctorReport] = useState<WiiiConnectDoctorReport | null>(null);
  const [doctorError, setDoctorError] = useState<string | undefined>();
  const [recentRuntimeFlowDoctorReport, setRecentRuntimeFlowDoctorReport] =
    useState<RuntimeFlowDoctorReport | null>(null);
  const [recentRuntimeFlowDoctorError, setRecentRuntimeFlowDoctorError] =
    useState<string | undefined>();
  const [runtimeFlowDoctorHistoryReport, setRuntimeFlowDoctorHistoryReport] =
    useState<RuntimeFlowDoctorHistoryReport | null>(null);
  const [runtimeFlowDoctorHistoryError, setRuntimeFlowDoctorHistoryError] =
    useState<string | undefined>();
  const [recentSemanticMemoryDoctorReport, setRecentSemanticMemoryDoctorReport] =
    useState<SemanticMemoryWriteDoctorReport | null>(null);
  const [recentSemanticMemoryDoctorError, setRecentSemanticMemoryDoctorError] =
    useState<string | undefined>();
  const [semanticMemoryDoctorHistoryReport, setSemanticMemoryDoctorHistoryReport] =
    useState<SemanticMemoryWriteDoctorHistoryReport | null>(null);
  const [semanticMemoryDoctorHistoryError, setSemanticMemoryDoctorHistoryError] =
    useState<string | undefined>();
  const [runtimePruneReport, setRuntimePruneReport] =
    useState<RuntimeFlowSessionEventPruneReport | null>(null);
  const [runtimePruneError, setRuntimePruneError] = useState<string | undefined>();
  const [runtimePruneLoading, setRuntimePruneLoading] = useState(false);
  const runtimeControlPlaneMountedRef = useRef(false);
  const authMode = useAuthStore((state) => state.authMode);
  const authUser = useAuthStore((state) => state.user);

  useEffect(() => {
    runtimeControlPlaneMountedRef.current = true;
    return () => {
      runtimeControlPlaneMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    fetchWiiiConnectProviders()
      .then((response) => {
        if (!mounted) return;
        setProviderRegistry(response.providers ?? []);
        setProviderRegistryLoaded(true);
      })
      .catch(() => {
        if (!mounted) return;
        setProviderRegistry(null);
        setProviderRegistryLoaded(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const refreshRuntimeControlPlane = useCallback(async () => {
    const surface = isEmbedded ? "embed" : "desktop";
    const canReadRecentRuntimeDoctor =
      authMode === "legacy" || authUser?.platform_role === "platform_admin";
    if (runtimeControlPlaneMountedRef.current) {
      setRuntimeRefreshing(true);
    }
    try {
      const [
        snapshotResult,
        doctorResult,
        recentDoctorResult,
        doctorHistoryResult,
        semanticDoctorResult,
        semanticDoctorHistoryResult,
      ] = await Promise.allSettled([
        fetchWiiiConnectSnapshot({ surface }),
        fetchWiiiConnectDoctor({ surface }),
        canReadRecentRuntimeDoctor
          ? fetchRecentRuntimeFlowDoctor({
              orgId: authUser?.active_organization_id,
              limit: 50,
            })
          : Promise.resolve(null),
        canReadRecentRuntimeDoctor
          ? fetchRuntimeFlowDoctorHistory({
              orgId: authUser?.active_organization_id,
              limit: 500,
              bucketLimit: 24,
            })
          : Promise.resolve(null),
        canReadRecentRuntimeDoctor
          ? fetchRecentSemanticMemoryDoctor({
              orgId: authUser?.active_organization_id,
              limit: 50,
            })
          : Promise.resolve(null),
        canReadRecentRuntimeDoctor
          ? fetchSemanticMemoryDoctorHistory({
              orgId: authUser?.active_organization_id,
              limit: 500,
              bucketLimit: 24,
            })
          : Promise.resolve(null),
      ]);
      if (!runtimeControlPlaneMountedRef.current) return;
      if (snapshotResult.status === "fulfilled") {
        setRuntimeSnapshot(snapshotResult.value);
        setRuntimeSnapshotError(undefined);
      } else {
        setRuntimeSnapshotError(
          snapshotResult.reason instanceof Error
            ? snapshotResult.reason.message
            : "snapshot_unavailable",
        );
      }
      if (doctorResult.status === "fulfilled") {
        setDoctorReport(doctorResult.value);
        setDoctorError(undefined);
      } else {
        setDoctorError(
          doctorResult.reason instanceof Error
            ? doctorResult.reason.message
            : "doctor_unavailable",
        );
      }
      if (recentDoctorResult.status === "fulfilled" && recentDoctorResult.value) {
        setRecentRuntimeFlowDoctorReport(recentDoctorResult.value);
        setRecentRuntimeFlowDoctorError(undefined);
      } else {
        setRecentRuntimeFlowDoctorReport(null);
        setRecentRuntimeFlowDoctorError(
          recentDoctorResult.status === "rejected"
            ? recentDoctorResult.reason instanceof Error
              ? recentDoctorResult.reason.message
              : "runtime_flow_doctor_unavailable"
            : "operator_access_required",
        );
      }
      if (doctorHistoryResult.status === "fulfilled" && doctorHistoryResult.value) {
        setRuntimeFlowDoctorHistoryReport(doctorHistoryResult.value);
        setRuntimeFlowDoctorHistoryError(undefined);
      } else {
        setRuntimeFlowDoctorHistoryReport(null);
        setRuntimeFlowDoctorHistoryError(
          doctorHistoryResult.status === "rejected"
            ? doctorHistoryResult.reason instanceof Error
              ? doctorHistoryResult.reason.message
              : "runtime_flow_doctor_history_unavailable"
            : "operator_access_required",
        );
      }
      if (semanticDoctorResult.status === "fulfilled" && semanticDoctorResult.value) {
        setRecentSemanticMemoryDoctorReport(semanticDoctorResult.value);
        setRecentSemanticMemoryDoctorError(undefined);
      } else {
        setRecentSemanticMemoryDoctorReport(null);
        setRecentSemanticMemoryDoctorError(
          semanticDoctorResult.status === "rejected"
            ? semanticDoctorResult.reason instanceof Error
              ? semanticDoctorResult.reason.message
              : "semantic_memory_doctor_unavailable"
            : "operator_access_required",
        );
      }
      if (
        semanticDoctorHistoryResult.status === "fulfilled" &&
        semanticDoctorHistoryResult.value
      ) {
        setSemanticMemoryDoctorHistoryReport(semanticDoctorHistoryResult.value);
        setSemanticMemoryDoctorHistoryError(undefined);
      } else {
        setSemanticMemoryDoctorHistoryReport(null);
        setSemanticMemoryDoctorHistoryError(
          semanticDoctorHistoryResult.status === "rejected"
            ? semanticDoctorHistoryResult.reason instanceof Error
              ? semanticDoctorHistoryResult.reason.message
              : "semantic_memory_doctor_history_unavailable"
            : "operator_access_required",
        );
      }
      setLastRuntimeRefreshAt(new Date().toISOString());
    } finally {
      if (runtimeControlPlaneMountedRef.current) {
        setRuntimeRefreshing(false);
      }
    }
  }, [authMode, authUser?.active_organization_id, authUser?.platform_role, isEmbedded]);
  const runRuntimePruneDryRun = useCallback(async () => {
    const canReadRecentRuntimeDoctor =
      authMode === "legacy" || authUser?.platform_role === "platform_admin";
    if (!canReadRecentRuntimeDoctor) {
      setRuntimePruneError("operator_access_required");
      return;
    }
    setRuntimePruneLoading(true);
    setRuntimePruneError(undefined);
    try {
      const report = await pruneRuntimeFlowSessionEvents({
        orgId: authUser?.active_organization_id,
        eventType: "runtime_flow_ledger",
        dryRun: true,
      });
      if (!runtimeControlPlaneMountedRef.current) return;
      setRuntimePruneReport(report);
    } catch {
      if (!runtimeControlPlaneMountedRef.current) return;
      setRuntimePruneError("retention_prune_unavailable");
    } finally {
      if (runtimeControlPlaneMountedRef.current) {
        setRuntimePruneLoading(false);
      }
    }
  }, [authMode, authUser?.active_organization_id, authUser?.platform_role]);
  const runRuntimePruneApply = useCallback(async () => {
    const canReadRecentRuntimeDoctor =
      authMode === "legacy" || authUser?.platform_role === "platform_admin";
    if (
      !canReadRecentRuntimeDoctor ||
      !runtimePruneReport?.dry_run ||
      runtimePruneReport.matched_count <= 0
    ) {
      return;
    }
    setRuntimePruneLoading(true);
    setRuntimePruneError(undefined);
    try {
      const report = await pruneRuntimeFlowSessionEvents({
        retentionDays: runtimePruneReport.retention_days,
        orgId: authUser?.active_organization_id,
        eventType: "runtime_flow_ledger",
        dryRun: false,
      });
      if (!runtimeControlPlaneMountedRef.current) return;
      setRuntimePruneReport(report);
      await refreshRuntimeControlPlane();
    } catch {
      if (!runtimeControlPlaneMountedRef.current) return;
      setRuntimePruneError("retention_prune_unavailable");
    } finally {
      if (runtimeControlPlaneMountedRef.current) {
        setRuntimePruneLoading(false);
      }
    }
  }, [
    authMode,
    authUser?.active_organization_id,
    authUser?.platform_role,
    refreshRuntimeControlPlane,
    runtimePruneReport?.dry_run,
    runtimePruneReport?.matched_count,
    runtimePruneReport?.retention_days,
  ]);

  useEffect(() => {
    void refreshRuntimeControlPlane();
    const timer = window.setInterval(() => {
      void refreshRuntimeControlPlane();
    }, WIII_CONNECT_RUNTIME_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refreshRuntimeControlPlane]);

  return {
    providerRegistry,
    providerRegistryLoaded,
    runtimeSnapshot,
    runtimeSnapshotError,
    runtimeRefreshing,
    lastRuntimeRefreshAt,
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
    runtimePruneError,
    runtimePruneLoading,
    refreshRuntimeControlPlane,
    runRuntimePruneDryRun,
    runRuntimePruneApply,
  };
}
