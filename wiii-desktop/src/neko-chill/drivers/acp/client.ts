/**
 * ACP JSON-RPC 2.0 correlation layer (T202) — protocol plumbing only.
 *
 * Sits on a line-oriented transport (the Tauri `neko_agent` commands in
 * production, a fake in tests) and correlates requests/responses in both
 * directions. Protocol SEMANTICS (methods, payload mapping) live in
 * `driver.ts`; this file never inspects params.
 */

import type { AcpTransport } from "@/neko/acp-transport";
import { AcpProtocolError, AcpRpcError, AcpTransportError, safeDiagnosticText } from "./errors";

export type { AcpTransport } from "@/neko/acp-transport";

export interface JsonRpcClientHandlers {
  /**
   * Agent→client REQUEST (e.g. session/request_permission). The resolved
   * value is sent back as the JSON-RPC result; a rejection becomes a
   * JSON-RPC error response (fail-closed for unsupported methods).
   */
  onAgentRequest(method: string, params: unknown): Promise<unknown>;
  /** Agent→client NOTIFICATION (e.g. session/update). */
  onNotification(method: string, params: unknown): void;
  /** Malformed frame or transport-level protocol violation. */
  onProtocolError(message: string): void;
}

interface PendingRequest {
  method: string;
  resolve: (result: unknown) => void;
  reject: (error: Error) => void;
  timeout?: ReturnType<typeof setTimeout>;
}

type JsonRpcId = number | string;

const METHOD_NOT_FOUND = -32601;
const INTERNAL_ERROR = -32603;

export class AcpJsonRpcClient {
  private nextId = 1;
  private readonly pending = new Map<number, PendingRequest>();
  private disposed = false;

  constructor(
    private readonly transport: AcpTransport,
    private readonly handlers: JsonRpcClientHandlers,
  ) {
    transport.onLine((line) => this.handleLine(line));
    transport.onExit(() => this.failAllPending("exit", "agent process exited"));
  }

  /** Send a client→agent request and await its result. */
  request(method: string, params: unknown, timeoutMs?: number): Promise<unknown> {
    if (this.disposed) return Promise.reject(new AcpTransportError("disposed", method, null, "client disposed"));
    const id = this.nextId++;
    const frame = JSON.stringify({ jsonrpc: "2.0", id, method, params });
    return new Promise((resolve, reject) => {
      const timeout = timeoutMs === undefined
        ? undefined
        : setTimeout(() => {
            if (!this.pending.delete(id)) return;
            reject(new AcpTransportError("timeout", method, id, `${method} timed out`));
          }, timeoutMs);
      this.pending.set(id, { method, resolve, reject, timeout });
      this.transport.send(frame).catch((err: unknown) => {
        const entry = this.pending.get(id);
        if (entry?.timeout) clearTimeout(entry.timeout);
        this.pending.delete(id);
        reject(new AcpTransportError("send", method, id, err instanceof Error ? err.message : err));
      });
    });
  }

  /** Send a client→agent notification (no response expected). */
  async notify(method: string, params: unknown): Promise<void> {
    if (this.disposed) return;
    await this.transport.send(JSON.stringify({ jsonrpc: "2.0", method, params }));
  }

  async dispose(): Promise<void> {
    this.disposed = true;
    this.failAllPending("disposed", "client disposed");
    await this.transport.kill();
  }

  private failAllPending(reason: "exit" | "disposed", message: string): void {
    for (const [id, entry] of this.pending) {
      if (entry.timeout) clearTimeout(entry.timeout);
      entry.reject(new AcpTransportError(reason, entry.method, id, message));
    }
    this.pending.clear();
  }

  private handleLine(line: string): void {
    const trimmed = line.trim();
    if (!trimmed) return;

    let frame: {
      id?: JsonRpcId | null;
      method?: string;
      params?: unknown;
      result?: unknown;
      error?: unknown;
    };
    try {
      frame = JSON.parse(trimmed);
    } catch {
      this.handlers.onProtocolError("malformed JSON-RPC frame");
      return;
    }

    if (!frame || typeof frame !== "object" || Array.isArray(frame)) {
      this.handlers.onProtocolError("malformed JSON-RPC frame");
      return;
    }

    // Agent → client request
    if (frame.id !== undefined && frame.id !== null && frame.method) {
      const id = frame.id;
      this.handlers.onAgentRequest(frame.method, frame.params).then(
        (result) => this.respond(id, { result: result ?? {} }),
        (err: unknown) =>
          this.respond(id, {
            error: {
              code: err instanceof UnsupportedMethodError ? METHOD_NOT_FOUND : INTERNAL_ERROR,
              message: safeDiagnosticText(err instanceof Error ? err.message : err) || "agent request failed",
            },
          }),
      );
      return;
    }

    // Agent → client notification
    if (frame.method) {
      this.handlers.onNotification(frame.method, frame.params);
      return;
    }

    // Response to one of our requests
    if (frame.id !== undefined && frame.id !== null) {
      if (typeof frame.id !== "number") {
        this.handlers.onProtocolError("response for unknown request id");
        return;
      }
      const entry = this.pending.get(frame.id);
      if (!entry) {
        this.handlers.onProtocolError("response for unknown request id");
        return;
      }
      this.pending.delete(frame.id);
      if (entry.timeout) clearTimeout(entry.timeout);
      if (frame.error !== undefined) {
        if (!frame.error || typeof frame.error !== "object" || Array.isArray(frame.error)) {
          entry.reject(new AcpProtocolError(frame.id, entry.method));
        } else {
          entry.reject(new AcpRpcError(frame.id, entry.method, frame.error));
        }
      } else {
        entry.resolve(frame.result);
      }
      return;
    }

    this.handlers.onProtocolError("frame with neither id nor method");
  }

  private respond(id: JsonRpcId, body: { result?: unknown; error?: unknown }): void {
    void this.transport
      .send(JSON.stringify({ jsonrpc: "2.0", id, ...body }))
      .catch(() => {
        /* transport gone — exit path handles cleanup */
      });
  }
}

/** Thrown by driver handlers for methods this client does not implement. */
export class UnsupportedMethodError extends Error {}
