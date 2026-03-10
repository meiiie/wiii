/**
 * Context Bridge — module-level PostMessage listener for host context.
 * Sprint 223 Refactor: Extracted from host-context-store.ts to keep stores pure.
 *
 * Registered at import time (synchronous), BEFORE React mounts or any
 * useEffect fires. Guarantees we capture host context PostMessages sent
 * by the parent during the iframe "load" event.
 *
 * Single source of truth — updates BOTH host-context-store (primary)
 * and page-context-store (backward compat).
 *
 * Usage: `import "@/lib/context-bridge";` (side-effect import)
 */
import { useHostContextStore } from "@/stores/host-context-store";
import { usePageContextStore } from "@/stores/page-context-store";

// ── Message types we handle ──

const CONTEXT_TYPES = new Set([
  "wiii:page-context",
  "wiii:capabilities",
  "wiii:context",
  "wiii:action-response",
]);

// ── Guard against double-registration ──

let _registered = false;

// ── Handler ──

function handleContextMessage(event: MessageEvent): void {
  const msgType = event.data?.type;
  if (!msgType || typeof msgType !== "string" || !CONTEXT_TYPES.has(msgType)) return;

  if (msgType === "wiii:page-context") {
    const payload = event.data.payload || event.data;
    const { student_state, available_actions, type: _type, ...pageCtx } = payload;

    // Primary: host-context-store
    useHostContextStore.getState().setLegacyPageContext(
      pageCtx, student_state, available_actions,
    );

    // Backward compat: page-context-store (only when page_type present)
    if (pageCtx.page_type) {
      usePageContextStore.getState().setPageContext(pageCtx);
      if (student_state) {
        usePageContextStore.getState().setStudentState(student_state);
      }
      if (available_actions) {
        usePageContextStore.getState().setAvailableActions(available_actions);
      }
    }
  } else if (msgType === "wiii:capabilities") {
    useHostContextStore.getState().setCapabilities(event.data.payload);
  } else if (msgType === "wiii:context") {
    useHostContextStore.getState().updateContext(event.data.payload);
  } else if (msgType === "wiii:action-response") {
    const { id, result } = event.data;
    if (id && result) {
      useHostContextStore.getState().resolveAction(id, result);
    }
  }
}

// ── Lifecycle (for tests) ──

export function initContextBridge(): void {
  if (_registered) return;
  if (typeof window === "undefined") return;
  window.addEventListener("message", handleContextMessage);
  _registered = true;
}

export function cleanupContextBridge(): void {
  if (typeof window === "undefined") return;
  window.removeEventListener("message", handleContextMessage);
  _registered = false;
}

// ── Module-level registration ──

initContextBridge();
