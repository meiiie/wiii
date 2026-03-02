/**
 * Page Context store — receives LMS page context via PostMessage.
 * Sprint 221: "Mắt Thần" — Page-Aware AI Context.
 *
 * LMS Angular parent sends wiii:page-context messages with current page info.
 * This store holds the latest context and provides it to useSSEStream
 * for inclusion in ChatRequest.user_context.
 */
import { create } from "zustand";

export interface PageContext {
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

export interface StudentPageState {
  time_on_page_ms?: number;
  scroll_percent?: number;
  quiz_attempts?: number;
  last_answer?: string;
  is_correct?: boolean;
  progress_percent?: number;
}

export interface PageAction {
  action: string;
  label: string;
  target?: string;
}

export interface PageContextForRequest {
  page_context: PageContext;
  student_state: StudentPageState | null;
  available_actions: PageAction[] | null;
}

interface PageContextState {
  pageContext: PageContext | null;
  studentState: StudentPageState | null;
  availableActions: PageAction[] | null;
  setPageContext: (ctx: PageContext) => void;
  setStudentState: (state: StudentPageState) => void;
  setAvailableActions: (actions: PageAction[]) => void;
  clear: () => void;
  getPageContextForRequest: () => PageContextForRequest | null;
}

const MAX_SNIPPET_LENGTH = 2000;

export const usePageContextStore = create<PageContextState>((set, get) => ({
  pageContext: null,
  studentState: null,
  availableActions: null,

  setPageContext: (ctx: PageContext) => {
    if (ctx.content_snippet && ctx.content_snippet.length > MAX_SNIPPET_LENGTH) {
      ctx = { ...ctx, content_snippet: ctx.content_snippet.slice(0, MAX_SNIPPET_LENGTH) };
    }
    set({ pageContext: ctx });
  },

  setStudentState: (state: StudentPageState) => {
    set({ studentState: state });
  },

  setAvailableActions: (actions: PageAction[]) => {
    set({ availableActions: actions });
  },

  clear: () => {
    set({ pageContext: null, studentState: null, availableActions: null });
  },

  getPageContextForRequest: () => {
    const { pageContext, studentState, availableActions } = get();
    if (!pageContext) return null;
    return {
      page_context: pageContext,
      student_state: studentState ?? null,
      available_actions: availableActions ?? null,
    };
  },
}));
