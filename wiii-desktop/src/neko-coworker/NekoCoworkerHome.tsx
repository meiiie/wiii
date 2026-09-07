import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BellRing,
  Check,
  Cpu,
  Database,
  Folder,
  HardDriveDownload,
  LoaderCircle,
  Monitor,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Unplug,
} from "lucide-react";
import { WiiiMark } from "@/components/common/WiiiMark";
import type { SignalInboxSummary } from "@/neko-computer/contracts";
import type { NekoProject } from "@/workbench/contracts";
import {
  consultSignalInbox,
  doctorComputer,
  installComputerPackage,
  removeComputer,
  removeComputerPackage,
} from "@/neko-computer/client";
import {
  coreComputerPackage,
  formatComputerBytes,
} from "@/neko-computer/package-model";
import { useNekoComputerStore } from "@/neko-computer/store";
import {
  DEFAULT_NEKO_COWORKER,
  coworkerWorkstationTitle,
} from "./profile";

export type SignalInboxViewState = SignalInboxSummary | "loading" | "unavailable";

export function signalInboxCardState(state: SignalInboxViewState): {
  value: string;
  detail: string;
  attention: boolean;
} {
  if (state === "loading") {
    return {
      value: "Đang kiểm tra",
      detail: "Đọc kho tín hiệu đã mã hóa",
      attention: false,
    };
  }
  if (state === "unavailable") {
    return {
      value: "Chưa kiểm tra được",
      detail: "Máy làm việc vẫn hoạt động bình thường",
      attention: false,
    };
  }
  if (state.gapCount > 0) {
    return {
      value: `${state.readyCount} việc đang chờ`,
      detail: `${state.gapCount} nguồn cần đồng bộ lại`,
      attention: true,
    };
  }
  if (state.readyCount > 0) {
    return {
      value: `${state.readyCount} việc đang chờ`,
      detail: "Neko sẽ kiểm tra trong phiên tiếp theo",
      attention: true,
    };
  }
  return {
    value: "Không có việc mới",
    detail: state.itemCount > 0
      ? `${state.itemCount} tín hiệu đã được xử lý hoặc hoãn`
      : "Kho tín hiệu đã cập nhật",
    attention: false,
  };
}

export function NekoCoworkerHome({ projects }: { projects: NekoProject[] }) {
  const coworker = DEFAULT_NEKO_COWORKER;
  const storedDoctor = useNekoComputerStore((state) => state.doctor);
  const status = useNekoComputerStore((state) => state.status);
  const refresh = useNekoComputerStore((state) => state.refresh);
  const grant = useNekoComputerStore((state) => state.grant);
  const revoke = useNekoComputerStore((state) => state.revoke);
  const ensure = useNekoComputerStore((state) => state.ensure);
  const [busyProject, setBusyProject] = useState<string | null>(null);
  const [pageBusy, setPageBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [removeOpen, setRemoveOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [inspectedDoctor, setInspectedDoctor] = useState(storedDoctor);
  const [signalInbox, setSignalInbox] = useState<SignalInboxViewState>("loading");
  const doctor = inspectedDoctor ?? storedDoctor;
  const corePackage = coreComputerPackage(doctor);
  const packageInstalled = corePackage?.state === "installed" || doctor?.packageReady === true;
  const packageRemovalBlocked = status?.environment?.seat.state !== undefined
    && status.environment.seat.state !== "available";
  const signalCard = signalInboxCardState(signalInbox);

  const refreshSignalInbox = useCallback(async () => {
    try {
      setSignalInbox(await consultSignalInbox(8));
    } catch {
      setSignalInbox("unavailable");
    }
  }, []);

  useEffect(() => {
    setPageBusy(true);
    void Promise.all([refresh(), doctorComputer(), refreshSignalInbox()])
      .then(([, result]) => setInspectedDoctor(result))
      .catch((reason) => setError(String(reason)))
      .finally(() => setPageBusy(false));
  }, [refresh, refreshSignalInbox]);

  const roots = useMemo(
    () => projects.flatMap((project) =>
      project.roots.map((root) => ({
        projectId: project.id,
        projectName: project.name,
        root,
      })),
    ),
    [projects],
  );
  const grantedKeys = useMemo(
    () => new Set((status?.grants ?? []).flatMap((item) => item.projectId ? [item.projectId] : [])),
    [status?.grants],
  );
  const activeKey = status?.activeProjectId ?? null;

  const runProjectAction = async (key: string, operation: () => Promise<void>) => {
    setBusyProject(key);
    setError(null);
    try {
      await operation();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusyProject(null);
    }
  };

  const refreshAll = async () => {
    setPageBusy(true);
    setError(null);
    try {
      const [, result] = await Promise.all([
        refresh(),
        doctorComputer(),
        refreshSignalInbox(),
      ]);
      setInspectedDoctor(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setPageBusy(false);
    }
  };

  const removeWorkstation = async () => {
    if (!status?.environmentId || confirmation !== "REMOVE NEKO") return;
    setPageBusy(true);
    setError(null);
    try {
      await removeComputer(status.environmentId, confirmation);
      await refresh();
      setRemoveOpen(false);
      setConfirmation("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setPageBusy(false);
    }
  };

  const removePackage = async () => {
    setPageBusy(true);
    setError(null);
    try {
      await removeComputerPackage();
      await refreshAll();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      setPageBusy(false);
    }
  };

  const installPackage = async () => {
    setPageBusy(true);
    setError(null);
    try {
      setInspectedDoctor(await installComputerPackage());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setPageBusy(false);
    }
  };

  return (
    <main className="h-full overflow-y-auto bg-[var(--nk-canvas)] px-6 py-8" data-testid="neko-coworker-home">
      <div className="mx-auto max-w-4xl">
        <header className="flex flex-wrap items-start gap-4">
          <div className="grid h-14 w-14 place-items-center rounded-2xl bg-[var(--nk-overlay)] shadow-[0_12px_36px_rgba(38,33,28,0.08)]">
            <WiiiMark size={38} title={coworker.displayName} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--nk-text-3)]">
              {coworker.roleLabel} · AI
            </p>
            <h1 className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-[var(--nk-text)]">
              {coworkerWorkstationTitle(coworker)}
            </h1>
            <p className="mt-1 max-w-2xl text-[12px] leading-5 text-[var(--nk-text-3)]">
              Một máy làm việc bền vững của Neko. Hồ sơ Browser và ứng dụng thuộc về Neko;
              mỗi Project chỉ được gắn vào khi bạn cấp quyền và có thể thu hồi bất cứ lúc nào.
            </p>
          </div>
          <button
            type="button"
            disabled={pageBusy}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 text-[10.5px] font-medium text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] disabled:opacity-40"
            onClick={() => void refreshAll()}
          >
            {pageBusy ? <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />}
            Kiểm tra
          </button>
        </header>

        <section className="mt-7 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <SummaryCard
            icon={Monitor}
            label="Máy làm việc"
            value={status?.environmentId ? "Đã thiết lập" : "Chưa thiết lập"}
            detail={status?.environment?.operatingSystem ?? "Linux · Debian 12"}
          />
          <SummaryCard
            icon={Folder}
            label="Project đang mở"
            value={status?.environment?.projectName ?? "Không có"}
            detail={status?.environment?.projectPath ?? "Neko chưa nhận thư mục nào"}
          />
          <SummaryCard
            icon={ShieldCheck}
            label="Quyền Project"
            value={`${status?.grants.length ?? 0} Project`}
            detail="Chỉ thư mục được cấp quyền mới được gắn vào"
          />
          <SummaryCard
            icon={BellRing}
            label="Việc đang chờ Neko"
            value={signalCard.value}
            detail={signalCard.detail}
            attention={signalCard.attention}
            testId="neko-signal-inbox-summary"
          />
        </section>

        <section className="mt-6 rounded-2xl border border-[var(--nk-border)] bg-[var(--nk-composer)]">
          <div className="flex items-center justify-between border-b border-[var(--nk-border)] px-4 py-3">
            <div>
              <h2 className="text-[12.5px] font-semibold text-[var(--nk-text)]">Quyền truy cập Project</h2>
              <p className="mt-0.5 text-[10px] text-[var(--nk-text-3)]">Neko chỉ nhìn thấy Project đang được mở trong máy của mình.</p>
            </div>
            <span className="rounded-md bg-[var(--nk-overlay)] px-2 py-1 text-[9px] font-medium text-[var(--nk-text-3)]">
              Read + Write
            </span>
          </div>
          <div className="divide-y divide-[var(--nk-border)]">
            {roots.length ? roots.map(({ projectId, projectName, root }) => {
              const projectRef = { projectId, projectName, projectPath: root.path };
              const actionKey = `${projectId}:${root.path}`;
              const granted = grantedKeys.has(projectId);
              const active = activeKey === projectId;
              const busy = busyProject === actionKey;
              return (
                <div key={`${projectId}:${root.path}`} className="flex items-center gap-3 px-4 py-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--nk-overlay)]">
                    <Folder aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-text-3)]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-[11.5px] font-medium text-[var(--nk-text)]">{projectName}</p>
                      {active ? <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.06em] text-emerald-700">Đang mở</span> : null}
                      {granted && !active ? <Check aria-label="Đã cấp quyền" className="h-3 w-3 text-emerald-600" /> : null}
                    </div>
                    <p className="mt-0.5 truncate text-[9.5px] text-[var(--nk-ghost)]">{root.path}</p>
                  </div>
                  {busy ? <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin text-[var(--nk-text-3)]" /> : null}
                  {granted ? (
                    <>
                      {!active ? (
                        <button
                          type="button"
                          disabled={busy}
                          className="h-7 rounded-md bg-[var(--nk-text)] px-2.5 text-[9.5px] font-semibold text-[var(--nk-canvas)] disabled:opacity-40"
                          onClick={() => void runProjectAction(actionKey, () => ensure(projectRef))}
                        >
                          Mở trong máy Neko
                        </button>
                      ) : null}
                      <button
                        type="button"
                        disabled={busy}
                        className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[9.5px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-danger)] disabled:opacity-40"
                        onClick={() => void runProjectAction(actionKey, () => revoke(projectRef))}
                      >
                        <Unplug aria-hidden="true" className="h-3 w-3" /> Thu hồi
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      className="h-7 rounded-md border border-[var(--nk-border)] px-2.5 text-[9.5px] font-medium text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] disabled:opacity-40"
                      onClick={() => void runProjectAction(actionKey, () => grant(projectRef))}
                    >
                      Cấp quyền
                    </button>
                  )}
                </div>
              );
            }) : (
              <p className="px-4 py-6 text-center text-[11px] text-[var(--nk-text-3)]">Thêm Project trước để cấp quyền cho Neko.</p>
            )}
          </div>
        </section>

        <section className="mt-4 overflow-hidden rounded-2xl border border-[var(--nk-border)] bg-[var(--nk-composer)]">
          <div className="px-4 py-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--nk-overlay)]">
                <Cpu aria-hidden="true" className="h-4 w-4 text-[var(--nk-text-2)]" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-[11.5px] font-semibold text-[var(--nk-text)]">
                    {corePackage?.displayName ?? "Web Computer Core"}
                  </h2>
                  <span className="rounded bg-[var(--nk-overlay)] px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.06em] text-[var(--nk-text-3)]">
                    Gói cốt lõi
                  </span>
                </div>
                <p className="mt-0.5 text-[9.5px] text-[var(--nk-text-3)]">
                  {packageInstalled
                    ? `Đã tải trên máy · ${formatComputerBytes(corePackage?.installedBytes)}`
                    : "Chưa tải · thêm Desktop, Browser, Terminal và Files cho Neko"}
                </p>
              </div>
              {!packageInstalled ? (
                <button
                  type="button"
                  disabled={pageBusy || doctor?.runtimeReady === false}
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-[var(--nk-text)] px-3 text-[9.5px] font-semibold text-[var(--nk-canvas)] hover:opacity-90 disabled:opacity-35"
                  onClick={() => void installPackage()}
                >
                  {pageBusy ? <LoaderCircle aria-hidden="true" className="h-3 w-3 animate-spin" /> : <HardDriveDownload aria-hidden="true" className="h-3 w-3" />}
                  Tải gói
                </button>
              ) : null}
              {packageInstalled ? (
                <button
                  type="button"
                  disabled={pageBusy || packageRemovalBlocked}
                  title={packageRemovalBlocked ? "Trả quyền điều khiển màn hình trước khi gỡ gói" : undefined}
                  className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[9.5px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-danger)] disabled:opacity-40"
                  onClick={() => void removePackage()}
                >
                  <Trash2 aria-hidden="true" className="h-3 w-3" /> Gỡ phần đã tải
                </button>
              ) : null}
              {status?.environmentId ? (
                <button
                  type="button"
                  className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[9.5px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-danger)]"
                  onClick={() => setRemoveOpen((value) => !value)}
                >
                  <Trash2 aria-hidden="true" className="h-3 w-3" /> Gỡ máy Neko
                </button>
              ) : null}
            </div>
            {corePackage?.description ? (
              <p className="mt-3 text-[9.5px] leading-4 text-[var(--nk-text-3)]">
                {corePackage.description}. Một bản được dùng chung cho mọi Project; gỡ gói vẫn giữ hồ sơ đăng nhập và dữ liệu làm việc của Neko.
              </p>
            ) : null}
            {removeOpen ? (
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-[var(--nk-danger-soft)] pt-4">
                <p className="min-w-52 flex-1 text-[10px] leading-4 text-[var(--nk-text-3)]">
                  Thao tác này xóa hồ sơ Browser/Home của Neko, nhưng không xóa source Project.
                  Nhập <strong className="text-[var(--nk-text)]">REMOVE NEKO</strong>.
                </p>
                <input
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  aria-label="Xác nhận gỡ máy của Neko"
                  className="h-8 w-44 rounded-lg border border-[var(--nk-border)] bg-[var(--nk-canvas)] px-2.5 text-[10px] outline-none focus:ring-2 focus:ring-[var(--nk-focus-soft)]"
                />
                <button
                  type="button"
                  disabled={confirmation !== "REMOVE NEKO" || pageBusy}
                  className="h-8 rounded-lg bg-[var(--nk-danger)] px-3 text-[10px] font-semibold text-white disabled:opacity-35"
                  onClick={() => void removeWorkstation()}
                >
                  Xóa máy làm việc
                </button>
              </div>
            ) : null}
          </div>

          <div className="grid border-t border-[var(--nk-border)] bg-[var(--nk-inset)]/45 md:grid-cols-3 md:divide-x md:divide-[var(--nk-border)]">
            <StorageFact
              icon={HardDriveDownload}
              label="Ứng dụng & hệ thống"
              value="Một bản dùng chung"
              detail={doctor?.storage?.locationSelectable ? "Có thể chọn vị trí lưu" : "Lưu cục bộ · runtime quản lý vị trí"}
            />
            <StorageFact
              icon={Database}
              label="Hồ sơ của Neko"
              value="Lưu bền vững"
              detail="Giữ đăng nhập và thiết lập khi gỡ gói"
            />
            <StorageFact
              icon={Folder}
              label="Tệp Project"
              value="Ở nguyên vị trí gốc"
              detail="Wiii gắn thư mục đang mở, không tạo bản sao"
            />
          </div>
        </section>

        {error ? (
          <p className="mt-4 rounded-xl border border-[var(--nk-danger-soft)] bg-[var(--nk-danger-soft)]/35 px-3 py-2.5 text-[10px] leading-4 text-[var(--nk-danger)]">
            {error}
          </p>
        ) : null}
      </div>
    </main>
  );
}

function StorageFact({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof Monitor;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="flex gap-2.5 px-4 py-3">
      <Icon aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--nk-text-3)]" />
      <div className="min-w-0">
        <p className="text-[8.5px] font-semibold uppercase tracking-[0.07em] text-[var(--nk-ghost)]">{label}</p>
        <p className="mt-1 text-[10px] font-medium text-[var(--nk-text-2)]">{value}</p>
        <p className="mt-0.5 text-[9px] leading-4 text-[var(--nk-text-3)]">{detail}</p>
      </div>
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  detail,
  attention = false,
  testId,
}: {
  icon: typeof Monitor;
  label: string;
  value: string;
  detail: string;
  attention?: boolean;
  testId?: string;
}) {
  return (
    <div
      className={`rounded-2xl border bg-[var(--nk-composer)] px-4 py-4 ${attention ? "border-[var(--nk-warning)]/45 shadow-[0_8px_24px_rgba(166,107,32,0.08)]" : "border-[var(--nk-border)]"}`}
      data-attention={attention || undefined}
      data-testid={testId}
      aria-live={testId ? "polite" : undefined}
    >
      <div className="flex items-center gap-2 text-[9.5px] font-medium uppercase tracking-[0.08em] text-[var(--nk-text-3)]">
        <Icon aria-hidden="true" className={`h-3.5 w-3.5 ${attention ? "text-[var(--nk-warning)]" : ""}`} />
        {label}
      </div>
      <p className="mt-3 truncate text-[13px] font-semibold text-[var(--nk-text)]">{value}</p>
      <p className="mt-1 truncate text-[9.5px] text-[var(--nk-ghost)]">{detail}</p>
    </div>
  );
}
