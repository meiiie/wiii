/** Neko Chill desktop-agent shell: projects -> sessions -> active runtime. */
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
} from "react";
import { Group, Panel, Separator, useDefaultLayout } from "react-resizable-panels";
import { nekoLayoutStorage } from "./browser-storage";
import { useShallow } from "zustand/react/shallow";
import {
  AlertTriangle,
  Bot,
  ChevronDown,
  Cloud,
  LoaderCircle,
  PanelLeft,
  PanelLeftClose,
  PanelRight,
  PlugZap,
  Info,
  Power,
  RefreshCw,
  Search,
} from "lucide-react";
import { TitleBar } from "@/components/layout/TitleBar";
import { WiiiMark } from "@/components/common/WiiiMark";
import { useNekoAgentStore } from "./stores/neko-agent-store";
import { useNekoProviderSessionStore } from "./stores/neko-provider-session-store";
import type { NekoProviderSessionRecord } from "@/neko/contracts";
import {
  disposeAllNekoRuntimes,
  startIdleReaper,
  useNekoSessionStore,
} from "./stores/neko-session-store";
import { NEKO_SESSION_STATUS_LABELS } from "./session-status";
import { sessionStatusDotClass } from "./session-catalog";
import { NekoTranscript } from "./components/NekoTranscript";
import { NekoComposer } from "./components/NekoComposer";
import { NekoOverview } from "./components/NekoOverview";
import { ProjectHome, type NekoTaskLaunchRequest } from "./components/ProjectHome";
import { ProjectDialog } from "./components/ProjectDialog";
import { SessionInspector } from "./components/SessionInspector";
import { SessionSidebar } from "./components/SessionSidebar";
import { NekoCommandCenter } from "./components/NekoCommandCenter";
import { NekoMenuBar } from "./components/NekoMenuBar";
import { CompletionNotices } from "./components/CompletionNotices";
import type { NekoWorkspaceTarget } from "./components/NekoWorkspacePane";
import { useNekoSessionCatalog } from "./hooks/useNekoSessionCatalog";
import { useWorkspacePresence } from "./hooks/useWorkspacePresence";
import {
  markWiiiPerformance,
  measureWiiiPerformance,
} from "@/lib/performance-telemetry";
import { useNekoWorkspaceStore } from "./stores/neko-workspace-store";
import {
  projectForSession,
  projectForWorkspace,
  useNekoProjectStore,
  workspaceKey,
} from "./stores/neko-project-store";
import {
  type ClientCommandName,
  type WorkbenchActionName,
} from "./command-items";
import type { ComposerInsertRequest } from "./components/NekoComposer";
import {
  chooseWorkspaceFolder,
  isAbsoluteWorkspacePath,
  type WorkspaceRef,
  workspaceFromPath,
} from "./workspace";
import "./theme.css";

if (import.meta.env.VITE_ENABLE_LOCAL_PREVIEW === "1" && typeof window !== "undefined") {
  (window as Window & {
    __wiiiPreviewStores?: {
      project: typeof useNekoProjectStore;
      session: typeof useNekoSessionStore;
    };
  }).__wiiiPreviewStores = {
    project: useNekoProjectStore,
    session: useNekoSessionStore,
  };
}

const LazyNekoWorkspacePane = lazy(async () => {
  const module = await import("./components/NekoWorkspacePane");
  return { default: module.NekoWorkspacePane };
});

const LazyNekoCoworkerHome = lazy(async () => {
  const module = await import("@/neko-coworker/NekoCoworkerHome");
  return { default: module.NekoCoworkerHome };
});

function SurfaceLoadingState() {
  return (
    <div className="grid h-full place-items-center bg-[var(--nk-canvas)] text-[11.5px] text-[var(--nk-text-3)]" role="status">
      Đang mở công cụ…
    </div>
  );
}

function NekoWorkspacePane(props: ComponentProps<typeof LazyNekoWorkspacePane>) {
  return (
    <Suspense fallback={<SurfaceLoadingState />}>
      <LazyNekoWorkspacePane key={props.session?.id ?? props.target?.id} {...props} />
    </Suspense>
  );
}

function useCompactWorkspace(breakpoint = 1040) {
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const update = () => setCompact(query.matches);
    update();
    query.addEventListener?.("change", update);
    return () => query.removeEventListener?.("change", update);
  }, [breakpoint]);
  return compact;
}

function WiiiNavigation({
  onOpenManaged,
  onOpenConnections,
  onOpenWork,
  showWorkNavigation,
}: {
  onOpenManaged: () => void;
  onOpenConnections: () => void;
  onOpenWork: () => void;
  showWorkNavigation: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    rootRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    const onDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || !rootRef.current?.contains(document.activeElement)) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus();
      } else if (event.key === "Tab") {
        setOpen(false);
        triggerRef.current?.focus();
      } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        const items = [...(rootRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];
        if (!items.length) return;
        event.preventDefault();
        const current = items.indexOf(document.activeElement as HTMLElement);
        const index = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
          : (current + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        items[index].focus();
      }
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div
      ref={rootRef}
      className="relative"
      onBlur={(event) => {
        if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        data-testid="mode-switcher"
        aria-label="Mở điều hướng Wiii. Khu vực hiện tại: Neko Chill"
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex h-8 items-center gap-1.5 rounded-lg px-1 text-[15px] font-semibold text-[var(--nk-text)] transition-colors hover:bg-[var(--nk-overlay)]"
        onClick={() => setOpen((value) => !value)}
      >
        <WiiiMark className="shrink-0" size={17} />
        <span>Wiii</span>
        <ChevronDown aria-hidden="true" className="h-3 w-3 text-[var(--nk-text-3)]" />
      </button>
      {open ? (
        <div
          role="menu"
          aria-label="Điều hướng Wiii"
          className="nk-chrome-popover absolute left-0 top-full z-50 mt-2 w-72 rounded-xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-1.5 shadow-lg"
          data-testid="mode-switcher-menu"
        >
          <div className="px-2.5 pb-1.5 pt-1">
            <span className="block text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--nk-ghost)]">
              Không gian trên máy
            </span>
          </div>
          {showWorkNavigation ? (
            <button
              type="button"
              role="menuitem"
              className="w-full rounded-lg px-2.5 py-2 text-left text-[11.5px] text-[var(--nk-text-3)] transition-colors hover:bg-[var(--nk-overlay)]"
              onClick={() => {
                setOpen(false);
                onOpenWork();
              }}
            >
              Mở bản thử nghiệm Công việc
            </button>
          ) : null}
          <button
            type="button"
            role="menuitem"
            aria-current="page"
            className="flex w-full items-start gap-2.5 rounded-lg bg-[var(--nk-item-active)] px-2.5 py-2.5 text-left"
            onClick={() => {
              setOpen(false);
              triggerRef.current?.focus();
            }}
          >
            <Bot aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-[var(--nk-text-2)]" />
            <span className="min-w-0 flex-1">
              <span className="flex items-center justify-between gap-3 text-[13px] font-medium text-[var(--nk-text)]">
                Neko Chill
                <span className="text-[9.5px] font-medium text-[var(--nk-ghost)]">Đang mở</span>
              </span>
              <span className="mt-0.5 block text-[11.5px] leading-4 text-[var(--nk-text-3)]">
                Quản lý project, harness và các phiên trên máy này
              </span>
            </span>
          </button>
          <div className="my-1 border-t border-[var(--nk-border)]" />
          <div className="px-2.5 pb-1 pt-1">
            <span className="block text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--nk-ghost)]">
              Kết nối
            </span>
          </div>
          <button
            type="button"
            role="menuitem"
            className="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2.5 text-left transition-colors hover:bg-[var(--nk-overlay)]"
            onClick={() => {
              setOpen(false);
              onOpenManaged();
            }}
          >
            <Cloud aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-[var(--nk-text-3)]" />
            <span className="min-w-0">
              <span className="block text-[13px] font-medium text-[var(--nk-text)]">Wiii Service</span>
              <span className="mt-0.5 block text-[11.5px] leading-4 text-[var(--nk-text-3)]">
                Đồng bộ và tri thức trực tuyến · tùy chọn
              </span>
            </span>
          </button>
          <button
            type="button"
            role="menuitem"
            className="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2.5 text-left transition-colors hover:bg-[var(--nk-overlay)]"
            onClick={() => {
              setOpen(false);
              onOpenConnections();
            }}
          >
            <PlugZap aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-[var(--nk-text-3)]" />
            <span className="min-w-0">
              <span className="block text-[13px] font-medium text-[var(--nk-text)]">Tài khoản & ứng dụng</span>
              <span className="mt-0.5 block text-[11.5px] leading-4 text-[var(--nk-text-3)]">
                Cấp, kiểm tra hoặc thu hồi quyền của Neko
              </span>
            </span>
          </button>
        </div>
      ) : null}
    </div>
  );
}

function SessionRecoveryState({
  loading,
  error,
  onRetry,
}: {
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <main
        className="grid min-h-0 flex-1 place-items-center px-6"
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center gap-3 text-[13px] text-[var(--nk-text-3)]">
          <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
          Đang khôi phục lịch sử phiên…
        </div>
      </main>
    );
  }
  return (
    <main className="grid min-h-0 flex-1 place-items-center px-6">
      <section
        className="w-full max-w-md rounded-2xl border border-[var(--nk-border-strong)] bg-[var(--nk-raised)] p-6 shadow-sm"
        role="alert"
        aria-labelledby="neko-history-error-title"
      >
        <div className="flex items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--nk-danger-soft)] text-[var(--nk-danger)]">
            <AlertTriangle aria-hidden="true" className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h1 id="neko-history-error-title" className="text-[14px] font-semibold text-[var(--nk-text)]">
              Chưa thể mở lịch sử phiên
            </h1>
            <p className="mt-1 text-[12px] leading-5 text-[var(--nk-text-3)]">
              Neko Chill đã khóa việc tạo và mở phiên để không ghi đè dữ liệu đang có.
            </p>
            {error ? (
              <p className="mt-2 break-words rounded-lg bg-[var(--nk-inset)] px-3 py-2 text-[11px] leading-4 text-[var(--nk-text-3)]">
                {error}
              </p>
            ) : null}
            <button
              type="button"
              className="mt-4 inline-flex h-8 items-center gap-2 rounded-lg bg-[var(--nk-inverse)] px-3 text-[12px] font-medium text-[var(--nk-on-inverse)] hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)]"
              onClick={onRetry}
            >
              <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
              Thử tải lại
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

function LiveNekoTranscript({
  sessionId,
  onResolvePermission,
  onInsertPrompt,
}: {
  sessionId: string;
  onResolvePermission: (optionId: string | null) => void;
  onInsertPrompt: (text: string) => void;
}) {
  const session = useNekoSessionStore((state) => state.sessions[sessionId]);
  useLayoutEffect(() => {
    measureWiiiPerformance("wiii:session:ready", "wiii:session:switch-start");
  }, [sessionId]);
  useLayoutEffect(() => {
    measureWiiiPerformance(
      "wiii:stream:commit",
      `wiii:stream:${sessionId}:start`,
    );
  }, [session?.updatedAt, sessionId]);
  if (!session) return null;
  return (
    <NekoTranscript
      session={session}
      onResolvePermission={onResolvePermission}
      onInsertPrompt={onInsertPrompt}
    />
  );
}

export default function NekoChillApp({
  onOpenManaged = () => {},
  onOpenConnections = onOpenManaged,
  onOpenWork = () => {},
  showWorkNavigation = false,
  taskLaunch = null,
}: {
  onOpenManaged?: () => void;
  onOpenConnections?: () => void;
  onOpenWork?: () => void;
  showWorkNavigation?: boolean;
  taskLaunch?: NekoTaskLaunchRequest | null;
}) {
  const detect = useNekoAgentStore((state) => state.detect);
  const agents = useNekoAgentStore((state) => state.agents);
  const hydrate = useNekoSessionStore((state) => state.hydrate);
  const hydrated = useNekoSessionStore((state) => state.hydrated);
  const hydrating = useNekoSessionStore((state) => state.hydrating);
  const hydrationError = useNekoSessionStore((state) => state.hydrationError);
  const activeSessionId = useNekoSessionStore((state) => state.activeSessionId);
  const sessions = useNekoSessionCatalog();
  const session = useMemo(
    () => activeSessionId
      ? useNekoSessionStore.getState().sessions[activeSessionId] ?? null
      : null,
    [activeSessionId, sessions],
  );
  const providerCatalogsById = useNekoProviderSessionStore((state) => state.catalogs);
  const providerCatalogs = useMemo(
    () => Object.values(providerCatalogsById),
    [providerCatalogsById],
  );
  const externalSessionCount = useMemo(() => {
    const attached = new Set(
      sessions.flatMap((item) =>
        item.backendSessionId ? [`${item.agentId}:${item.backendSessionId}`] : [],
      ),
    );
    return providerCatalogs
      .flatMap((catalog) => catalog.sessions)
      .filter((item) => !attached.has(`${item.providerId}:${item.nativeSessionId}`)).length;
  }, [providerCatalogs, sessions]);
  const providerDiscoveryLoading = useNekoProviderSessionStore((state) => state.loading);
  const refreshProviderSessions = useNekoProviderSessionStore((state) => state.refresh);
  const projects = useNekoProjectStore((state) => state.projects);
  const projectsHydrated = useNekoProjectStore((state) => state.hydrated);
  const hydrateProjects = useNekoProjectStore((state) => state.hydrate);
  const ensureWorkspaceProjects = useNekoProjectStore((state) => state.ensureWorkspaceProjects);
  const createProject = useNekoProjectStore((state) => state.createProject);
  const updateProject = useNekoProjectStore((state) => state.updateProject);
  const attachWorkspace = useNekoSessionStore((state) => state.attachWorkspace);
  const cancelTurn = useNekoSessionStore((state) => state.cancelTurn);
  const closeSession = useNekoSessionStore((state) => state.closeSession);
  const resolvePermission = useNekoSessionStore((state) => state.resolvePermission);
  const sendPrompt = useNekoSessionStore((state) => state.sendPrompt);
  const importProviderSession = useNekoSessionStore((state) => state.importProviderSession);
  const setActiveSession = useNekoSessionStore((state) => state.setActiveSession);
  const setConfigOption = useNekoSessionStore((state) => state.setConfigOption);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [commandCenterOpen, setCommandCenterOpen] = useState(false);
  const workspaceToggleRef = useRef<HTMLButtonElement>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [coworkerHomeOpen, setCoworkerHomeOpen] = useState(false);
  const [projectDialog, setProjectDialog] = useState<"create" | string | null>(null);
  const [projectHomeResetToken, setProjectHomeResetToken] = useState(0);
  const [harnessFocusRequest, setHarnessFocusRequest] = useState(0);
  const [projectWorkspaceRoot, setProjectWorkspaceRoot] = useState<WorkspaceRef | null>(null);
  const [insertRequest, setInsertRequest] = useState<ComposerInsertRequest | null>(null);
  const compactWorkspace = useCompactWorkspace();
  const compactSidebar = useCompactWorkspace(720);

  useLayoutEffect(() => {
    measureWiiiPerformance("wiii:boot:neko-ready", "wiii:boot:start");
  }, []);
  const workspacePane = useNekoWorkspaceStore(useShallow((state) => {
    const pane = activeSessionId ? state.sessions[activeSessionId] : undefined;
    return pane ? { open: pane.open, unseenChanges: pane.unseenChanges } : null;
  }));
  const ensureWorkspaceSession = useNekoWorkspaceStore((state) => state.ensureSession);
  const refreshWorkspace = useNekoWorkspaceStore((state) => state.refresh);
  const restoreActivities = useNekoWorkspaceStore((state) => state.restoreActivities);
  const setWorkspaceTab = useNekoWorkspaceStore((state) => state.setTab);
  const toggleWorkspace = useNekoWorkspaceStore((state) => state.toggle);
  const closeWorkspace = useNekoWorkspaceStore((state) => state.close);
  const knownWorkspacePaths = useMemo(
    () => [...new Set(sessions.flatMap((item) => item.workspace?.path ? [item.workspace.path] : []))],
    [sessions],
  );
  const knownWorkspaceKey = knownWorkspacePaths.join("\n");
  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const taskProject = useMemo(() => taskLaunch ? {
    id: `task:${taskLaunch.execution.runId}`,
    name: taskLaunch.workspace.name,
    roots: [taskLaunch.workspace],
    preferredHarnessId: null,
    createdAt: 0,
    updatedAt: 0,
  } : null, [taskLaunch?.execution.runId, taskLaunch?.workspace.path]);
  const projectHome = selectedProject ?? taskProject;
  const projectWorkspaceId = projectHome ? `project:${projectHome.id}` : null;
  const projectWorkspacePane = useNekoWorkspaceStore(useShallow((state) => {
    const pane = projectWorkspaceId ? state.sessions[projectWorkspaceId] : undefined;
    return pane ? { open: pane.open } : null;
  }));
  const sessionPresence = useWorkspacePresence(Boolean(session?.workspace && workspacePane?.open), `${activeSessionId}:${compactWorkspace}`);
  const projectPresence = useWorkspacePresence(Boolean(projectWorkspaceRoot && projectWorkspacePane?.open), `${projectWorkspaceId}:${compactWorkspace}`);
  const sessionPanelIds = useMemo(
    () => sessionPresence.present && !compactWorkspace
      ? ["neko-chat", "neko-workspace"]
      : ["neko-chat"],
    [compactWorkspace, sessionPresence.present],
  );
  const projectPanelIds = useMemo(
    () => projectPresence.present && projectWorkspaceRoot && !compactWorkspace
      ? ["neko-project-home", "neko-project-workspace"]
      : ["neko-project-home"],
    [compactWorkspace, projectPresence.present, projectWorkspaceRoot],
  );
  const sessionWorkspaceLayout = useDefaultLayout({
    id: "wiii-neko-session-workspace",
    panelIds: sessionPanelIds,
    storage: nekoLayoutStorage,
  });
  const projectWorkspaceLayout = useDefaultLayout({
    id: "wiii-neko-project-workspace",
    panelIds: projectPanelIds,
    storage: nekoLayoutStorage,
  });
  const editingProject = projectDialog && projectDialog !== "create"
    ? projects.find((project) => project.id === projectDialog) ?? null
    : null;
  const sessionWorkspaceTarget = useMemo<NekoWorkspaceTarget | null>(() =>
    session?.workspace ? {
      id: session.id,
      sessionId: session.id,
      projectId: session.projectId ?? undefined,
      workspace: session.workspace,
    } : null,
  [session?.id, session?.projectId, session?.workspace?.name, session?.workspace?.path]);
  const projectWorkspaceTarget = useMemo<NekoWorkspaceTarget | null>(() =>
    projectWorkspaceId && projectWorkspaceRoot && projectHome ? {
      id: projectWorkspaceId,
      projectId: projectHome.id,
      projectName: projectHome.name,
      workspace: projectWorkspaceRoot,
    } : null,
  [projectHome?.id, projectHome?.name, projectWorkspaceId, projectWorkspaceRoot]);

  useEffect(() => {
    if (!projectHome) {
      setProjectWorkspaceRoot(null);
      return;
    }
    setProjectWorkspaceRoot((current) => {
      const stillAvailable = current
        ? projectHome.roots.find((root) => workspaceKey(root.path) === workspaceKey(current.path))
        : null;
      return stillAvailable ?? projectHome.roots[0] ?? null;
    });
  }, [projectHome?.id, projectHome?.roots]);

  const updateProjectWorkspace = useCallback((workspace: WorkspaceRef) => {
    setProjectWorkspaceRoot((current) =>
      current && workspaceKey(current.path) === workspaceKey(workspace.path)
        ? current
        : workspace,
    );
  }, []);

  const toggleProjectWorkspace = useCallback(() => {
    if (!projectWorkspaceId || !projectWorkspaceRoot) return;
    ensureWorkspaceSession(projectWorkspaceId);
    const opening = !useNekoWorkspaceStore.getState().sessions[projectWorkspaceId]?.open;
    if (opening) {
      if (compactWorkspace) setSidebarOpen(false);
      setWorkspaceTab(projectWorkspaceId, "files");
      void refreshWorkspace(projectWorkspaceId, projectWorkspaceRoot, { force: true });
      return;
    }
    closeWorkspace(projectWorkspaceId);
  }, [
    closeWorkspace,
    compactWorkspace,
    ensureWorkspaceSession,
    projectWorkspaceId,
    projectWorkspaceRoot,
    refreshWorkspace,
    setWorkspaceTab,
  ]);

  useEffect(() => {
    void detect("neko");
    void hydrate();
    void hydrateProjects();
    const stopIdleReaper = startIdleReaper();
    return () => {
      stopIdleReaper();
      void disposeAllNekoRuntimes();
    };
  }, [detect, hydrate, hydrateProjects]);

  useEffect(() => {
    if (!hydrated || !projectsHydrated) return;
    const workspaces = Object.values(useNekoSessionStore.getState().sessions)
      .flatMap((item) => item.workspace ? [item.workspace] : []);
    void ensureWorkspaceProjects(workspaces);
  }, [ensureWorkspaceProjects, hydrated, knownWorkspaceKey, projectsHydrated]);

  useEffect(() => {
    if (!hydrated || agents.length === 0) return;
    void refreshProviderSessions(agents, knownWorkspacePaths, { includeProjectScoped: false });
  }, [agents, hydrated, knownWorkspaceKey, refreshProviderSessions]);

  useEffect(() => {
    setInspectorOpen(false);
  }, [activeSessionId]);

  useEffect(() => {
    if (session) setCoworkerHomeOpen(false);
  }, [session?.id]);

  useEffect(() => {
    if (!taskLaunch || !projectsHydrated) return;
    setActiveSession(null);
    setCoworkerHomeOpen(false);
    void ensureWorkspaceProjects([taskLaunch.workspace]).then(() => {
      const project = projectForWorkspace(
        useNekoProjectStore.getState().projects,
        taskLaunch.workspace.path,
      );
      setSelectedProjectId(project?.id ?? null);
      setProjectHomeResetToken((value) => value + 1);
    });
  }, [ensureWorkspaceProjects, projectsHydrated, setActiveSession, taskLaunch?.execution.runId, taskLaunch?.workspace.path]);

  useEffect(() => {
    if (!session?.workspace) return;
    const project = projectForSession(projects, session);
    if (project) setSelectedProjectId(project.id);
  }, [projects, session?.id, session?.workspace?.path]);

  useEffect(() => {
    if (!session?.workspace) return;
    const shouldRefresh = useNekoWorkspaceStore.getState().sessions[session.id]?.open ?? false;
    ensureWorkspaceSession(session.id);
    restoreActivities(
      session.id,
      session.workspace,
      session.events.flatMap((event) =>
        event.data.type === "workspace-activity"
          ? [{
              id: event.data.activityId,
              title: event.data.title,
              kind: "file" as const,
              status: event.data.status,
              operation: event.data.operation ?? undefined,
              locations: event.data.locations,
              toolName: event.data.toolName,
              detail: event.data.detail,
            }]
          : [],
      ),
    );
    if (shouldRefresh) void refreshWorkspace(session.id, session.workspace);
  }, [
    ensureWorkspaceSession,
    refreshWorkspace,
    restoreActivities,
    session?.id,
    session?.workspace?.path,
  ]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.altKey || event.shiftKey || !(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (key !== "k" && key !== "b") return;
      event.preventDefault();
      event.stopPropagation();
      if (key === "k") setCommandCenterOpen((value) => {
        if (!value) markWiiiPerformance("wiii:command:open-start");
        return !value;
      });
      else setSidebarOpen((value) => !value);
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, []);

  useEffect(() => {
    if (compactSidebar) setSidebarOpen(false);
  }, [compactSidebar]);

  const handleProjectCommand = async () => {
    if (!session) return;
    if (session.workspace) {
      if (!useNekoWorkspaceStore.getState().sessions[session.id]?.open) {
        if (compactWorkspace) setSidebarOpen(false);
        toggleWorkspace(session.id);
      }
      void refreshWorkspace(session.id, session.workspace, { force: true });
      return;
    }
    const workspace = await chooseWorkspaceFolder();
    if (workspace) await attachWorkspace(session.id, workspace);
  };

  const workspaceSessionId = session?.id;
  const sessionWorkspace = session?.workspace;
  const handleToggleSessionWorkspace = useCallback(() => {
    if (!workspaceSessionId || !sessionWorkspace) return;

    setInspectorOpen(false);
    const opening = !useNekoWorkspaceStore.getState().sessions[workspaceSessionId]?.open;
    if (opening && compactWorkspace) setSidebarOpen(false);
    toggleWorkspace(workspaceSessionId);
    if (opening) void refreshWorkspace(workspaceSessionId, sessionWorkspace, { force: true });
  }, [compactWorkspace, refreshWorkspace, workspaceSessionId, sessionWorkspace, toggleWorkspace]);

  const handleImportProviderSession = async (providerSession: NekoProviderSessionRecord) => {
    const agent = agents.find((candidate) => candidate.id === providerSession.providerId);
    if (!agent?.found) {
      throw new Error("Harness của phiên này hiện không còn sẵn sàng trên máy.");
    }
    const workspace = providerSession.workspacePath && isAbsoluteWorkspacePath(providerSession.workspacePath)
      ? workspaceFromPath(providerSession.workspacePath)
      : await chooseWorkspaceFolder();
    if (!workspace) {
      throw new Error("Cần chọn folder gốc trước khi gắn phiên này vào Wiii.");
    }
    await importProviderSession(providerSession, agent, workspace);
  };

  const showOverview = useCallback(() => {
    setActiveSession(null);
    setSelectedProjectId(null);
    setCoworkerHomeOpen(false);
    if (compactSidebar) setSidebarOpen(false);
  }, [compactSidebar, setActiveSession]);

  const showCoworkerHome = useCallback(() => {
    setActiveSession(null);
    setSelectedProjectId(null);
    setCoworkerHomeOpen(true);
    if (compactSidebar) setSidebarOpen(false);
  }, [compactSidebar, setActiveSession]);

  const selectProject = useCallback((projectId: string) => {
    setActiveSession(null);
    setCoworkerHomeOpen(false);
    setSelectedProjectId(projectId);
    setProjectHomeResetToken((value) => value + 1);
    if (compactSidebar) setSidebarOpen(false);
  }, [compactSidebar, setActiveSession]);

  const openSession = useCallback((sessionId: string, projectId: string | null) => {
    markWiiiPerformance("wiii:session:switch-start");
    setCoworkerHomeOpen(false);
    setSelectedProjectId(projectId);
    setActiveSession(sessionId);
    if (compactSidebar) setSidebarOpen(false);
  }, [compactSidebar, setActiveSession]);

  const openSessionFromCatalog = useCallback((sessionId: string) => {
    const target = useNekoSessionStore.getState().sessions[sessionId];
    openSession(sessionId, target?.projectId ?? null);
  }, [openSession]);

  const handleNewSession = useCallback(() => {
    if (compactSidebar) setSidebarOpen(false);
    const latestSession = [...sessions]
      .sort((left, right) => right.updatedAt - left.updatedAt)
      .find((item) => item.workspace);
    const target = selectedProject
      ?? (latestSession ? projectForSession(projects, latestSession) : null)
      ?? [...projects].sort((left, right) => right.updatedAt - left.updatedAt)[0]
      ?? null;
    setActiveSession(null);
    setCoworkerHomeOpen(false);
    if (!target) {
      setProjectDialog("create");
      return;
    }
    setSelectedProjectId(target.id);
    setProjectHomeResetToken((value) => value + 1);
  }, [compactSidebar, projects, selectedProject, sessions, setActiveSession]);

  const openProjectDialog = useCallback(() => setProjectDialog("create"), []);
  const openCommandCenter = useCallback(() => {
    markWiiiPerformance("wiii:command:open-start");
    setCommandCenterOpen(true);
  }, []);
  const openConnectionsFromSidebar = useCallback(() => {
    if (compactSidebar) setSidebarOpen(false);
    onOpenConnections();
  }, [compactSidebar, onOpenConnections]);
  const openProjectDialogFromSidebar = useCallback(() => {
    if (compactSidebar) setSidebarOpen(false);
    openProjectDialog();
  }, [compactSidebar, openProjectDialog]);
  const editProjectFromSidebar = useCallback((projectId: string) => {
    if (compactSidebar) setSidebarOpen(false);
    setProjectDialog(projectId);
  }, [compactSidebar]);

  const handleClientCommand = (command: ClientCommandName) => {
    if (command === "new") handleNewSession();
    else if (command === "project") void handleProjectCommand();
    else if (command === "search") openCommandCenter();
    else setInspectorOpen(true);
  };

  const insertIntoComposer = (text: string) => {
    setInsertRequest((current) => ({ text, token: (current?.token ?? 0) + 1 }));
  };

  const handleWorkbenchAction = (action: WorkbenchActionName) => {
    if (action === "new") handleNewSession();
    else if (action === "toggle-sidebar") setSidebarOpen((value) => !value);
    else if (action === "project") void handleProjectCommand();
    else setInspectorOpen(true);
  };

  const sidebarToggle = (
    <button
      type="button"
      className="nk-chrome-button grid h-8 w-8 shrink-0 place-items-center rounded-md text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"
      aria-label={sidebarOpen ? "Ẩn cây dự án và phiên" : "Hiện cây dự án và phiên"}
      aria-pressed={!sidebarOpen}
      aria-expanded={sidebarOpen}
      aria-keyshortcuts="Control+B Meta+B"
      title={`${sidebarOpen ? "Ẩn" : "Hiện"} cây dự án và phiên (Ctrl+B / ⌘B)`}
      onClick={() => setSidebarOpen((value) => !value)}
      data-testid="neko-sidebar-toggle"
    >
      {sidebarOpen ? (
        <PanelLeftClose aria-hidden="true" className="h-4 w-4" />
      ) : (
        <PanelLeft aria-hidden="true" className="h-4 w-4" />
      )}
    </button>
  );

  const titleWorkspaceOpen = session?.workspace
    ? Boolean(workspacePane?.open)
    : Boolean(projectWorkspacePane?.open);
  const workspaceAvailable = Boolean(session?.workspace || (projectHome && projectWorkspaceRoot));
  const restoreWorkspaceFocus = useCallback(() => workspaceToggleRef.current?.focus(), []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.shiftKey
        || !(event.ctrlKey || event.metaKey) || !event.altKey
        || event.key.toLowerCase() !== "b" || !workspaceAvailable) return;
      event.preventDefault();
      event.stopPropagation();
      if (session?.workspace) handleToggleSessionWorkspace();
      else toggleProjectWorkspace();
      workspaceToggleRef.current?.focus();
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [handleToggleSessionWorkspace, session?.workspace, toggleProjectWorkspace, workspaceAvailable]);

  const titleWorkspaceToggle = session?.workspace || (projectHome && projectWorkspaceRoot) ? (
    <button
      ref={workspaceToggleRef}
      type="button"
      className={`nk-chrome-button relative inline-flex h-8 min-w-8 shrink-0 items-center justify-center gap-1.5 rounded-md px-2 text-[12px] ${titleWorkspaceOpen ? "bg-[var(--nk-overlay-strong)] text-[var(--nk-text)]" : "text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"}`}
      aria-label={session?.workspace
        ? (titleWorkspaceOpen ? "Ẩn workspace phiên" : "Mở workspace phiên")
        : (titleWorkspaceOpen ? "Ẩn công cụ Project" : "Mở công cụ Project")}
      aria-pressed={titleWorkspaceOpen}
      aria-expanded={titleWorkspaceOpen}
      title={`${titleWorkspaceOpen ? "Ẩn" : "Mở"} công cụ (Ctrl+Alt+B / ⌘⌥B)`}
      aria-keyshortcuts="Control+Alt+B Meta+Alt+B"
      onClick={session?.workspace ? handleToggleSessionWorkspace : toggleProjectWorkspace}
      data-testid={session?.workspace ? "session-workspace-toggle" : "project-workspace-toggle"}
    >
      <PanelRight aria-hidden="true" className="h-4 w-4" />
      <span className="hidden sm:inline">Công cụ</span>
      {workspacePane?.unseenChanges ? <span aria-label="Có thay đổi mới" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-[var(--nk-accent)]" /> : null}
    </button>
  ) : null;

  const sidebarSurface = (
    <SessionSidebar
      header={<>
        <WiiiNavigation onOpenManaged={onOpenManaged} onOpenConnections={onOpenConnections} onOpenWork={onOpenWork} showWorkNavigation={showWorkNavigation} />
        <button type="button" className="nk-chrome-button grid h-8 w-8 place-items-center rounded-md text-[var(--nk-text-2)]"
          aria-label="Tìm phiên hoặc chạy lệnh" title="Tìm phiên hoặc chạy lệnh (Ctrl+K / ⌘K)" aria-keyshortcuts="Control+K Meta+K"
          onClick={openCommandCenter}><Search size={16} aria-hidden="true" /></button>
      </>}
      overviewActive={!session && !projectHome && !coworkerHomeOpen}
      coworkerActive={coworkerHomeOpen}
      onShowConnections={openConnectionsFromSidebar}
      projects={projects}
      selectedProjectId={selectedProjectId}
      externalSessionCount={externalSessionCount}
      onShowOverview={showOverview}
      onShowCoworker={showCoworkerHome}
      onNewSession={handleNewSession}
      onCreateProject={openProjectDialogFromSidebar}
      onSelectProject={selectProject}
      onEditProject={editProjectFromSidebar}
      onOpenSession={openSession}
    />
  );

  return (
    <div className="nk-root flex h-screen flex-col bg-[var(--nk-canvas)] text-[var(--nk-text)]">
      <CompletionNotices onOpen={(sessionId) => {
        if (useNekoSessionStore.getState().sessions[sessionId]) openSessionFromCatalog(sessionId);
      }} />
      <TitleBar
        minimal
        browserVisible
        leading={<>{sidebarToggle}<NekoMenuBar ready={hydrated}
          sidebarOpen={sidebarOpen} workspaceOpen={titleWorkspaceOpen} workspaceAvailable={workspaceAvailable}
          onNewSession={handleNewSession} onCreateProject={openProjectDialog} onSearch={openCommandCenter}
          onToggleSidebar={() => setSidebarOpen((value) => !value)}
          onToggleWorkspace={session?.workspace ? handleToggleSessionWorkspace : toggleProjectWorkspace}
          onConnections={onOpenConnections} /></>}
        commandCenter={false}
      />
      <div className="relative flex min-h-0 flex-1">
        {!hydrated ? (
          <SessionRecoveryState
            loading={hydrating || !hydrationError}
            error={hydrationError}
            onRetry={() => void hydrate()}
          />
        ) : (
          <>
            {sidebarOpen && compactSidebar ? (
              <>
                <button
                  type="button"
                  className="absolute inset-0 z-40 bg-black/15"
                  aria-label="Đóng cây dự án và phiên"
                  onClick={() => setSidebarOpen(false)}
                />
                <div className="nk-sidebar-entry absolute inset-y-0 left-0 z-50 flex shadow-[16px_0_40px_rgba(20,20,20,0.14)]">
                  {sidebarSurface}
                </div>
              </>
            ) : sidebarOpen ? sidebarSurface : null}
            <section className="nk-work-area flex min-h-0 min-w-0 flex-1 flex-col" aria-label="Vùng làm việc">
              <header className="nk-surface-toolbar flex h-12 shrink-0 items-center justify-between gap-3 px-4" data-testid="work-area-toolbar">
                <div className="flex min-w-0 items-center gap-2.5">
                  {session && <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${sessionStatusDotClass(session)}`} />}
                  <div className="min-w-0">
                    <h1 className="truncate text-[13px] font-medium text-[var(--nk-text)]">{session?.title ?? (coworkerHomeOpen ? "Neko · Đồng nghiệp AI" : projectHome?.name ?? "Tổng quan")}</h1>
                    {session && <p className="truncate text-[10.5px] text-[var(--nk-text-3)]">{session.agentName} · {NEKO_SESSION_STATUS_LABELS[session.status]}</p>}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1" data-testid="work-area-actions">
                  {session && <button type="button" className="nk-chrome-button grid h-8 w-8 place-items-center rounded-md text-[var(--nk-text-3)]"
                    aria-label={inspectorOpen ? "Ẩn thông tin phiên" : "Mở thông tin phiên"} aria-pressed={inspectorOpen} title="Thông tin phiên"
                    onClick={() => { if (!inspectorOpen) closeWorkspace(session.id); setInspectorOpen((value) => !value); }}><Info size={15} aria-hidden="true" /></button>}
                  {session && session.status !== "exited" && session.status !== "stopping" && (session.status !== "error" || session.runtime !== null) && (
                    <button type="button" className="nk-chrome-button flex h-8 items-center gap-1.5 rounded-md px-2 text-[11.5px] text-[var(--nk-text-3)]" onClick={() => void closeSession(session.id)}><Power size={13} aria-hidden="true" />Kết thúc</button>
                  )}
                  {titleWorkspaceToggle}
                </div>
              </header>
            {session ? (
          <div className="relative flex min-h-0 min-w-0 flex-1">
            <Group
              orientation="horizontal"
              id={`neko-workspace-layout-${session.id}`}
              defaultLayout={sessionWorkspaceLayout.defaultLayout}
              onLayoutChanged={sessionWorkspaceLayout.onLayoutChanged}
              className="min-w-0 flex-1"
            >
              <Panel
                id="neko-chat"
                defaultSize={sessionPresence.present && !compactWorkspace ? 42 : 100}
                minSize={28}
              >
            <div className="flex h-full min-w-0 flex-1 flex-col">
              <LiveNekoTranscript
                sessionId={session.id}
                onResolvePermission={(optionId) => void resolvePermission(optionId)}
                onInsertPrompt={insertIntoComposer}
              />
              <NekoComposer
                key={session.id}
                session={session}
                disabled={session.status === "connecting" || session.status === "error"}
                streaming={session.status === "streaming"}
                onSend={(text, onAccepted) => sendPrompt(text, onAccepted)}
                onCancel={() => void cancelTurn()}
                onSetConfigOption={(optionId, value) => void setConfigOption(optionId, value)}
                onClientCommand={handleClientCommand}
                insertRequest={insertRequest}
              />
            </div>
              </Panel>
              {sessionPresence.present && !compactWorkspace ? (
                <>
                  <Separator className="nk-workspace-separator" aria-label="Điều chỉnh độ rộng công cụ" disabled={!workspacePane?.open} />
                  <Panel id="neko-workspace" defaultSize={58} minSize={36}>
                    <div ref={sessionPresence.ref} className="nk-workspace-frame h-full" aria-hidden={!workspacePane?.open || undefined}>
                      {sessionWorkspaceTarget ? <NekoWorkspacePane target={sessionWorkspaceTarget} exiting={!workspacePane?.open} onClose={restoreWorkspaceFocus} /> : null}
                    </div>
                  </Panel>
                </>
              ) : null}
            </Group>
            {sessionPresence.present && compactWorkspace ? (
              <div ref={sessionPresence.ref} className="nk-workspace-frame absolute inset-0 z-30 bg-[var(--nk-composer)]" aria-hidden={!workspacePane?.open || undefined}>
                {sessionWorkspaceTarget ? <NekoWorkspacePane target={sessionWorkspaceTarget} exiting={!workspacePane?.open} onClose={restoreWorkspaceFocus} /> : null}
              </div>
            ) : null}
            {inspectorOpen ? (
              <>
                <button
                  type="button"
                  className="absolute inset-0 z-20 bg-black/10 xl:hidden"
                  aria-label="Đóng thông tin phiên"
                  onClick={() => setInspectorOpen(false)}
                />
                <SessionInspector
                  session={session}
                  onClose={() => setInspectorOpen(false)}
                  onSetConfigOption={(optionId, value) => void setConfigOption(optionId, value)}
                  onInsertCommand={(text) => {
                    insertIntoComposer(text);
                    setInspectorOpen(false);
                  }}
                />
              </>
            ) : null}
          </div>
            ) : coworkerHomeOpen ? (
              <Suspense fallback={<SurfaceLoadingState />}>
                <LazyNekoCoworkerHome projects={projects} />
              </Suspense>
            ) : projectHome ? (
              <div className="relative flex min-h-0 min-w-0 flex-1">
                <Group
                  orientation="horizontal"
                  id={`neko-project-workspace-layout-${projectHome.id}`}
                  defaultLayout={projectWorkspaceLayout.defaultLayout}
                  onLayoutChanged={projectWorkspaceLayout.onLayoutChanged}
                  className="min-w-0 flex-1"
                >
                  <Panel
                    id="neko-project-home"
                    defaultSize={projectPresence.present && !compactWorkspace ? 42 : 100}
                    minSize={28}
                  >
                    <ProjectHome
                      key={projectHome.id}
                      project={projectHome}
                      taskLaunch={taskLaunch}
                      resetToken={projectHomeResetToken}
                      onWorkspaceChange={updateProjectWorkspace}
                      onManageHarness={() => {
                        showOverview();
                        setHarnessFocusRequest((value) => value + 1);
                      }}
                      onEditProject={selectedProject
                        ? () => setProjectDialog(selectedProject.id)
                        : undefined}
                    />
                  </Panel>
                  {projectPresence.present && projectWorkspaceTarget && !compactWorkspace ? (
                    <>
                      <Separator className="nk-workspace-separator" aria-label="Điều chỉnh độ rộng công cụ" disabled={!projectWorkspacePane?.open} />
                      <Panel id="neko-project-workspace" defaultSize={58} minSize={36}>
                        <div ref={projectPresence.ref} className="nk-workspace-frame h-full" aria-hidden={!projectWorkspacePane?.open || undefined}>
                          <NekoWorkspacePane target={projectWorkspaceTarget} requestedSurface="files" exiting={!projectWorkspacePane?.open} onClose={restoreWorkspaceFocus} />
                        </div>
                      </Panel>
                    </>
                  ) : null}
                </Group>
                {projectPresence.present && projectWorkspaceTarget && compactWorkspace ? (
                  <div ref={projectPresence.ref} className="nk-workspace-frame absolute inset-0 z-30 bg-[var(--nk-composer)]" aria-hidden={!projectWorkspacePane?.open || undefined}>
                    <NekoWorkspacePane target={projectWorkspaceTarget} requestedSurface="files" exiting={!projectWorkspacePane?.open} onClose={restoreWorkspaceFocus} />
                  </div>
                ) : null}
              </div>
            ) : (
              <NekoOverview
                harnessFocusRequest={harnessFocusRequest}
                sessions={sessions}
                agents={agents}
                providerCatalogs={providerCatalogs}
                discoveryLoading={providerDiscoveryLoading}
                onNewSession={handleNewSession}
                onOpenSession={openSessionFromCatalog}
                onRefreshDiscovery={() => void refreshProviderSessions(
                  agents,
                  knownWorkspacePaths,
                  { includeProjectScoped: true },
                )}
                onImportProviderSession={handleImportProviderSession}
              />
            )}
            </section>
          </>
        )}
      </div>
      {hydrated ? (
        <NekoCommandCenter
          open={commandCenterOpen}
          sessions={sessions}
          activeSession={session}
          sidebarOpen={sidebarOpen}
          onClose={() => setCommandCenterOpen(false)}
          onAction={handleWorkbenchAction}
          onSelectSession={openSessionFromCatalog}
          onInsertCommand={insertIntoComposer}
        />
      ) : null}
      {projectDialog ? (
        <ProjectDialog
          project={editingProject}
          onCancel={() => setProjectDialog(null)}
          onSave={async (name, roots) => {
            let projectId: string;
            if (editingProject) {
              await updateProject(editingProject.id, name, roots);
              projectId = editingProject.id;
            } else {
              projectId = await createProject(name, roots);
            }
            setProjectDialog(null);
            setActiveSession(null);
            setCoworkerHomeOpen(false);
            setSelectedProjectId(projectId);
            setProjectHomeResetToken((value) => value + 1);
          }}
        />
      ) : null}
    </div>
  );
}
