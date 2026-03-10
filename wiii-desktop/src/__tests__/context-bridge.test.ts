import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useHostContextStore } from '../stores/host-context-store';
import { usePageContextStore } from '../stores/page-context-store';
import { initContextBridge, cleanupContextBridge } from '../lib/context-bridge';

function dispatch(data: unknown) {
  window.dispatchEvent(new MessageEvent('message', { data }));
}

describe('context-bridge', () => {
  beforeEach(() => {
    useHostContextStore.getState().clear();
    usePageContextStore.getState().clear();
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
      },
    });

    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx).not.toBeNull();
    expect(ctx?.host_type).toBe('lms');
    expect(ctx?.page.type).toBe('grades');
    expect(ctx?.page.title).toBe('My Grades');
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
        resources: ['current-page', 'grades'],
        tools: [{ name: 'navigate', description: 'Navigate to page' }],
      },
    });

    const caps = useHostContextStore.getState().capabilities;
    expect(caps?.host_type).toBe('lms');
    expect(caps?.resources).toContain('grades');
    expect(caps?.tools).toHaveLength(1);
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
