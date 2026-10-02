/** Passive display codec only. No execution-v1 opt-in, grants, echoes or recovery.
 * Stable subset: neko-core ba27a32/25d9a49 ACP-EXECUTION-BINDING-V1.md.
 * Unknown extensions (including interaction/capability lists) are not projected.
 */
import type { NekoExecutionProjection } from "../types";
import { canonicalRootsEqual, type NekoTaskReceipt } from "./task-protocol";

function own(value: unknown, key: string): unknown {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return undefined;
  return Object.getOwnPropertyDescriptor(value, key)?.value;
}
function text(value: unknown, limit: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= limit
    && !/[\u0000-\u001f\u007f]/.test(value)
    && new TextEncoder().encode(value).byteLength <= limit;
}
const unknown = Object.freeze({ status: "unknown" } as const);
const unsupported = Object.freeze({ status: "unsupported" } as const);
const unverified = Object.freeze({ status: "unverified" } as const);

/** Call only after the existing task/session/generation admission guard. */
export function projectNekoExecutionReceipt(
  envelope: unknown, task: NekoTaskReceipt, advertised: unknown,
): NekoExecutionProjection {
  const value = own(own(envelope, "_meta"), "neko.execution");
  if (value === undefined) return unknown;
  if (advertised === undefined) return unverified;
  if (own(advertised, "version") !== 1 || own(value, "version") !== 1) return unsupported;
  const taskId = own(value, "taskId");
  const root = own(value, "root");
  const activationId = own(value, "activationId");
  const activationEpoch = own(value, "activationEpoch");
  if (!text(taskId, 256) || !text(root, 32768) || !text(activationId, 256)
    || !Number.isSafeInteger(activationEpoch) || (activationEpoch as number) < 1
    || taskId !== task.id || !canonicalRootsEqual(root, task.root)
    || activationId !== task.activationId || activationEpoch !== task.activationEpoch) return unverified;
  const bashTarget = own(value, "bashTarget");
  const bashExecutor = own(value, "bashExecutor");
  const approval = own(value, "approval");
  const approvalMode = own(approval, "mode");
  const yolo = own(approval, "yolo");
  if ((bashTarget !== "host" && bashTarget !== "sandbox")
    || (bashExecutor !== "local-process" && bashExecutor !== "native-backend")
    || (approvalMode !== "default" && approvalMode !== "accept-edits" && approvalMode !== "plan" && approvalMode !== "auto")) return unsupported;
  if (typeof yolo !== "boolean" || (yolo && approvalMode !== "auto")
    || own(value, "confinement") !== (bashTarget === "host" ? "none" : "required-not-attested")
    || own(value, "osAuthority") !== "not-attested") return unverified;
  // Digests are opaque. They are neither decoded nor displayed as grants.
  const authorityId = own(value, "authorityId");
  const policyId = own(value, "policyId");
  if (!(authorityId === null || (typeof authorityId === "string" && /^[a-f0-9]{64}$/i.test(authorityId)))
    || typeof policyId !== "string" || !/^[a-f0-9]{64}$/i.test(policyId)) return unverified;
  const backend = own(value, "nativeBackend");
  let nativeBackendSandbox: "backend-enforced" | "unsupported" | null = null;
  if (backend !== null) {
    const sandbox = own(backend, "bashSandbox");
    if (own(backend, "protocol") !== "neko-native-posix-v1"
      || (sandbox !== "backend-enforced" && sandbox !== "unsupported")) return unsupported;
    if (!text(own(backend, "root"), 32768)) return unverified;
    nativeBackendSandbox = sandbox;
  } else if (bashExecutor === "native-backend") return unverified;
  // Local Bash may coexist with a backend for other tools. Backend root is a
  // separate machine/path assertion and must not be forced equal to task root.
  return Object.freeze({ status: "reported", version: 1, taskId, root,
    activationEpoch: activationEpoch as number, activationId,
    bashTarget, bashExecutor, approvalMode, yolo, nativeBackendSandbox });
}

export function executionCapability(initializeResult: unknown): unknown {
  return own(own(initializeResult, "_meta"), "neko.executionProtocol");
}
