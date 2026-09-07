import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CoworkerComputerStatus } from "@/neko-computer/contracts";

const mocks = vi.hoisted(() => ({
  consultSignalInbox: vi.fn(),
  doctorComputer: vi.fn(),
  refresh: vi.fn(),
  grant: vi.fn(),
  revoke: vi.fn(),
  ensure: vi.fn(),
  installComputerPackage: vi.fn(),
  removeComputer: vi.fn(),
  removeComputerPackage: vi.fn(),
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
  installComputerPackage: mocks.installComputerPackage,
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

import {
  NekoCoworkerHome,
  signalInboxCardState,
} from "@/neko-coworker/NekoCoworkerHome";

const doctor = {
  supported: true,
  runtimeReady: true,
  packageReady: false,
  packages: [],
  storage: { locationSelectable: false },
};

const summary = {
  protocolVersion: "wiii-signal-inbox.v1" as const,
  encrypted: true as const,
  itemCount: 5,
  readyCount: 3,
  gapCount: 1,
  counts: [],
  pendingRefs: ["signal:opaque-1"],
};

describe("Neko coworker Signal Inbox", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.status = { coworkerId: "neko", environmentId: null, environment: null,
      activeProjectId: null, activeProjectPath: null, grants: [] };
    mocks.refresh.mockResolvedValue(mocks.status);
    mocks.doctorComputer.mockResolvedValue(doctor);
    mocks.consultSignalInbox.mockResolvedValue(summary);
  });

  it("does not grant or activate sibling roots of a multi-root Project", async () => {
    const root = { name: "First", path: "C:/fixture/first" };
    const sibling = { name: "Second", path: "C:/fixture/second" };
    mocks.status = { ...mocks.status, activeProjectId: "project-test", activeProjectPath: root.path,
      grants: [{ coworkerId: "neko", projectId: "project-test", projectName: "Fixture",
        projectPath: root.path, accessMode: "read_write", createdAt: "fixture", updatedAt: "fixture" }] };
    mocks.grant.mockResolvedValue(undefined);
    render(<NekoCoworkerHome projects={[{ id: "project-test", name: "Fixture", roots: [root, sibling],
      preferredHarnessId: "neko", createdAt: 1, updatedAt: 1 }]} />);
    await waitFor(() => expect(mocks.consultSignalInbox).toHaveBeenCalledOnce());
    expect(screen.getAllByText("Đang mở")).toHaveLength(1);
    const grant = screen.getByRole("button", { name: /Cấp quyền/ });
    fireEvent.click(grant);
    await waitFor(() => expect(mocks.grant).toHaveBeenCalledWith({
      projectId: "project-test", projectName: "Fixture", projectPath: sibling.path,
    }));
  });

  it("renders bounded attention counts on entry and refreshes only on demand", async () => {
    render(<NekoCoworkerHome projects={[]} />);

    const card = await screen.findByTestId("neko-signal-inbox-summary");
    await waitFor(() => expect(card.textContent).toContain("3 việc đang chờ"));
    expect(card.textContent).toContain("1 nguồn cần đồng bộ lại");
    expect(card.getAttribute("data-attention")).toBe("true");
    expect(card.textContent).not.toContain("signal:opaque-1");
    expect(mocks.consultSignalInbox).toHaveBeenCalledTimes(1);
    expect(mocks.consultSignalInbox).toHaveBeenCalledWith(8);

    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra" }));
    await waitFor(() => expect(mocks.consultSignalInbox).toHaveBeenCalledTimes(2));
  });

  it("keeps workstation management available when inbox consultation fails", async () => {
    mocks.consultSignalInbox.mockRejectedValueOnce(new Error("inbox unavailable"));

    render(<NekoCoworkerHome projects={[]} />);

    const card = await screen.findByTestId("neko-signal-inbox-summary");
    await waitFor(() => expect(card.textContent).toContain("Chưa kiểm tra được"));
    expect(card.textContent).toContain("Máy làm việc vẫn hoạt động bình thường");
    expect(screen.getByRole("button", { name: "Kiểm tra" })).toBeTruthy();
    expect(screen.queryByText("inbox unavailable")).toBeNull();
  });

  it("does not mark a fully processed inbox as attention-worthy", () => {
    expect(signalInboxCardState({
      ...summary,
      readyCount: 0,
      gapCount: 0,
    })).toEqual({
      value: "Không có việc mới",
      detail: "5 tín hiệu đã được xử lý hoặc hoãn",
      attention: false,
    });
  });
});
