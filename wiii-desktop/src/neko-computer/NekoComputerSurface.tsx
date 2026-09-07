import { FormEvent, memo, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ChevronDown,
  CircleStop,
  Cpu,
  Globe2,
  HardDriveDownload,
  History,
  LoaderCircle,
  MonitorUp,
  PackageOpen,
  Play,
  RefreshCw,
  RotateCcw,
  ScanSearch,
  Send,
  SlidersHorizontal,
  TerminalSquare,
  Trash2,
  UserRound,
} from "lucide-react";
import { WiiiMark } from "@/components/common/WiiiMark";
import type { WorkspaceRef } from "@/workbench/contracts";
import {
  DEFAULT_NEKO_COWORKER,
  coworkerWorkstationTitle,
  describeCoworkerSeat,
  localUserControlsSeat,
} from "@/neko/coworker-profile";
import { computerProjectKey, useNekoComputerStore } from "./store";
import type {
  ComputerHistoryPage,
  ComputerHistoryStatus,
  ComputerResourcePreset,
  ComputerTerminalResult,
} from "./contracts";
import {
  deleteComputerHistory,
  readComputerHistory,
  readComputerHistoryStatus,
  setComputerHistoryEnabled,
} from "./client";
import {
  buildComputerViewerUrl,
  parseComputerViewerMessage,
} from "./viewer-lifecycle";
import { computerPackUpdateSummary, coreComputerPackage } from "./package-model";

export type NekoComputerSurfaceMode = "computer" | "browser" | "terminal";
type ViewerPresentationState =
  | "loading"
  | "connected"
  | "visible"
  | "stalled"
  | "disconnected"
  | "failed";

interface NekoComputerSurfaceProps {
  mode: NekoComputerSurfaceMode;
  projectId: string;
  projectName: string;
  workspace: WorkspaceRef;
}

function formatBytes(value: number): string {
  if (value >= 1024 ** 3) return `${Math.round((value / 1024 ** 3) * 10) / 10} GB`;
  if (value >= 1024 ** 2) return `${Math.round(value / 1024 ** 2)} MB`;
  return `${value} B`;
}

function statusLabel(state: string): string {
  if (state === "ready") return "Đang chạy";
  if (state === "suspended") return "Đã tạm dừng";
  if (state === "preparing") return "Đang chuẩn bị";
  if (state === "unknown_outcome") return "Cần kiểm tra";
  return "Có lỗi";
}

const RESOURCE_PRESETS: Array<{
  id: ComputerResourcePreset;
  label: string;
  detail: string;
}> = [
  { id: "auto", label: "Tự động", detail: "Wiii chọn theo máy này" },
  { id: "compact", label: "Tiết kiệm", detail: "1 CPU · 2 GB" },
  { id: "balanced", label: "Cân bằng", detail: "2 CPU · 4 GB" },
  { id: "performance", label: "Hiệu năng", detail: "4 CPU · 8 GB" },
];

function presetLabel(preset: ComputerResourcePreset | undefined): string {
  return RESOURCE_PRESETS.find((item) => item.id === preset)?.label ?? "Cân bằng";
}

function NekoComputerSurfaceComponent({
  mode,
  projectId,
  projectName,
  workspace,
}: NekoComputerSurfaceProps) {
  const key = computerProjectKey(projectId);
  const projectRef = useMemo(() => ({
    projectId,
    projectName,
    projectPath: workspace.path,
  }), [projectId, projectName, workspace.path]);
  const project = useNekoComputerStore((state) => state.projects[key]);
  const doctor = useNekoComputerStore((state) => state.doctor);
  const corePackage = coreComputerPackage(doctor);
  const status = useNekoComputerStore((state) => state.status);
  const environment = project?.environment ?? null;
  const packUpdate = computerPackUpdateSummary(environment, corePackage);
  const ensure = useNekoComputerStore((state) => state.ensure);
  const execute = useNekoComputerStore((state) => state.execute);
  const grant = useNekoComputerStore((state) => state.grant);
  const handBack = useNekoComputerStore((state) => state.handBack);
  const hydrate = useNekoComputerStore((state) => state.hydrate);
  const navigate = useNekoComputerStore((state) => state.navigate);
  const observeSemantics = useNekoComputerStore((state) => state.observeSemantics);
  const remove = useNekoComputerStore((state) => state.remove);
  const removePackage = useNekoComputerStore((state) => state.removePackage);
  const reset = useNekoComputerStore((state) => state.reset);
  const resume = useNekoComputerStore((state) => state.resume);
  const suspend = useNekoComputerStore((state) => state.suspend);
  const takeControl = useNekoComputerStore((state) => state.takeControl);
  const [url, setUrl] = useState("https://www.google.com");
  const [command, setCommand] = useState("pwd && ls -la");
  const [terminalResult, setTerminalResult] = useState<ComputerTerminalResult | null>(null);
  const [terminalBusy, setTerminalBusy] = useState(false);
  const [browserBusy, setBrowserBusy] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetConfirmation, setResetConfirmation] = useState("");
  const [removeOpen, setRemoveOpen] = useState(false);
  const [removeConfirmation, setRemoveConfirmation] = useState("");
  const [packageRemoveOpen, setPackageRemoveOpen] = useState(false);
  const [resourcePreset, setResourcePreset] = useState<ComputerResourcePreset>("auto");
  const [displayRevision, setDisplayRevision] = useState(0);
  const [viewerState, setViewerState] = useState<ViewerPresentationState>("loading");
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyDeleteArmed, setHistoryDeleteArmed] = useState(false);
  const [historyStatus, setHistoryStatus] = useState<ComputerHistoryStatus | null>(null);
  const [historyPage, setHistoryPage] = useState<ComputerHistoryPage | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const viewerFrameRef = useRef<HTMLIFrameElement>(null);
  const userOwnsSeat = environment
    ? localUserControlsSeat(environment.seat.state)
    : false;
  const canObserve = Boolean(environment?.state === "ready" && environment.attachUrl);
  const coworker = DEFAULT_NEKO_COWORKER;
  const workstationTitle = coworkerWorkstationTitle(coworker);
  const projectGranted = Boolean(
    status?.grants.some(
      (item) => item.projectId === projectId,
    ),
  );
  const workstationExists = Boolean(status?.environmentId);
  const viewerOwnershipLabel = environment
    ? describeCoworkerSeat(coworker, environment.seat.state, userOwnsSeat)
    : "Đang quan sát";
  const viewerUrl = useMemo(() => {
    if (!environment?.attachUrl) return null;
    return buildComputerViewerUrl(
      environment.attachUrl,
      userOwnsSeat ? "control" : "observe",
    );
  }, [environment?.attachUrl, userOwnsSeat]);
  const viewerOrigin = useMemo(() => {
    if (!environment?.attachUrl) return null;
    try {
      return new URL(environment.attachUrl).origin;
    } catch {
      return null;
    }
  }, [environment?.attachUrl]);
  const reconnectDisplay = useCallback(() => {
    setViewerState("loading");
    setDisplayRevision((value) => value + 1);
  }, []);

  const loadHistory = useCallback(async () => {
    if (!environment?.environmentId) return;
    setHistoryBusy(true);
    setHistoryError(null);
    try {
      const [nextStatus, nextPage] = await Promise.all([
        readComputerHistoryStatus(),
        readComputerHistory(environment.environmentId, null, 30),
      ]);
      setHistoryStatus(nextStatus);
      setHistoryPage(nextPage);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : String(error));
    } finally {
      setHistoryBusy(false);
    }
  }, [environment?.environmentId]);

  useEffect(() => {
    if (historyOpen) void loadHistory();
  }, [historyOpen, loadHistory]);

  useEffect(() => {
    void hydrate(projectRef).catch(() => undefined);
  }, [hydrate, projectRef]);

  useEffect(() => {
    setViewerState("loading");
    if (mode !== "computer" || !environment?.attachUrl || !viewerOrigin) return;
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== viewerOrigin) return;
      if (event.source !== viewerFrameRef.current?.contentWindow) return;
      const message = parseComputerViewerMessage(event.data);
      if (!message) return;
      if (message.phase === "rfb.connected") setViewerState("connected");
      else if (message.phase === "framebuffer.visible") setViewerState("visible");
      else if (message.phase === "rfb.disconnected") setViewerState("disconnected");
      else if (message.phase === "rfb.security_failure" || message.phase === "framebuffer.failed") {
        setViewerState("failed");
      } else if (message.phase === "rfb.timeout" || message.phase === "framebuffer.timeout") {
        setViewerState("stalled");
      }
    };
    window.addEventListener("message", onMessage);
    const timeout = window.setTimeout(() => {
      setViewerState((current) => current === "visible" ? current : "stalled");
    }, 16_000);
    return () => {
      window.removeEventListener("message", onMessage);
      window.clearTimeout(timeout);
    };
  }, [displayRevision, environment?.attachUrl, mode, viewerOrigin]);

  useEffect(() => {
    if (mode !== "computer" || environment?.state !== "ready") return;
    let active = true;
    setSemanticLoading(true);
    void observeSemantics(projectRef)
      .catch(() => undefined)
      .finally(() => {
        if (active) setSemanticLoading(false);
      });
    return () => {
      active = false;
    };
  }, [environment?.environmentId, environment?.state, mode, observeSemantics, projectRef]);

  const resetPhrase = environment ? "RESET NEKO" : "";
  const removePhrase = environment ? "REMOVE NEKO" : "";

  const onTerminal = async (event: FormEvent) => {
    event.preventDefault();
    if (!command.trim()) return;
    setTerminalBusy(true);
    try {
      setTerminalResult(await execute(projectRef, command));
    } catch {} finally {
      setTerminalBusy(false);
    }
  };

  const onNavigate = async (event: FormEvent) => {
    event.preventDefault();
    setBrowserBusy(true);
    try {
      await navigate(projectRef, url.trim());
    } catch {} finally {
      setBrowserBusy(false);
    }
  };

  if (project?.loading) {
    return (
      <ComputerCentered>
        <LoaderCircle aria-hidden="true" className="mx-auto h-6 w-6 animate-spin text-[var(--nk-text-3)]" />
        <p className="mt-3 text-[12px] text-[var(--nk-text-2)]">Đang kiểm tra máy tính của Neko…</p>
      </ComputerCentered>
    );
  }

  if (!environment) {
    return (
      <ComputerCentered>
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[var(--nk-overlay)] shadow-[0_8px_30px_rgba(38,33,28,0.06)]">
          <WiiiMark size={32} title={coworker.displayName} />
        </div>
        <p className="mt-3 text-[9px] font-semibold uppercase tracking-[0.12em] text-[var(--nk-text-3)]">
          {coworker.displayName} · {coworker.roleLabel}
        </p>
        <h3 className="mt-4 text-[15px] font-semibold text-[var(--nk-text)]">
          {workstationTitle}
        </h3>
        <p className="mx-auto mt-2 max-w-md text-[11px] leading-5 text-[var(--nk-text-3)]">
          Thêm một máy làm việc riêng để Neko dùng Browser, Terminal và ứng dụng mà không tranh thao tác với bạn.
          Neko đọc cấu trúc giao diện trước; hình ảnh và tọa độ chỉ là phương án dự phòng.
          Hồ sơ trình duyệt và ứng dụng thuộc về Neko; Project <strong className="font-medium text-[var(--nk-text-2)]">{workspace.name}</strong> chỉ được gắn vào khi bạn cấp quyền.
        </p>

        <details className="group mx-auto mt-5 max-w-lg rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] text-left">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-3.5 py-3 text-[10.5px] font-medium text-[var(--nk-text-2)]">
            <SlidersHorizontal aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-3)]" />
            Cấu hình
            <span className="ml-auto text-[9.5px] font-normal text-[var(--nk-text-3)]">
              {resourcePreset === "auto"
                ? `Tự động · ${presetLabel(doctor?.recommendedPreset)}`
                : presetLabel(resourcePreset)}
            </span>
            <ChevronDown aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-ghost)] transition-transform group-open:rotate-180" />
          </summary>
          <div className="grid gap-1 border-t border-[var(--nk-border)] p-2 sm:grid-cols-2">
            {RESOURCE_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                aria-pressed={resourcePreset === preset.id}
                className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${resourcePreset === preset.id ? "border-[var(--nk-border-strong)] bg-[var(--nk-overlay-strong)]" : "border-transparent hover:bg-[var(--nk-overlay)]"}`}
                onClick={() => setResourcePreset(preset.id)}
              >
                <span className="flex items-center gap-2 text-[10.5px] font-medium text-[var(--nk-text)]">
                  <Cpu aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-3)]" />
                  {preset.label}
                  {preset.id === "auto" ? (
                    <span className="rounded bg-[var(--nk-inset)] px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.06em] text-[var(--nk-text-3)]">Khuyên dùng</span>
                  ) : null}
                </span>
                <span className="mt-1 block text-[9.5px] text-[var(--nk-text-3)]">{preset.detail}</span>
              </button>
            ))}
          </div>
        </details>

        <div className="mx-auto mt-3 max-w-lg rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] px-3.5 py-3 text-left">
          <div className="flex items-center gap-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--nk-overlay)]">
              <PackageOpen aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-2)]" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[10.5px] font-medium text-[var(--nk-text)]">Gói máy tính công việc</p>
              <p className="mt-0.5 text-[9.5px] text-[var(--nk-text-3)]">
                {doctor?.packageReady
                  ? "Đã tải trên máy · có thể gỡ và tải lại bất cứ lúc nào"
                  : "Chưa tải · Wiii sẽ thêm tính năng này khi bạn thiết lập"}
              </p>
              {corePackage ? (
                <p className="mt-1 text-[8.5px] text-[var(--nk-text-3)]">
                  {corePackage.manifest.version} · {corePackage.manifest.channel === "stable" ? "ổn định" : "thử nghiệm"} · hồ sơ v{corePackage.manifest.profileSchemaVersion} · tự phục hồi lớp chạy khi nâng cấp lỗi
                </p>
              ) : null}
            </div>
            {doctor?.packageReady ? (
              <button
                type="button"
                disabled={project?.mutating}
                className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[9.5px] font-medium text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)] disabled:opacity-40"
                onClick={() => setPackageRemoveOpen((value) => !value)}
              >
                <Trash2 aria-hidden="true" className="h-3 w-3" /> Gỡ gói
              </button>
            ) : null}
          </div>
          {packageRemoveOpen ? (
            <div className="mt-3 border-t border-[var(--nk-border)] pt-3">
              <p className="text-[9.5px] leading-4 text-[var(--nk-text-3)]">
                Gỡ phần đã tải để giải phóng dung lượng. Project không bị xóa; hồ sơ làm việc của Neko chỉ được xóa khi bạn gỡ hẳn máy của Neko.
              </p>
              <div className="mt-2 flex justify-end gap-2">
                <button type="button" className="h-7 rounded-md px-2.5 text-[9.5px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)]" onClick={() => setPackageRemoveOpen(false)}>
                  Hủy
                </button>
                <button
                  type="button"
                  disabled={project?.mutating}
                  className="h-7 rounded-md bg-[var(--nk-text)] px-2.5 text-[9.5px] font-semibold text-[var(--nk-canvas)] disabled:opacity-40"
                  onClick={() => void removePackage(projectRef).then(() => setPackageRemoveOpen(false)).catch(() => undefined)}
                >
                  Gỡ gói đã tải
                </button>
              </div>
            </div>
          ) : null}
        </div>

        {doctor && !doctor.supported ? (
          <div className="mx-auto mt-5 max-w-lg rounded-xl border border-[var(--nk-danger-soft)] bg-[var(--nk-danger-soft)]/40 px-4 py-3 text-left">
            <p className="flex items-center gap-2 text-[11px] font-medium text-[var(--nk-danger)]">
              <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />
              Chưa thể bật Computer trên máy này
            </p>
            <p className="mt-1 text-[10.5px] leading-5 text-[var(--nk-text-3)]">
              Wiii cần nền tảng chạy cục bộ được bật trước. Không có thay đổi nào được thực hiện khi điều kiện này chưa sẵn sàng.
            </p>
            <button
              type="button"
              className="mt-2 inline-flex h-7 items-center gap-1.5 rounded-md border border-[var(--nk-border)] bg-[var(--nk-composer)] px-2.5 text-[10px] font-medium text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)]"
              onClick={() => void hydrate(projectRef).catch(() => undefined)}
            >
              <RefreshCw aria-hidden="true" className="h-3 w-3" /> Kiểm tra lại
            </button>
          </div>
        ) : (
          <button
            type="button"
            disabled={project?.mutating}
            className="mx-auto mt-5 inline-flex h-9 items-center gap-2 rounded-lg bg-[var(--nk-text)] px-4 text-[11px] font-semibold text-[var(--nk-canvas)] transition-opacity hover:opacity-90 disabled:opacity-50"
            onClick={() => void (async () => {
              if (!projectGranted) await grant(projectRef);
              await ensure(projectRef, resourcePreset);
            })().catch(() => undefined)}
          >
            {project?.mutating ? (
              <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <HardDriveDownload aria-hidden="true" className="h-3.5 w-3.5" />
            )}
            {workstationExists
              ? projectGranted
                ? "Mở Project trong máy Neko"
                : "Cấp quyền và mở Project"
              : doctor?.packageReady
                ? "Thiết lập máy của Neko"
                : "Tải và thiết lập máy của Neko"}
          </button>
        )}
        <p className="mx-auto mt-3 max-w-md text-[9.5px] leading-4 text-[var(--nk-ghost)]">
          Lần đầu cần tải vài trăm MB và có thể mất vài phút. Wiii sẽ tự hoàn tất các bước còn lại.
        </p>
        <details className="mx-auto mt-2 max-w-md text-left text-[9px] leading-4 text-[var(--nk-ghost)]">
          <summary className="cursor-pointer text-center hover:text-[var(--nk-text-3)]">Chi tiết kỹ thuật</summary>
          <p className="mt-2 rounded-lg bg-[var(--nk-inset)] px-3 py-2">
            Hệ điều hành: Linux · Debian 12 Bookworm. AI interface: Neko Computer Semantic v1 (AT-SPI). Provider: nền chạy cục bộ · 1 display seat. Project đang hoạt động được gắn tại /workspace/project;
            Wiii không gắn home, Docker socket hoặc thư mục credential của máy bạn. Đây chưa phải VM cách ly mã độc.
            {doctor?.detail ? ` ${doctor.detail}` : ""}
          </p>
        </details>
        {project?.error ? <ComputerError message={project.error} /> : null}
      </ComputerCentered>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-[var(--nk-canvas)]">
      <div className="flex min-h-10 shrink-0 flex-wrap items-center gap-2 border-b border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 py-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${environment.state === "ready" ? "bg-emerald-500" : environment.state === "unknown_outcome" ? "bg-amber-500" : "bg-[var(--nk-ghost)]"}`} />
        <WiiiMark size={18} title={coworker.displayName} className="shrink-0" />
        <span className="text-[10.5px] font-semibold text-[var(--nk-text)]">Máy của {coworker.displayName}</span>
        <span className="text-[9.5px] text-[var(--nk-text-3)]">
          {packUpdate ? "Cần nâng cấp" : statusLabel(environment.state)}
        </span>
        <span className="hidden text-[9px] text-[var(--nk-ghost)] xl:inline">
          {environment.operatingSystem} · {environment.resources.cpus} CPU · {formatBytes(environment.resources.memoryBytes)} · {environment.resources.pidsLimit} PID
        </span>
        <button
          type="button"
          disabled={semanticLoading || environment.state !== "ready"}
          className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[9px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] disabled:opacity-40"
          title={project?.semanticError
            ? `Bản đồ giao diện chưa sẵn sàng: ${project.semanticError}`
            : "Làm mới bản đồ giao diện dành cho agent"}
          onClick={() => {
            setSemanticLoading(true);
            void observeSemantics(projectRef)
              .catch(() => undefined)
              .finally(() => setSemanticLoading(false));
          }}
        >
          {semanticLoading ? <LoaderCircle aria-hidden="true" className="h-3 w-3 animate-spin" /> : <ScanSearch aria-hidden="true" className="h-3 w-3" />}
          {project?.semanticSnapshot
            ? `AI map · ${project.semanticSnapshot.nodes.length}`
            : project?.semanticError
              ? "AI map cần thử lại"
              : "AI map"}
        </button>
        <span className="ml-auto rounded-md bg-[var(--nk-overlay)] px-2 py-1 text-[8.5px] font-medium text-[var(--nk-text-3)]">
          Chạy trên máy
        </span>
        {mode === "computer" && canObserve ? (
          <ComputerControl
            icon={RefreshCw}
            label="Kết nối lại"
            onClick={reconnectDisplay}
          />
        ) : null}
        {mode === "computer" && environment.state === "ready" ? (
          userOwnsSeat ? (
            <ComputerControl
              icon={UserRound}
              label="Kết thúc can thiệp"
              disabled={project?.mutating}
              onClick={() => void handBack(projectRef).catch(() => undefined)}
            />
          ) : (
            <ComputerControl
              icon={MonitorUp}
              label={environment.seat.state === "agent_controlled" ? "Can thiệp" : "Nhận điều khiển"}
              disabled={project?.mutating}
              onClick={() => void takeControl(projectRef).catch(() => undefined)}
            />
          )
        ) : null}
        {environment.state === "suspended" ? (
          <ComputerControl
            icon={packUpdate ? PackageOpen : Play}
            label={packUpdate ? "Nâng cấp" : "Tiếp tục"}
            disabled={project?.mutating}
            onClick={() => void resume(projectRef).catch(() => undefined)}
          />
        ) : (
          <ComputerControl icon={CircleStop} label="Tạm dừng" disabled={project?.mutating || environment.state !== "ready"} onClick={() => void suspend(projectRef).catch(() => undefined)} />
        )}
        <ComputerControl icon={History} label="Lịch sử" onClick={() => {
          setHistoryDeleteArmed(false);
          setHistoryOpen((value) => !value);
        }} />
        <ComputerControl icon={RotateCcw} label="Reset" danger onClick={() => {
          setRemoveOpen(false);
          setResetOpen((value) => !value);
        }} />
        <ComputerControl icon={Trash2} label="Gỡ" danger onClick={() => {
          setResetOpen(false);
          setRemoveOpen((value) => !value);
        }} />
      </div>

      {packUpdate ? (
        <div
          data-testid="computer-pack-update"
          className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-amber-300/60 bg-amber-50/75 px-4 py-2 text-amber-950 dark:border-amber-800/60 dark:bg-amber-950/25 dark:text-amber-100"
        >
          <PackageOpen aria-hidden="true" className="h-4 w-4 shrink-0" />
          <p className="min-w-0 flex-1 text-[10px] leading-4">
            Máy của {coworker.displayName} đang dùng {packUpdate.activeVersion} và cần nâng lên {packUpdate.targetVersion}. Hồ sơ đăng nhập và dữ liệu ứng dụng được giữ nguyên.
          </p>
          <button
            type="button"
            disabled={project?.mutating}
            className="inline-flex h-7 items-center gap-1.5 rounded-md bg-amber-950 px-2.5 text-[9.5px] font-semibold text-white transition-colors hover:bg-amber-900 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-amber-200 dark:text-amber-950 dark:hover:bg-amber-100"
            onClick={() => void resume(projectRef).catch(() => undefined)}
          >
            {project?.mutating ? <LoaderCircle aria-hidden="true" className="h-3 w-3 animate-spin" /> : <RefreshCw aria-hidden="true" className="h-3 w-3" />}
            Nâng cấp ngay
          </button>
        </div>
      ) : null}

      {historyOpen ? (
        <div className="shrink-0 border-b border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 py-3">
          <div className="mx-auto max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-48 flex-1">
                <p className="text-[10.5px] font-semibold text-[var(--nk-text)]">Lịch sử Computer cục bộ</p>
                <p className="mt-0.5 text-[9px] text-[var(--nk-text-3)]">
                  {historyStatus
                    ? `${historyStatus.enabled ? "Đang ghi" : "Đang tắt"} · ${historyStatus.entryCount} hành động · mã hóa ${historyStatus.cipher} · giữ ${historyStatus.retentionDays} ngày`
                    : "Đang đọc lịch sử đã mã hóa…"}
                </p>
              </div>
              <button type="button" disabled={historyBusy} className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[9px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] disabled:opacity-40" onClick={() => void loadHistory()}>
                {historyBusy ? <LoaderCircle aria-hidden="true" className="h-3 w-3 animate-spin" /> : <RefreshCw aria-hidden="true" className="h-3 w-3" />}
                Làm mới
              </button>
              <button
                type="button"
                disabled={historyBusy || !historyStatus}
                className="inline-flex h-7 items-center rounded-md px-2 text-[9px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] disabled:opacity-40"
                onClick={() => {
                  if (!historyStatus) return;
                  setHistoryBusy(true);
                  void setComputerHistoryEnabled(!historyStatus.enabled)
                    .then((nextStatus) => setHistoryStatus(nextStatus))
                    .catch((error) => setHistoryError(error instanceof Error ? error.message : String(error)))
                    .finally(() => setHistoryBusy(false));
                }}
              >
                {historyStatus?.enabled ? "Tạm dừng ghi" : "Bật lịch sử"}
              </button>
              <button
                type="button"
                disabled={historyBusy || !historyPage?.entries.length}
                className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[9px] text-[var(--nk-danger)] hover:bg-[var(--nk-danger-soft)] disabled:opacity-35"
                onClick={() => {
                  if (!historyDeleteArmed) {
                    setHistoryDeleteArmed(true);
                    return;
                  }
                  setHistoryBusy(true);
                  void deleteComputerHistory(environment.environmentId)
                    .then(() => {
                      setHistoryDeleteArmed(false);
                      return loadHistory();
                    })
                    .catch((error) => setHistoryError(error instanceof Error ? error.message : String(error)))
                    .finally(() => setHistoryBusy(false));
                }}
              >
                <Trash2 aria-hidden="true" className="h-3 w-3" />
                {historyDeleteArmed ? "Nhấn lại để xóa" : "Xóa lịch sử Project"}
              </button>
            </div>
            {historyError ? <p className="mt-2 text-[9px] text-[var(--nk-danger)]">{historyError}</p> : null}
            {historyStatus?.lastError ? <p className="mt-2 text-[9px] text-amber-700">Lần ghi gần nhất có lỗi: {historyStatus.lastError}</p> : null}
            <div className="mt-2 max-h-44 overflow-auto rounded-lg border border-[var(--nk-border)] bg-[var(--nk-canvas)]">
              {historyPage?.entries.length ? historyPage.entries.map((entry) => (
                <div key={entry.seq} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b border-[var(--nk-border)] px-3 py-2 last:border-b-0">
                  <div className="min-w-0">
                    <p className="truncate text-[9.5px] font-medium text-[var(--nk-text)]">{entry.action} · {entry.targetRef}</p>
                    <p className="mt-0.5 truncate text-[8.5px] text-[var(--nk-text-3)]">{entry.effect ?? entry.outcome} · {entry.route ?? "adapter"} · {entry.evidence.join(", ") || "không có bằng chứng"}</p>
                  </div>
                  <time className="text-[8px] text-[var(--nk-ghost)]" dateTime={entry.at}>{new Date(entry.at).toLocaleString()}</time>
                </div>
              )) : (
                <p className="px-3 py-5 text-center text-[9px] text-[var(--nk-ghost)]">Chưa có hành động Computer nào được lưu.</p>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {resetOpen ? (
        <div className="shrink-0 border-b border-[var(--nk-danger-soft)] bg-[var(--nk-danger-soft)]/35 px-3 py-2.5">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2">
            <p className="min-w-48 flex-1 text-[10px] leading-4 text-[var(--nk-text-2)]">
              Reset xóa hồ sơ Browser/Home của Neko, không xóa Project. Nhập <strong>{resetPhrase}</strong> để xác nhận.
            </p>
            <input
              value={resetConfirmation}
              onChange={(event) => setResetConfirmation(event.target.value)}
              className="h-7 w-52 rounded-md border border-[var(--nk-border)] bg-[var(--nk-composer)] px-2 text-[10px] outline-none focus:ring-2 focus:ring-[var(--nk-focus-soft)]"
              aria-label="Xác nhận reset Local Computer"
            />
            <button
              type="button"
              disabled={resetConfirmation !== resetPhrase || project?.mutating}
              className="h-7 rounded-md bg-[var(--nk-danger)] px-3 text-[10px] font-semibold text-white disabled:opacity-35"
              onClick={() => void reset(projectRef, resetConfirmation).then(() => {
                setResetOpen(false);
                setResetConfirmation("");
              }).catch(() => undefined)}
            >
              Reset computer
            </button>
          </div>
        </div>
      ) : null}

      {removeOpen ? (
        <div className="shrink-0 border-b border-[var(--nk-danger-soft)] bg-[var(--nk-danger-soft)]/35 px-3 py-2.5">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2">
            <p className="min-w-48 flex-1 text-[10px] leading-4 text-[var(--nk-text-2)]">
              Gỡ máy làm việc và toàn bộ hồ sơ Browser/Home của Neko. Source của các Project không bị xóa. Nhập <strong>{removePhrase}</strong> để xác nhận.
            </p>
            <input
              value={removeConfirmation}
              onChange={(event) => setRemoveConfirmation(event.target.value)}
              className="h-7 w-52 rounded-md border border-[var(--nk-border)] bg-[var(--nk-composer)] px-2 text-[10px] outline-none focus:ring-2 focus:ring-[var(--nk-focus-soft)]"
              aria-label="Xác nhận gỡ Computer của Project"
            />
            <button
              type="button"
              disabled={removeConfirmation !== removePhrase || project?.mutating}
              className="h-7 rounded-md bg-[var(--nk-danger)] px-3 text-[10px] font-semibold text-white disabled:opacity-35"
              onClick={() => void remove(projectRef, removeConfirmation).then(() => {
                setRemoveOpen(false);
                setRemoveConfirmation("");
              }).catch(() => undefined)}
            >
              Gỡ Computer
            </button>
          </div>
        </div>
      ) : null}

      {environment.state === "unknown_outcome" ? (
        <div className="shrink-0 border-b border-amber-200/70 bg-amber-50/60 px-3 py-2.5">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2">
            <div className="min-w-48 flex-1">
              <p className="text-[10.5px] font-medium text-amber-900">Lần thiết lập trước chưa có kết quả chắc chắn</p>
              <p className="mt-0.5 text-[9.5px] leading-4 text-amber-800/75">Wiii sẽ kiểm tra tài nguyên đã có và tiếp tục an toàn, không tạo Computer trùng.</p>
            </div>
            <button
              type="button"
              disabled={project?.mutating}
              className="inline-flex h-7 items-center gap-1.5 rounded-md bg-amber-900 px-2.5 text-[9.5px] font-semibold text-white disabled:opacity-40"
              onClick={() => void ensure(projectRef, "auto").catch(() => undefined)}
            >
              {project?.mutating ? <LoaderCircle aria-hidden="true" className="h-3 w-3 animate-spin" /> : <RefreshCw aria-hidden="true" className="h-3 w-3" />}
              Kiểm tra và tiếp tục
            </button>
          </div>
        </div>
      ) : null}

      {mode === "browser" ? (
        <form className="flex h-10 shrink-0 items-center gap-2 border-b border-[var(--nk-border)] px-3" onSubmit={onNavigate}>
          <Globe2 aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-3)]" />
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            aria-label="Địa chỉ Browser của Local Computer"
            className="min-w-0 flex-1 bg-transparent text-[10.5px] text-[var(--nk-text)] outline-none placeholder:text-[var(--nk-ghost)]"
            placeholder="https://…"
          />
          <button type="submit" disabled={browserBusy || environment.state !== "ready"} className="grid h-7 w-7 place-items-center rounded-md text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] disabled:opacity-40" aria-label="Mở trong Browser">
            {browserBusy ? <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" /> : <Send aria-hidden="true" className="h-3.5 w-3.5" />}
          </button>
        </form>
      ) : null}

      {mode === "terminal" ? (
        <div className="flex min-h-0 flex-1 flex-col bg-[#151514] text-[#e8e5dd]">
          <form className="flex shrink-0 items-center gap-2 border-b border-white/10 px-3 py-2" onSubmit={onTerminal}>
            <TerminalSquare aria-hidden="true" className="h-3.5 w-3.5 text-[#9d9a92]" />
            <span className="text-[9px] text-[#77746d]">/workspace/project</span>
            <input value={command} onChange={(event) => setCommand(event.target.value)} aria-label="Lệnh trong Local Computer" className="min-w-0 flex-1 bg-transparent font-mono text-[10.5px] outline-none" />
            <button type="submit" disabled={terminalBusy || environment.state !== "ready"} className="rounded-md bg-white/10 px-2.5 py-1 text-[9.5px] hover:bg-white/15 disabled:opacity-40">
              {terminalBusy ? "Đang chạy…" : "Chạy"}
            </button>
          </form>
          <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words p-4 font-mono text-[10.5px] leading-5 text-[#d8d6cf]">
            {terminalResult
              ? `$ ${command}\n${terminalResult.stdout}${terminalResult.stderr ? `\n${terminalResult.stderr}` : ""}\n\n[exit ${terminalResult.exitCode ?? "unknown"}${terminalResult.truncated ? ", output truncated" : ""}]`
              : "Terminal này chạy bên trong Local Computer — không phải PowerShell/cmd của máy bạn."}
          </pre>
        </div>
      ) : (
        <div className="relative min-h-0 flex-1 bg-[#121211]">
          {canObserve && viewerUrl ? (
            <iframe
              ref={viewerFrameRef}
              key={`${environment.environmentId}:${displayRevision}:${userOwnsSeat ? "control" : "observe"}`}
              title={`Local Computer · ${workspace.name}`}
              src={viewerUrl}
              sandbox="allow-scripts allow-same-origin"
              referrerPolicy="no-referrer"
              className="h-full w-full border-0 bg-[#111]"
            />
          ) : (
            <ComputerCentered dark>
              <UserRound aria-hidden="true" className="mx-auto h-7 w-7 text-[#88857e]" />
              <h3 className="mt-3 text-[13px] font-semibold text-[#ece9e2]">
                {environment.state === "ready" ? "Màn hình đang được khóa theo lease" : "Computer chưa chạy"}
              </h3>
              <p className="mx-auto mt-1.5 max-w-sm text-[10.5px] leading-5 text-[#959189]">
                {environment.seat.state === "agent_controlled"
                  ? `Agent ${environment.seat.ownerId ?? "khác"} đang điều khiển. Handoff phải rõ ràng; Wiii không giành tab âm thầm.`
                  : "Nhận điều khiển để đăng nhập, xử lý CAPTCHA hoặc thao tác nhạy cảm. Khi xong, hãy trả màn hình cho agent."}
              </p>
              {environment.state === "ready" && environment.seat.state !== "agent_controlled" ? (
                <button type="button" disabled={project?.mutating} className="mx-auto mt-4 inline-flex h-8 items-center gap-2 rounded-lg bg-[#eeeae1] px-3 text-[10px] font-semibold text-[#171716] disabled:opacity-50" onClick={() => void takeControl(projectRef).catch(() => undefined)}>
                  <MonitorUp aria-hidden="true" className="h-3.5 w-3.5" /> Nhận điều khiển
                </button>
              ) : null}
            </ComputerCentered>
          )}
          {canObserve && viewerState !== "visible" ? (
            <ComputerViewerStatus state={viewerState} onReconnect={reconnectDisplay} />
          ) : null}
          {canObserve && viewerState === "visible" ? (
            <div className="pointer-events-none absolute bottom-3 left-1/2 z-20 -translate-x-1/2 rounded-full border border-white/10 bg-black/65 px-3 py-1.5 text-[9px] font-medium text-white/90 shadow-lg backdrop-blur">
              {viewerOwnershipLabel}
            </div>
          ) : null}
        </div>
      )}

      {project?.error ? <ComputerError message={project.error} compact /> : null}
    </div>
  );
}

export const NekoComputerSurface = memo(NekoComputerSurfaceComponent);

function ComputerViewerStatus({
  state,
  onReconnect,
}: {
  state: Exclude<ViewerPresentationState, "visible">;
  onReconnect: () => void;
}) {
  const waiting = state === "loading" || state === "connected";
  const copy = state === "connected"
    ? "Đã kết nối · đang nhận hình ảnh từ Computer…"
    : state === "disconnected"
      ? "Kết nối màn hình đã bị gián đoạn."
      : state === "failed"
        ? "Wiii không thể mở màn hình Computer."
        : state === "stalled"
          ? "Computer đang chạy nhưng chưa gửi được hình ảnh."
          : "Đang mở màn hình Computer…";
  return (
    <div className="absolute inset-0 z-10 grid place-items-center bg-[#121211] px-6 text-center">
      <div className="max-w-sm">
        {waiting ? (
          <LoaderCircle aria-hidden="true" className="mx-auto h-5 w-5 animate-spin text-[#8f8b84]" />
        ) : (
          <AlertTriangle aria-hidden="true" className="mx-auto h-5 w-5 text-amber-300/80" />
        )}
        <p className="mt-3 text-[11px] font-medium text-[#e7e3dc]">{copy}</p>
        {!waiting ? (
          <>
            <p className="mx-auto mt-1.5 text-[9.5px] leading-4 text-[#928e87]">
              Phiên Computer vẫn được giữ nguyên; kết nối lại không tạo thêm máy hay mất dữ liệu.
            </p>
            <button
              type="button"
              className="mx-auto mt-3 inline-flex h-8 items-center gap-1.5 rounded-lg bg-[#eeeae1] px-3 text-[10px] font-semibold text-[#171716] hover:bg-white"
              onClick={onReconnect}
            >
              <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" /> Kết nối lại
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}

function ComputerCentered({
  children,
  dark = false,
}: {
  children: ReactNode;
  dark?: boolean;
}) {
  return (
    <div className={`grid h-full min-h-0 place-items-center overflow-auto px-8 py-10 text-center ${dark ? "bg-[#121211]" : "bg-[var(--nk-canvas)]"}`}>
      <div className="w-full max-w-2xl">{children}</div>
    </div>
  );
}

function ComputerControl({
  icon: Icon,
  label,
  disabled,
  danger = false,
  onClick,
}: {
  icon: typeof Play;
  label: string;
  disabled?: boolean;
  danger?: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" disabled={disabled} className={`inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[9.5px] font-medium transition-colors disabled:opacity-35 ${danger ? "text-[var(--nk-danger)] hover:bg-[var(--nk-danger-soft)]" : "text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)]"}`} onClick={onClick}>
      <Icon aria-hidden="true" className="h-3 w-3" /> {label}
    </button>
  );
}

function ComputerError({ message, compact = false }: { message: string; compact?: boolean }) {
  const normalized = message.toLocaleLowerCase();
  const description = normalized.includes("not a valid windows path")
    ? {
        title: "Không thể kết nối thư mục Project",
        detail: "Wiii chưa chuyển được đường dẫn Windows cho Computer. Source Project vẫn nguyên vẹn; bạn có thể thử lại sau khi Wiii kiểm tra trạng thái.",
      }
    : normalized.includes("computer_package_in_use")
      ? {
          title: "Gói Computer đang được sử dụng",
          detail: "Hãy gỡ Computer khỏi các Project đang dùng trước. Dữ liệu Project không bị ảnh hưởng.",
        }
      : normalized.includes("unknown_outcome")
        ? {
            title: "Cần kiểm tra lại trạng thái",
            detail: "Wiii không tự lặp thao tác khi chưa biết kết quả trước đó. Hãy dùng nút kiểm tra và tiếp tục để khôi phục an toàn.",
          }
        : {
            title: "Không thể hoàn tất thao tác Computer",
            detail: "Không có thay đổi nào được lặp lại tự động. Bạn có thể kiểm tra lại nền tảng cục bộ rồi thử tiếp.",
          };

  return (
    <div role="alert" className={`${compact ? "shrink-0 border-t" : "mx-auto mt-4 max-w-lg rounded-xl border"} border-[var(--nk-danger-soft)] bg-[var(--nk-danger-soft)]/40 px-3 py-2.5 text-left`}>
      <p className="flex items-center gap-1.5 text-[10.5px] font-medium text-[var(--nk-danger)]">
        <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5 shrink-0" /> {description.title}
      </p>
      <p className="mt-1 text-[9.5px] leading-4 text-[var(--nk-text-3)]">{description.detail}</p>
      <details className="mt-1.5 text-[9px] text-[var(--nk-text-3)]">
        <summary className="cursor-pointer select-none hover:text-[var(--nk-text-2)]">Chi tiết lỗi</summary>
        <code className="mt-1.5 block max-h-24 overflow-auto whitespace-pre-wrap break-all rounded-md bg-[var(--nk-inset)] px-2 py-1.5 font-mono text-[8.5px] leading-4 text-[var(--nk-danger)]">
          {message}
        </code>
      </details>
    </div>
  );
}
