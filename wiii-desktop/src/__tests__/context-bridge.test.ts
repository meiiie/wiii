import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useHostContextStore } from '../stores/host-context-store';
import { usePageContextStore } from '../stores/page-context-store';
import { initContextBridge, cleanupContextBridge } from '../lib/context-bridge';

function setDocumentReferrer(value: string) {
  Object.defineProperty(document, 'referrer', {
    value,
    configurable: true,
  });
}

function dispatch(data: unknown, origin = '') {
  window.dispatchEvent(new MessageEvent('message', { data, origin }));
}

describe('context-bridge', () => {
  beforeEach(() => {
    useHostContextStore.getState().clear();
    usePageContextStore.getState().clear();
    setDocumentReferrer('');
    // Ensure bridge is active
    cleanupContextBridge();
    initContextBridge();
  });

  afterEach(() => {
    cleanupContextBridge();
  });

  // ── wiii:page-context ──

  it('wiii:page-context updates host-context-store', () => {
    dispatch({
      type: 'wiii:page-context',
      payload: {
        page_type: 'grades',
        page_title: 'My Grades',
        course_name: 'COLREGs',
        user_role: 'student',
        workflow_stage: 'learning',
      },
    });

    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx).not.toBeNull();
    expect(ctx?.host_type).toBe('lms');
    expect(ctx?.page.type).toBe('grades');
    expect(ctx?.page.title).toBe('My Grades');
    expect(ctx?.user_role).toBe('student');
    expect(ctx?.workflow_stage).toBe('learning');
  });

  it('wiii:page-context updates page-context-store (backward compat)', () => {
    dispatch({
      type: 'wiii:page-context',
      payload: {
        page_type: 'lesson',
        page_title: 'Rule 14',
        course_name: 'COLREGs',
        content_snippet: 'Head-on situation',
      },
    });

    const pageCtx = usePageContextStore.getState().pageContext;
    expect(pageCtx).not.toBeNull();
    expect(pageCtx?.page_type).toBe('lesson');
    expect(pageCtx?.page_title).toBe('Rule 14');
  });

  it('wiii:page-context skips page-context-store when page_type missing', () => {
    dispatch({
      type: 'wiii:page-context',
      payload: {
        page_title: 'Untitled',
        course_name: 'COLREGs',
      },
    });

    // host-context-store should still update (type defaults to "unknown")
    expect(useHostContextStore.getState().currentContext).not.toBeNull();
    // page-context-store should NOT update (no page_type)
    expect(usePageContextStore.getState().pageContext).toBeNull();
  });

  it('wiii:page-context handles direct payload (no nested payload key)', () => {
    dispatch({
      type: 'wiii:page-context',
      page_type: 'quiz',
      page_title: 'Quiz 1',
      quiz_question: 'What is Rule 14?',
    });

    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.page.type).toBe('quiz');
    expect(ctx?.page.title).toBe('Quiz 1');
  });

  it('wiii:page-context preserves structured field in content', () => {
    const structured = { courses: [{ name: 'COLREGs', progress: 70 }] };
    dispatch({
      type: 'wiii:page-context',
      payload: {
        page_type: 'grades',
        page_title: 'Grades',
        structured,
      },
    });

    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.content?.structured).toEqual(structured);
  });

  // ── wiii:capabilities ──

  it('wiii:capabilities updates capabilities', () => {
    dispatch({
      type: 'wiii:capabilities',
      payload: {
        host_type: 'lms',
        host_name: 'Maritime LMS',
        connector_id: 'maritime-lms',
        host_workspace_id: 'org-1',
        host_organization_id: 'org-1',
        version: '2',
        resources: ['current-page', 'grades'],
        surfaces: ['ai_sidebar'],
        tools: [{ name: 'navigate', description: 'Navigate to page' }],
      },
    });

    const caps = useHostContextStore.getState().capabilities;
    expect(caps?.host_type).toBe('lms');
    expect(caps?.version).toBe('2');
    expect(caps?.connector_id).toBe('maritime-lms');
    expect(caps?.host_workspace_id).toBe('org-1');
    expect(caps?.host_organization_id).toBe('org-1');
    expect(caps?.resources).toContain('grades');
    expect(caps?.surfaces).toContain('ai_sidebar');
    expect(caps?.tools).toHaveLength(1);
  });

  it('wiii:page-context preserves operator fields', () => {
    dispatch({
      type: 'wiii:page-context',
      payload: {
        page_type: 'course_editor',
        page_title: 'Curriculum',
        user_role: 'teacher',
        workflow_stage: 'authoring',
        selection: { type: 'lesson_block', label: 'Intro' },
        editable_scope: { type: 'course', allowed_operations: ['quiz'] },
        entity_refs: [{ type: 'course', id: 'c-1', title: 'COLREGs' }],
      },
    });

    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.user_role).toBe('teacher');
    expect(ctx?.workflow_stage).toBe('authoring');
    expect(ctx?.selection).toEqual({ type: 'lesson_block', label: 'Intro' });
    expect(ctx?.editable_scope).toEqual({ type: 'course', allowed_operations: ['quiz'] });
    expect(ctx?.entity_refs).toEqual([{ type: 'course', id: 'c-1', title: 'COLREGs' }]);
  });

  it('wiii:page-context preserves connector overlays for host-session runtime', () => {
    dispatch({
      type: 'wiii:page-context',
      payload: {
        page_type: 'course_editor',
        page_title: 'Curriculum',
        connector_id: 'maritime-lms',
        host_user_id: 'teacher-1',
        host_workspace_id: 'org-1',
        host_organization_id: 'org-1',
      },
    });

    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.connector_id).toBe('maritime-lms');
    expect(ctx?.host_user_id).toBe('teacher-1');
    expect(ctx?.host_workspace_id).toBe('org-1');
    expect(ctx?.host_organization_id).toBe('org-1');
  });

  // ── wiii:context ──

  it('wiii:context updates generic context', () => {
    dispatch({
      type: 'wiii:context',
      payload: {
        host_type: 'ecommerce',
        page: { type: 'product', title: 'Zebra ZXP7' },
      },
    });

    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.host_type).toBe('ecommerce');
    expect(ctx?.page.type).toBe('product');
  });

  // ── wiii:action-response ──

  it('wiii:action-response resolves pending action', async () => {
    // Create a pending action
    const actionPromise = useHostContextStore.getState().requestAction(
      'navigate', { url: '/lesson/1' },
    );

    // Find the pending request ID
    const pending = useHostContextStore.getState().pendingActions;
    const requestId = Array.from(pending.keys())[0];
    expect(requestId).toBeDefined();

    // Simulate host response
    dispatch({
      type: 'wiii:action-response',
      id: requestId,
      result: { success: true, data: { navigated: true } },
    });

    const result = await actionPromise;
    expect(result.success).toBe(true);
    expect(result.data?.navigated).toBe(true);
  });

  // ── Filtering ──

  it('ignores non-wiii messages', () => {
    dispatch({ type: 'some-other-message', payload: { foo: 'bar' } });
    expect(useHostContextStore.getState().currentContext).toBeNull();
  });

  it('ignores messages with no type', () => {
    dispatch({ payload: { page_type: 'lesson' } });
    expect(useHostContextStore.getState().currentContext).toBeNull();
  });

  it('ignores messages with non-string type', () => {
    dispatch({ type: 42, payload: {} });
    expect(useHostContextStore.getState().currentContext).toBeNull();
  });

  it('ignores wiii:clear-chat (handled by EmbedApp)', () => {
    dispatch({ type: 'wiii:clear-chat' });
    expect(useHostContextStore.getState().currentContext).toBeNull();
  });

  it('rejects context messages from origins that do not match the parent referrer', () => {
    setDocumentReferrer('https://trusted.example/lms');

    dispatch({
      type: 'wiii:page-context',
      payload: { page_type: 'lesson', page_title: 'Injected' },
    }, 'https://evil.example');

    expect(useHostContextStore.getState().currentContext).toBeNull();
  });

  it('accepts context messages from the parent referrer origin', () => {
    setDocumentReferrer('https://trusted.example/lms');

    dispatch({
      type: 'wiii:page-context',
      payload: { page_type: 'lesson', page_title: 'Trusted' },
    }, 'https://trusted.example');

    expect(useHostContextStore.getState().currentContext?.page.title).toBe('Trusted');
  });

  // ── Lifecycle ──

  it('cleanupContextBridge stops processing', () => {
    cleanupContextBridge();

    dispatch({
      type: 'wiii:page-context',
      payload: { page_type: 'lesson', page_title: 'Test' },
    });

    expect(useHostContextStore.getState().currentContext).toBeNull();
  });

  it('initContextBridge re-registers after cleanup', () => {
    cleanupContextBridge();
    initContextBridge();

    dispatch({
      type: 'wiii:page-context',
      payload: { page_type: 'lesson', page_title: 'Test' },
    });

    expect(useHostContextStore.getState().currentContext).not.toBeNull();
  });

  it('double initContextBridge does not create duplicate handlers', () => {
    // Re-init multiple times
    initContextBridge();
    initContextBridge();

    // Send page-context with student_state
    dispatch({
      type: 'wiii:page-context',
      payload: {
        page_type: 'lesson',
        page_title: 'Dedup Test',
        student_state: { scroll_percent: 50 },
      },
    });

    // If duplicated, setLegacyPageContext would be called twice.
    // We verify the store has correct data (not corrupted by double-call).
    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.page.type).toBe('lesson');
    expect(ctx?.page.title).toBe('Dedup Test');

    // page-context-store should also be set exactly once
    const pageCtx = usePageContextStore.getState().pageContext;
    expect(pageCtx?.page_type).toBe('lesson');
  });
});
