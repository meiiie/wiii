import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CoworkerComputerStatus } from "@/neko-computer/contracts";

const mocks = vi.hoisted(() => ({
  consultSignalInbox: vi.fn(),
  doctorComputer: vi.fn(),
  hasNativeComputerAuthority: vi.fn(() => false),
  installComputerPackage: vi.fn(),
  removeComputer: vi.fn(),
  removeComputerPackage: vi.fn(),
  refresh: vi.fn(),
  grant: vi.fn(),
  revoke: vi.fn(),
  ensure: vi.fn(),
  status: {
    coworkerId: "neko",
    environmentId: null,
    environment: null,
    activeProjectId: null,
    activeProjectPath: null,
    grants: [],
  } as CoworkerComputerStatus,
}));

vi.mock("@/neko-computer/client", () => ({
  consultSignalInbox: mocks.consultSignalInbox,
  doctorComputer: mocks.doctorComputer,
  hasNativeComputerAuthority: mocks.hasNativeComputerAuthority,
  installComputerPackage: mocks.installComputerPackage,
  NATIVE_COMPUTER_UNAVAILABLE_VI:
    "Bản xem trước trình duyệt không điều khiển được máy tính của Neko. Hãy dùng app desktop Wiii để kiểm tra và tải gói.",
  removeComputer: mocks.removeComputer,
  removeComputerPackage: mocks.removeComputerPackage,
}));

vi.mock("@/neko-computer/store", () => ({
  useNekoComputerStore: (selector: (state: unknown) => unknown) => selector({
    doctor: null,
    status: mocks.status,
    refresh: mocks.refresh,
    grant: mocks.grant,
    revoke: mocks.revoke,
    ensure: mocks.ensure,
  }),
}));

import { NekoCoworkerHome } from "@/neko-coworker/NekoCoworkerHome";

describe("Neko coworker browser computer-invoke honesty", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.hasNativeComputerAuthority.mockReturnValue(false);
    mocks.status = {
      coworkerId: "neko",
      environmentId: null,
      environment: null,
      activeProjectId: null,
      activeProjectPath: null,
      grants: [],
    };
  });

  it("shows VI honesty and skips invoke on mount in browser preview", async () => {
    render(<NekoCoworkerHome projects={[]} />);

    const honesty = await screen.findByTestId("browser-computer-honesty");
    expect(honesty.textContent).toMatch(/trình duyệt|desktop Wiii/i);
    expect(screen.queryByText(/Cannot read properties of undefined/i)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();

    await waitFor(() => {
      expect(mocks.doctorComputer).not.toHaveBeenCalled();
      expect(mocks.refresh).not.toHaveBeenCalled();
      expect(mocks.consultSignalInbox).not.toHaveBeenCalled();
    });

    const check = screen.getByRole("button", { name: "Kiểm tra" });
    expect((check as HTMLButtonElement).disabled).toBe(true);
    expect(check.getAttribute("title") ?? "").toMatch(/trình duyệt|desktop Wiii/i);

    const download = screen.getByRole("button", { name: /Tải gói/i });
    expect((download as HTMLButtonElement).disabled).toBe(true);
    expect(download.getAttribute("title") ?? "").toMatch(/trình duyệt|desktop Wiii/i);
  });

  it("still refreshes when native computer authority is present", async () => {
    mocks.hasNativeComputerAuthority.mockReturnValue(true);
    mocks.refresh.mockResolvedValue(mocks.status);
    mocks.doctorComputer.mockResolvedValue({
      supported: true,
      runtimeReady: true,
      packageReady: false,
      packages: [],
      storage: { locationSelectable: false },
    });
    mocks.consultSignalInbox.mockResolvedValue({
      protocolVersion: "wiii-signal-inbox.v1",
      encrypted: true,
      itemCount: 0,
      readyCount: 0,
      gapCount: 0,
      counts: [],
      pendingRefs: [],
    });

    render(<NekoCoworkerHome projects={[]} />);

    await waitFor(() => expect(mocks.doctorComputer).toHaveBeenCalledOnce());
    expect(mocks.refresh).toHaveBeenCalledOnce();
    expect(screen.queryByTestId("browser-computer-honesty")).toBeNull();
    expect((screen.getByRole("button", { name: "Kiểm tra" }) as HTMLButtonElement).disabled).toBe(false);
  });
});
