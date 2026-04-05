import { describe, it, expect, beforeEach } from 'vitest';
import { useHostContextStore } from '../stores/host-context-store';

describe('host-context-store', () => {
  beforeEach(() => {
    useHostContextStore.getState().clear();
  });

  it('should accept capabilities declaration', () => {
    useHostContextStore.getState().setCapabilities({
      host_type: 'lms',
      host_name: 'Maritime LMS',
      resources: ['current-page'],
      tools: [{ name: 'navigate', description: 'Nav', input_schema: {} }],
    });
    const caps = useHostContextStore.getState().capabilities;
    expect(caps?.host_type).toBe('lms');
    expect(caps?.tools).toHaveLength(1);
  });

  it('should update context', () => {
    const store = useHostContextStore.getState();
    store.updateContext({
      host_type: 'lms',
      page: { type: 'lesson', title: 'COLREGs' },
    });
    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.page.type).toBe('lesson');
  });

  it('should format context for chat request', () => {
    const store = useHostContextStore.getState();
    store.updateContext({
      host_type: 'lms',
      page: { type: 'quiz', title: 'Test' },
      user_state: { scroll_percent: 50 },
    });
    const forRequest = useHostContextStore.getState().getContextForRequest();
    expect(forRequest).not.toBeNull();
    expect(forRequest?.host_type).toBe('lms');
    expect(forRequest?.page.type).toBe('quiz');
  });

  it('should handle legacy wiii:page-context format', () => {
    const store = useHostContextStore.getState();
    store.setLegacyPageContext({
      page_type: 'lesson',
      page_title: 'Rule 14',
      course_name: 'COLREGs',
    });
    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.host_type).toBe('lms');
    expect(ctx?.page.type).toBe('lesson');
    expect(ctx?.page.title).toBe('Rule 14');
  });

  it('should truncate long content snippets', () => {
    const store = useHostContextStore.getState();
    store.updateContext({
      host_type: 'lms',
      page: { type: 'lesson', title: 'T' },
      content: { snippet: 'A'.repeat(5000) },
    });
    const snippet = useHostContextStore.getState().currentContext?.content?.snippet;
    expect(snippet?.length).toBeLessThanOrEqual(2000);
  });

  it('should clear state', () => {
    const store = useHostContextStore.getState();
    store.updateContext({
      host_type: 'lms',
      page: { type: 'lesson', title: 'T' },
    });
    store.clear();
    expect(useHostContextStore.getState().currentContext).toBeNull();
    expect(useHostContextStore.getState().capabilities).toBeNull();
  });

  it('should preserve metadata in legacy conversion', () => {
    const store = useHostContextStore.getState();
    store.setLegacyPageContext({
      page_type: 'quiz',
      page_title: 'Test Quiz',
      course_name: 'Safety',
      quiz_question: 'Which vessel gives way?',
      quiz_options: ['Vessel A', 'Vessel B'],
    });
    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.page.metadata?.course_name).toBe('Safety');
    expect(ctx?.page.metadata?.quiz_question).toBe('Which vessel gives way?');
  });

  it('should preserve connector and workspace overlays from legacy page context', () => {
    const store = useHostContextStore.getState();
    store.setLegacyPageContext({
      page_type: 'course_editor',
      page_title: 'Curriculum',
      connector_id: 'maritime-lms',
      host_user_id: 'teacher-1',
      host_workspace_id: 'org-1',
      host_organization_id: 'org-1',
    });

    const ctx = useHostContextStore.getState().currentContext;
    expect(ctx?.connector_id).toBe('maritime-lms');
    expect(ctx?.host_user_id).toBe('teacher-1');
    expect(ctx?.host_workspace_id).toBe('org-1');
    expect(ctx?.host_organization_id).toBe('org-1');
  });
});
