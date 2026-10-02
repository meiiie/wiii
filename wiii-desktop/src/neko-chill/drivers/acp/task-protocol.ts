/** Pure codec for Neko's opt-in ACP task protocol v1.
 * Contract: neko-core docs/process/ACP-TASK-PROTOCOL-V1.md at 72908bb3949c61811cfd1996ab9e69f1fdd8bd90.
 * Host grants, effective-root canonicalization, work-item mapping and process
 * generation checks belong to the caller; a receipt is correlation data only.
 */
export const NEKO_TASK_PROTOCOL = Object.freeze({ version: 1, mode: "fixed-active-task" } as const);

export interface NekoTaskReceipt {
  readonly version: 1;
  readonly mode: "fixed-active-task";
  readonly id: string;
  readonly label: string;
  readonly root: string;
  readonly activationEpoch: number;
  readonly activationId: string;
}

export interface NekoTaskAdmission {
  readonly sessionId: string;
  readonly receipt: NekoTaskReceipt;
}

export interface NekoTaskRecovery {
  readonly version: 1;
  readonly kind: "writer_unavailable" | "recovery_required";
  readonly action: "retain_mapping_and_request_recovery";
}

export type NekoTaskProtocolFailure =
  | "missing-capability" | "unsupported-capability" | "invalid-label"
  | "missing-receipt" | "invalid-receipt" | "invalid-session-id"
  | "root-mismatch" | "task-mismatch" | "label-mismatch"
  | "activation-mismatch" | "session-mismatch" | "identity-collision";

/** Static text only: never put an untrusted root, label or wire payload in UI errors. */
export class NekoTaskProtocolError extends Error {
  constructor(readonly reason: NekoTaskProtocolFailure) {
    super(`Không thể xác minh phạm vi tác vụ Neko (${reason}). Phiên chưa được cho phép tiếp tục.`);
    this.name = "NekoTaskProtocolError";
  }
}

const MAX_ID_BYTES = 256;
// Match Neko's label admission bound; UTF-8 bytes matter for Vietnamese/CJK.
const MAX_LABEL_BYTES = 256;
// Local transport bound, not a filesystem grant or a platform path-length claim.
const MAX_ROOT_BYTES = 32768;
const CONTROL = /[\u0000-\u001f\u007f]/;

function object(value: unknown): object | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value : undefined;
}

function own(value: unknown, key: string): unknown {
  const record = object(value);
  // Wire JSON has no accessors. Do not execute getters supplied by other callers.
  return record ? Object.getOwnPropertyDescriptor(record, key)?.value : undefined;
}

function validText(value: unknown, maxBytes: number): value is string {
  return typeof value === "string" && value.length > 0 && value.trim().length > 0
    && value.length <= maxBytes && !CONTROL.test(value)
    && new TextEncoder().encode(value).byteLength <= maxBytes;
}

function epoch(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function fail(reason: NekoTaskProtocolFailure): never { throw new NekoTaskProtocolError(reason); }

function withoutWindowsVerbatimPrefix(root: string): string {
  if (/^\\\\\?\\UNC\\/i.test(root)) return "\\\\" + root.slice(8);
  return /^\\\\\?\\/.test(root) ? root.slice(4) : root;
}

function looksLikeCanonicalWindowsRoot(root: string): boolean {
  const plain = withoutWindowsVerbatimPrefix(root);
  return /^[a-z]:[\\/]/i.test(plain) || /^\\\\[^\\/]+[\\/][^\\/]+/.test(plain);
}

/** Compare identities of roots ALREADY canonicalized by the native host/runtime.
 * This performs no filesystem lookup and proves neither membership nor authority.
 * Neko realpathSync.native lowercases Windows roots; host canonicalization may
 * preserve case or a verbatim prefix. POSIX case and separators stay unchanged.
 */
export function canonicalRootIdentity(root: string, platform?: "windows" | "posix"): string {
  const windows = platform === "windows" || (platform === undefined && looksLikeCanonicalWindowsRoot(root));
  if (!windows) return root;
  const plain = withoutWindowsVerbatimPrefix(root).replaceAll("/", "\\");
  if (!looksLikeCanonicalWindowsRoot(plain)) return root;
  const folded = plain.toLowerCase();
  // Keep an absolute drive root absolute; `C:` is a relative path on Windows.
  if (/^[a-z]:\\+$/.test(folded)) return folded.slice(0, 2) + "\\";
  return folded.replace(/\\+$/, "");
}

export function canonicalRootsEqual(root: string, authorizedRoot: string): boolean {
  const platform = looksLikeCanonicalWindowsRoot(authorizedRoot) ? "windows" : "posix";
  return canonicalRootIdentity(root, platform) === canonicalRootIdentity(authorizedRoot, platform);
}

function receiptValue(value: unknown): NekoTaskReceipt {
  if (value === undefined) fail("missing-receipt");
  const id = own(value, "id");
  const label = own(value, "label");
  const root = own(value, "root");
  const activationEpoch = own(value, "activationEpoch");
  const activationId = own(value, "activationId");
  if (own(value, "version") !== 1 || own(value, "mode") !== NEKO_TASK_PROTOCOL.mode
    || !validText(id, MAX_ID_BYTES) || !validText(label, MAX_LABEL_BYTES)
    || !validText(root, MAX_ROOT_BYTES) || !epoch(activationEpoch)
    || !validText(activationId, MAX_ID_BYTES)) fail("invalid-receipt");
  if (id === activationId) fail("identity-collision");
  // Extra extension fields are ignored. Only supported fields enter the mapping.
  return Object.freeze({ version: 1, mode: NEKO_TASK_PROTOCOL.mode,
    id, label, root, activationEpoch, activationId });
}

export function parseNekoTaskReceipt(envelope: unknown): NekoTaskReceipt {
  return receiptValue(own(own(envelope, "_meta"), "neko.task"));
}

/** Validate a persisted receipt without inferring a legacy fallback on failure. */
export function validateNekoTaskReceipt(value: unknown): NekoTaskReceipt {
  return receiptValue(value);
}

export function assertNekoTaskCapability(initializeResult: unknown): typeof NEKO_TASK_PROTOCOL {
  const capability = own(own(initializeResult, "_meta"), "neko.taskProtocol");
  if (capability === undefined) fail("missing-capability");
  if (own(initializeResult, "protocolVersion") !== 1 || own(capability, "version") !== 1
    || own(capability, "mode") !== NEKO_TASK_PROTOCOL.mode) fail("unsupported-capability");
  return NEKO_TASK_PROTOCOL;
}

export function buildNekoTaskNewMeta(label: string) {
  if (!validText(label, MAX_LABEL_BYTES)) fail("invalid-label");
  return { "neko.taskProtocol": NEKO_TASK_PROTOCOL, "neko.taskLabel": label };
}

export function buildNekoTaskLoadMeta(receipt: NekoTaskReceipt) {
  const saved = receiptValue(receipt);
  return { "neko.taskProtocol": NEKO_TASK_PROTOCOL, "neko.taskExpected": {
    id: saved.id, root: saved.root,
    activationEpoch: saved.activationEpoch, activationId: saved.activationId,
  } };
}

export function buildNekoTaskEchoMeta(receipt: NekoTaskReceipt) {
  const current = receiptValue(receipt);
  return { "neko.task": { version: 1 as const, id: current.id,
    activationEpoch: current.activationEpoch, activationId: current.activationId } };
}

function sessionIdFrom(envelope: unknown, receipt: NekoTaskReceipt): string {
  const sessionId = own(envelope, "sessionId");
  if (!validText(sessionId, MAX_ID_BYTES)) fail("invalid-session-id");
  if (sessionId === receipt.id || sessionId === receipt.activationId) fail("identity-collision");
  return sessionId;
}

function assertRoot(receipt: NekoTaskReceipt, authorizedRoot: string): void {
  if (!validText(authorizedRoot, MAX_ROOT_BYTES) || !canonicalRootsEqual(receipt.root, authorizedRoot)) fail("root-mismatch");
}

export function validateNekoTaskNewReceipt(result: unknown, expected: {
  readonly authorizedRoot: string;
  readonly label: string;
}): NekoTaskAdmission {
  const receipt = parseNekoTaskReceipt(result);
  const sessionId = sessionIdFrom(result, receipt);
  assertRoot(receipt, expected.authorizedRoot);
  if (receipt.label !== expected.label) fail("label-mismatch");
  if (receipt.activationEpoch !== 1) fail("activation-mismatch");
  return Object.freeze({ sessionId, receipt });
}

/** Validates one response; does not perform or schedule any retry. */
export function validateNekoTaskLoadReceipt(result: unknown, expected: {
  readonly sessionId: string;
  readonly authorizedRoot: string;
  readonly expected: NekoTaskReceipt;
  readonly allowPriorReceiptRetry?: boolean;
}): NekoTaskAdmission {
  const saved = receiptValue(expected.expected);
  const receipt = parseNekoTaskReceipt(result);
  // ACP load/resume results need not repeat the requested sessionId. Bind the
  // already selected coordinator when absent; an explicit response ID must
  // still be valid and match. An own accessor/undefined value is not absence.
  const response = object(result);
  const suppliedId = response ? Object.getOwnPropertyDescriptor(response, "sessionId") : undefined;
  const sessionId = sessionIdFrom(suppliedId === undefined ? { sessionId: expected.sessionId } : result, receipt);
  if (!validText(expected.sessionId, MAX_ID_BYTES) || sessionId !== expected.sessionId) fail("session-mismatch");
  assertRoot(saved, expected.authorizedRoot);
  assertRoot(receipt, expected.authorizedRoot);
  if (receipt.id !== saved.id) fail("task-mismatch");
  if (receipt.label !== saved.label) fail("label-mismatch");
  const recovery = own(own(result, "_meta"), "neko.taskRecovery");
  const priorRetry = expected.allowPriorReceiptRetry === true
    && own(recovery, "version") === 1 && own(recovery, "kind") === "prior_receipt_retry";
  const increment = priorRetry ? 2 : 1;
  if (saved.activationEpoch > Number.MAX_SAFE_INTEGER - increment
    || receipt.activationEpoch !== saved.activationEpoch + increment
    || receipt.activationId === saved.activationId) fail("activation-mismatch");
  // A returned recovery marker is not an implicit client authorization to retry.
  if (recovery !== undefined && !priorRetry) fail("activation-mismatch");
  return Object.freeze({ sessionId, receipt });
}

/** For prompt/close responses, whose normal ACP shape does not include sessionId. */
export function assertNekoTaskCurrentReceipt(envelope: unknown, expected: NekoTaskReceipt): NekoTaskReceipt {
  const current = receiptValue(expected);
  const receipt = parseNekoTaskReceipt(envelope);
  if (!canonicalRootsEqual(receipt.root, current.root)) fail("root-mismatch");
  if (receipt.id !== current.id) fail("task-mismatch");
  if (receipt.label !== current.label) fail("label-mismatch");
  if (receipt.activationEpoch !== current.activationEpoch || receipt.activationId !== current.activationId) fail("activation-mismatch");
  return receipt;
}

/** Caller must additionally verify its native process generation before projection. */
export function assertNekoTaskEventBinding(params: unknown, expectedSessionId: string,
  expected: NekoTaskReceipt): NekoTaskReceipt {
  const receipt = assertNekoTaskCurrentReceipt(params, expected);
  const sessionId = sessionIdFrom(params, receipt);
  if (!validText(expectedSessionId, MAX_ID_BYTES) || sessionId !== expectedSessionId) fail("session-mismatch");
  return receipt;
}

/** Use raw JSON-RPC error data BEFORE diagnostic redaction; retain only this typed subset.
 * Unknown/malformed RPC errors return undefined and must keep the normal fault path.
 */
export function parseNekoTaskRecoveryError(code: unknown, rawData: unknown): NekoTaskRecovery | undefined {
  if (code !== -32002) return undefined;
  const value = own(rawData, "neko.taskError");
  const kind = own(value, "kind");
  if (own(value, "version") !== 1 || (kind !== "writer_unavailable" && kind !== "recovery_required")
    || own(value, "action") !== "retain_mapping_and_request_recovery") return undefined;
  return Object.freeze({ version: 1, kind, action: "retain_mapping_and_request_recovery" });
}

/** Match Neko's case-sensitive leading /task command grammar; never inspect prose. */
export function classifyFixedTaskCommand(text: string, fixedLane: boolean): "new" | "use" | undefined {
  if (!fixedLane) return undefined;
  const match = /^\/task\s+(new|use)(?:\s|$)/.exec(text.trim());
  return match ? match[1] as "new" | "use" : undefined;
}
