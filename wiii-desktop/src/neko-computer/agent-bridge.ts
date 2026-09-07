import {
  acquireComputerSeat,
  actOnComputerSemantics,
  computerRequestId,
  consultSignalInbox,
  describeWorkPlane,
  executeWorkPlane,
  observeComputerSemantics,
  queryWorkPlane,
  readComputerHistory,
  readComputerHistoryStatus,
  releaseComputerSeat,
  resolveCoworkerComputer,
} from "./client";
import type {
  ComputerDisplaySeat,
  ComputerEnvironment,
  ComputerHistoryPage,
  ComputerHistoryStatus,
  ComputerInputStep,
  ComputerSemanticAction,
  ComputerSemanticActResult,
  ComputerSemanticObserveOptions,
  ComputerSemanticSnapshot,
  ComputerWorkstationManifest,
  CoworkerComputerStatus,
  SignalInboxSummary,
  WorkPlaneDescriptor,
  WorkPlaneQueryOptions,
  WorkPlaneQueryResult,
  WorkPlaneTransactionInput,
  WorkPlaneTransactionResult,
} from "./contracts";
import { buildWorkstationManifest } from "./workstation-manifest";
import {
  ComputerProcedureRuntime,
  parseProcedureRun,
} from "./procedure-runtime";

export const WIII_COMPUTER_AGENT_METHODS = {
  status: "_wiii/computer/v1/status",
  observe: "_wiii/computer/v1/observe",
  acquire: "_wiii/computer/v1/lease/acquire",
  act: "_wiii/computer/v1/act",
  release: "_wiii/computer/v1/lease/release",
} as const;

export const WIII_COMPUTER_AGENT_CAPABILITY = "dev.wiii.computer.v1";
export const WIII_COMPUTER_HISTORY_AGENT_METHODS = {
  status: "_wiii/computer-history/v1/status",
  query: "_wiii/computer-history/v1/query",
} as const;
export const WIII_COMPUTER_HISTORY_AGENT_CAPABILITY = "dev.wiii.computer-history.v1";
export const WIII_WORK_PLANE_AGENT_METHODS = {
  describe: "_wiii/work-plane/v1/describe",
  query: "_wiii/work-plane/v1/query",
  execute: "_wiii/work-plane/v1/execute",
} as const;
export const WIII_WORK_PLANE_AGENT_CAPABILITY = "dev.wiii.work-plane.v1";
export const WIII_SIGNAL_INBOX_AGENT_METHODS = {
  consult: "_wiii/signal-inbox/v1/consult",
} as const;
export const WIII_SIGNAL_INBOX_AGENT_CAPABILITY = "dev.wiii.signal-inbox.v1";
export const WIII_COMPUTER_PROCEDURE_AGENT_METHODS = {
  catalog: "_wiii/computer-procedures/v1/catalog",
  run: "_wiii/computer-procedures/v1/run",
} as const;
export const WIII_COMPUTER_PROCEDURE_AGENT_CAPABILITY = "dev.wiii.computer-procedures.v1";

const METHOD_SET = new Set<string>([
  ...Object.values(WIII_COMPUTER_AGENT_METHODS),
  ...Object.values(WIII_COMPUTER_HISTORY_AGENT_METHODS),
  ...Object.values(WIII_WORK_PLANE_AGENT_METHODS),
  ...Object.values(WIII_SIGNAL_INBOX_AGENT_METHODS),
  ...Object.values(WIII_COMPUTER_PROCEDURE_AGENT_METHODS),
]);

export interface AgentComputerBridge {
  handles(method: string): boolean;
  handle(method: string, params: unknown, signal?: AbortSignal): Promise<unknown>;
  dispose(): Promise<void>;
}

export interface AgentComputerBridgeDependencies {
  resolveStatus(): Promise<CoworkerComputerStatus>;
  acquireSeat(
    environmentId: string,
    ownerId: string,
    userControlled: boolean,
    requestId: string,
  ): Promise<ComputerDisplaySeat>;
  releaseSeat(
    environmentId: string,
    leaseId: string,
    requestId: string,
  ): Promise<ComputerDisplaySeat>;
  observe(environmentId: string, options: ComputerSemanticObserveOptions): Promise<ComputerSemanticSnapshot>;
  historyStatus(): Promise<ComputerHistoryStatus>;
  historyQuery(environmentId: string, beforeSeq: number | null, limit: number): Promise<ComputerHistoryPage>;
  signalInboxConsult?(maxRefs: number): Promise<SignalInboxSummary>;
  workPlaneDescribe(environmentId: string, projectId: string): Promise<WorkPlaneDescriptor>;
  workPlaneQuery(
    environmentId: string,
    projectId: string,
    options: WorkPlaneQueryOptions,
  ): Promise<WorkPlaneQueryResult>;
  workPlaneExecute(input: WorkPlaneTransactionInput, requestId: string): Promise<WorkPlaneTransactionResult>;
  act(input: {
    environmentId: string;
    leaseId: string;
    stateVersion: string;
    targetRef: string;
    expectedRole: string;
    expectedName: string;
    action: ComputerSemanticAction;
    text?: string | null;
    key?: string | null;
    inputSequence?: ComputerInputStep[];
    returnObservation?: boolean;
    realtimeMode?: "continuous" | "stepped";
  }, requestId: string): Promise<ComputerSemanticActResult>;
}

interface ActiveComputer {
  environmentId: string;
  state: "preparing" | "ready" | "suspended" | "error" | "unknown_outcome";
  operatingSystem: string;
  semanticProtocol: string;
  seatState: "available" | "agent_controlled" | "user_controlled";
}

interface AgentActParams {
  operationId: string;
  stateVersion: string;
  targetRef: string;
  expectedRole: string;
  expectedName: string;
  action: ComputerSemanticAction;
  text?: string | null;
  key?: string | null;
  inputSequence?: ComputerInputStep[];
  returnObservation?: boolean;
  realtimeMode?: "continuous" | "stepped";
}

interface AgentWorkTransactionParams {
  operationId: string;
  capabilityId: string;
  capabilityVersion: string;
  targetRef: string;
  ifRevision: string;
  input: Record<string, unknown>;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Wiii Computer request parameters must be an object");
  }
  return value as Record<string, unknown>;
}

function requiredString(
  record: Record<string, unknown>,
  key: string,
  maxLength: number,
): string {
  const value = record[key];
  if (typeof value !== "string" || !value.trim() || value.length > maxLength) {
    throw new Error(`Wiii Computer requires a valid ${key}`);
  }
  return value;
}

function supportedComputerKey(value: unknown): value is string {
  if (typeof value !== "string") return false;
  if ([
    "Alt",
    "Control",
    "Shift",
    "Meta",
    "ArrowLeft",
    "ArrowUp",
    "ArrowRight",
    "ArrowDown",
    "Enter",
    "Escape",
    "Tab",
    "Space",
    "Backspace",
    "Delete",
    "Home",
    "End",
    "PageUp",
    "PageDown",
  ].includes(value)) {
    return true;
  }
  const characters = Array.from(value);
  const codePoint = characters[0]?.codePointAt(0) ?? 0;
  return characters.length === 1 && codePoint > 31 && codePoint !== 127;
}

function parseInputSequence(value: unknown): ComputerInputStep[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 64) {
    throw new Error("Wiii Computer inputSequence must contain 1 to 64 steps");
  }
  let totalMs = 0;
  return value.map((candidate) => {
    const step = asRecord(candidate);
    if (!Array.isArray(step.keys) || step.keys.length < 1 || step.keys.length > 3
      || !step.keys.every(supportedComputerKey)) {
      throw new Error("Wiii Computer inputSequence step keys must contain 1 to 3 allowlisted keys");
    }
    const keys = step.keys as string[];
    if (new Set(keys).size !== keys.length) {
      throw new Error("Wiii Computer inputSequence step keys must be unique");
    }
    const holdMs = step.holdMs;
    const waitMs = step.waitMs ?? 0;
    if (!Number.isInteger(holdMs) || Number(holdMs) < 16 || Number(holdMs) > 2_000) {
      throw new Error("Wiii Computer inputSequence holdMs must be between 16 and 2000");
    }
    if (!Number.isInteger(waitMs) || Number(waitMs) < 0 || Number(waitMs) > 1_000) {
      throw new Error("Wiii Computer inputSequence waitMs must be between 0 and 1000");
    }
    totalMs += Number(holdMs) + Number(waitMs);
    if (totalMs > 8_000) {
      throw new Error("Wiii Computer inputSequence must finish within 8000 ms");
    }
    return { keys, holdMs: Number(holdMs), waitMs: Number(waitMs) };
  });
}

function parseActParams(value: unknown): AgentActParams {
  const params = asRecord(value);
  const action = params.action;
  if (action !== "focus" && action !== "invoke" && action !== "set_text" && action !== "press_key" && action !== "input_sequence") {
    throw new Error("Wiii Computer action must be focus, invoke, set_text, press_key, or input_sequence");
  }
  const text = params.text;
  if (text !== undefined && text !== null && typeof text !== "string") {
    throw new Error("Wiii Computer action text must be a string");
  }
  if (typeof text === "string" && text.length > 100_000) {
    throw new Error("Wiii Computer action text is too large");
  }
  if (action === "set_text" && typeof text !== "string") {
    throw new Error("Wiii Computer set_text requires text");
  }
  if (action !== "set_text" && text !== undefined && text !== null) {
    throw new Error("Wiii Computer text is only valid for set_text");
  }
  const key = params.key;
  if (key !== undefined && key !== null && typeof key !== "string") {
    throw new Error("Wiii Computer action key must be a string");
  }
  if (action === "press_key" && !supportedComputerKey(key)) {
    throw new Error("Wiii Computer press_key requires an allowlisted key");
  }
  if (action !== "press_key" && key !== undefined && key !== null) {
    throw new Error("Wiii Computer key is only valid for press_key");
  }
  const inputSequence = params.inputSequence;
  const parsedInputSequence = action === "input_sequence" ? parseInputSequence(inputSequence) : undefined;
  if (action !== "input_sequence" && inputSequence !== undefined && inputSequence !== null
    && (!Array.isArray(inputSequence) || inputSequence.length > 0)) {
    throw new Error("Wiii Computer inputSequence is only valid for input_sequence");
  }
  const returnObservation = params.returnObservation;
  if (returnObservation !== undefined && typeof returnObservation !== "boolean") {
    throw new Error("Wiii Computer returnObservation must be a boolean");
  }
  const realtimeMode = params.realtimeMode;
  if (realtimeMode !== undefined && realtimeMode !== null
    && realtimeMode !== "continuous" && realtimeMode !== "stepped") {
    throw new Error("Wiii Computer realtimeMode must be continuous or stepped");
  }
  if (realtimeMode !== undefined && realtimeMode !== null
    && (params.expectedRole !== "canvas"
      || !["focus", "press_key", "input_sequence"].includes(action))) {
    throw new Error("Wiii Computer realtimeMode requires a canvas keyboard action");
  }
  if (realtimeMode === "stepped" && returnObservation !== true) {
    throw new Error("Wiii Computer stepped realtimeMode requires returnObservation");
  }
  return {
    operationId: requiredString(params, "operationId", 200),
    stateVersion: requiredString(params, "stateVersion", 500),
    targetRef: requiredString(params, "targetRef", 500),
    expectedRole: requiredString(params, "expectedRole", 200),
    expectedName: requiredString(params, "expectedName", 2_000),
    action,
    ...(text === undefined ? {} : { text }),
    ...(key === undefined ? {} : { key }),
    ...(parsedInputSequence === undefined ? {} : { inputSequence: parsedInputSequence }),
    ...(returnObservation === undefined ? {} : { returnObservation }),
    ...(realtimeMode === undefined || realtimeMode === null ? {} : { realtimeMode }),
  };
}

function operationIdFrom(value: unknown): string {
  return requiredString(asRecord(value), "operationId", 200);
}

function historyQueryFrom(value: unknown): { beforeSeq: number | null; limit: number } {
  const params = value === undefined || value === null ? {} : asRecord(value);
  const beforeSeq = params.beforeSeq ?? null;
  if (beforeSeq !== null && (!Number.isSafeInteger(beforeSeq) || Number(beforeSeq) < 1)) {
    throw new Error("Wiii Computer History beforeSeq is invalid");
  }
  const limit = params.limit ?? 50;
  if (!Number.isInteger(limit) || Number(limit) < 1) {
    throw new Error("Wiii Computer History limit must be a positive integer");
  }
  return { beforeSeq: beforeSeq === null ? null : Number(beforeSeq), limit: Math.min(Number(limit), 100) };
}

function signalInboxMaxRefsFrom(value: unknown): number {
  const params = value === undefined || value === null ? {} : asRecord(value);
  const maxRefs = params.maxRefs ?? 8;
  if (!Number.isSafeInteger(maxRefs) || Number(maxRefs) < 0 || Number(maxRefs) > 32) {
    throw new Error("Wiii Signal Inbox maxRefs must be between 0 and 32");
  }
  return Number(maxRefs);
}

function workQueryFrom(value: unknown): WorkPlaneQueryOptions {
  const params = asRecord(value);
  const view = params.view;
  if (view !== "children" && view !== "content" && view !== "spreadsheet") {
    throw new Error("Wiii Work Plane view must be children, content, or spreadsheet");
  }
  const boundedInteger = (key: "maxItems" | "offset" | "maxBytes", fallback: number, minimum: number, maximum: number) => {
    const candidate = params[key] ?? fallback;
    if (!Number.isSafeInteger(candidate) || Number(candidate) < minimum || Number(candidate) > maximum) {
      throw new Error(`Wiii Work Plane ${key} is invalid`);
    }
    return Number(candidate);
  };
  const optionalString = (key: "sheet" | "range", maximum: number) => {
    const candidate = params[key];
    if (candidate === undefined || candidate === null) return null;
    if (typeof candidate !== "string" || !candidate || candidate.length > maximum) {
      throw new Error(`Wiii Work Plane ${key} is invalid`);
    }
    return candidate;
  };
  return {
    resourceRef: requiredString(params, "resourceRef", 512),
    view,
    maxItems: boundedInteger("maxItems", 100, 1, 200),
    offset: boundedInteger("offset", 0, 0, 10_000_000),
    maxBytes: boundedInteger("maxBytes", 64 * 1024, 1, 64 * 1024),
    sheet: optionalString("sheet", 200),
    range: optionalString("range", 100),
  };
}

function workTransactionFrom(value: unknown): AgentWorkTransactionParams {
  const params = asRecord(value);
  const ifRevision = requiredString(params, "ifRevision", 96);
  if (!ifRevision.startsWith("sha256:")) {
    throw new Error("Wiii Work Plane ifRevision is invalid");
  }
  const input = asRecord(params.input);
  if (new TextEncoder().encode(JSON.stringify(input)).byteLength > 256 * 1024) {
    throw new Error("Wiii Work Plane input exceeds 262144 bytes");
  }
  return {
    operationId: requiredString(params, "operationId", 200),
    capabilityId: requiredString(params, "capabilityId", 120),
    capabilityVersion: requiredString(params, "capabilityVersion", 32),
    targetRef: requiredString(params, "targetRef", 512),
    ifRevision,
    input,
  };
}

function historyStatusForAgent(status: ComputerHistoryStatus) {
  return {
    available: status.available,
    enabled: status.enabled,
    encrypted: status.encrypted,
    retentionDays: status.retentionDays,
    entryCount: status.entryCount,
    healthy: status.lastError === null,
  };
}

function historyPageForAgent(page: ComputerHistoryPage) {
  return {
    entries: page.entries.map((entry) => ({
      seq: entry.seq,
      at: entry.at,
      outcome: entry.outcome,
      action: entry.action,
      targetRef: entry.targetRef,
      beforeStateVersion: entry.beforeStateVersion,
      afterStateVersion: entry.afterStateVersion,
      verified: entry.verified,
      effect: entry.effect,
      route: entry.route,
      evidence: entry.evidence,
      code: entry.code,
    })),
    nextBeforeSeq: page.nextBeforeSeq,
    hasMore: page.hasMore,
  };
}

function observeOptionsFrom(value: unknown): ComputerSemanticObserveOptions {
  if (value === undefined || value === null) return { maxNodes: 400 };
  const params = asRecord(value);
  const maxNodes = params.maxNodes ?? 400;
  if (!Number.isInteger(maxNodes) || Number(maxNodes) < 1) {
    throw new Error("Wiii Computer maxNodes must be a positive integer");
  }
  const optionalString = (key: "scopeRef" | "continuation" | "sinceStateVersion" | "visualRef", limit: number): string | null => {
    const candidate = params[key];
    if (candidate === undefined || candidate === null) return null;
    if (typeof candidate !== "string" || !candidate || candidate.length > limit) {
      throw new Error(`Wiii Computer ${key} is invalid`);
    }
    return candidate;
  };
  const known = params.knownNodeVersions ?? [];
  if (!Array.isArray(known) || known.length > 2000) {
    throw new Error("Wiii Computer knownNodeVersions is invalid");
  }
  const knownNodeVersions = known.map((entry) => {
    const record = asRecord(entry);
    const ref = requiredString(record, "ref", 256);
    const version = requiredString(record, "version", 96);
    if (!version.startsWith("sha256:")) {
      throw new Error("Wiii Computer node version is invalid");
    }
    return { ref, version };
  });
  const sinceStateVersion = optionalString("sinceStateVersion", 96);
  if (sinceStateVersion !== null && !sinceStateVersion.startsWith("sha256:")) {
    throw new Error("Wiii Computer sinceStateVersion is invalid");
  }
  return {
    maxNodes: Math.min(Number(maxNodes), 400),
    scopeRef: optionalString("scopeRef", 256),
    continuation: optionalString("continuation", 4096),
    sinceStateVersion,
    knownNodeVersions,
    visualRef: optionalString("visualRef", 256),
  };
}

function defaultDependencies(): AgentComputerBridgeDependencies {
  return {
    resolveStatus: resolveCoworkerComputer,
    acquireSeat: (environmentId, ownerId, userControlled, requestId) =>
      acquireComputerSeat(environmentId, ownerId, userControlled, requestId),
    releaseSeat: (environmentId, leaseId, requestId) =>
      releaseComputerSeat(environmentId, leaseId, requestId),
    observe: (environmentId, options) => observeComputerSemantics(environmentId, options),
    historyStatus: readComputerHistoryStatus,
    historyQuery: readComputerHistory,
    signalInboxConsult: consultSignalInbox,
    workPlaneDescribe: describeWorkPlane,
    workPlaneQuery: queryWorkPlane,
    workPlaneExecute: executeWorkPlane,
    act: (input, requestId) => actOnComputerSemantics(input, requestId),
  };
}

export class WiiiComputerAgentBridge implements AgentComputerBridge {
  private readonly ownerId: string;
  private lease: { environmentId: string; leaseId: string } | null = null;
  private workstationManifestCache: {
    key: string;
    manifest: ComputerWorkstationManifest;
  } | null = null;

  constructor(
    sessionId: string,
    private readonly projectId: string,
    private readonly dependencies: AgentComputerBridgeDependencies = defaultDependencies(),
  ) {
    if (!sessionId || sessionId.length > 170) {
      throw new Error("Wiii Computer requires a valid agent session id");
    }
    if (!projectId.trim()) {
      throw new Error("Wiii Computer requires a stable Project identity");
    }
    this.ownerId = `agent-session:${sessionId}`;
  }

  private procedureRuntime(signal?: AbortSignal): ComputerProcedureRuntime {
    return new ComputerProcedureRuntime({
      projectId: this.projectId,
      resolveContext: async () => {
        const current = await this.status();
        if (!current.available || !current.computer || !current.workstation) {
          throw new Error(`${current.code}: ${current.detail}`);
        }
        return {
          computer: current.computer,
          workstationContextVersion: current.workstation.contextVersion,
        };
      },
      observe: (environmentId) => this.dependencies.observe(environmentId, {
        maxNodes: 16,
        scopeRef: "workstation:main",
      }),
      describeWorkPlane: (environmentId) => (
        this.dependencies.workPlaneDescribe(environmentId, this.projectId)
      ),
      executeWorkPlane: (input, operationId) => {
        signal?.throwIfAborted();
        return this.dependencies.workPlaneExecute(input, operationId);
      },
      hasLease: (environmentId) => this.lease?.environmentId === environmentId,
      acquire: (operationId) => this.acquire(operationId, signal),
      act: (input) => this.act(input, signal),
      release: (operationId) => this.release(operationId),
    });
  }

  handles(method: string): boolean {
    return METHOD_SET.has(method);
  }

  async handle(method: string, params: unknown, signal?: AbortSignal): Promise<unknown> {
    signal?.throwIfAborted();
    switch (method) {
      case WIII_COMPUTER_AGENT_METHODS.status:
        return this.status();
      case WIII_COMPUTER_AGENT_METHODS.observe: {
        const computer = await this.requireActiveComputer();
        return this.dependencies.observe(computer.environmentId, observeOptionsFrom(params));
      }
      case WIII_COMPUTER_AGENT_METHODS.acquire:
        return this.acquire(operationIdFrom(params), signal);
      case WIII_COMPUTER_AGENT_METHODS.act:
        return this.act(parseActParams(params), signal);
      case WIII_COMPUTER_AGENT_METHODS.release:
        return { released: await this.release(operationIdFrom(params)) };
      case WIII_COMPUTER_HISTORY_AGENT_METHODS.status:
        return historyStatusForAgent(await this.dependencies.historyStatus());
      case WIII_COMPUTER_HISTORY_AGENT_METHODS.query: {
        const history = await this.dependencies.historyStatus();
        if (!history.enabled) {
          throw new Error("computer_history_disabled: the user has not enabled Computer History");
        }
        const computer = await this.requireActiveComputer();
        const query = historyQueryFrom(params);
        const page = await this.dependencies.historyQuery(computer.environmentId, query.beforeSeq, query.limit);
        return historyPageForAgent(page);
      }
      case WIII_SIGNAL_INBOX_AGENT_METHODS.consult: {
        const maxRefs = signalInboxMaxRefsFrom(params);
        if (!this.dependencies.signalInboxConsult) {
          throw new Error("signal_inbox_unavailable: Wiii host did not provide Signal Inbox");
        }
        return this.dependencies.signalInboxConsult(maxRefs);
      }
      case WIII_WORK_PLANE_AGENT_METHODS.describe: {
        const computer = await this.requireActiveComputer();
        return this.dependencies.workPlaneDescribe(computer.environmentId, this.projectId);
      }
      case WIII_WORK_PLANE_AGENT_METHODS.query: {
        const computer = await this.requireActiveComputer();
        return this.dependencies.workPlaneQuery(
          computer.environmentId,
          this.projectId,
          workQueryFrom(params),
        );
      }
      case WIII_WORK_PLANE_AGENT_METHODS.execute: {
        const computer = await this.requireActiveComputer();
        const { operationId, ...transaction } = workTransactionFrom(params);
        signal?.throwIfAborted();
        return this.dependencies.workPlaneExecute({
          environmentId: computer.environmentId,
          projectId: this.projectId,
          ...transaction,
        }, operationId);
      }
      case WIII_COMPUTER_PROCEDURE_AGENT_METHODS.catalog:
        return this.procedureRuntime().catalog();
      case WIII_COMPUTER_PROCEDURE_AGENT_METHODS.run:
        return this.procedureRuntime(signal).run(parseProcedureRun(params));
      default:
        throw new Error(`Unsupported Wiii Computer method: ${method}`);
    }
  }

  async dispose(): Promise<void> {
    await this.release(computerRequestId());
  }

  private async workstationManifest(
    environment: ComputerEnvironment,
  ): Promise<ComputerWorkstationManifest> {
    const key = [
      environment.environmentId,
      environment.updatedAt,
      environment.projectName,
      environment.operatingSystem,
    ].join("\u0000");
    if (this.workstationManifestCache?.key === key) {
      return this.workstationManifestCache.manifest;
    }
    let launcherNodes: ComputerSemanticSnapshot["nodes"] = [];
    if (environment.state === "ready") {
      try {
        const snapshot = await this.dependencies.observe(environment.environmentId, {
          maxNodes: 16,
          scopeRef: "workstation:main",
        });
        launcherNodes = snapshot.nodes;
      } catch {
        launcherNodes = [];
      }
    }
    const manifest = buildWorkstationManifest({
      operatingSystem: environment.operatingSystem,
      projectName: environment.projectName,
      launcherNodes,
    });
    this.workstationManifestCache = { key, manifest };
    return manifest;
  }

  private async status(): Promise<{
    protocolVersion: "wiii-computer.agent.v1";
    available: boolean;
    code: string;
    detail: string;
    computer: ActiveComputer | null;
    workstation: ComputerWorkstationManifest | null;
    agentHasControl: boolean;
  }> {
    const status = await this.dependencies.resolveStatus();
    const environment = status.environment;
    const projectMatches = Boolean(
      environment
      && status.activeProjectId === this.projectId,
    );
    if (!environment) {
      return {
        protocolVersion: "wiii-computer.agent.v1",
        available: false,
        code: "computer_not_installed",
        detail: "Neko's Computer has not been installed in Wiii.",
        computer: null,
        workstation: null,
        agentHasControl: false,
      };
    }
    if (!projectMatches) {
      return {
        protocolVersion: "wiii-computer.agent.v1",
        available: false,
        code: "project_not_active",
        detail: "This session's Project is not the active granted Project in Neko's Computer.",
        computer: null,
        workstation: null,
        agentHasControl: false,
      };
    }
    return {
      protocolVersion: "wiii-computer.agent.v1",
      available: environment.state === "ready",
      code: environment.state === "ready" ? "ready" : `computer_${environment.state}`,
      detail: environment.state === "ready"
        ? "Neko's Computer is ready for this Project."
        : `Neko's Computer is ${environment.state}.`,
      computer: {
        environmentId: environment.environmentId,
        state: environment.state,
        operatingSystem: environment.operatingSystem,
        semanticProtocol: environment.semanticProtocol,
        seatState: environment.seat.state,
      },
      workstation: await this.workstationManifest(environment),
      agentHasControl: Boolean(
        this.lease
        && this.lease.environmentId === environment.environmentId
        && environment.seat.state === "agent_controlled",
      ),
    };
  }

  private async requireActiveComputer(): Promise<ActiveComputer> {
    const current = await this.status();
    if (!current.available || !current.computer) {
      throw new Error(`${current.code}: ${current.detail}`);
    }
    return current.computer;
  }

  private async acquire(
    operationId: string,
    signal?: AbortSignal,
  ): Promise<{ acquired: true; seatState: "agent_controlled" }> {
    const computer = await this.requireActiveComputer();
    if (this.lease && this.lease.environmentId !== computer.environmentId) {
      await this.release(computerRequestId());
    }
    signal?.throwIfAborted();
    const seat = await this.dependencies.acquireSeat(
      computer.environmentId,
      this.ownerId,
      false,
      operationId,
    );
    if (seat.state !== "agent_controlled" || !seat.leaseId) {
      throw new Error("Wiii Computer did not grant an agent-controlled display lease");
    }
    this.lease = { environmentId: computer.environmentId, leaseId: seat.leaseId };
    return { acquired: true, seatState: "agent_controlled" };
  }

  private async act(params: AgentActParams, signal?: AbortSignal): Promise<ComputerSemanticActResult> {
    const computer = await this.requireActiveComputer();
    signal?.throwIfAborted();
    if (!this.lease || this.lease.environmentId !== computer.environmentId) {
      throw new Error("computer_lease_required: acquire agent control before acting");
    }
    const { operationId, ...action } = params;
    return this.dependencies.act({
      environmentId: computer.environmentId,
      leaseId: this.lease.leaseId,
      ...action,
    }, operationId);
  }

  private async release(operationId: string): Promise<boolean> {
    const lease = this.lease;
    if (!lease) return true;
    await this.dependencies.releaseSeat(lease.environmentId, lease.leaseId, operationId);
    this.lease = null;
    return true;
  }
}

export function createComputerAgentBridge(input: {
  sessionId: string;
  projectId: string;
}): AgentComputerBridge {
  return new WiiiComputerAgentBridge(input.sessionId, input.projectId);
}
