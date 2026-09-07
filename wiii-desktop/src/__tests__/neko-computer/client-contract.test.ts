import { beforeEach, describe, expect, it, vi } from "vitest";

const tauri = vi.hoisted(() => ({ invoke: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({ invoke: tauri.invoke }));

import {
  acquireComputerSeat,
  actOnComputerSemantics,
  claimSignalInbox,
  consultSignalInbox,
  deferSignalItem,
  ensureComputer,
  executeComputerTerminal,
  grantCoworkerProject,
  installComputerPackage,
  navigateComputerBrowser,
  pollComputerAppEvents,
  observeComputerSemantics,
  deleteComputerHistory,
  describeWorkPlane,
  executeWorkPlane,
  queryWorkPlane,
  readComputerHistory,
  readComputerHistoryStatus,
  setComputerHistoryEnabled,
  readComputerEvents,
  resolveCoworkerComputer,
  removeComputer,
  removeComputerPackage,
  resetComputer,
  releaseComputerSeat,
  resolveSignalItem,
  revokeSignalAccount,
  subscribeComputerSeatChanges,
  revokeCoworkerProject,
} from "@/neko-computer/client";

describe("Neko Computer client authority contract", () => {
  const project = {
    projectId: "project-wiii",
    projectName: "Wiii",
    projectPath: "E:\\Projects\\Wiii",
  };
  beforeEach(() => {
    tauri.invoke.mockReset().mockResolvedValue({});
  });

  it("sends project intent without renderer-owned Docker configuration", async () => {
    await ensureComputer(project, "auto", "request-ensure");

    expect(tauri.invoke).toHaveBeenCalledWith("neko_computer_ensure", {
      request: {
        requestId: "request-ensure",
        coworkerId: "wiii-coworker-neko",
        ...project,
        resourcePreset: "auto",
      },
    });
    const serialized = JSON.stringify(tauri.invoke.mock.calls[0]?.[1]);
    expect(serialized).not.toMatch(/image|container|volume|binary|program|port/i);
  });

  it("exposes coworker status and revocable Project grants without Docker primitives", async () => {
    await resolveCoworkerComputer();
    await grantCoworkerProject(project, "request-grant");
    await revokeCoworkerProject(project.projectId, "request-revoke");

    expect(tauri.invoke).toHaveBeenNthCalledWith(1, "neko_computer_coworker_status", {
      request: { coworkerId: "wiii-coworker-neko" },
    });
    expect(tauri.invoke).toHaveBeenNthCalledWith(2, "neko_computer_project_grant", {
      request: {
        requestId: "request-grant",
        coworkerId: "wiii-coworker-neko",
        ...project,
      },
    });
    expect(tauri.invoke).toHaveBeenNthCalledWith(3, "neko_computer_project_revoke", {
      request: {
        requestId: "request-revoke",
        coworkerId: "wiii-coworker-neko",
        projectId: "project-wiii",
      },
    });
    expect(JSON.stringify(tauri.invoke.mock.calls)).not.toMatch(
      /image|container|volume|binary|program|port/i,
    );
  });

  it("carries idempotency IDs on every mutating operation", async () => {
    await acquireComputerSeat("computer-a", "user:session-a", true, "request-seat");
    await executeComputerTerminal("computer-a", "pwd", "request-terminal");
    await navigateComputerBrowser("computer-a", "https://example.com", "request-browser");
    await resetComputer("computer-a", "RESET NEKO", "request-reset");
    await removeComputer("computer-a", "REMOVE NEKO", "request-remove");
    await installComputerPackage("request-package-install");
    await removeComputerPackage("request-package-remove");

    expect(tauri.invoke.mock.calls.map(([, args]) => args.request.requestId)).toEqual([
      "request-seat",
      "request-terminal",
      "request-browser",
      "request-reset",
      "request-remove",
      "request-package-install",
      "request-package-remove",
    ]);
  });

  it("publishes native seat changes to the renderer immediately", async () => {
    const acquired = {
      seatId: "seat-computer-a",
      state: "agent_controlled",
      leaseId: "lease-agent-a",
      ownerId: "agent-session:session-a",
      updatedAt: "2026-08-28T06:00:00.000Z",
    } as const;
    const available = {
      ...acquired,
      state: "available",
      leaseId: null,
      ownerId: null,
      updatedAt: "2026-08-28T06:00:01.000Z",
    } as const;
    tauri.invoke
      .mockResolvedValueOnce(acquired)
      .mockResolvedValueOnce(available);
    const changes: unknown[] = [];
    const unsubscribe = subscribeComputerSeatChanges((change) => changes.push(change));

    try {
      await acquireComputerSeat("computer-a", acquired.ownerId, false, "request-acquire");
      await releaseComputerSeat("computer-a", acquired.leaseId, "request-release");
    } finally {
      unsubscribe();
    }

    expect(changes).toEqual([
      { environmentId: "computer-a", seat: acquired },
      { environmentId: "computer-a", seat: available },
    ]);
  });

  it("keeps package and Project removal behind intent-only native commands", async () => {
    await installComputerPackage("request-package-install");
    await removeComputer("computer-a", "REMOVE NEKO", "request-remove");
    await removeComputerPackage("request-package-remove");

    expect(tauri.invoke).toHaveBeenNthCalledWith(1, "neko_computer_package_install", {
      request: {
        requestId: "request-package-install",
        coworkerId: "wiii-coworker-neko",
        packageId: "web-computer-core",
      },
    });
    expect(tauri.invoke).toHaveBeenNthCalledWith(2, "neko_computer_remove", {
      request: {
        requestId: "request-remove",
        environmentId: "computer-a",
        confirmation: "REMOVE NEKO",
      },
    });
    expect(tauri.invoke).toHaveBeenNthCalledWith(3, "neko_computer_package_remove", {
      request: {
        requestId: "request-package-remove",
        coworkerId: "wiii-coworker-neko",
        packageId: "web-computer-core",
      },
    });
    const serialized = JSON.stringify(tauri.invoke.mock.calls.map(([, args]) => args));
    expect(serialized).not.toMatch(/image|container|volume|binary|program|port/i);
  });

  it("replays a durable per-environment event stream from a sequence cursor", async () => {
    await readComputerEvents("computer-a", 41, 50);

    expect(tauri.invoke).toHaveBeenCalledWith("neko_computer_events_read", {
      environmentId: "computer-a",
      afterSeq: 41,
      limit: 50,
    });
  });

  it("polls only bounded content-free app-event batches", async () => {
    await pollComputerAppEvents({
      environmentId: "computer-a",
      afterCursor: "atspi:0123456789abcdef:41",
      limit: 32,
      waitMs: 0,
    });

    expect(tauri.invoke).toHaveBeenCalledWith("neko_computer_app_events_poll", {
      request: {
        environmentId: "computer-a",
        afterCursor: "atspi:0123456789abcdef:41",
        limit: 32,
        waitMs: 0,
      },
    });
  });

  it("observes a bounded semantic snapshot without exposing runtime implementation", async () => {
    await observeComputerSemantics("computer-a", 240);

    expect(tauri.invoke).toHaveBeenCalledWith("neko_computer_semantic_observe", {
      request: { environmentId: "computer-a", maxNodes: 240 },
    });
  });

  it("passes scoped continuation and delta state as an opaque semantic request", async () => {
    await observeComputerSemantics("computer-a", {
      maxNodes: 40,
      scopeRef: "app:browser",
      continuation: "opaque-cursor",
      sinceStateVersion: `sha256:${"a".repeat(64)}`,
      knownNodeVersions: [{ ref: "web:button", version: `sha256:${"b".repeat(64)}` }],
    });

    expect(tauri.invoke).toHaveBeenCalledWith("neko_computer_semantic_observe", {
      request: {
        environmentId: "computer-a",
        maxNodes: 40,
        scopeRef: "app:browser",
        continuation: "opaque-cursor",
        sinceStateVersion: `sha256:${"a".repeat(64)}`,
        knownNodeVersions: [{ ref: "web:button", version: `sha256:${"b".repeat(64)}` }],
        visualRef: null,
      },
    });
  });

  it("exposes encrypted Computer History inspection and deletion without provider details", async () => {
    await readComputerHistoryStatus();
    await setComputerHistoryEnabled(true);
    await readComputerHistory("computer-a", 42, 20);
    await deleteComputerHistory("computer-a");

    expect(tauri.invoke).toHaveBeenNthCalledWith(1, "neko_computer_history_status");
    expect(tauri.invoke).toHaveBeenNthCalledWith(2, "neko_computer_history_set_enabled", {
      request: { enabled: true },
    });
    expect(tauri.invoke).toHaveBeenNthCalledWith(3, "neko_computer_history_query", {
      request: { environmentId: "computer-a", beforeSeq: 42, limit: 20 },
    });
    expect(tauri.invoke).toHaveBeenNthCalledWith(4, "neko_computer_history_delete", {
      request: { environmentId: "computer-a" },
    });
    expect(JSON.stringify(tauri.invoke.mock.calls)).not.toMatch(/docker|container|volume|attachUrl/i);
  });

  it("keeps Signal Inbox consultation content-free and mutations operation-bound", async () => {
    await consultSignalInbox(8);
    await claimSignalInbox("worker-neko", 2, 120);
    await deferSignalItem(
      "signal-1",
      "signal-lease-1",
      "2026-09-01T00:00:00.000Z",
      "operation-defer-1",
    );
    await resolveSignalItem(
      "signal-1",
      "signal-lease-1",
      "handled",
      "history:101",
      "operation-resolve-1",
    );
    await revokeSignalAccount("grant-neko-mail");

    expect(tauri.invoke.mock.calls).toEqual([
      ["neko_signal_inbox_consult", { request: { maxRefs: 8 } }],
      ["neko_signal_inbox_claim", {
        request: { workerId: "worker-neko", maxItems: 2, leaseSeconds: 120 },
      }],
      ["neko_signal_inbox_defer", {
        request: {
          signalId: "signal-1",
          leaseId: "signal-lease-1",
          operationId: "operation-defer-1",
          availableAt: "2026-09-01T00:00:00.000Z",
        },
      }],
      ["neko_signal_inbox_resolve", {
        request: {
          signalId: "signal-1",
          leaseId: "signal-lease-1",
          operationId: "operation-resolve-1",
          outcome: "handled",
          sourceRevision: "history:101",
        },
      }],
      ["neko_signal_inbox_revoke_account", {
        request: { accountGrantRef: "grant-neko-mail" },
      }],
    ]);
    expect(JSON.stringify(tauri.invoke.mock.calls)).not.toMatch(
      /subject|messageText|body|attachment|rawCallback|credential|token/i,
    );
  });

  it("requires a snapshot version, target identity and display lease for semantic actions", async () => {
    await actOnComputerSemantics(
      {
        environmentId: "computer-a",
        leaseId: "lease-agent-a",
        stateVersion: `sha256:${"a".repeat(64)}`,
        targetRef: "ui-0042",
        expectedRole: "push button",
        expectedName: "Open",
        action: "invoke",
      },
      "request-semantic-act",
    );

    expect(tauri.invoke).toHaveBeenCalledWith("neko_computer_semantic_act", {
      request: {
        requestId: "request-semantic-act",
        environmentId: "computer-a",
        leaseId: "lease-agent-a",
        stateVersion: `sha256:${"a".repeat(64)}`,
        targetRef: "ui-0042",
        expectedRole: "push button",
        expectedName: "Open",
        action: "invoke",
        text: null,
        key: null,
        inputSequence: [],
      },
    });
    const serialized = JSON.stringify(tauri.invoke.mock.calls[0]?.[1]);
    expect(serialized).not.toMatch(/docker|binary|program|coordinate|selector/i);
  });

  it("sends provider-neutral Work Plane queries and revision-bound transactions", async () => {
    await describeWorkPlane("computer-a", "project-wiii");
    await queryWorkPlane("computer-a", "project-wiii", {
      resourceRef: "work:project",
      view: "children",
      maxItems: 10,
    });
    await executeWorkPlane({
      environmentId: "computer-a",
      projectId: "project-wiii",
      capabilityId: "project.file.create",
      capabilityVersion: "1",
      targetRef: "work:project",
      ifRevision: `sha256:${"a".repeat(64)}`,
      input: { path: "draft.txt", content: "hello" },
    }, "operation-work-1");

    expect(tauri.invoke).toHaveBeenNthCalledWith(1, "neko_computer_work_plane_describe", {
      request: { environmentId: "computer-a", projectId: "project-wiii" },
    });
    expect(tauri.invoke).toHaveBeenNthCalledWith(2, "neko_computer_work_plane_query", {
      request: {
        environmentId: "computer-a",
        projectId: "project-wiii",
        resourceRef: "work:project",
        view: "children",
        maxItems: 10,
        offset: 0,
        maxBytes: 64 * 1024,
        sheet: null,
        range: null,
      },
    });
    expect(tauri.invoke).toHaveBeenNthCalledWith(3, "neko_computer_work_plane_execute", {
      request: expect.objectContaining({
        requestId: "operation-work-1",
        projectId: "project-wiii",
        ifRevision: `sha256:${"a".repeat(64)}`,
      }),
    });
    expect(JSON.stringify(tauri.invoke.mock.calls)).not.toMatch(/docker|container|hostPath|selector|coordinate/i);
  });
});
