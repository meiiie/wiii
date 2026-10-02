/** Durable correlation between an explicit Wiii work item and one Neko task.
 * A saved receipt is never a permission grant or proof of a live process.
 * The factory must separately prove host membership, canonical root and generation.
 */
import type { NekoExecutionBinding } from "@/neko/control-client";
import { isAbsoluteWorkspacePath } from "./workspace";
import {
  NEKO_TASK_PROTOCOL,
  buildNekoTaskNewMeta,
  canonicalRootsEqual,
  validateNekoTaskReceipt,
  type NekoTaskReceipt,
} from "./drivers/acp/task-protocol";

export interface NekoTaskMappingHost {
  readonly threadId: string;
  readonly providerId: string;
  readonly projectId: string | null;
  readonly execution: NekoExecutionBinding | null;
  /** Selected path identity only; this can be an alias and is not native proof. */
  readonly workspacePath: string;
}

export type NekoTaskMappingRecoveryReason =
  | "unfinished-new" | "unfinished-load" | "new-response-uncertain"
  | "load-response-uncertain" | "receipt-persistence-failed"
  | "writer-unavailable" | "recovery-required" | "close-unconfirmed"
  | "unsupported-capability" | "admission-failed" | "process-ended";

interface MappingIdentity {
  readonly version: 1;
  readonly mode: "fixed-active-task";
  readonly threadId: string;
  readonly execution: Readonly<NekoExecutionBinding>;
  readonly projectId: string | null;
  readonly workspacePath: string;
  /** Provisional selected path in pending-new; proven canonical root after binding. */
  readonly authorizedRoot: string;
  readonly label: string;
}

export type NekoTaskScopeMapping = MappingIdentity & (
  | { readonly state: "pending-new"; readonly backendSessionId: null; readonly receipt: null }
  | { readonly state: "bound" | "pending-load"; readonly backendSessionId: string; readonly receipt: NekoTaskReceipt }
  | { readonly state: "recovery-required"; readonly backendSessionId: string | null;
      readonly receipt: NekoTaskReceipt | null; readonly reason: NekoTaskMappingRecoveryReason }
);

export interface InvalidNekoTaskMapping {
  readonly state: "invalid";
  readonly reason: "invalid-mapping" | "host-binding-mismatch";
  /** Retain a fully validated saved mapping for diagnosis; this never admits it. */
  readonly retained?: NekoTaskScopeMapping;
}

/** Invalid scoped metadata remains explicitly blocked when the next snapshot is saved. */
export type NekoTaskScopeState = NekoTaskScopeMapping | InvalidNekoTaskMapping;

export type NekoTaskMappingDecision =
  | { readonly kind: "legacy" }
  | { readonly kind: "scoped"; readonly mapping: NekoTaskScopeMapping }
  | { readonly kind: "blocked"; readonly mapping: InvalidNekoTaskMapping };

type MappingFailure = "invalid-host" | "invalid-mapping" | "invalid-transition"
  | "missing-root-proof" | "root-mismatch" | "task-mismatch" | "activation-mismatch";

export class NekoTaskMappingError extends Error {
  constructor(readonly reason: MappingFailure) {
    super(`Không thể xác minh liên kết tác vụ Neko (${reason}). Phiên chưa được phép tiếp tục.`);
    this.name = "NekoTaskMappingError";
  }
}

const RECOVERY_REASONS = new Set<NekoTaskMappingRecoveryReason>([
  "unfinished-new", "unfinished-load", "new-response-uncertain", "load-response-uncertain",
  "receipt-persistence-failed", "writer-unavailable", "recovery-required", "close-unconfirmed",
  "unsupported-capability", "admission-failed", "process-ended",
]);
const CONTROL = /[\u0000-\u001f\u007f]/;

function own(value: unknown, key: string): unknown {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return undefined;
  // Persisted JSON has no getters; never execute one in an in-process caller.
  return Object.getOwnPropertyDescriptor(value, key)?.value;
}

function text(value: unknown, maxBytes = 256): value is string {
  return typeof value === "string" && value.length > 0 && value.trim().length > 0
    && value.length <= maxBytes && !CONTROL.test(value)
    && new TextEncoder().encode(value).byteLength <= maxBytes;
}

function root(value: unknown): value is string {
  return text(value, 32768) && isAbsoluteWorkspacePath(value);
}

function execution(value: unknown): Readonly<NekoExecutionBinding> | null {
  const taskId = own(value, "taskId");
  const runId = own(value, "runId");
  const environmentId = own(value, "environmentId");
  return text(taskId) && text(runId) && text(environmentId)
    ? Object.freeze({ taskId, runId, environmentId }) : null;
}

function fail(reason: MappingFailure): never { throw new NekoTaskMappingError(reason); }

function identity(host: NekoTaskMappingHost, label: string): MappingIdentity {
  const binding = execution(host.execution);
  if (host.providerId !== "neko" || !text(host.threadId) || !binding
    || !(host.projectId === null || text(host.projectId)) || !root(host.workspacePath)) fail("invalid-host");
  buildNekoTaskNewMeta(label);
  return { version: 1, mode: NEKO_TASK_PROTOCOL.mode, threadId: host.threadId,
    execution: binding, projectId: host.projectId, workspacePath: host.workspacePath,
    authorizedRoot: host.workspacePath, label };
}

function blocked(reason: InvalidNekoTaskMapping["reason"], retained?: NekoTaskScopeMapping): NekoTaskMappingDecision {
  return Object.freeze({ kind: "blocked", mapping: Object.freeze({ state: "invalid", reason,
    ...(retained ? { retained } : {}) }) });
}

/** Only explicit ADE execution opts in. Provider alternatives and manual legacy stay unchanged. */
export function createPendingNekoTaskMapping(host: NekoTaskMappingHost, label: string): NekoTaskScopeMapping | undefined {
  if (host.providerId !== "neko" || host.execution === null || host.execution === undefined) return undefined;
  return Object.freeze({ ...identity(host, label), state: "pending-new", backendSessionId: null, receipt: null });
}

function readMapping(raw: unknown): NekoTaskScopeMapping {
  const state = own(raw, "state");
  const threadId = own(raw, "threadId");
  const binding = execution(own(raw, "execution"));
  const projectId = own(raw, "projectId");
  const workspacePath = own(raw, "workspacePath");
  const authorizedRoot = own(raw, "authorizedRoot");
  const label = own(raw, "label");
  if (own(raw, "version") !== 1 || own(raw, "mode") !== NEKO_TASK_PROTOCOL.mode
    || !text(threadId) || !binding || !(projectId === null || text(projectId))
    || !root(workspacePath) || !root(authorizedRoot) || !text(label)) fail("invalid-mapping");
  const base: MappingIdentity = { version: 1, mode: NEKO_TASK_PROTOCOL.mode,
    threadId, execution: binding, projectId, workspacePath, authorizedRoot, label };
  const backendSessionId = own(raw, "backendSessionId");
  const receiptRaw = own(raw, "receipt");
  if (state === "pending-new") {
    if (backendSessionId !== null || receiptRaw !== null
      || !canonicalRootsEqual(workspacePath, authorizedRoot)) fail("invalid-mapping");
    return Object.freeze({ ...base, state, backendSessionId: null, receipt: null });
  }
  if (state !== "bound" && state !== "pending-load" && state !== "recovery-required") fail("invalid-mapping");
  const reason = own(raw, "reason");
  if (state === "recovery-required"
    && (typeof reason !== "string" || !RECOVERY_REASONS.has(reason as NekoTaskMappingRecoveryReason))) fail("invalid-mapping");
  if (backendSessionId === null && receiptRaw === null && state === "recovery-required") {
    return Object.freeze({ ...base, state, backendSessionId: null, receipt: null,
      reason: reason as NekoTaskMappingRecoveryReason });
  }
  if (!text(backendSessionId)) fail("invalid-mapping");
  const receipt = validateNekoTaskReceipt(receiptRaw);
  if (!canonicalRootsEqual(receipt.root, authorizedRoot) || receipt.label !== label
    || receipt.id === backendSessionId || receipt.activationId === backendSessionId) fail("invalid-mapping");
  return state === "recovery-required"
    ? Object.freeze({ ...base, state, backendSessionId, receipt, reason: reason as NekoTaskMappingRecoveryReason })
    : Object.freeze({ ...base, state, backendSessionId, receipt });
}

/** Missing metadata is legacy. Present-but-malformed metadata can never become legacy. */
export function parseNekoTaskMapping(raw: unknown): NekoTaskMappingDecision {
  if (raw === undefined) return Object.freeze({ kind: "legacy" });
  if (own(raw, "state") === "invalid") {
    const reason = own(raw, "reason");
    const retainedRaw = own(raw, "retained");
    let retained: NekoTaskScopeMapping | undefined;
    if (retainedRaw !== undefined) {
      try { retained = readMapping(retainedRaw); } catch { /* marker remains blocked */ }
    }
    return blocked(reason === "host-binding-mismatch" ? reason : "invalid-mapping", retained);
  }
  try { return Object.freeze({ kind: "scoped", mapping: readMapping(raw) }); }
  catch { return blocked("invalid-mapping"); }
}

export function isNekoTaskScopeMapping(value: unknown): value is NekoTaskScopeMapping {
  return parseNekoTaskMapping(value).kind === "scoped";
}

export function isNekoTaskScopeState(value: unknown): value is NekoTaskScopeState {
  if (isNekoTaskScopeMapping(value)) return true;
  return own(value, "state") === "invalid"
    && ["invalid-mapping", "host-binding-mismatch"].includes(own(value, "reason") as string)
    && (own(value, "retained") === undefined || isNekoTaskScopeMapping(own(value, "retained")));
}

function sameHost(mapping: NekoTaskScopeMapping, host: NekoTaskMappingHost): boolean {
  const binding = execution(host.execution);
  return host.providerId === "neko" && mapping.threadId === host.threadId
    && mapping.projectId === host.projectId && binding !== null
    && mapping.execution.taskId === binding.taskId && mapping.execution.runId === binding.runId
    && mapping.execution.environmentId === binding.environmentId
    && root(host.workspacePath) && canonicalRootsEqual(mapping.workspacePath, host.workspacePath);
}

export function markNekoTaskRecovery(mapping: NekoTaskScopeMapping, reason: NekoTaskMappingRecoveryReason): NekoTaskScopeMapping {
  const safe = readMapping(mapping);
  if (!RECOVERY_REASONS.has(reason)) fail("invalid-transition");
  return Object.freeze({ ...safe, state: "recovery-required", reason });
}

/** Restore durable receipt facts only; a history read is not a load attempt.
 * The session store restores runtime=null. An explicit send must persist
 * beginNekoTaskLoad before startup and validate a fresh receipt before dispatch.
 * Interrupted durable new/load intents remain blocked, never auto-replayed.
 */
export function restoreNekoTaskMapping(raw: unknown, host: NekoTaskMappingHost): NekoTaskMappingDecision {
  const parsed = parseNekoTaskMapping(raw);
  if (parsed.kind !== "scoped") return parsed;
  if (!sameHost(parsed.mapping, host)) return blocked("host-binding-mismatch", parsed.mapping);
  const mapping = parsed.mapping;
  if (mapping.state === "bound") return parsed;
  if (mapping.state === "pending-new" || mapping.state === "pending-load") return Object.freeze({ kind: "scoped",
    mapping: markNekoTaskRecovery(mapping, mapping.state === "pending-new" ? "unfinished-new" : "unfinished-load") });
  return parsed;
}

/** Pure preparation only. Caller owns a strict write and one explicit load attempt. */
export function beginNekoTaskLoad(mapping: NekoTaskScopeMapping): NekoTaskScopeMapping {
  const safe = readMapping(mapping);
  if (safe.state !== "bound" && safe.state !== "pending-load") fail("invalid-transition");
  return Object.freeze({ ...safe, state: "pending-load" });
}

/** Called after native membership/root/generation checks and wire admission validation.
 * Binding is not durable until the caller's strict snapshot write completes.
 */
export function bindNekoTaskMapping(mapping: NekoTaskScopeMapping, receiptValue: NekoTaskReceipt,
  backendSessionId: string, authorizedCanonicalRoot?: string): NekoTaskScopeMapping {
  const safe = readMapping(mapping);
  const receipt = validateNekoTaskReceipt(receiptValue);
  if (!text(backendSessionId) || backendSessionId === receipt.id || backendSessionId === receipt.activationId) fail("invalid-mapping");
  if (safe.state !== "pending-new" && safe.state !== "pending-load" && safe.state !== "bound") fail("invalid-transition");
  if (safe.state === "pending-new" && authorizedCanonicalRoot === undefined) fail("missing-root-proof");
  const provenRoot = authorizedCanonicalRoot ?? safe.authorizedRoot;
  if (!root(provenRoot) || !canonicalRootsEqual(receipt.root, provenRoot)) fail("root-mismatch");
  if (receipt.label !== safe.label) fail("task-mismatch");
  if (safe.state === "pending-new") {
    if (receipt.activationEpoch !== 1) fail("activation-mismatch");
  } else {
    if (backendSessionId !== safe.backendSessionId || receipt.id !== safe.receipt.id
      || !canonicalRootsEqual(provenRoot, safe.authorizedRoot)
      || !canonicalRootsEqual(receipt.root, safe.receipt.root)) fail("task-mismatch");
    if (safe.state === "bound") {
      if (receipt.activationEpoch !== safe.receipt.activationEpoch
        || receipt.activationId !== safe.receipt.activationId) fail("activation-mismatch");
    } else if (safe.receipt.activationEpoch === Number.MAX_SAFE_INTEGER
      || receipt.activationEpoch !== safe.receipt.activationEpoch + 1
      || receipt.activationId === safe.receipt.activationId) fail("activation-mismatch");
  }
  return Object.freeze({ ...safe, state: "bound", authorizedRoot: provenRoot, backendSessionId, receipt });
}
