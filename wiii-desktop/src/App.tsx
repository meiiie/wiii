/**
 * Root App component — initializes stores, mounts layout.
 * Sprint 106: Loading screen during init.
 */
import { lazy, Suspense, useEffect } from "react";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { useUIStore } from "@/stores/ui-store";
import { WorkbenchApp } from "@/workbench/WorkbenchApp";
import { detectWorkbenchHost, type WorkbenchHost } from "@/workbench/host";
import { BootSplash } from "@/workbench/WorkbenchBoot";

const WiiiCloudApp = lazy(async () => import("@/workbench/WiiiCloudApp"));

const AvatarPreview = lazy(async () => {
  const mod = await import("@/components/common/AvatarPreview");
  return { default: mod.AvatarPreview };
});

const PointyPreview = lazy(async () => {
  const mod = await import("@/components/common/PointyPreview");
  return { default: mod.PointyPreview };
});

const NekoMotionLab = lazy(async () => import("@/neko-motion-lab/NekoMotionLab"));

const NekoChillApp = lazy(async () => import("@/neko-chill/NekoChillApp"));

const WiiiAdeApp = lazy(async () => import("@/ade/WiiiAdeApp"));

const WiiiConnectPage = lazy(async () => {
  const mod = await import("@/components/connect/WiiiConnectPage");
  return { default: mod.WiiiConnectPage };
});

function WiiiConnectPreview() {
  useEffect(() => {
    useUIStore.getState().openWiiiConnect("gmail");
  }, []);
  return <WiiiConnectPage />;
}
/**
 * Host-aware Workbench boundary (#923).
 *
 * The inactive surface stays unmounted. Desktop can run a local agent without
 * cloud bootstrap; hosted web can only open remotely-backed capabilities.
 */
export function WorkbenchGate({ host = detectWorkbenchHost() }: { host?: WorkbenchHost }) {
  return (
    <WorkbenchApp
      host={host}
      loadingFallback={<BootSplash label="Wiii đang mở Workbench..." />}
      renderLocal={({ openManaged }) => (
        <ErrorBoundary>
          <Suspense fallback={<BootSplash label="Wiii đang mở không gian cục bộ..." />}>
            <NekoChillApp
              onOpenManaged={openManaged}
              onOpenConnections={() => {
                useUIStore.getState().openWiiiConnect("gmail");
                openManaged();
              }}
            />
          </Suspense>
        </ErrorBoundary>
      )}
      renderManaged={({ openLocal }) => (
        <ErrorBoundary>
          <Suspense fallback={<BootSplash label="Wiii đang mở không gian được quản lý..." />}>
            <WiiiCloudApp
              onOpenLocal={host.capabilities.localProcess ? openLocal : undefined}
            />
          </Suspense>
        </ErrorBoundary>
      )}
    />
  );
}

export default function App() {
  const localPreviewEnabled =
    import.meta.env.DEV || import.meta.env.VITE_ENABLE_LOCAL_PREVIEW === "1";
  // Dev tool: ?preview=avatar shows avatar preview page
  if (window.location.search.includes("preview=avatar")) {
    return (
      <Suspense fallback={<BootSplash label="Wiii đang mở bản xem trước..." />}>
        <AvatarPreview />
      </Suspense>
    );
  }

  // Wiii Pointy demo: ?preview=pointy showcases the spring-physics
  // multi-cursor system. Standalone — no auth, no chat boot, just
  // visual verification of the cursor architecture.
  if (window.location.search.includes("preview=pointy")) {
    return (
      <Suspense fallback={<BootSplash label="Wiii Pointy đang khởi động..." />}>
        <PointyPreview />
      </Suspense>
    );
  }

  // Standalone Neko behavior rig: no auth, cloud polling, chat, or agent
  // runtime. Research is intentionally isolated from production state.
  if (window.location.search.includes("preview=neko-motion")) {
    return (
      <Suspense fallback={<BootSplash label="Neko Motion Lab đang mở..." />}>
        <NekoMotionLab />
      </Suspense>
    );
  }

  // Local UX review rig: renders the real Neko Chill shell with browser
  // fallback storage. Native harness launch remains unavailable, so reviewers
  // can approve information architecture without building an installer.
  if (localPreviewEnabled && window.location.search.includes("preview=neko-chill")) {
    return (
      <Suspense fallback={<BootSplash label="Neko Chill đang mở bản xem trước..." />}>
        <NekoChillApp />
      </Suspense>
    );
  }

  if (localPreviewEnabled && window.location.search.includes("preview=wiii-connect")) {
    return (
      <Suspense fallback={<BootSplash label="Wiii đang mở kết nối..." />}>
        <WiiiConnectPreview />
      </Suspense>
    );
  }

  // Product-shell verification rig: browser fallback storage, no managed
  // bootstrap and no native provider side effects until a task is dispatched.
  if (localPreviewEnabled && window.location.search.includes("preview=ade")) {
    return (
      <Suspense fallback={<BootSplash label="Wiii đang mở Công việc..." />}>
        <WiiiAdeApp />
      </Suspense>
    );
  }

  return <WorkbenchGate />;
}
