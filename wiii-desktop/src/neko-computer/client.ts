import { invoke } from "@tauri-apps/api/core";
import type { AppEventBatch, AppEventPollRequest } from "./app-events";
import { v4 as uuidv4 } from "uuid";
import type {
  ComputerDisplaySeat,
  ComputerDoctor,
  ComputerEnvironment,
  ComputerHistoryPage,
  ComputerHistoryStatus,
  ComputerInputStep,
  ComputerReplayPage,
  ComputerResourcePreset,
  ComputerSemanticAction,
  ComputerSemanticActResult,
  ComputerSemanticObserveOptions,
  ComputerSemanticSnapshot,
  WorkPlaneDescriptor,
  WorkPlaneQueryOptions,
  WorkPlaneQueryResult,
  WorkPlaneTransactionInput,
  WorkPlaneTransactionResult,
  ComputerTerminalResult,
  ComputerProjectGrant,
  ComputerProjectRef,
  CoworkerComputerStatus,
  SignalInboxSummary,
  SignalItem,
  SignalOutcome,
} from "./contracts";
import { DEFAULT_NEKO_COWORKER } from "@/neko/coworker-profile";
import { COMPUTER_CORE_PACKAGE_ID } from "./package-model";

export interface ComputerSeatChange {
  environmentId: string;
  seat: ComputerDisplaySeat;
}

type ComputerSeatChangeListener = (change: ComputerSeatChange) => void;

const computerSeatChangeListeners = new Set<ComputerSeatChangeListener>();

export function subscribeComputerSeatChanges(
  listener: ComputerSeatChangeListener,
): () => void {
  computerSeatChangeListeners.add(listener);
  return () => computerSeatChangeListeners.delete(listener);
}

function publishComputerSeatChange(change: ComputerSeatChange): void {
  for (const listener of computerSeatChangeListeners) {
    try {
      listener(change);
    } catch (error) {
      console.error("Computer seat projection failed", error);
    }
  }
}

export function hasNativeComputerAuthority(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function computerRequestId(): string {
  return `computer-${uuidv4()}`;
}

export async function doctorComputer(): Promise<ComputerDoctor> {
  return invoke<ComputerDoctor>("neko_computer_doctor");
}

export async function ensureComputer(
  project: ComputerProjectRef,
  resourcePreset: ComputerResourcePreset = "auto",
  requestId = computerRequestId(),
): Promise<ComputerEnvironment> {
  return invoke<ComputerEnvironment>("neko_computer_ensure", {
    request: {
      requestId,
      coworkerId: DEFAULT_NEKO_COWORKER.id,
      ...project,
      resourcePreset,
    },
  });
}

export async function resolveCoworkerComputer(): Promise<CoworkerComputerStatus> {
  return invoke<CoworkerComputerStatus>("neko_computer_coworker_status", {
    request: { coworkerId: DEFAULT_NEKO_COWORKER.id },
  });
}

export async function grantCoworkerProject(
  project: ComputerProjectRef,
  requestId = computerRequestId(),
): Promise<ComputerProjectGrant> {
  return invoke<ComputerProjectGrant>("neko_computer_project_grant", {
    request: {
      requestId,
      coworkerId: DEFAULT_NEKO_COWORKER.id,
      ...project,
    },
  });
}

export async function revokeCoworkerProject(
  projectId: string,
  requestId = computerRequestId(),
): Promise<void> {
  return invoke<void>("neko_computer_project_revoke", {
    request: {
      requestId,
      coworkerId: DEFAULT_NEKO_COWORKER.id,
      projectId,
    },
  });
}

export async function removeComputerPackage(
  requestId = computerRequestId(),
  packageId = COMPUTER_CORE_PACKAGE_ID,
): Promise<ComputerDoctor> {
  return invoke<ComputerDoctor>("neko_computer_package_remove", {
    request: { requestId, coworkerId: DEFAULT_NEKO_COWORKER.id, packageId },
  });
}

export async function installComputerPackage(
  requestId = computerRequestId(),
  packageId = COMPUTER_CORE_PACKAGE_ID,
): Promise<ComputerDoctor> {
  return invoke<ComputerDoctor>("neko_computer_package_install", {
    request: { requestId, coworkerId: DEFAULT_NEKO_COWORKER.id, packageId },
  });
}

export async function removeComputer(
  environmentId: string,
  confirmation: string,
  requestId = computerRequestId(),
): Promise<void> {
  return invoke<void>("neko_computer_remove", {
    request: { requestId, environmentId, confirmation },
  });
}

export async function suspendComputer(
  environmentId: string,
  requestId = computerRequestId(),
): Promise<ComputerEnvironment> {
  return invoke<ComputerEnvironment>("neko_computer_suspend", {
    request: { requestId, environmentId },
  });
}

export async function resumeComputer(
  environmentId: string,
  requestId = computerRequestId(),
): Promise<ComputerEnvironment> {
  return invoke<ComputerEnvironment>("neko_computer_resume", {
    request: { requestId, environmentId },
  });
}

export async function resetComputer(
  environmentId: string,
  confirmation: string,
  requestId = computerRequestId(),
): Promise<ComputerEnvironment> {
  return invoke<ComputerEnvironment>("neko_computer_reset", {
    request: { requestId, environmentId, confirmation },
  });
}

export async function acquireComputerSeat(
  environmentId: string,
  ownerId: string,
  userControlled: boolean,
  requestId = computerRequestId(),
): Promise<ComputerDisplaySeat> {
  const seat = await invoke<ComputerDisplaySeat>("neko_computer_seat_acquire", {
    request: { requestId, environmentId, ownerId, userControlled },
  });
  publishComputerSeatChange({ environmentId, seat });
  return seat;
}

export async function releaseComputerSeat(
  environmentId: string,
  leaseId: string,
  requestId = computerRequestId(),
): Promise<ComputerDisplaySeat> {
  const seat = await invoke<ComputerDisplaySeat>("neko_computer_seat_release", {
    request: { requestId, environmentId, leaseId },
  });
  publishComputerSeatChange({ environmentId, seat });
  return seat;
}

export async function executeComputerTerminal(
  environmentId: string,
  command: string,
  requestId = computerRequestId(),
): Promise<ComputerTerminalResult> {
  return invoke<ComputerTerminalResult>("neko_computer_terminal_exec", {
    request: { requestId, environmentId, command },
  });
}

export async function navigateComputerBrowser(
  environmentId: string,
  url: string,
  requestId = computerRequestId(),
): Promise<void> {
  return invoke<void>("neko_computer_browser_navigate", {
    request: { requestId, environmentId, url },
  });
}

export async function readComputerEvents(
  environmentId: string,
  afterSeq = 0,
  limit = 100,
): Promise<ComputerReplayPage> {
  return invoke<ComputerReplayPage>("neko_computer_events_read", {
    environmentId,
    afterSeq,
    limit,
  });
}

export async function pollComputerAppEvents(
  request: AppEventPollRequest,
): Promise<AppEventBatch> {
  return invoke<AppEventBatch>("neko_computer_app_events_poll", { request });
}

export async function observeComputerSemantics(
  environmentId: string,
  options: number | ComputerSemanticObserveOptions = 400,
): Promise<ComputerSemanticSnapshot> {
  const request = typeof options === "number"
    ? { environmentId, maxNodes: options }
    : {
        environmentId,
        maxNodes: options.maxNodes ?? 400,
        scopeRef: options.scopeRef ?? null,
        continuation: options.continuation ?? null,
        sinceStateVersion: options.sinceStateVersion ?? null,
        knownNodeVersions: options.knownNodeVersions ?? [],
        visualRef: options.visualRef ?? null,
      };
  return invoke<ComputerSemanticSnapshot>("neko_computer_semantic_observe", {
    request,
  });
}

export async function actOnComputerSemantics(
  input: {
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
  },
  requestId = computerRequestId(),
): Promise<ComputerSemanticActResult> {
  return invoke<ComputerSemanticActResult>("neko_computer_semantic_act", {
    request: {
      requestId,
      ...input,
      text: input.text ?? null,
      key: input.key ?? null,
      inputSequence: input.inputSequence ?? [],
    },
  });
}

export async function readComputerHistoryStatus(): Promise<ComputerHistoryStatus> {
  return invoke<ComputerHistoryStatus>("neko_computer_history_status");
}

export async function setComputerHistoryEnabled(enabled: boolean): Promise<ComputerHistoryStatus> {
  return invoke<ComputerHistoryStatus>("neko_computer_history_set_enabled", {
    request: { enabled },
  });
}

export async function readComputerHistory(
  environmentId: string,
  beforeSeq: number | null = null,
  limit = 50,
): Promise<ComputerHistoryPage> {
  return invoke<ComputerHistoryPage>("neko_computer_history_query", {
    request: { environmentId, beforeSeq, limit },
  });
}

export async function deleteComputerHistory(environmentId: string): Promise<number> {
  return invoke<number>("neko_computer_history_delete", {
    request: { environmentId },
  });
}

export async function consultSignalInbox(maxRefs = 8): Promise<SignalInboxSummary> {
  return invoke<SignalInboxSummary>("neko_signal_inbox_consult", {
    request: { maxRefs },
  });
}

export async function claimSignalInbox(
  workerId: string,
  maxItems = 1,
  leaseSeconds = 120,
): Promise<SignalItem[]> {
  return invoke<SignalItem[]>("neko_signal_inbox_claim", {
    request: { workerId, maxItems, leaseSeconds },
  });
}

export async function deferSignalItem(
  signalId: string,
  leaseId: string,
  availableAt: string,
  operationId = computerRequestId(),
): Promise<SignalItem> {
  return invoke<SignalItem>("neko_signal_inbox_defer", {
    request: { signalId, leaseId, operationId, availableAt },
  });
}

export async function resolveSignalItem(
  signalId: string,
  leaseId: string,
  outcome: SignalOutcome,
  sourceRevision: string,
  operationId = computerRequestId(),
): Promise<SignalItem> {
  return invoke<SignalItem>("neko_signal_inbox_resolve", {
    request: { signalId, leaseId, operationId, outcome, sourceRevision },
  });
}

export async function revokeSignalAccount(accountGrantRef: string): Promise<number> {
  return invoke<number>("neko_signal_inbox_revoke_account", {
    request: { accountGrantRef },
  });
}

export async function describeWorkPlane(
  environmentId: string,
  projectId: string,
): Promise<WorkPlaneDescriptor> {
  return invoke<WorkPlaneDescriptor>("neko_computer_work_plane_describe", {
    request: { environmentId, projectId },
  });
}

export async function queryWorkPlane(
  environmentId: string,
  projectId: string,
  options: WorkPlaneQueryOptions,
): Promise<WorkPlaneQueryResult> {
  return invoke<WorkPlaneQueryResult>("neko_computer_work_plane_query", {
    request: {
      environmentId,
      projectId,
      resourceRef: options.resourceRef,
      view: options.view,
      maxItems: options.maxItems ?? 100,
      offset: options.offset ?? 0,
      maxBytes: options.maxBytes ?? 64 * 1024,
      sheet: options.sheet ?? null,
      range: options.range ?? null,
    },
  });
}

export async function executeWorkPlane(
  input: WorkPlaneTransactionInput,
  requestId = computerRequestId(),
): Promise<WorkPlaneTransactionResult> {
  return invoke<WorkPlaneTransactionResult>("neko_computer_work_plane_execute", {
    request: { requestId, ...input },
  });
}
