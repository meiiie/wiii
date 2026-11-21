/** Connect page composition; each tab owns its focused panels. */
import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  PlugZap,
  RefreshCw,
  Route,
  ShieldCheck,
} from "lucide-react";
import { type FullPageTab, FullPageView } from "@/components/layout/FullPageView";
import {
  buildCapabilityStatusViewModel,
  type CapabilityStatusTone,
  runtimePathFromLifecycleEvents,
} from "@/lib/capability-status";
import {
  buildRuntimeFlowLedgerViewModel,
  buildRuntimeFlowTraceViewModel,
  latestRuntimeFlowLedger,
  latestRuntimeFlowTrace,
} from "@/lib/runtime-flow-trace";
import { useChatStore } from "@/stores/chat-store";
import { useConnectionStore } from "@/stores/connection-store";
import { useHostContextStore } from "@/stores/host-context-store";
import { useUIStore } from "@/stores/ui-store";
import { CapabilitySummaryPanel, PathPolicyTable } from "./AccessPathsPanel";
import { isEmbeddedWindow, snapshotStats } from "./connect-display";
import type { ConnectTab } from "./connect-types";
import { ConnectionCatalog } from "./ConnectionCatalog";
import { ConnectionsGrid, LocalRuntimeFallback, ProviderRoadmap } from "./ConnectionsPanel";
import { StatusPill, SummaryMetric } from "./ConnectStatus";
import { RuntimeSection } from "./RuntimeSection";
import { useConnectControlPlane } from "./useConnectControlPlane";

const tabs: FullPageTab[] = [
  { id: "catalog", label: "Ứng dụng", icon: <PlugZap size={15} /> },
  { id: "connections", label: "Đã kết nối", icon: <Database size={15} /> },
  { id: "paths", label: "Quyền truy cập", icon: <Route size={15} /> },
  { id: "runtime", label: "Chẩn đoán", icon: <Activity size={15} /> },
];

export function WiiiConnectPage() {
  const [activeTab, setActiveTab] = useState<ConnectTab>("catalog");
  const focusProviderSlug = useUIStore((state) => state.wiiiConnectFocusProvider);
  const navigateToChat = useUIStore((state) => state.navigateToChat);
  const connectionStatus = useConnectionStore((state) => state.status);
  const serverVersion = useConnectionStore((state) => state.serverVersion);
  const lastCheckedAt = useConnectionStore((state) => state.lastCheckedAt);
  const errorMessage = useConnectionStore((state) => state.errorMessage);
  const capabilities = useHostContextStore((state) => state.capabilities);
  const currentContext = useHostContextStore((state) => state.currentContext);
  const streamingLifecycleEvents = useChatStore(
    (state) => state.streamingLifecycleEvents,
  );
  const lastCompletedLifecycleEvents = useChatStore(
    (state) => state.lastCompletedLifecycleEvents,
  );
  const activeConversation = useChatStore((state) => state.activeConversation());
  const pendingStreamMetadata = useChatStore((state) => state.pendingStreamMetadata);
  const isEmbedded = isEmbeddedWindow();
  const {
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
  } = useConnectControlPlane(isEmbedded);

  const runtimePath = useMemo(
    () =>
      runtimePathFromLifecycleEvents(
        streamingLifecycleEvents,
        lastCompletedLifecycleEvents,
      ),
    [streamingLifecycleEvents, lastCompletedLifecycleEvents],
  );
  const runtimeFlowTrace = useMemo(
    () =>
      buildRuntimeFlowTraceViewModel(
        latestRuntimeFlowTrace(activeConversation?.messages, pendingStreamMetadata),
      ),
    [activeConversation?.messages, pendingStreamMetadata],
  );
  const runtimeFlowLedger = useMemo(
    () =>
      buildRuntimeFlowLedgerViewModel(
        latestRuntimeFlowLedger(activeConversation?.messages, pendingStreamMetadata),
      ),
    [activeConversation?.messages, pendingStreamMetadata],
  );
  const snapshot = runtimePath?.wiiiConnect ?? runtimeSnapshot;
  const stats = snapshotStats(snapshot);
  const runtimeSyncLabel = runtimeRefreshing
    ? "Đang đồng bộ"
    : lastRuntimeRefreshAt
      ? "Đã đồng bộ"
      : "Chờ đồng bộ";

  const fallbackModel = useMemo(
    () =>
      buildCapabilityStatusViewModel({
        connectionStatus,
        capabilities,
        currentContext,
        isEmbedded,
        serverVersion,
        lastCheckedAt,
        errorMessage,
        runtimePath,
      }),
    [
      connectionStatus,
      capabilities,
      currentContext,
      isEmbedded,
      serverVersion,
      lastCheckedAt,
      errorMessage,
      runtimePath,
    ],
  );

  const snapshotTone: CapabilityStatusTone =
    !snapshot ? "pending" : stats.warningCount > 0 ? "warn" : stats.ready > 0 ? "ok" : "off";

  return (
    <FullPageView
      title="Kết nối"
      subtitle="Tài khoản và ứng dụng của Neko"
      icon={<PlugZap size={18} />}
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={(id) => setActiveTab(id as ConnectTab)}
      onClose={navigateToChat}
    >
      <div className="space-y-6" data-testid="wiii-connect-page">
        <section>
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-xl font-semibold text-text">Neko được phép làm việc ở đâu?</h1>
              <p className="mt-1 max-w-3xl text-sm text-text-secondary">
                Kết nối tài khoản, xem chính xác quyền Neko đang có và thu hồi quyền bất cứ lúc nào.
              </p>
            </div>
            <StatusPill tone={snapshotTone}>
              {snapshot ? `${stats.ready}/${stats.total} sẵn sàng` : "Chưa có dữ liệu"}
            </StatusPill>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <SummaryMetric
              icon={Database}
              label="Tài khoản"
              value={snapshot ? `${stats.total}` : `${fallbackModel.items.length} mục`}
              tone={snapshot ? "ok" : "pending"}
            />
            <SummaryMetric
              icon={CheckCircle2}
              label="Neko dùng được"
              value={snapshot ? `${stats.ready}/${stats.total}` : fallbackModel.summary}
              tone={snapshotTone}
            />
            <SummaryMetric
              icon={Route}
              label="Quyền hoạt động"
              value={
                snapshot?.capability_summary
                  ? `${stats.readyPathCount}/${stats.pathCount} sẵn sàng`
                  : snapshot
                    ? `${stats.pathCount}`
                    : "Đang chờ"
              }
              tone={
                stats.blockedPathCount > 0
                  ? "warn"
                  : stats.pathCount > 0
                    ? "ok"
                    : "pending"
              }
            />
            <SummaryMetric
              icon={AlertTriangle}
              label="Cần chú ý"
              value={`${stats.warningCount}${runtimeSnapshotError ? "+API" : ""}`}
              tone={stats.warningCount > 0 || runtimeSnapshotError ? "warn" : "ok"}
            />
            <SummaryMetric
              icon={RefreshCw}
              label="Đồng bộ"
              value={runtimeSyncLabel}
              tone={
                runtimeSnapshotError || doctorError
                  ? "warn"
                  : lastRuntimeRefreshAt
                    ? "ok"
                    : "pending"
              }
            />
          </div>
        </section>

        {focusProviderSlug === "gmail" && activeTab === "catalog" ? (
          <section
            className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3"
            data-testid="gmail-connection-guide"
          >
            <div className="flex items-start gap-3">
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-surface text-primary">
                <ShieldCheck size={16} aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-text">Kết nối Gmail thử nghiệm của Neko</h2>
                <p className="mt-1 max-w-3xl text-sm leading-5 text-text-secondary">
                  Gmail đang đăng nhập trong Máy của Neko không tự cấp quyền API. Hãy bấm
                  “Kết nối Gmail”, chọn đúng tài khoản Google đó và chấp thuận quyền đọc.
                  Wiii không sao chép cookie Chrome; bạn có thể ngắt kết nối ngay tại đây.
                </p>
              </div>
            </div>
          </section>
        ) : null}

        {activeTab === "catalog" && (
          <ConnectionCatalog
            snapshot={snapshot}
            fallbackModel={fallbackModel}
            providerRegistry={providerRegistry}
            providerRegistryLoaded={providerRegistryLoaded}
            initialProviderSlug={focusProviderSlug}
            onRuntimeRefresh={refreshRuntimeControlPlane}
          />
        )}

        {activeTab === "connections" && (
          <>
            <ConnectionsGrid connections={snapshot?.connections ?? []} snapshot={snapshot} />
            {!snapshot && <LocalRuntimeFallback sections={fallbackModel.sections} />}
            <ProviderRoadmap />
          </>
        )}

        {activeTab === "paths" && (
          <>
            <CapabilitySummaryPanel snapshot={snapshot} />
            <PathPolicyTable paths={snapshot?.path_capabilities ?? []} />
          </>
        )}

        {activeTab === "runtime" && (
            <RuntimeSection
              runtimePath={runtimePath}
              runtimeFlowLedger={runtimeFlowLedger}
              runtimeFlowTrace={runtimeFlowTrace}
              doctorReport={doctorReport}
              doctorError={doctorError}
              recentRuntimeFlowDoctorReport={recentRuntimeFlowDoctorReport}
              recentRuntimeFlowDoctorError={recentRuntimeFlowDoctorError}
              runtimeFlowDoctorHistoryReport={runtimeFlowDoctorHistoryReport}
              runtimeFlowDoctorHistoryError={runtimeFlowDoctorHistoryError}
              recentSemanticMemoryDoctorReport={recentSemanticMemoryDoctorReport}
              recentSemanticMemoryDoctorError={recentSemanticMemoryDoctorError}
              semanticMemoryDoctorHistoryReport={semanticMemoryDoctorHistoryReport}
              semanticMemoryDoctorHistoryError={semanticMemoryDoctorHistoryError}
              runtimePruneReport={runtimePruneReport}
              runtimePruneLoading={runtimePruneLoading}
              runtimePruneError={runtimePruneError}
              onRuntimePruneDryRun={runRuntimePruneDryRun}
              onRuntimePruneApply={runRuntimePruneApply}
          />
        )}
      </div>
    </FullPageView>
  );
}
