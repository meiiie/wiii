import { describe, expect, it, vi } from "vitest";
import {
  WIII_COMPUTER_AGENT_METHODS,
  WIII_COMPUTER_HISTORY_AGENT_METHODS,
  WIII_COMPUTER_PROCEDURE_AGENT_METHODS,
  WIII_SIGNAL_INBOX_AGENT_METHODS,
  WIII_WORK_PLANE_AGENT_METHODS,
  WiiiComputerAgentBridge,
  type AgentComputerBridgeDependencies,
} from "@/neko-computer/agent-bridge";
import type {
  ComputerEnvironment,
  ComputerSemanticNode,
  CoworkerComputerStatus,
  WorkCapability,
} from "@/neko-computer/contracts";
import {
  WIII_BROWSER_NAVIGATE_PROCEDURE,
  WIII_WORK_PLANE_SEQUENCE_PROCEDURE,
} from "@/neko-computer/procedures";

function readyEnvironment(
  projectPath = "E:\\Projects\\Wiii",
  projectId = "project-wiii",
): ComputerEnvironment {
  return {
    environmentId: "computer-neko",
    projectId,
    projectName: "Wiii",
    projectPath,
    providerKind: "local_docker",
    isolationClass: "shared_container",
    computerKind: "web_computer",
    operatingSystem: "Linux Â· Debian 12",
    semanticProtocol: "neko-computer.semantic.v1",
    state: "ready",
    projectMount: "/workspace/project",
    attachUrl: "http://127.0.0.1:4000/?token=must-not-leak",
    resources: {
      cpus: "2",
      memoryBytes: 4_000_000_000,
      pidsLimit: 320,
      sharedMemoryBytes: 512_000_000,
      temporaryStorageBytes: 2_000_000_000,
    },
    seat: {
      seatId: "seat-computer-neko",
      state: "available",
      leaseId: null,
      ownerId: null,
      updatedAt: "2026-08-27T00:00:00.000Z",
    },
    createdAt: "2026-08-27T00:00:00.000Z",
    updatedAt: "2026-08-27T00:00:00.000Z",
  };
}

function status(
  projectId = "project-wiii",
  projectPath = "E:\\Projects\\Wiii",
): CoworkerComputerStatus {
  return {
    coworkerId: "wiii-coworker-neko",
    environmentId: "computer-neko",
    activeProjectId: projectId,
    activeProjectPath: projectPath,
    environment: readyEnvironment(projectPath, projectId),
    grants: [],
  };
}

function dependencies(
  current: CoworkerComputerStatus = status(),
): AgentComputerBridgeDependencies {
  return {
    resolveStatus: vi.fn(async () => current),
    acquireSeat: vi.fn(async (_environmentId, ownerId) => ({
      seatId: "seat-computer-neko",
      state: "agent_controlled",
      leaseId: "lease-agent",
      ownerId,
      updatedAt: "2026-08-27T00:00:01.000Z",
    })),
    releaseSeat: vi.fn(async () => ({
      seatId: "seat-computer-neko",
      state: "available",
      leaseId: null,
      ownerId: null,
      updatedAt: "2026-08-27T00:00:02.000Z",
    })),
    observe: vi.fn(async (environmentId, options) => ({
      protocolVersion: "neko-computer.semantic.v1",
      environmentId,
      stateVersion: "state-1",
      capturedAt: "2026-08-27T00:00:03.000Z",
      platform: "linux_atspi",
      screen: { width: 1440, height: 900 },
      activeWindowRef: "window-1",
      frame: {
        version: "wiii-ai-frame.v1",
        scope: "desktop",
        observationModel: "scene_graph",
        actionModel: "typed_refs",
        coordinates: "adapter_private",
        modalities: ["accessibility", "desktop"],
        interaction: {
          mode: "semantic_control",
          targetRef: "window-1",
          inputActions: ["focus"],
          keymapSource: "none",
          shortcuts: [],
          feedback: "semantic_delta",
        },
      },
      nodes: [{
        ref: "window-1",
        parentRef: "workstation:main",
        appId: "terminal",
        role: "window",
        name: "Terminal",
        description: null,
        value: null,
        states: ["active"],
        actions: ["focus"],
        bounds: null,
        sources: ["desktop", "accessibility"],
        version: "sha256:node-1",
      }],
      truncated: (options.maxNodes ?? 400) < 400,
      scopeRef: options.scopeRef ?? null,
      projection: options.sinceStateVersion ? "delta" : "full",
      nextContinuation: null,
      deltaFromStateVersion: options.sinceStateVersion ?? null,
      removedRefs: [],
    })),
    historyStatus: vi.fn(async () => ({
      available: true,
      enabled: true,
      encrypted: true,
      cipher: "xchacha20-poly1305",
      keyProtection: "windows-dpapi-current-user",
      retentionDays: 30,
      entryCount: 1,
      lastError: null,
    })),
    historyQuery: vi.fn(async () => ({
      entries: [{
        seq: 7,
        at: "2026-08-29T00:00:00.000Z",
        environmentId: "computer-neko",
        outcome: "completed",
        action: "invoke",
        targetRef: "app:browser",
        beforeStateVersion: "sha256:before",
        afterStateVersion: "sha256:after",
        verified: true,
        effect: "confirmed",
        route: "launcher",
        evidence: ["application_started"],
        code: null,
      }],
      nextBeforeSeq: null,
      hasMore: false,
    })),
    signalInboxConsult: vi.fn(async (maxRefs) => ({
      protocolVersion: "wiii-signal-inbox.v1",
      encrypted: true,
      itemCount: 2,
      readyCount: 1,
      gapCount: 0,
      counts: [{
        sourceId: "gmail.history.v1",
        state: "pending",
        priorityClass: "normal",
        count: 1,
      }],
      pendingRefs: maxRefs === 0 ? [] : ["signal-opaque-1"],
    })),
    workPlaneDescribe: vi.fn(async () => ({
      protocolVersion: "wiii-work-plane.preview.v1",
      sourceAuthority: "source_application",
      resourceModel: "typed_revisioned_resources",
      transactionModel: "optimistic_idempotent",
      root: {
        ref: "work:project",
        resourceType: "project.root",
        name: "Project",
        parentRef: null,
        revision: `sha256:${"c".repeat(64)}`,
        mediaType: null,
        capabilities: ["project.file.create"],
        source: "project",
        metadata: {},
      },
      capabilities: [],
    })),
    workPlaneQuery: vi.fn(async () => ({
      protocolVersion: "wiii-work-plane.preview.v1",
      resource: {
        ref: "work:project",
        resourceType: "project.root",
        name: "Project",
        parentRef: null,
        revision: `sha256:${"c".repeat(64)}`,
        mediaType: null,
        capabilities: ["project.file.create"],
        source: "project",
        metadata: {},
      },
      items: [],
      data: {},
      truncated: false,
      nextOffset: null,
      evidence: ["source_revision"],
    })),
    workPlaneExecute: vi.fn(async (input) => ({
      protocolVersion: "wiii-work-plane.preview.v1",
      outcome: "completed",
      code: null,
      detail: "verified",
      capabilityId: input.capabilityId,
      targetRef: input.targetRef,
      beforeRevision: input.ifRevision,
      afterRevision: `sha256:${"d".repeat(64)}`,
      changes: [{
        ref: input.targetRef,
        kind: "updated",
        beforeRevision: input.ifRevision,
        afterRevision: `sha256:${"d".repeat(64)}`,
      }],
      evidence: ["file_hash_readback"],
      reversible: true,
      recovery: null,
    })),
    act: vi.fn(async (input) => ({
      environmentId: input.environmentId,
      outcome: "completed",
      code: null,
      detail: "verified",
      action: input.action,
      targetRef: input.targetRef,
      beforeStateVersion: input.stateVersion,
      afterStateVersion: "state-2",
      verified: true,
      effect: "confirmed",
      route: "accessibility_action",
      evidence: ["semantic_state_change"],
      escalation: null,
    })),
  };
}

function enableProcedureFixtures(deps: AgentComputerBridgeDependencies): void {
  const browserNode: ComputerSemanticNode = {
    ref: "app:browser",
    parentRef: "workstation:main",
    appId: "browser",
    role: "browser",
    name: "Trình duyệt",
    description: "Typed Browser launcher",
    value: null,
    states: ["enabled", "accepts_text_query"],
    actions: ["invoke", "set_text", "press_key", "input_sequence"],
    bounds: null,
    sources: ["workstation"],
    version: `sha256:${"a".repeat(64)}`,
    adapter: {
      id: "wiii.chrome.v1",
      version: "1",
      capabilities: ["navigate", "search", "semantic_controls", "persistent_profile"],
    },
  };
  vi.mocked(deps.observe).mockImplementation(async (environmentId, options) => ({
    protocolVersion: "neko-computer.semantic.v1",
    environmentId,
    stateVersion: `sha256:${"b".repeat(64)}`,
    capturedAt: "2026-09-02T00:00:00.000Z",
    platform: "linux_atspi",
    screen: { width: 1440, height: 900 },
    activeWindowRef: "app:browser",
    frame: null,
    nodes: [browserNode],
    truncated: false,
    scopeRef: options.scopeRef ?? null,
    projection: "full",
    nextContinuation: null,
    deltaFromStateVersion: null,
    removedRefs: [],
  }));
  const capability: WorkCapability = {
    id: "project.file.create",
    version: "1",
    resourceTypes: ["project.root"],
    inputSchema: {
      type: "object",
      required: ["path", "content"],
      properties: {
        path: { type: "string" },
        content: { type: "string" },
      },
    },
    mutating: true,
    risk: "reversible_local_edit",
    approval: "project_write_grant",
    retry: "idempotency_key_and_revision",
    reversible: true,
    maxInputBytes: 4_096,
    evidence: ["file_hash_readback"],
  };
  vi.mocked(deps.workPlaneDescribe).mockResolvedValue({
    protocolVersion: "wiii-work-plane.preview.v1",
    sourceAuthority: "source_application",
    resourceModel: "typed_revisioned_resources",
    transactionModel: "optimistic_idempotent",
    root: {
      ref: "work:project",
      resourceType: "project.root",
      name: "Project",
      parentRef: null,
      revision: `sha256:${"c".repeat(64)}`,
      mediaType: null,
      capabilities: [capability.id],
      source: "project",
      metadata: {},
    },
    capabilities: [capability],
  });
}

describe("WiiiComputerAgentBridge", () => {
  it("publishes the exact Neko Core Computer wire methods", () => {
    expect(Object.values(WIII_COMPUTER_AGENT_METHODS)).toHaveLength(5);
    expect(Object.values(WIII_COMPUTER_AGENT_METHODS).every((method) =>
      method.startsWith("_wiii/computer/v1/"),
    )).toBe(true);
  });

  it("exposes encrypted history as a separate read-only capability", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    const historyStatus = await bridge.handle(WIII_COMPUTER_HISTORY_AGENT_METHODS.status, {});
    expect(historyStatus).toMatchObject({ encrypted: true, enabled: true, healthy: true });
    expect(historyStatus).not.toHaveProperty("cipher");
    expect(historyStatus).not.toHaveProperty("keyProtection");
    const history = await bridge.handle(
      WIII_COMPUTER_HISTORY_AGENT_METHODS.query,
      { beforeSeq: 9, limit: 500 },
    );
    expect(history).toMatchObject({ entries: [{ action: "invoke" }], hasMore: false });
    expect(history).not.toHaveProperty("entries.0.environmentId");
    expect(deps.historyQuery).toHaveBeenCalledWith("computer-neko", 9, 100);
  });

  it("consults only bounded content-free Signal Inbox metadata", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    await expect(bridge.handle(WIII_SIGNAL_INBOX_AGENT_METHODS.consult, { maxRefs: 4 }))
      .resolves.toEqual(expect.objectContaining({
        encrypted: true,
        readyCount: 1,
        pendingRefs: ["signal-opaque-1"],
      }));
    expect(deps.signalInboxConsult).toHaveBeenCalledWith(4);
    await expect(bridge.handle(WIII_SIGNAL_INBOX_AGENT_METHODS.consult, { maxRefs: 33 }))
      .rejects.toThrow("between 0 and 32");
    expect(deps.acquireSeat).not.toHaveBeenCalled();
  });

  it("uses source-backed Work Plane without acquiring the display seat", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    await expect(bridge.handle(WIII_WORK_PLANE_AGENT_METHODS.describe, {}))
      .resolves.toMatchObject({
        protocolVersion: "wiii-work-plane.preview.v1",
        sourceAuthority: "source_application",
      });
    await bridge.handle(WIII_WORK_PLANE_AGENT_METHODS.query, {
      resourceRef: "work:project",
      view: "children",
      maxItems: 20,
    });
    await expect(bridge.handle(WIII_WORK_PLANE_AGENT_METHODS.execute, {
      operationId: "operation-work-1",
      capabilityId: "project.file.create",
      capabilityVersion: "1",
      targetRef: "work:project",
      ifRevision: `sha256:${"c".repeat(64)}`,
      input: { path: "draft.txt", content: "hello" },
    })).resolves.toMatchObject({ outcome: "completed", evidence: ["file_hash_readback"] });

    expect(deps.workPlaneQuery).toHaveBeenCalledWith(
      "computer-neko",
      "project-wiii",
      expect.objectContaining({ resourceRef: "work:project", view: "children", maxItems: 20 }),
    );
    expect(deps.workPlaneExecute).toHaveBeenCalledWith(
      expect.objectContaining({
        environmentId: "computer-neko",
        projectId: "project-wiii",
        capabilityId: "project.file.create",
      }),
      "operation-work-1",
    );
    expect(deps.acquireSeat).not.toHaveBeenCalled();
  });

  it("publishes a bounded procedure catalog from live adapter contracts", async () => {
    const deps = dependencies();
    enableProcedureFixtures(deps);
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    const catalog = await bridge.handle(WIII_COMPUTER_PROCEDURE_AGENT_METHODS.catalog, {}) as {
      protocolVersion: string;
      procedures: Array<Record<string, unknown>>;
    };
    expect(catalog.protocolVersion).toBe("wiii-computer-procedures.v1");
    expect(catalog.procedures).toEqual([
      expect.objectContaining({
        id: WIII_BROWSER_NAVIGATE_PROCEDURE,
        status: "promoted",
        displayLeaseRequired: true,
        maxSteps: 1,
      }),
      expect.objectContaining({
        id: WIII_WORK_PLANE_SEQUENCE_PROCEDURE,
        status: "promoted",
        displayLeaseRequired: false,
        maxSteps: 16,
      }),
    ]);
    expect(JSON.stringify(catalog)).not.toMatch(/E:\\|computer-neko|target=|hello/i);
    expect(deps.acquireSeat).not.toHaveBeenCalled();
  });

  it("runs typed Browser navigation under one internally managed lease", async () => {
    const deps = dependencies();
    enableProcedureFixtures(deps);
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);
    const catalog = await bridge.handle(WIII_COMPUTER_PROCEDURE_AGENT_METHODS.catalog, {}) as {
      procedures: Array<{ id: string; compatibilityFingerprint: string }>;
    };
    const procedure = catalog.procedures.find((candidate) => candidate.id === WIII_BROWSER_NAVIGATE_PROCEDURE)!;

    await expect(bridge.handle(WIII_COMPUTER_PROCEDURE_AGENT_METHODS.run, {
      operationId: "procedure-browser-1",
      procedureId: procedure.id,
      compatibilityFingerprint: procedure.compatibilityFingerprint,
      parameters: { target: "https://example.com/held-out" },
    })).resolves.toMatchObject({
      protocolVersion: "wiii-computer-procedures.v1",
      outcome: "completed",
      completedSteps: 1,
      totalSteps: 1,
      steps: [{ verified: true }],
    });
    expect(deps.acquireSeat).toHaveBeenCalledTimes(1);
    expect(deps.act).toHaveBeenCalledWith(
      expect.objectContaining({
        leaseId: "lease-agent",
        stateVersion: `sha256:${"b".repeat(64)}`,
        targetRef: "app:browser",
        expectedRole: "browser",
        action: "set_text",
        text: "https://example.com/held-out",
        returnObservation: true,
      }),
      "procedure-browser-1:step-01",
    );
    expect(deps.releaseSeat).toHaveBeenCalledTimes(1);
  });

  it("preflights and replays a bounded Work Plane sequence without a display lease", async () => {
    const deps = dependencies();
    enableProcedureFixtures(deps);
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);
    const catalog = await bridge.handle(WIII_COMPUTER_PROCEDURE_AGENT_METHODS.catalog, {}) as {
      procedures: Array<{ id: string; compatibilityFingerprint: string }>;
    };
    const procedure = catalog.procedures.find((candidate) => candidate.id === WIII_WORK_PLANE_SEQUENCE_PROCEDURE)!;
    const revision = `sha256:${"c".repeat(64)}`;

    await expect(bridge.handle(WIII_COMPUTER_PROCEDURE_AGENT_METHODS.run, {
      operationId: "procedure-work-1",
      procedureId: procedure.id,
      compatibilityFingerprint: procedure.compatibilityFingerprint,
      parameters: {
        transactions: [
          {
            capabilityId: "project.file.create",
            capabilityVersion: "1",
            targetRef: "work:project",
            ifRevision: revision,
            input: { path: "one.txt", content: "one" },
          },
          {
            capabilityId: "project.file.create",
            capabilityVersion: "1",
            targetRef: "work:project",
            ifRevision: revision,
            input: { path: "two.txt", content: "two" },
          },
        ],
      },
    })).resolves.toMatchObject({
      outcome: "completed",
      completedSteps: 2,
      totalSteps: 2,
    });
    expect(deps.workPlaneExecute).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ capabilityId: "project.file.create" }),
      "procedure-work-1:step-01",
    );
    expect(deps.workPlaneExecute).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ capabilityId: "project.file.create" }),
      "procedure-work-1:step-02",
    );
    expect(deps.acquireSeat).not.toHaveBeenCalled();
  });

  it("fails procedure preflight on contract drift before any mutation", async () => {
    const deps = dependencies();
    enableProcedureFixtures(deps);
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    await expect(bridge.handle(WIII_COMPUTER_PROCEDURE_AGENT_METHODS.run, {
      operationId: "procedure-stale-1",
      procedureId: WIII_WORK_PLANE_SEQUENCE_PROCEDURE,
      compatibilityFingerprint: "stale-contract",
      parameters: { transactions: [] },
    })).rejects.toThrow("procedure_contract_drift");
    expect(deps.workPlaneExecute).not.toHaveBeenCalled();
    expect(deps.acquireSeat).not.toHaveBeenCalled();
  });

  it("stops a Work Plane procedure at the first rejected child", async () => {
    const deps = dependencies();
    enableProcedureFixtures(deps);
    vi.mocked(deps.workPlaneExecute)
      .mockResolvedValueOnce({
        protocolVersion: "wiii-work-plane.preview.v1",
        outcome: "rejected",
        code: "stale_revision",
        detail: "refresh source state",
        capabilityId: "project.file.create",
        targetRef: "work:project",
        beforeRevision: `sha256:${"c".repeat(64)}`,
        afterRevision: `sha256:${"c".repeat(64)}`,
        changes: [],
        evidence: ["source_revision_mismatch"],
        reversible: true,
        recovery: "query",
      });
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);
    const catalog = await bridge.handle(WIII_COMPUTER_PROCEDURE_AGENT_METHODS.catalog, {}) as {
      procedures: Array<{ id: string; compatibilityFingerprint: string }>;
    };
    const procedure = catalog.procedures.find((candidate) => candidate.id === WIII_WORK_PLANE_SEQUENCE_PROCEDURE)!;
    const transaction = {
      capabilityId: "project.file.create",
      capabilityVersion: "1",
      targetRef: "work:project",
      ifRevision: `sha256:${"c".repeat(64)}`,
      input: { path: "held-out.txt", content: "value" },
    };

    await expect(bridge.handle(WIII_COMPUTER_PROCEDURE_AGENT_METHODS.run, {
      operationId: "procedure-stop-1",
      procedureId: procedure.id,
      compatibilityFingerprint: procedure.compatibilityFingerprint,
      parameters: { transactions: [transaction, transaction] },
    })).resolves.toMatchObject({
      outcome: "rejected",
      code: "stale_revision",
      completedSteps: 0,
      totalSteps: 2,
    });
    expect(deps.workPlaneExecute).toHaveBeenCalledTimes(1);
  });

  it("rejects malformed Work Plane revisions and unbounded queries at the bridge", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    await expect(bridge.handle(WIII_WORK_PLANE_AGENT_METHODS.query, {
      resourceRef: "work:project",
      view: "children",
      maxItems: 201,
    })).rejects.toThrow("maxItems");
    await expect(bridge.handle(WIII_WORK_PLANE_AGENT_METHODS.execute, {
      operationId: "operation-work-invalid",
      capabilityId: "project.file.create",
      capabilityVersion: "1",
      targetRef: "work:project",
      ifRevision: "stale",
      input: {},
    })).rejects.toThrow("ifRevision");
    expect(deps.workPlaneQuery).not.toHaveBeenCalled();
    expect(deps.workPlaneExecute).not.toHaveBeenCalled();
  });

  it("fails closed when the session Project is not active", async () => {
    const deps = dependencies(status("project-other", "E:\\Projects\\Other"));
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.observe, {}))
      .rejects.toThrow("project_not_active");
    expect(deps.observe).not.toHaveBeenCalled();
  });

  it("keeps authority when the same Project moves to another drive", async () => {
    const deps = dependencies(status("project-wiii", "D:\\Moved\\Wiii"));
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.status, {}))
      .resolves.toMatchObject({ available: true, code: "ready" });
  });

  it("observes without exposing the display URL and caps semantic nodes", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    const current = await bridge.handle(WIII_COMPUTER_AGENT_METHODS.status, {});
    expect(JSON.stringify(current)).not.toContain("token=must-not-leak");
    expect(current).toMatchObject({ available: true, code: "ready", agentHasControl: false });

    const manifest = (current as { workstation: unknown }).workstation;
    expect(manifest).toMatchObject({
      schemaVersion: "wiii-workstation.manifest.v1",
      label: "Máy tính công việc của Neko",
      coworkerName: "Neko",
      persistence: "durable",
      interactionMode: "semantic",
      activeProjectLabel: "Wiii",
      surfaces: ["computer", "browser", "terminal", "files"],
      apps: [
        { appId: "browser", displayName: "Trình duyệt", state: "available", actions: ["invoke"] },
        { appId: "terminal", displayName: "Terminal", state: "available", actions: ["invoke"] },
        { appId: "files", displayName: "Tệp dự án", state: "available", actions: ["invoke"] },
      ],
      installedApps: [
        { appId: "browser", displayName: "Trình duyệt", state: "available", actions: ["invoke"] },
        { appId: "terminal", displayName: "Terminal", state: "available", actions: ["invoke"] },
        { appId: "files", displayName: "Tệp dự án", state: "available", actions: ["invoke"] },
      ],
    });
    const serializedManifest = JSON.stringify(manifest);
    expect(serializedManifest).not.toMatch(/computer-neko|lease-agent|127\.0\.0\.1|docker|token|exec|E:\\/i);

    const observed = await bridge.handle(WIII_COMPUTER_AGENT_METHODS.observe, { maxNodes: 9_999 });
    expect(observed).toMatchObject({
      frame: {
        version: "wiii-ai-frame.v1",
        actionModel: "typed_refs",
        interaction: {
          mode: "semantic_control",
          targetRef: "window-1",
          feedback: "semantic_delta",
        },
      },
      nodes: [{ sources: ["desktop", "accessibility"] }],
    });
    expect(deps.observe).toHaveBeenCalledWith("computer-neko", {
      maxNodes: 400,
      scopeRef: null,
      continuation: null,
      sinceStateVersion: null,
      knownNodeVersions: [],
      visualRef: null,
    });

    await bridge.handle(WIII_COMPUTER_AGENT_METHODS.observe, {
      maxNodes: 12,
      scopeRef: "app:browser",
      sinceStateVersion: `sha256:${"a".repeat(64)}`,
      knownNodeVersions: [{ ref: "web:button", version: `sha256:${"b".repeat(64)}` }],
      visualRef: null,
    });
    expect(deps.observe).toHaveBeenLastCalledWith("computer-neko", {
      maxNodes: 12,
      scopeRef: "app:browser",
      continuation: null,
      sinceStateVersion: `sha256:${"a".repeat(64)}`,
      knownNodeVersions: [{ ref: "web:button", version: `sha256:${"b".repeat(64)}` }],
      visualRef: null,
    });
  });

  it("discovers optional workstation apps once per session context", async () => {
    const deps = dependencies();
    const baseObserve = vi.mocked(deps.observe).getMockImplementation()!;
    vi.mocked(deps.observe).mockImplementation(async (environmentId, options) => {
      const snapshot = await baseObserve(environmentId, options);
      if (options.scopeRef !== "workstation:main") return snapshot;
      return {
        ...snapshot,
        activeWindowRef: null,
        nodes: [
          {
            ref: "app:wechat",
            parentRef: "workstation:main",
            appId: "wechat",
            role: "application_launcher",
            name: "WeChat",
            description: "Persistent coworker messaging profile",
            value: null,
            states: ["enabled"],
            actions: ["invoke"],
            bounds: null,
            sources: ["workstation"],
            version: `sha256:${"e".repeat(64)}`,
          },
        ],
      };
    });
    const bridge = new WiiiComputerAgentBridge("session-apps", "project-wiii", deps);

    const first = await bridge.handle(WIII_COMPUTER_AGENT_METHODS.status, {}) as {
      workstation: {
        apps: Array<{ appId: string }>;
        installedApps: Array<{ appId: string }>;
      };
    };
    const second = await bridge.handle(WIII_COMPUTER_AGENT_METHODS.status, {}) as {
      workstation: {
        apps: Array<{ appId: string }>;
        installedApps: Array<{ appId: string }>;
      };
    };

    expect(first.workstation.apps.map((app) => app.appId)).toEqual([
      "browser",
      "terminal",
      "files",
    ]);
    expect(first.workstation.installedApps.map((app) => app.appId)).toEqual([
      "browser",
      "terminal",
      "files",
      "wechat",
    ]);
    expect(second.workstation).toEqual(first.workstation);
    expect(deps.observe).toHaveBeenCalledTimes(1);
    expect(deps.observe).toHaveBeenCalledWith("computer-neko", {
      maxNodes: 16,
      scopeRef: "workstation:main",
    });
  });

  it("requires a private agent lease and passes exact semantic preconditions", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);
    const action = {
      operationId: "operation-act-1",
      stateVersion: "state-1",
      targetRef: "button-submit",
      expectedRole: "button",
      expectedName: "Send",
      action: "invoke" as const,
    };

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, action))
      .rejects.toThrow("computer_lease_required");
    await bridge.handle(WIII_COMPUTER_AGENT_METHODS.acquire, {
      operationId: "operation-acquire-1",
    });
    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, action))
      .resolves.toMatchObject({
        outcome: "completed",
        verified: true,
        effect: "confirmed",
        route: "accessibility_action",
        evidence: ["semantic_state_change"],
      });
    expect(deps.acquireSeat).toHaveBeenCalledWith(
      "computer-neko",
      "agent-session:session-1",
      false,
      "operation-acquire-1",
    );
    expect(deps.act).toHaveBeenCalledWith(
      expect.objectContaining({
        environmentId: "computer-neko",
        leaseId: "lease-agent",
        stateVersion: action.stateVersion,
        targetRef: action.targetRef,
        expectedRole: action.expectedRole,
        expectedName: action.expectedName,
        action: action.action,
      }),
      "operation-act-1",
    );
  });

  it("accepts one printable browser key and rejects control sequences", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);
    await bridge.handle(WIII_COMPUTER_AGENT_METHODS.acquire, {
      operationId: "operation-acquire-key",
    });

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      operationId: "operation-key-n",
      stateVersion: "state-1",
      targetRef: "app:browser",
      expectedRole: "browser",
      expectedName: "TrÃ¬nh duyá»‡t",
      action: "press_key",
      key: "n",
    })).resolves.toMatchObject({ outcome: "completed", verified: true });
    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      operationId: "operation-key-newline",
      stateVersion: "state-1",
      targetRef: "app:browser",
      expectedRole: "browser",
      expectedName: "TrÃ¬nh duyá»‡t",
      action: "press_key",
      key: "\n",
    })).rejects.toThrow("allowlisted key");
  });

  it("accepts a bounded input chord sequence and rejects unbounded timing", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);
    await bridge.handle(WIII_COMPUTER_AGENT_METHODS.acquire, {
      operationId: "operation-acquire-sequence",
    });

    const inputSequence = [
      { keys: ["Shift", "ArrowUp"], holdMs: 240, waitMs: 20 },
      { keys: ["ArrowRight"], holdMs: 90, waitMs: 0 },
    ];
    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      operationId: "operation-input-sequence",
      stateVersion: "state-1",
      targetRef: "app:browser",
      expectedRole: "browser",
      expectedName: "Trình duyệt",
      action: "input_sequence",
      inputSequence,
      returnObservation: true,
    })).resolves.toMatchObject({ outcome: "completed", verified: true });
    expect(deps.act).toHaveBeenLastCalledWith(
      expect.objectContaining({ inputSequence, returnObservation: true }),
      "operation-input-sequence",
    );

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      operationId: "operation-input-sequence-long",
      stateVersion: "state-1",
      targetRef: "app:browser",
      expectedRole: "browser",
      expectedName: "Trình duyệt",
      action: "input_sequence",
      inputSequence: [{ keys: ["ArrowUp"], holdMs: 2_001 }],
    })).rejects.toThrow("holdMs");

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      operationId: "operation-input-sequence-invalid-observation",
      stateVersion: "state-1",
      targetRef: "app:browser",
      expectedRole: "browser",
      expectedName: "Trình duyệt",
      action: "input_sequence",
      inputSequence,
      returnObservation: "yes",
    })).rejects.toThrow("returnObservation must be a boolean");
  });

  it("keeps stepped realtime control explicit and canvas-scoped", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);
    await bridge.handle(WIII_COMPUTER_AGENT_METHODS.acquire, {
      operationId: "operation-acquire-realtime",
    });

    const inputSequence = [{ keys: ["ArrowUp"], holdMs: 160, waitMs: 0 }];
    await bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      operationId: "operation-realtime-step",
      stateVersion: "state-1",
      targetRef: "web-canvas",
      expectedRole: "canvas",
      expectedName: "Game canvas",
      action: "input_sequence",
      inputSequence,
      returnObservation: true,
      realtimeMode: "stepped",
    });
    expect(deps.act).toHaveBeenLastCalledWith(
      expect.objectContaining({ realtimeMode: "stepped", returnObservation: true }),
      "operation-realtime-step",
    );

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      operationId: "operation-realtime-no-observation",
      stateVersion: "state-1",
      targetRef: "web-canvas",
      expectedRole: "canvas",
      expectedName: "Game canvas",
      action: "input_sequence",
      inputSequence,
      realtimeMode: "stepped",
    })).rejects.toThrow("requires returnObservation");

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      operationId: "operation-realtime-wrong-target",
      stateVersion: "state-1",
      targetRef: "app:browser",
      expectedRole: "browser",
      expectedName: "TrÃ¬nh duyá»‡t",
      action: "press_key",
      key: "Enter",
      returnObservation: true,
      realtimeMode: "stepped",
    })).rejects.toThrow("requires a canvas keyboard action");
  });

  it("releases control once on explicit release or disposal", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    await bridge.handle(WIII_COMPUTER_AGENT_METHODS.acquire, {
      operationId: "operation-acquire-1",
    });
    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.release, {
      operationId: "operation-release-1",
    }))
      .resolves.toEqual({ released: true });
    await bridge.dispose();
    expect(deps.releaseSeat).toHaveBeenCalledTimes(1);
    expect(deps.releaseSeat).toHaveBeenCalledWith(
      "computer-neko",
      "lease-agent",
      "operation-release-1",
    );
  });

  it("requires stable operation ids for every mutating request", async () => {
    const deps = dependencies();
    const bridge = new WiiiComputerAgentBridge("session-1", "project-wiii", deps);

    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.acquire, {}))
      .rejects.toThrow("operationId");
    await expect(bridge.handle(WIII_COMPUTER_AGENT_METHODS.act, {
      stateVersion: "state-1",
      targetRef: "button-submit",
      expectedRole: "button",
      expectedName: "Send",
      action: "invoke",
    })).rejects.toThrow("operationId");
  });
});
