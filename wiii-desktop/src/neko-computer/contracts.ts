import type { ComputerSeatState } from "@/neko/seat-contract";

export type { ComputerSeatState } from "@/neko/seat-contract";

export type ComputerState =
  | "preparing"
  | "ready"
  | "suspended"
  | "error"
  | "unknown_outcome";

export type ComputerResourcePreset =
  | "auto"
  | "compact"
  | "balanced"
  | "performance";

export type ComputerProviderKind =
  | "local_docker"
  | "local_wsl"
  | "local_apple_vm"
  | "local_linux_rootless"
  | "cloud";

export type ComputerIsolationClass =
  | "shared_container"
  | "dedicated_vm"
  | "rootless_container"
  | "remote_vm";

export interface ComputerResources {
  cpus: string;
  memoryBytes: number;
  pidsLimit: number;
  sharedMemoryBytes: number;
  temporaryStorageBytes: number;
}

export interface ComputerDisplaySeat {
  seatId: string;
  state: ComputerSeatState;
  leaseId: string | null;
  ownerId: string | null;
  updatedAt: string;
}

export interface ComputerProjectRef {
  projectId: string;
  projectName: string;
  projectPath: string;
}

export interface ComputerEnvironment {
  environmentId: string;
  projectId: string | null;
  projectName: string;
  projectPath: string;
  providerKind: ComputerProviderKind;
  isolationClass: ComputerIsolationClass;
  computerKind: "web_computer";
  operatingSystem: string;
  semanticProtocol: "neko-computer.semantic.v1";
  activePackVersion?: string | null;
  packUpdateAvailable?: boolean;
  state: ComputerState;
  projectMount: "/workspace/project";
  attachUrl: string | null;
  resources: ComputerResources;
  seat: ComputerDisplaySeat;
  createdAt: string;
  updatedAt: string;
}

export interface ComputerProjectGrant {
  coworkerId: string;
  projectId: string | null;
  projectName: string;
  projectPath: string;
  accessMode: "read_write";
  createdAt: string;
  updatedAt: string;
}

export interface CoworkerComputerStatus {
  coworkerId: string;
  environmentId: string | null;
  activeProjectId: string | null;
  activeProjectPath: string | null;
  environment: ComputerEnvironment | null;
  grants: ComputerProjectGrant[];
}

export type ComputerWorkstationSurface =
  | "computer"
  | "browser"
  | "terminal"
  | "files";

export interface ComputerWorkstationApp {
  appId: string;
  displayName: string;
  state: "available" | "running" | "unavailable";
  actions: ComputerSemanticAction[];
}

export interface ComputerWorkstationManifest {
  schemaVersion: "wiii-workstation.manifest.v1";
  contextVersion: string;
  label: string;
  coworkerName: string;
  persistence: "durable" | "ephemeral";
  operatingSystem: string;
  interactionMode: "semantic";
  activeProjectLabel: string;
  surfaces: ComputerWorkstationSurface[];
  apps: ComputerWorkstationApp[];
  installedApps?: ComputerWorkstationApp[];
}

export type ComputerSemanticAction = "focus" | "invoke" | "set_text" | "press_key" | "input_sequence";

export interface ComputerInputStep {
  keys: string[];
  holdMs: number;
  waitMs?: number;
}

export interface ComputerSemanticBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ComputerSemanticNode {
  ref: string;
  parentRef: string | null;
  appId: string | null;
  role: string;
  name: string;
  description: string | null;
  value: string | null;
  states: string[];
  actions: ComputerSemanticAction[];
  bounds: ComputerSemanticBounds | null;
  sources?: Array<"workstation" | "browser" | "desktop" | "accessibility" | "dom" | "layout" | "temporal_visual" | "visual_fingerprint" | "canvas_fingerprint">;
  shortcuts?: string[];
  version: string;
  adapter?: ComputerAppAdapter | null;
}

export interface ComputerAppAdapter {
  id: "wiii.chrome.v1" | "wiii.files.v1" | "wiii.terminal.v1" | "wiii.wechat.v1" | "wiii.wechat.v2" | "wiii.libreoffice.v1" | string;
  version: string;
  capabilities: string[];
}

export interface ComputerKnownNodeVersion {
  ref: string;
  version: string;
}

export interface ComputerSemanticObserveOptions {
  maxNodes?: number;
  scopeRef?: string | null;
  continuation?: string | null;
  sinceStateVersion?: string | null;
  knownNodeVersions?: ComputerKnownNodeVersion[];
  visualRef?: string | null;
}

export interface ComputerVisualPatch {
  ref: string;
  mimeType: "image/png" | "image/jpeg";
  width: number;
  height: number;
  sha256: string;
  data: string;
}

export interface ComputerAiFrame {
  version: "wiii-ai-frame.v1";
  scope: "workstation" | "browser" | "desktop";
  observationModel: "scene_graph";
  actionModel: "typed_refs";
  coordinates: "adapter_private";
  modalities: string[];
  interaction?: ComputerInteractionContext | null;
}

export interface ComputerInteractionContext {
  mode: "semantic_control" | "text_entry" | "document_navigation" | "canvas_keyboard";
  targetRef: string | null;
  inputActions: ComputerSemanticAction[];
  keymapSource: "none" | "declared" | "unknown";
  shortcuts: string[];
  feedback: "observe" | "semantic_delta" | "post_action_visual";
  clockMode?: "continuous" | "stepped";
  clockModes?: Array<"continuous" | "stepped">;
  clockWatchdogMs?: number | null;
}

export interface ComputerRealtimeClockResult {
  mode: "continuous" | "stepped";
  activeMs: number;
  watchdogMs: number;
  deadlineMs: number | null;
}

export interface ComputerSemanticSnapshot {
  protocolVersion: "neko-computer.semantic.v1";
  environmentId: string;
  stateVersion: string;
  capturedAt: string;
  platform: "linux_atspi";
  screen: { width: number; height: number };
  activeWindowRef: string | null;
  frame?: ComputerAiFrame | null;
  nodes: ComputerSemanticNode[];
  truncated: boolean;
  scopeRef: string | null;
  projection: "full" | "delta";
  nextContinuation: string | null;
  deltaFromStateVersion: string | null;
  removedRefs: string[];
  visualPatch?: ComputerVisualPatch | null;
}

export interface ComputerSemanticActResult {
  environmentId: string;
  outcome: "completed" | "rejected";
  code: string | null;
  detail: string;
  action: ComputerSemanticAction;
  targetRef: string;
  beforeStateVersion: string;
  afterStateVersion: string;
  verified: boolean;
  effect?: "confirmed" | "input_delivered" | "unverifiable" | "refused" | null;
  route?: string | null;
  evidence?: string[];
  escalation?: "observe" | "choose_supported_action" | "stop" | null;
  visualPatch?: ComputerVisualPatch | null;
  clock?: ComputerRealtimeClockResult | null;
  observation?: ComputerSemanticSnapshot | null;
}

export type WorkPlaneResourceType =
  | "project.root"
  | "project.file"
  | "spreadsheet.workbook"
  | string;

export interface WorkCapability {
  id: string;
  version: string;
  resourceTypes: WorkPlaneResourceType[];
  inputSchema: Record<string, unknown>;
  mutating: boolean;
  risk: "reversible_local_edit" | string;
  approval: "project_write_grant" | string;
  retry: "idempotency_key_and_revision" | string;
  reversible: boolean;
  maxInputBytes: number;
  evidence: string[];
}

export interface WorkResource {
  ref: string;
  resourceType: WorkPlaneResourceType;
  name: string;
  parentRef: string | null;
  revision: string;
  mediaType: string | null;
  capabilities: string[];
  source: "project" | string;
  metadata: Record<string, unknown>;
}

export interface WorkPlaneDescriptor {
  protocolVersion: "wiii-work-plane.preview.v1";
  sourceAuthority: "source_application";
  resourceModel: "typed_revisioned_resources";
  transactionModel: "optimistic_idempotent";
  root: WorkResource;
  capabilities: WorkCapability[];
}

export interface WorkPlaneQueryOptions {
  resourceRef: string;
  view: "children" | "content" | "spreadsheet";
  maxItems?: number;
  offset?: number;
  maxBytes?: number;
  sheet?: string | null;
  range?: string | null;
}

export interface WorkPlaneQueryResult {
  protocolVersion: "wiii-work-plane.preview.v1";
  resource: WorkResource;
  items: WorkResource[];
  data: Record<string, unknown>;
  truncated: boolean;
  nextOffset: number | null;
  evidence: string[];
}

export interface WorkPlaneTransactionInput {
  environmentId: string;
  projectId: string;
  capabilityId: string;
  capabilityVersion: string;
  targetRef: string;
  ifRevision: string;
  input: Record<string, unknown>;
}

export interface WorkChange {
  ref: string;
  kind: string;
  beforeRevision: string | null;
  afterRevision: string | null;
}

export interface WorkPlaneTransactionResult {
  protocolVersion: "wiii-work-plane.preview.v1";
  outcome: "completed" | "rejected";
  code: string | null;
  detail: string;
  capabilityId: string;
  targetRef: string;
  beforeRevision: string;
  afterRevision: string;
  changes: WorkChange[];
  evidence: string[];
  reversible: boolean;
  recovery: string | null;
}

export interface ComputerHistoryEntry {
  seq: number;
  at: string;
  environmentId: string;
  outcome: "completed" | "rejected";
  action: ComputerSemanticAction;
  targetRef: string;
  beforeStateVersion: string;
  afterStateVersion: string;
  verified: boolean;
  effect: string | null;
  route: string | null;
  evidence: string[];
  code: string | null;
}

export interface ComputerHistoryStatus {
  available: boolean;
  enabled: boolean;
  encrypted: boolean;
  cipher: "xchacha20-poly1305" | string;
  keyProtection: "windows-dpapi-current-user" | "app-private-file" | string;
  retentionDays: number;
  entryCount: number;
  lastError: string | null;
}

export interface ComputerHistoryPage {
  entries: ComputerHistoryEntry[];
  nextBeforeSeq: number | null;
  hasMore: boolean;
}

export type SignalKind =
  | "content_changed"
  | "state_changed"
  | "attention_required"
  | "conflict"
  | "approval_required";

export type SignalPriority = "low" | "normal" | "high" | "urgent";
export type SignalState =
  | "pending"
  | "claimed"
  | "deferred"
  | "resolved"
  | "expired"
  | "dead_letter";
export type SignalOutcome =
  | "handled"
  | "ignored"
  | "failed"
  | "revoked"
  | "unknown_external_outcome";

export interface SignalClaim {
  workerId: string;
  leaseId: string;
  expiresAt: string;
  attempt: number;
}

export interface SignalItem {
  signalId: string;
  sourceId: string;
  accountGrantRef: string;
  appId: string;
  resourceRef: string;
  kind: SignalKind;
  sourceCursor: string;
  observedAt: string;
  availableAt: string;
  expiresAt: string;
  priorityClass: SignalPriority;
  state: SignalState;
  claim: SignalClaim | null;
  contentAvailable: boolean;
  gapDetected: boolean;
  coalescedCount: number;
  lastOutcome: SignalOutcome | null;
}

export interface SignalCount {
  sourceId: string;
  state: SignalState;
  priorityClass: SignalPriority;
  count: number;
}

export interface SignalInboxSummary {
  protocolVersion: "wiii-signal-inbox.v1";
  encrypted: true;
  itemCount: number;
  readyCount: number;
  gapCount: number;
  counts: SignalCount[];
  pendingRefs: string[];
}

export interface ComputerDoctor {
  supported: boolean;
  runtimeReady: boolean;
  packageReady: boolean;
  dockerCli: boolean;
  daemonReady: boolean;
  imageReady: boolean;
  providerKind: ComputerProviderKind;
  isolationClass: ComputerIsolationClass;
  availableCpus: number | null;
  availableMemoryBytes: number | null;
  recommendedPreset: Exclude<ComputerResourcePreset, "auto">;
  packages: ComputerPackageStatus[];
  storage: ComputerStorageSummary;
  detail: string;
}

export type ComputerPackageState = "installed" | "not_installed";

export interface ComputerPackageStatus {
  packageId: string;
  displayName: string;
  description: string;
  state: ComputerPackageState;
  manifest: ComputerPackManifest;
  installedBytes: number | null;
  sharedAcrossProjects: boolean;
  preservesProfileOnRemove: boolean;
  capabilities: string[];
}

export interface ComputerPackManifest {
  schemaVersion: "wiii-computer-pack.v2";
  version: string;
  channel: "stable" | "preview";
  aiFrameVersion: "wiii-ai-frame.v1";
  profileSchemaVersion: number;
  upgradePolicy: "replace_shell_preserve_profile";
  rollbackPolicy: "automatic_shell_restore";
}

export interface ComputerStorageSummary {
  packageStoreKind: "runtime_managed_local";
  profileStoreKind: "durable_local";
  projectStoreKind: "host_source";
  locationSelectable: boolean;
}

export interface ComputerTerminalResult {
  environmentId: string;
  exitCode: number | null;
  stdout: string;
  stderr: string;
  truncated: boolean;
  replayedWithoutOutput: boolean;
}

export interface ComputerEvent {
  eventId: string;
  streamId: string;
  seq: number;
  at: string;
  type: string;
  environmentId: string;
  payload: Record<string, unknown>;
}

export interface ComputerReplayPage {
  streamId: string;
  events: ComputerEvent[];
  nextAfterSeq: number;
  hasMore: boolean;
}
