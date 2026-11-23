import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ComputerTerminalResult, CoworkerComputerStatus } from "@/neko-computer/contracts";
import type { ProjectComputerState } from "@/neko-computer/store";

const mocks = vi.hoisted(() => ({
  hasNativeComputerAuthority: vi.fn(() => false),
  hydrate: vi.fn(async () => undefined),
  grant: vi.fn(async () => undefined),
  ensure: vi.fn(async () => undefined),
  execute: vi.fn(),
  handBack: vi.fn(),
  navigate: vi.fn(),
  observeSemantics: vi.fn(),
  remove: vi.fn(),
  removePackage: vi.fn(),
  reset: vi.fn(),
  resume: vi.fn(),
  suspend: vi.fn(),
  takeControl: vi.fn(),
  doctor: null as unknown,
  status: {
    coworkerId: "neko",
    environmentId: null,
    environment: null,
    activeProjectId: null,
    activeProjectPath: null,
    grants: [],
  } as CoworkerComputerStatus,
  project: {
    environment: null,
    semanticSnapshot: null,
    semanticError: null,
    loading: false,
    mutating: false,
    error: "Computer chỉ hoạt động trong Wiii Desktop.",
  } as ProjectComputerState,
}));

vi.mock("@/neko-computer/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/neko-computer/client")>();
  return {
    ...actual,
    hasNativeComputerAuthority: mocks.hasNativeComputerAuthority,
    NATIVE_COMPUTER_UNAVAILABLE_VI:
      "Bản xem trước trình duyệt không điều khiển được máy tính của Neko. Hãy dùng app desktop Wiii để kiểm tra và tải gói.",
    deleteComputerHistory: vi.fn(),
    readComputerHistory: vi.fn(),
    readComputerHistoryStatus: vi.fn(),
    setComputerHistoryEnabled: vi.fn(),
  };
});

vi.mock("@/neko-computer/store", () => ({
  computerProjectKey: (projectId: string) => projectId.trim(),
  useNekoComputerStore: (selector: (state: unknown) => unknown) =>
    selector({
      doctor: mocks.doctor,
      status: mocks.status,
      projects: { "project-1": mocks.project },
      hydrate: mocks.hydrate,
      grant: mocks.grant,
      ensure: mocks.ensure,
      execute: mocks.execute,
      handBack: mocks.handBack,
      navigate: mocks.navigate,
      observeSemantics: mocks.observeSemantics,
      remove: mocks.remove,
      removePackage: mocks.removePackage,
      reset: mocks.reset,
      resume: mocks.resume,
      suspend: mocks.suspend,
      takeControl: mocks.takeControl,
    }),
}));

import { NekoComputerSurface } from "@/neko-computer/NekoComputerSurface";

function readyComputer() {
  mocks.hasNativeComputerAuthority.mockReturnValue(true);
  mocks.project = { ...mocks.project, error: null, environment: {
    environmentId: "computer-fixture", projectId: "project-1", projectName: "CONT3",
    projectPath: "/tmp/cont3", providerKind: "local_docker", isolationClass: "shared_container",
    computerKind: "web_computer", operatingSystem: "Linux", semanticProtocol: "neko-computer.semantic.v1",
    state: "ready", projectMount: "/workspace/project", attachUrl: "http://127.0.0.1:4317/wiii.html#password=fixture",
    resources: { cpus: "2", memoryBytes: 4294967296, pidsLimit: 320,
      sharedMemoryBytes: 536870912, temporaryStorageBytes: 4294967296 },
    seat: { seatId: "seat-fixture", state: "available", leaseId: null, ownerId: null, updatedAt: "fixture" },
    createdAt: "fixture", updatedAt: "fixture",
  } };
}

describe("Neko Computer tools-pane invoke honesty", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.execute.mockReset();
    mocks.observeSemantics.mockReset().mockResolvedValue(undefined);
    mocks.hasNativeComputerAuthority.mockReturnValue(false);
    mocks.project = {
      environment: null,
      semanticSnapshot: null,
      semanticError: null,
      loading: false,
      mutating: false,
      error: "Computer chỉ hoạt động trong Wiii Desktop.",
    };
    mocks.doctor = null;
    mocks.status = {
      coworkerId: "neko",
      environmentId: null,
      environment: null,
      activeProjectId: null,
      activeProjectPath: null,
      grants: [],
    };
  });

  it("disables setup CTA in browser preview and keeps honesty details", async () => {
    render(
      <NekoComputerSurface
        mode="computer"
        projectId="project-1"
        projectName="CONT3"
        workspace={{ path: "/tmp/cont3", name: "CONT3" }}
      />,
    );

    await waitFor(() => expect(mocks.hydrate).toHaveBeenCalled());

    const cta = screen.getByTestId("computer-setup-cta") as HTMLButtonElement;
    expect(cta.disabled).toBe(true);
    expect(cta.getAttribute("title") ?? "").toMatch(/trình duyệt|desktop Wiii/i);
    expect(cta.textContent).toMatch(/Tải và thiết lập/i);

    expect(screen.getByText(/Computer chỉ hoạt động trong Wiii Desktop/i)).toBeTruthy();
    expect(screen.queryByText(/Cannot read properties of undefined/i)).toBeNull();
    expect(mocks.grant).not.toHaveBeenCalled();
    expect(mocks.ensure).not.toHaveBeenCalled();
  });

  it("keeps setup CTA enabled when native computer authority is present", async () => {
    mocks.hasNativeComputerAuthority.mockReturnValue(true);
    mocks.project = {
      ...mocks.project,
      error: null,
    };

    render(
      <NekoComputerSurface
        mode="computer"
        projectId="project-1"
        projectName="CONT3"
        workspace={{ path: "/tmp/cont3", name: "CONT3" }}
      />,
    );

    await waitFor(() => expect(mocks.hydrate).toHaveBeenCalled());
    const cta = screen.getByTestId("computer-setup-cta") as HTMLButtonElement;
    expect(cta.disabled).toBe(false);
    expect(cta.getAttribute("title")).toBeNull();
  });

  it("handles browser display readiness and failure without a permanent loading overlay", async () => {
    mocks.hasNativeComputerAuthority.mockReturnValue(true);
    mocks.project = {
      ...mocks.project,
      error: null,
      environment: {
        environmentId: "computer-fixture", projectId: "project-1", projectName: "CONT3",
        projectPath: "/tmp/cont3", providerKind: "local_docker", isolationClass: "shared_container",
        computerKind: "web_computer", operatingSystem: "Linux", semanticProtocol: "neko-computer.semantic.v1",
        state: "ready", projectMount: "/workspace/project", attachUrl: "http://127.0.0.1:4317/wiii.html#password=fixture",
        resources: { cpus: "2", memoryBytes: 4294967296, pidsLimit: 320,
          sharedMemoryBytes: 536870912, temporaryStorageBytes: 4294967296 },
        seat: { seatId: "seat-fixture", state: "available", leaseId: null, ownerId: null, updatedAt: "fixture" },
        createdAt: "fixture", updatedAt: "fixture",
      },
    };
    render(<NekoComputerSurface mode="browser" projectId="project-1" projectName="CONT3"
      workspace={{ path: "/tmp/cont3", name: "CONT3" }} />);
    await waitFor(() => expect(mocks.hydrate).toHaveBeenCalled());
    const frame = screen.getByTitle("Local Computer · CONT3") as HTMLIFrameElement;
    const report = (phase: string, origin = "http://127.0.0.1:4317") => fireEvent(window,
      new MessageEvent("message", { origin, source: frame.contentWindow,
        data: { source: "wiii-computer-viewer-v1", phase, at: 1 } }));

    report("framebuffer.visible", "https://untrusted.example");
    expect(screen.getByText("Đang mở màn hình Computer…")).toBeTruthy();
    report("framebuffer.visible");
    expect(screen.queryByText("Đang mở màn hình Computer…")).toBeNull();
    report("rfb.security_failure");
    expect(screen.getByText("Wiii không thể mở màn hình Computer.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Kết nối lại" })).toBeTruthy();
  });

  it.each([
    { phases: ["rfb.connected", "framebuffer.visible", "rfb.disconnected"], copy: "Kết nối màn hình đã bị gián đoạn." },
    { phases: ["rfb.security_failure"], copy: "Wiii không thể mở màn hình Computer." },
    { phases: ["framebuffer.visible"], copy: null },
    { phases: ["rfb.connected"], copy: "Computer đang chạy nhưng chưa gửi được hình ảnh." },
    { phases: [], copy: "Computer đang chạy nhưng chưa gửi được hình ảnh." },
  ])("shows truthful viewer status past the startup deadline ($phases)", async ({ phases, copy }) => {
    vi.useFakeTimers();
    readyComputer();
    const view = render(<NekoComputerSurface mode="computer" projectId="project-1" projectName="CONT3"
      workspace={{ path: "/tmp/cont3", name: "CONT3" }} />);
    try {
      const frame = screen.getByTitle("Local Computer · CONT3") as HTMLIFrameElement;
      const display = within(frame.parentElement!);
      for (const phase of phases) {
        fireEvent(window, new MessageEvent("message", {
          origin: "http://127.0.0.1:4317", source: frame.contentWindow,
          data: { source: "wiii-computer-viewer-v1", phase, at: 1 },
        }));
      }
      await act(async () => { vi.advanceTimersByTime(16_001); });
      if (copy) {
        expect(display.getByText(copy)).toBeTruthy();
        expect(display.getByRole("button", { name: "Kết nối lại" })).toBeTruthy();
      } else {
        expect(display.queryByText("Đang mở màn hình Computer…")).toBeNull();
        expect(display.queryByRole("button", { name: "Kết nối lại" })).toBeNull();
      }
      if (phases.includes("rfb.disconnected") || phases.includes("rfb.security_failure")) {
        expect(display.queryByText("Computer đang chạy nhưng chưa gửi được hình ảnh.")).toBeNull();
      }
    } finally {
      view.unmount();
      vi.useRealTimers();
    }
  });

  it("returns keyboard focus only from the current controlled viewer without changing the seat", async () => {
    readyComputer();
    mocks.project.environment!.seat.state = "user_controlled";
    const props = { mode: "computer" as const, projectId: "project-1", projectName: "CONT3",
      workspace: { path: "/tmp/cont3", name: "CONT3" } };
    const view = render(<NekoComputerSurface {...props} />);
    await act(async () => { await Promise.resolve(); });
    let frame = screen.getByTitle("Local Computer · CONT3") as HTMLIFrameElement;
    const summary = screen.getByText("Chi tiết").closest("summary")!;
    const control = screen.getByRole("button", { name: "Kết thúc can thiệp" });
    const report = (source: Window | null, origin = "http://127.0.0.1:4317") => fireEvent(window,
      new MessageEvent("message", { origin, source,
        data: { source: "wiii-computer-viewer-v1", phase: "keyboard.release", at: 1 } }));
    control.focus();
    report(frame.contentWindow, "https://untrusted.example");
    report(window);
    report(frame.contentWindow);
    expect(document.activeElement).toBe(control);
    frame.focus();
    report(frame.contentWindow);
    expect(document.activeElement).toBe(summary);
    expect(new URL(frame.src).searchParams.get("view_only")).toBe("0");
    const previousWindow = frame.contentWindow;
    mocks.project.environment!.seat.state = "available";
    await act(async () => { view.rerender(<NekoComputerSurface {...props} workspace={{ ...props.workspace }} />); });
    frame = screen.getByTitle("Local Computer · CONT3") as HTMLIFrameElement;
    const takeover = screen.getByRole("button", { name: "Nhận điều khiển" });
    frame.focus();
    report(previousWindow);
    report(frame.contentWindow);
    expect(document.activeElement).toBe(frame);
    expect(takeover).toBeTruthy();
    expect(new URL(frame.src).searchParams.get("view_only")).toBe("1");
    expect(mocks.handBack).not.toHaveBeenCalled();
    expect(mocks.takeControl).not.toHaveBeenCalled();
    expect(mocks.execute).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
  });

  it("waits for a fresh viewer on each display-mode switch and ignores the old frame", async () => {
    readyComputer();
    const props = { projectId: "project-1", projectName: "CONT3", workspace: { path: "/tmp/cont3", name: "CONT3" } };
    const view = render(<NekoComputerSurface {...props} mode="computer" />);
    let frame = screen.getByTitle("Local Computer · CONT3") as HTMLIFrameElement;
    const report = (source: Window | null) => fireEvent(window, new MessageEvent("message", {
      origin: "http://127.0.0.1:4317", source,
      data: { source: "wiii-computer-viewer-v1", phase: "framebuffer.visible", at: 1 },
    }));
    report(frame.contentWindow);
    expect(screen.queryByText("Đang mở màn hình Computer…")).toBeNull();
    for (const mode of ["browser", "computer", "browser"] as const) {
      const previousFrame = frame;
      const previousWindow = frame.contentWindow;
      view.rerender(<NekoComputerSurface {...props} mode={mode} />);
      frame = screen.getByTitle("Local Computer · CONT3") as HTMLIFrameElement;
      expect(frame).not.toBe(previousFrame);
      expect(frame.src).toBe(previousFrame.src);
      report(previousWindow);
      expect(screen.getByText("Đang mở màn hình Computer…")).toBeTruthy();
      report(frame.contentWindow);
      expect(screen.queryByText("Đang mở màn hình Computer…")).toBeNull();
    }
    expect(mocks.ensure).not.toHaveBeenCalled();
    expect(mocks.resume).not.toHaveBeenCalled();
    expect(mocks.suspend).not.toHaveBeenCalled();
    expect(mocks.takeControl).not.toHaveBeenCalled();
  });

  it("keeps completed Terminal output labeled with its executed command while editing the next draft", async () => {
    readyComputer();
    const result: ComputerTerminalResult = {
      environmentId: "computer-fixture", stdout: "5 tests passed\n", stderr: "", exitCode: 0,
      truncated: false, replayedWithoutOutput: false,
    };
    mocks.execute.mockResolvedValueOnce(result).mockResolvedValueOnce({ ...result, stdout: " M src/export.mjs\n" });
    render(<NekoComputerSurface mode="terminal" projectId="project-1" projectName="CONT3"
      workspace={{ path: "/tmp/cont3", name: "CONT3" }} />);
    const input = screen.getByRole("textbox", { name: "Lệnh trong Local Computer" }) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "node --test" } });
    fireEvent.click(screen.getByRole("button", { name: "Chạy" }));
    const output = await screen.findByText(/5 tests passed/);
    expect(output.textContent).toContain("$ node --test\n");

    fireEvent.change(input, { target: { value: "git status" } });
    fireEvent.blur(input);
    expect(input.value).toBe("git status");
    expect(output.textContent).toContain("$ node --test\n");
    expect(output.textContent).not.toContain("$ git status\n");
    expect(mocks.execute).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Chạy" }));
    const nextOutput = await screen.findByText(/M src\/export.mjs/);
    expect(nextOutput.textContent).toContain("$ git status\n");
    expect(nextOutput.textContent).not.toContain("5 tests passed");
    expect(mocks.execute.mock.calls.map(([, command]) => command)).toEqual(["node --test", "git status"]);
  });

  it("pairs an asynchronous Terminal result with the submitted command rather than an in-flight edit", async () => {
    readyComputer();
    let finish!: (result: ComputerTerminalResult) => void;
    mocks.execute.mockReturnValueOnce(new Promise<ComputerTerminalResult>((resolve) => { finish = resolve; }));
    render(<NekoComputerSurface mode="terminal" projectId="project-1" projectName="CONT3"
      workspace={{ path: "/tmp/cont3", name: "CONT3" }} />);
    const input = screen.getByRole("textbox", { name: "Lệnh trong Local Computer" }) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "printf ready" } });
    fireEvent.click(screen.getByRole("button", { name: "Chạy" }));
    expect((screen.getByRole("button", { name: "Đang chạy…" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(input, { target: { value: "git status" } });

    await act(async () => finish({
      environmentId: "computer-fixture", stdout: "ready", stderr: "", exitCode: 0,
      truncated: false, replayedWithoutOutput: false,
    }));
    expect(input.value).toBe("git status");
    const output = screen.getByText(/\[exit 0\]/);
    expect(output.textContent).toContain("$ printf ready\nready");
    expect(output.textContent).not.toContain("$ git status\n");
    expect(mocks.execute).toHaveBeenCalledTimes(1);
  });

  it("acknowledges actual inspection and never reports success over a newer error", async () => {
    readyComputer();
    const snapshot = {
      protocolVersion: "neko-computer.semantic.v1" as const, environmentId: "computer-fixture",
      stateVersion: "snapshot-1", capturedAt: "2026-11-22T05:00:00Z", platform: "linux_atspi" as const,
      screen: { width: 800, height: 600 }, activeWindowRef: null, nodes: [], truncated: false,
      scopeRef: null, projection: "full" as const, nextContinuation: null,
      deltaFromStateVersion: null, removedRefs: [],
    };
    mocks.observeSemantics.mockImplementationOnce(async () => { mocks.project.semanticSnapshot = snapshot; });
    render(<NekoComputerSurface mode="browser" projectId="project-1" projectName="CONT3"
      workspace={{ path: "/tmp/cont3", name: "CONT3" }} />);
    fireEvent.click(screen.getByText("Chi tiết"));
    expect(screen.queryByText("Đã kiểm tra giao diện")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra giao diện" }));
    await screen.findByText("Đã kiểm tra giao diện");
    mocks.observeSemantics.mockImplementationOnce(async () => {
      mocks.project.semanticError = "private native detail";
      throw new Error("private native detail");
    });
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra giao diện" }));
    await screen.findByText("Chưa kiểm tra được. Hãy thử lại.");
    expect(screen.queryByText("Đã kiểm tra giao diện")).toBeNull();
    expect(screen.queryByText("private native detail")).toBeNull();
  });
});
