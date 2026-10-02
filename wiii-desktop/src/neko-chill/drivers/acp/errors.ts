import { parseNekoTaskRecoveryError, type NekoTaskRecovery } from "./task-protocol";
import type { DriverDiagnosticData, DriverErrorDiagnostic } from "../types";

const MAX_INPUT = 4096;
const MAX_TEXT = 256;
const MAX_DATA = 2048;
const REDACTED = "Chi tiết nhạy cảm đã được ẩn.";
const OMITTED = "Chi tiết không an toàn hoặc quá dài đã được ẩn.";
const SENSITIVE = /authorization|cookie|password|passwd|secret|credential|api[\s_-]?key|access[\s_-]?token|refresh[\s_-]?token|\bbearer\b|\btoken\b|(?:sk-|gh[pousr]_|AIza|AKIA|eyJ)[A-Za-z0-9_-]{8,}|[A-Za-z0-9_+\/-]{40,}/i;
const PAYLOAD = /[{}]|(?:headers|request|response|body|prompt|messages)\s*["']?\s*[:=]/i;

/** Conservative diagnostic projection, never a raw provider payload or log. */
export function safeDiagnosticText(value: unknown, limit = MAX_TEXT): string {
  if (typeof value !== "string") return "";
  if (value.length > MAX_INPUT) return OMITTED;
  // Inspect before truncating: credentials beyond the visible limit must not leak.
  if (SENSITIVE.test(value)) return REDACTED;
  if (PAYLOAD.test(value)) return OMITTED;
  const text = value
    .replace(/\b[a-z][a-z0-9+.-]*:\/\/[^\s<>"']+/gi, "[địa chỉ đã ẩn]")
    .replace(/\bwww\.[^\s<>"']+/gi, "[địa chỉ đã ẩn]")
    .replace(/[^\s<>"'()[\]{}]+@[^\s<>"'()[\]{}]+\.[^\s<>"'()[\]{}]+/g, "[địa chỉ email đã ẩn]")
    .replace(/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g, " ")
    .replace(/\s+/g, " ").trim();
  const points = Array.from(text);
  return points.length > limit ? points.slice(0, limit).join("") + "…" : text;
}

function ownValue(object: object, key: string): unknown {
  // JSON is data, but tests/callers must not accidentally execute getters.
  return Object.getOwnPropertyDescriptor(object, key)?.value;
}

export function projectDiagnosticData(input: unknown): DriverDiagnosticData | undefined {
  let budget = 768;
  const project = (value: unknown, depth: number): DriverDiagnosticData | undefined => {
    if (!value || typeof value !== "object" || Array.isArray(value) || depth > 2) return undefined;
    const output: DriverDiagnosticData = Object.create(null);
    for (const key of ["code", "type", "kind", "status", "statusCode", "retryable", "reason", "error", "details"]) {
      const child = ownValue(value, key);
      if (typeof child === "number" && Number.isSafeInteger(child)) output[key] = child;
      else if (typeof child === "boolean") output[key] = child;
      else if (typeof child === "string" && budget > 0) {
        const safe = safeDiagnosticText(child, Math.min(key === "details" ? 384 : 128, budget));
        if (safe) { output[key] = safe; budget -= Array.from(safe).length; }
      } else if (key === "error" && depth < 2) {
        const nested = project(child, depth + 1);
        if (nested) output[key] = nested;
      }
    }
    return Object.keys(output).length ? output : undefined;
  };
  const data = project(input, 0);
  return data && JSON.stringify(data).length <= MAX_DATA ? data : undefined;
}

function detailText(data?: DriverDiagnosticData): string {
  if (typeof data?.details === "string") return data.details;
  if (typeof data?.reason === "string") return data.reason;
  if (data?.error && typeof data.error === "object") return detailText(data.error);
  return "";
}

const RPC_LABELS: Record<number, string> = {
  [-32700]: "Agent không đọc được yêu cầu RPC",
  [-32600]: "Agent báo yêu cầu RPC không hợp lệ",
  [-32601]: "Agent không hỗ trợ thao tác này",
  [-32602]: "Agent báo tham số không hợp lệ",
  [-32603]: "Agent gặp lỗi nội bộ",
};

/** An agent RESPONSE error. A rejected permission is a normal result, never this type. */
export class AcpRpcError extends Error {
  readonly kind = "rpc";
  readonly code: number | null;
  readonly data: DriverDiagnosticData | undefined;
  readonly dataPresent: boolean;
  readonly method: string;
  readonly taskRecovery: NekoTaskRecovery | undefined;

  constructor(readonly requestId: number, method: string, error: { code?: unknown; message?: unknown; data?: unknown }) {
    const code = Number.isSafeInteger(error.code) ? error.code as number : null;
    const data = projectDiagnosticData(error.data);
    const remote = safeDiagnosticText(error.message);
    const details = detailText(data);
    const label = code !== null ? RPC_LABELS[code] ?? "Agent báo lỗi RPC" : "Agent báo lỗi RPC";
    const codeLabel = code === null ? "" : ` (${code})`;
    const remoteLabel = remote && remote !== "Internal error" ? `: ${remote}` : ".";
    super(`${label}${codeLabel}${remoteLabel}${details ? ` Chi tiết: ${details}` : ""}`);
    this.name = "AcpRpcError";
    this.code = code;
    // Read only the versioned bounded subset before diagnostic redaction.
    this.taskRecovery = parseNekoTaskRecoveryError(code, error.data);
    this.data = data;
    this.dataPresent = error.data !== undefined;
    this.method = safeDiagnosticText(method, 128);
  }
}

export class AcpTransportError extends Error {
  readonly kind = "transport";
  readonly method: string;
  constructor(readonly reason: "send" | "exit" | "timeout" | "disposed", method: string, readonly requestId: number | null, message: unknown) {
    super(safeDiagnosticText(message) || "Không thể liên lạc với agent.");
    this.name = "AcpTransportError";
    this.method = safeDiagnosticText(method, 128);
  }
}

export class AcpProtocolError extends Error {
  readonly kind = "protocol";
  readonly method: string;
  constructor(readonly requestId: number, method: string) {
    super("Agent trả phản hồi RPC không hợp lệ.");
    this.name = "AcpProtocolError";
    this.method = safeDiagnosticText(method, 128);
  }
}

/** The store renders errors as Markdown; diagnostics must remain inert text. */
export function projectAcpFailure(error: unknown): { message: string; diagnostic?: DriverErrorDiagnostic } {
  const raw = error instanceof Error ? error.message : safeDiagnosticText(error);
  const message = (safeDiagnosticText(raw, 800) || "Agent gặp lỗi chưa xác định.")
    .replace(/[\\`*_[\]<>!|]/g, "\\$&");
  if (!(error instanceof AcpRpcError || error instanceof AcpTransportError || error instanceof AcpProtocolError)) return { message };
  return {
    message,
    diagnostic: {
      category: error.kind === "rpc" ? "rpc-response" : error.kind,
      operation: error.method,
      ...(error.requestId !== null ? { requestId: error.requestId } : {}),
      ...(error instanceof AcpRpcError ? { code: error.code, dataPresent: error.dataPresent, ...(error.data ? { data: error.data } : {}) } : {}),
      ...(error instanceof AcpTransportError ? { reason: error.reason } : {}),
    },
  };
}
