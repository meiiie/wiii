/**
 * Host Context Store — generic context from any host application.
 * Sprint 222: "Wiii Universal Context Engine"
 *
 * Replaces Sprint 221's LMS-specific page-context-store with a
 * host-agnostic store supporting LMS, e-commerce, trading, CRM, etc.
 */
import { create } from "zustand";

const MAX_SNIPPET_LENGTH = 2000;

// ── Types ──

export interface HostPage {
  type: string;
  title?: string;
  url?: string;
  content_type?: string;
  metadata?: Record<string, unknown>;
}

export interface HostContext {
  host_type: string;
  host_name?: string;
  resource_uri?: string;
  page: HostPage;
  user_state?: Record<string, unknown> | null;
  content?: { snippet?: string; structured?: unknown } | null;
  available_actions?: Array<{
    action: string;
    label: string;
    input_schema?: unknown;
    roles?: string[];
  }> | null;
}

export interface HostCapabilities {
  host_type: string;
  host_name?: string;
  resources: string[];
  tools: Array<{
    name: string;
    description: string;
    input_schema?: unknown;
    roles?: string[];
  }>;
}

interface LegacyPageContext {
  page_type?: string;
  page_title?: string;
  course_id?: string;
  course_name?: string;
  lesson_id?: string;
  lesson_name?: string;
  chapter_name?: string;
  content_snippet?: string;
  content_type?: string;
  quiz_question?: string;
  quiz_options?: string[];
  assignment_description?: string;
}

// ── Action Support (Sprint 222b Phase 5) ──

export interface ActionResult {
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

// ── Store ──

interface HostContextState {
  capabilities: HostCapabilities | null;
  currentContext: HostContext | null;
  setCapabilities: (caps: HostCapabilities) => void;
  updateContext: (ctx: HostContext) => void;
  setLegacyPageContext: (
    ctx: LegacyPageContext,
    studentState?: Record<string, unknown> | null,
    actions?: Array<Record<string, unknown>> | null,
  ) => void;
  clear: () => void;
  getContextForRequest: () => HostContext | null;

  // Sprint 222b Phase 5: Bidirectional Actions
  pendingActions: Map<string, {
    resolve: (result: ActionResult) => void;
    reject: (error: Error) => void;
    timeout: ReturnType<typeof setTimeout>;
  }>;
  requestAction: (action: string, params: Record<string, unknown>) => Promise<ActionResult>;
  resolveAction: (requestId: string, result: ActionResult) => void;
}

function truncateSnippet(ctx: HostContext): HostContext {
  if (ctx.content?.snippet && ctx.content.snippet.length > MAX_SNIPPET_LENGTH) {
    return {
      ...ctx,
      content: {
        ...ctx.content,
        snippet: ctx.content.snippet.slice(0, MAX_SNIPPET_LENGTH),
      },
    };
  }
  return ctx;
}

function legacyToHostContext(
  legacy: LegacyPageContext,
  studentState?: Record<string, unknown> | null,
  actions?: Array<Record<string, unknown>> | null,
): HostContext {
  const metadata: Record<string, unknown> = {};
  const metaKeys = [
    "course_id",
    "course_name",
    "lesson_id",
    "lesson_name",
    "chapter_name",
    "content_type",
    "quiz_question",
    "quiz_options",
    "assignment_description",
  ] as const;
  for (const key of metaKeys) {
    const val = legacy[key as keyof LegacyPageContext];
    if (val !== undefined && val !== null) {
      metadata[key] = val;
    }
  }

  return {
    host_type: "lms",
    page: {
      type: legacy.page_type || "unknown",
      title: legacy.page_title,
      metadata,
    },
    user_state: studentState || null,
    content: legacy.content_snippet
      ? { snippet: legacy.content_snippet }
      : null,
    available_actions:
      (actions as HostContext["available_actions"]) || null,
  };
}

export const useHostContextStore = create<HostContextState>((set, get) => ({
  capabilities: null,
  currentContext: null,

  setCapabilities: (caps) => set({ capabilities: caps }),

  updateContext: (ctx) => set({ currentContext: truncateSnippet(ctx) }),

  setLegacyPageContext: (ctx, studentState, actions) => {
    const hostCtx = legacyToHostContext(ctx, studentState, actions);
    set({ currentContext: truncateSnippet(hostCtx) });
  },

  clear: () => {
    // Clear pending action timeouts
    const pending = get().pendingActions;
    for (const entry of pending.values()) {
      clearTimeout(entry.timeout);
    }
    set({ capabilities: null, currentContext: null, pendingActions: new Map() });
  },

  getContextForRequest: () => get().currentContext,

  pendingActions: new Map(),

  requestAction: (action, params) => {
    return new Promise<ActionResult>((resolve, reject) => {
      const requestId = `req-${Math.random().toString(36).slice(2, 14)}`;
      const timeout = setTimeout(() => {
        const pending = get().pendingActions;
        pending.delete(requestId);
        set({ pendingActions: new Map(pending) });
        reject(new Error(`Action timeout: ${action} (${requestId})`));
      }, 30000);

      const pending = get().pendingActions;
      pending.set(requestId, { resolve, reject, timeout });
      set({ pendingActions: new Map(pending) });

      // Send PostMessage to host
      if (window.parent !== window) {
        window.parent.postMessage({
          type: "wiii:action-request",
          id: requestId,
          action,
          params,
        }, "*");
      }
    });
  },

  resolveAction: (requestId, result) => {
    const pending = get().pendingActions;
    const entry = pending.get(requestId);
    if (entry) {
      clearTimeout(entry.timeout);
      pending.delete(requestId);
      set({ pendingActions: new Map(pending) });
      entry.resolve(result);
    }
  },
}));
