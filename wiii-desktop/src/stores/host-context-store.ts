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

  clear: () => set({ capabilities: null, currentContext: null }),

  getContextForRequest: () => get().currentContext,
}));
