import { v4 as uuidv4 } from "uuid";

export interface OrphanAcpSession {
  sessionId: string;
  _meta?: Record<string, unknown>;
}

export class LegacyLeaseRecoveryError extends Error {
  constructor(readonly busy: boolean) {
    super(busy
      ? "Còn cuộc trò chuyện chưa dừng hẳn. Hãy dừng rồi thử lại."
      : "Chưa nối lại được cuộc trò chuyện. Bạn có thể thử lại.");
    this.name = "LegacyLeaseRecoveryError";
  }
}

/** Best-effort ACP cleanup, not transport reattachment or native stop proof.
 * Neko must release its writer lease before its PID namespace is destroyed.
 * Only a close request is allowed; no initialize/load/prompt or new process.
 * Native cancellation and durable terminal reconciliation remain mandatory.
 */
export function tryCloseOrphanAcpSession(agentSessionId: string, params: OrphanAcpSession): Promise<boolean> {
  const id = `wiii-recovery-close-${uuidv4()}`;
  return new Promise(resolve => {
    let finished = false;
    let unlisten: (() => void) | undefined;
    const finish = (acknowledged: boolean) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      try { unlisten?.(); } catch { /* Cleanup cannot strand the bounded stop path. */ }
      resolve(acknowledged);
    };
    // Covers listener setup and the write as well as the peer response.
    const timer = setTimeout(() => finish(false), 1_500);
    void (async () => {
      const [{ invoke }, { listen }] = await Promise.all([
        import("@tauri-apps/api/core"), import("@tauri-apps/api/event"),
      ]);
      const detach = await listen<string>(`neko-session://line/${agentSessionId}`, event => {
        if (finished || typeof event.payload !== "string" || event.payload.length > 65_536) return;
        try {
          const frame: unknown = JSON.parse(event.payload);
          if (!frame || typeof frame !== "object" || Array.isArray(frame)) return;
          const response = frame as Record<string, unknown>;
          if (response.jsonrpc !== "2.0" || response.id !== id) return;
          if (Object.prototype.hasOwnProperty.call(response, "error")) finish(false);
          else if (Object.prototype.hasOwnProperty.call(response, "result")) {
            finish(Boolean(response.result && typeof response.result === "object" && !Array.isArray(response.result)));
          }
        } catch { /* Ignore unrelated/malformed output; the deadline is bounded. */ }
      });
      if (finished) { detach(); return; }
      unlisten = detach;
      await invoke("neko_control_session_write", {
        request: {
          requestId: uuidv4(), agentSessionId,
          line: JSON.stringify({ jsonrpc: "2.0", id, method: "session/close", params }),
        },
      });
    })().catch(() => finish(false));
  });
}
