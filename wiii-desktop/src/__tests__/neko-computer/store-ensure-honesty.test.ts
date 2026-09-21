import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  hasNativeComputerAuthority: vi.fn(() => false),
  doctorComputer: vi.fn(),
  ensureComputer: vi.fn(),
  grantCoworkerProject: vi.fn(),
  resolveCoworkerComputer: vi.fn(),
}));

vi.mock("@/neko-computer/client", () => ({
  acquireComputerSeat: vi.fn(),
  doctorComputer: mocks.doctorComputer,
  ensureComputer: mocks.ensureComputer,
  executeComputerTerminal: vi.fn(),
  grantCoworkerProject: mocks.grantCoworkerProject,
  hasNativeComputerAuthority: mocks.hasNativeComputerAuthority,
  navigateComputerBrowser: vi.fn(),
  observeComputerSemantics: vi.fn(),
  removeComputer: vi.fn(),
  removeComputerPackage: vi.fn(),
  releaseComputerSeat: vi.fn(),
  resetComputer: vi.fn(),
  resolveCoworkerComputer: mocks.resolveCoworkerComputer,
  resumeComputer: vi.fn(),
  revokeCoworkerProject: vi.fn(),
  subscribeComputerSeatChanges: () => () => undefined,
  suspendComputer: vi.fn(),
}));

import { useNekoComputerStore } from "@/neko-computer/store";

const project = {
  projectId: "project-1",
  projectName: "CONT3",
  projectPath: "/tmp/cont3",
};

describe("computer store ensure/grant browser honesty", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.hasNativeComputerAuthority.mockReturnValue(false);
    useNekoComputerStore.setState({
      doctor: null,
      status: null,
      projects: {},
    });
  });

  it("does not invoke ensure/grant without native authority", async () => {
    await useNekoComputerStore.getState().ensure(project);
    await useNekoComputerStore.getState().grant(project);

    const pane = useNekoComputerStore.getState().projects["project-1"];
    expect(pane.error).toMatch(/Wiii Desktop/i);
    expect(mocks.ensureComputer).not.toHaveBeenCalled();
    expect(mocks.grantCoworkerProject).not.toHaveBeenCalled();
    expect(mocks.doctorComputer).not.toHaveBeenCalled();
  });
});
