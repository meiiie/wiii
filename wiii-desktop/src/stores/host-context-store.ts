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
  connector_id?: string;
  host_user_id?: string;
  host_workspace_id?: string;
  host_organization_id?: string;
  resource_uri?: string;
  page: HostPage;
  user_role?: string;
  workflow_stage?: string;
  selection?: Record<string, unknown> | null;
  editable_scope?: Record<string, unknown> | null;
  entity_refs?: Array<Record<string, unknown>> | null;
  user_state?: Record<string, unknown> | null;
  host_action_feedback?: {
    last_action_result?: {
      params?: {
        source?: string;
      } | null;
    } | null;
  } | null;
  content?: { snippet?: string; structured?: unknown } | null;
  available_actions?: Array<{
    action?: string;
    name?: string;
    label: string;
    input_schema?: unknown;
    roles?: string[];
    permission?: string;
    required_permissions?: string[];
    requires_confirmation?: boolean;
    mutates_state?: boolean;
    surface?: string;
    result_schema?: unknown;
  }> | null;
}

export interface HostCapabilities {
  host_type: string;
  host_name?: string;
  connector_id?: string;
  host_workspace_id?: string;
  host_organization_id?: string;
  version?: string;
  resources: string[];
  surfaces?: string[];
  tools: Array<{
    name: string;
    description: string;
    input_schema?: unknown;
    roles?: string[];
    permission?: string;
    required_permissions?: string[];
    requires_confirmation?: boolean;
    mutates_state?: boolean;
    surface?: string;
    result_schema?: unknown;
  }>;
}

interface LegacyPageContext {
  [key: string]: unknown;
  page_type?: string;
  page_title?: string;
  connector_id?: string;
  host_user_id?: string;
  host_workspace_id?: string;
  host_organization_id?: string;
  action?: string;
  user_role?: string;
  workflow_stage?: string;
  selection?: Record<string, unknown> | null;
  editable_scope?: Record<string, unknown> | null;
  entity_refs?: Array<Record<string, unknown>> | null;
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
  structured?: unknown;
}

// ── Action Support (Sprint 222b Phase 5) ──

export interface ActionResult {
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

export interface HostActionFeedbackItem {
  request_id: string;
  action: string;
  params?: Record<string, unknown>;
  success: boolean;
  summary?: string;
  error?: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

// ── Store ──

interface HostContextState {
  capabilities: HostCapabilities | null;
  currentContext: HostContext | null;
  lastActionResult: HostActionFeedbackItem | null;
  recentActionResults: HostActionFeedbackItem[];
  setCapabilities: (caps: HostCapabilities) => void;
  updateContext: (ctx: HostContext) => void;
  setLegacyPageContext: (
    ctx: LegacyPageContext,
    studentState?: Record<string, unknown> | null,
    actions?: Array<Record<string, unknown>> | null,
  ) => void;
  clear: () => void;
  getContextForRequest: () => HostContext | null;
  getActionFeedbackForRequest: () => {
    last_action_result?: HostActionFeedbackItem;
    recent_action_results?: HostActionFeedbackItem[];
  } | null;

  // Sprint 222b Phase 5: Bidirectional Actions
  pendingActions: Map<string, {
    action: string;
    params: Record<string, unknown>;
    resolve: (result: ActionResult) => void;
    reject: (error: Error) => void;
    timeout: ReturnType<typeof setTimeout>;
  }>;
  requestAction: (
    action: string,
    params: Record<string, unknown>,
    requestId?: string,
  ) => Promise<ActionResult>;
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
  const metadata = Object.create(null) as Record<string, unknown>;
  const blockedMetadataKeys = new Set(["__proto__", "prototype", "constructor"]);
  const metaKeys = [
    "action",
    "workflow_stage",
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
  const topLevelKeys = new Set([
    "page_type",
    "page_title",
    "connector_id",
    "host_user_id",
    "host_workspace_id",
    "host_organization_id",
    "user_role",
    "selection",
    "editable_scope",
    "entity_refs",
    "content_snippet",
    "structured",
  ]);
  for (const key of metaKeys) {
    const val = legacy[key as keyof LegacyPageContext];
    if (val !== undefined && val !== null) {
      metadata[key] = val;
    }
  }
  for (const [key, val] of Object.entries(legacy)) {
    if (
      blockedMetadataKeys.has(key) ||
      topLevelKeys.has(key) ||
      Object.prototype.hasOwnProperty.call(metadata, key) ||
      val === undefined ||
      val === null
    ) {
      continue;
    }
    metadata[key] = val;
  }

  return {
    host_type: "lms",
    connector_id: legacy.connector_id,
    host_user_id: legacy.host_user_id,
    host_workspace_id: legacy.host_workspace_id,
    host_organization_id: legacy.host_organization_id,
    page: {
      type: legacy.page_type || "unknown",
      title: legacy.page_title,
      metadata,
    },
    user_role: legacy.user_role || undefined,
    workflow_stage: legacy.workflow_stage || undefined,
    selection: legacy.selection || null,
    editable_scope: legacy.editable_scope || null,
    entity_refs: legacy.entity_refs || null,
    user_state: studentState || null,
    content: (legacy.content_snippet || legacy.structured)
      ? {
          snippet: legacy.content_snippet || undefined,
          structured: legacy.structured || undefined,
        }
      : null,
    available_actions:
      (actions as HostContext["available_actions"]) || null,
  };
}

export const useHostContextStore = create<HostContextState>((set, get) => ({
  capabilities: null,
  currentContext: null,
  lastActionResult: null,
  recentActionResults: [],

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
    set({
      capabilities: null,
      currentContext: null,
      lastActionResult: null,
      recentActionResults: [],
      pendingActions: new Map(),
    });
  },

  getContextForRequest: () => get().currentContext,

  getActionFeedbackForRequest: () => {
    const last = get().lastActionResult;
    const recent = get().recentActionResults;
    if (!last && recent.length === 0) {
      return null;
    }
    return {
      last_action_result: last || undefined,
      recent_action_results: recent.length > 0 ? recent : undefined,
    };
  },

  pendingActions: new Map(),

  requestAction: (action, params, requestId) => {
    return new Promise<ActionResult>((resolve, reject) => {
      const finalRequestId = requestId || `req-${Math.random().toString(36).slice(2, 14)}`;
      const timeout = setTimeout(() => {
        const pending = get().pendingActions;
        pending.delete(finalRequestId);
        set({ pendingActions: new Map(pending) });
        reject(new Error(`Action timeout: ${action} (${finalRequestId})`));
      }, 30000);

      const pending = get().pendingActions;
      pending.set(finalRequestId, { action, params, resolve, reject, timeout });
      set({ pendingActions: new Map(pending) });

      // Send PostMessage to host
      if (window.parent !== window) {
        window.parent.postMessage({
          type: "wiii:action-request",
          id: finalRequestId,
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
      const data = result.data || undefined;
      const summary =
        typeof data?.summary === "string" && data.summary.trim().length > 0
          ? data.summary.trim()
          : result.success
            ? `Host action ${entry.action} completed.`
            : (result.error || `Host action ${entry.action} failed.`);
      const feedback: HostActionFeedbackItem = {
        request_id: requestId,
        action: entry.action,
        params: entry.params,
        success: result.success,
        summary,
        error: result.error,
        data,
        timestamp: new Date().toISOString(),
      };
      const recent = [feedback, ...get().recentActionResults].slice(0, 6);
      set({
        pendingActions: new Map(pending),
        lastActionResult: feedback,
        recentActionResults: recent,
      });
      entry.resolve(result);
    }
  },
}));
