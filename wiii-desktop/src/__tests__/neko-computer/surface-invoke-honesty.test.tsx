import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CoworkerComputerStatus } from "@/neko-computer/contracts";

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
  },
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

describe("Neko Computer tools-pane invoke honesty", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
});
