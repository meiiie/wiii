/**
 * PostMessage bridge for iframe embed ↔ parent communication.
 * Sprint 176: Phase 1 — basic ready signal + origin validation.
 * Sprint 194b: Phase 2 — strict origin validation, no wildcard "*".
 *
 * Messages from embed → parent:
 *   wiii:ready         — embed loaded and initialized
 *   wiii:auth-expired  — JWT expired, parent should refresh
 *   wiii:error         — error occurred in embed
 *
 * Messages from parent → embed:
 *   wiii:auth           — refresh tokens
 *   wiii:theme          — change theme
 *   wiii:send-message   — trigger a chat message
 */

export interface WiiiMessage {
  type: string;
  payload?: Record<string, unknown>;
}

/** Check if we're running inside an iframe */
export function isEmbedded(): boolean {
  try {
    return window.self !== window.top;
  } catch {
    // Cross-origin iframe — we're definitely embedded
    return true;
  }
}

// =============================================================================
// Sprint 194b (C3): Strict parent origin management
// =============================================================================

let _parentOrigin: string | null = null;

/**
 * Set the parent window origin explicitly.
 * Called during embed initialization with the configured or detected origin.
 * This MUST be set before sendToParent will transmit sensitive messages.
 */
export function setParentOrigin(origin: string): void {
  _parentOrigin = origin;
}

/**
 * Extract origin from a URL string. Returns null if invalid.
 */
function extractOrigin(url: string): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.origin;
  } catch {
    return null;
  }
}

/**
 * Get the effective parent origin for postMessage.
 * Priority: explicit config → document.referrer → null (refuse).
 */
function getTargetOrigin(): string | null {
  if (_parentOrigin) return _parentOrigin;
  return extractOrigin(document.referrer);
}

/**
 * Send a postMessage to the parent window.
 * Only sends if we're actually embedded in an iframe.
 *
 * Sprint 194b: Uses configured or detected parent origin instead of wildcard "*".
 * Refuses to send if no origin is available (security: prevents data leak to unknown embedders).
 */
export function sendToParent(type: string, payload?: Record<string, unknown>): void {
  if (!isEmbedded()) return;

  const message: WiiiMessage = { type, payload };

  try {
    const targetOrigin = getTargetOrigin();
    if (!targetOrigin) {
      console.warn("[embed-bridge] No parent origin configured — refusing to send message:", type);
      return;
    }
    window.parent.postMessage(message, targetOrigin);
  } catch (err) {
    console.warn("[embed-bridge] Failed to send message to parent:", err);
  }
}

/**
 * Send the ready signal to parent window.
 * Called after embed initialization is complete.
 */
export function sendReadySignal(): void {
  sendToParent("wiii:ready", { version: "1.0.0" });
}

/**
 * Send auth-expired signal to parent window.
 * Parent should respond with fresh tokens.
 */
export function sendAuthExpired(): void {
  sendToParent("wiii:auth-expired");
}

/**
 * Send error signal to parent window.
 */
export function sendError(code: string, message: string): void {
  sendToParent("wiii:error", { code, message });
}

/**
 * Listen for messages from parent window.
 * Returns cleanup function.
 *
 * Sprint 194b (M2): Default deny — MUST have allowedOrigins configured.
 * When no origins are specified, all messages are rejected.
 */
export function onParentMessage(
  handler: (msg: WiiiMessage) => void,
  allowedOrigins?: string[]
): () => void {
  const listener = (event: MessageEvent) => {
    // Sprint 194b: Default deny — must have allowedOrigins configured
    if (!allowedOrigins || allowedOrigins.length === 0) {
      console.warn("[embed-bridge] No allowed origins configured — ignoring incoming message");
      return;
    }

    // Origin validation
    if (!allowedOrigins.includes(event.origin)) {
      return;
    }

    // Only handle wiii: messages
    const data = event.data;
    if (!data || typeof data !== "object" || typeof data.type !== "string") return;
    if (!data.type.startsWith("wiii:")) return;

    handler(data as WiiiMessage);
  };

  window.addEventListener("message", listener);
  return () => window.removeEventListener("message", listener);
}
