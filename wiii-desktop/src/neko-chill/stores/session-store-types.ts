/** Shared session contracts and Immer-aware action access; no runtime state. */
import type { ContentBlock } from "@/api/types";
import type { WorkspaceRef } from "../workspace";
import type { AgentLaunchProfile, DetectedAgent } from "./neko-agent-store";
import type { NekoTopLevelSessionKind } from "@/neko/session-ownership";
import type { NekoExecutionBinding, NekoControlClient } from "@/neko/control-client";
import type { NekoTaskScopeState } from "../task-scope-mapping";
import type { NekoExecutionProjection, DriverConfigOption, DriverCommand, PermissionRequest, DriverEvent, Driver } from "../drivers/types";
import type { NekoSessionEvent } from "../session-events";
import type { RuntimeProviderSnapshot } from "../runtime-manager";
import type { DriverLaunchConfig } from "../drivers/factory";
import type { NekoProviderSessionRecord } from "@/neko/contracts";
import type { Mutate, StoreApi } from "zustand";
import type { } from "zustand/middleware/immer";
export interface NekoMessage {
  id: string;
  role: "user" | "assistant";
  /** Plain text for user messages. */
  text?: string;
  /** Streamed blocks for assistant messages (ContentBlock vocabulary). */
  blocks?: ContentBlock[];
}
export type NekoSessionStatus = "connecting" | "stopping" | "dispatching" | "idle" | "streaming" | "exited" | "error";
export interface NekoSession {
  id: string;
  agentId: string;
  agentName: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  /** Exact ACP cwd. Legacy v1 sessions hydrate with null until attached. */
  workspace: WorkspaceRef | null;
  /** Neko's config-first launch choice; null for other agents/default launch. */
  launchProfile: AgentLaunchProfile | null;
  /** Top-level Neko identity. Missing values hydrate as worker/scratch for rollback compatibility. */
  kind?: NekoTopLevelSessionKind;
  /** Explicit Neko Project facet. Null keeps manual/imported legacy sessions unassigned. */
  projectId?: string | null;
  /** Wiii work identity; null means this is a manual/legacy Neko session. */
  execution?: NekoExecutionBinding | null;
  /** Provider-owned durable ACP id; independent from Wiii's local session id. */
  backendSessionId: string | null;
  /** Durable task correlation; never live authority or a second memory layer. */
  taskScope?: NekoTaskScopeState;
  /** Ephemeral current-generation display only; deliberately omitted from persistence. */
  executionProjection?: {
    providerInstanceId: string;
    value: NekoExecutionProjection;
  };
  /** Last complete capability snapshot reported by the live driver. */
  controls: DriverConfigOption[];
  commands: DriverCommand[];
  pendingControlId: string | null;
  /** Last user/agent activity — drives the 30-minute idle reap (T601). */
  lastActivityAt: number;
  status: NekoSessionStatus;
  messages: NekoMessage[];
  /** Durable, append-only facts at Wiii's model/runtime boundary. */
  events: NekoSessionEvent[];
  /** Highest sequence ever allocated, including rolled-back staged facts. */
  eventHighWaterMark: number;
  /** Current provider identity; null for a restored or stopped session. */
  runtime: RuntimeProviderSnapshot | null;
  /** Set while the agent waits on an approval (FR-006); UI must resolve it. */
  pendingPermission: PermissionRequest | null;
  /** Prevents two UI decisions from racing across the durability barrier. */
  resolvingPermissionId: string | null;
  /** True while a cancel command crosses its durability barrier. */
  cancelPending: boolean;
  /** Lifecycle lock held through runtime teardown and terminal persistence. */
  closePending: boolean;
  /** Lifecycle lock held from delete intent through durable deletion. */
  deletePending: boolean;
  /** Honest error text for the banner when status is error/exited. */
  statusDetail?: string;
}
/** Injected so tests can fake the driver without Tauri (vi.mock factory). */
export type DriverFactory = (agent: DetectedAgent, sessionId: string, launch: DriverLaunchConfig, onEvent: (event: DriverEvent) => void, ownDriver: (driver: Driver) => void) => Promise<Driver>;
export type NativeControlReader = Pick<NekoControlClient, "listSessions" | "readEvents" | "unresolvedStartSessionIds" | "reconcilableStartSessionIds" | "cancelUnresolvedStarts">;
export interface NekoSessionState {
  sessions: Record<string, NekoSession>;
  activeSessionId: string | null;
  hydrated: boolean;
  hydrating: boolean;
  hydrationError: string | null;
  /** Load persisted sessions from local storage (T502, FR-008). */
  hydrate: () => Promise<void>;
  createSession: (agent: DetectedAgent, workspace: WorkspaceRef, launchProfile?: AgentLaunchProfile | null, options?: {
    execution?: NekoExecutionBinding;
    projectId?: string | null;
    title?: string;
  }) => Promise<string>;
  /** Wrap a provider-owned conversation without copying or claiming its history. */
  importProviderSession: (providerSession: NekoProviderSessionRecord, agent: DetectedAgent, workspace: WorkspaceRef) => Promise<string>;
  /** One-time migration path for a legacy transcript with no workspace. */
  attachWorkspace: (sessionId: string, workspace: WorkspaceRef) => Promise<void>;
  sendPrompt: (text: string, onAccepted?: () => void) => Promise<void>;
  sendPromptToSession: (sessionId: string, text: string, onAccepted?: () => void, stillAuthorized?: () => boolean) => Promise<void>;
  cancelTurn: () => Promise<void>;
  resolvePermission: (optionId: string | null) => Promise<void>;
  setConfigOption: (optionId: string, value: string | boolean) => Promise<void>;
  /** End the live agent process but KEEP the transcript (persisted). */
  closeSession: (sessionId: string) => Promise<void>;
  /** Remove a session from state AND local storage. */
  deleteSession: (sessionId: string) => Promise<void>;
  setActiveSession: (sessionId: string | null) => void;
  /** DriverEvent intake — exported on the store for direct unit testing. */
  handleEvent: (event: DriverEvent) => void;
}
export type SessionStoreApi = Mutate<StoreApi<NekoSessionState>, [
  [
    "zustand/immer",
    never
  ]
]>;
export type SessionSet = SessionStoreApi["setState"];
export type SessionGet = SessionStoreApi["getState"];
