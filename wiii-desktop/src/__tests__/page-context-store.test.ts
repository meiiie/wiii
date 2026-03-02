import { describe, it, expect, beforeEach } from "vitest";
import { usePageContextStore } from "@/stores/page-context-store";

describe("page-context-store (Sprint 221)", () => {
  beforeEach(() => {
    usePageContextStore.getState().clear();
  });

  it("starts with null page context", () => {
    const state = usePageContextStore.getState();
    expect(state.pageContext).toBeNull();
  });

  it("sets page context from postMessage payload", () => {
    usePageContextStore.getState().setPageContext({
      page_type: "lesson",
      page_title: "Áp suất khí quyển",
      course_name: "Khí Tượng Hải Dương",
      content_snippet: "Áp suất tiêu chuẩn...",
    });
    expect(usePageContextStore.getState().pageContext?.page_type).toBe("lesson");
    expect(usePageContextStore.getState().pageContext?.page_title).toBe("Áp suất khí quyển");
  });

  it("sets student state separately", () => {
    usePageContextStore.getState().setStudentState({
      time_on_page_ms: 180000,
      scroll_percent: 45,
    });
    expect(usePageContextStore.getState().studentState?.time_on_page_ms).toBe(180000);
  });

  it("sets available actions", () => {
    usePageContextStore.getState().setAvailableActions([
      { action: "navigate", label: "Bài tiếp theo", target: "/lessons/43" },
    ]);
    expect(usePageContextStore.getState().availableActions).toHaveLength(1);
  });

  it("clear resets all fields", () => {
    usePageContextStore.getState().setPageContext({ page_type: "quiz" });
    usePageContextStore.getState().setStudentState({ quiz_attempts: 2 });
    usePageContextStore.getState().setAvailableActions([{ action: "hint", label: "Gợi ý" }]);
    usePageContextStore.getState().clear();
    const state = usePageContextStore.getState();
    expect(state.pageContext).toBeNull();
    expect(state.studentState).toBeNull();
    expect(state.availableActions).toBeNull();
  });

  it("truncates content_snippet to 2000 chars", () => {
    const longSnippet = "x".repeat(3000);
    usePageContextStore.getState().setPageContext({
      page_type: "lesson",
      content_snippet: longSnippet,
    });
    const snippet = usePageContextStore.getState().pageContext?.content_snippet;
    expect(snippet).toBeDefined();
    expect(snippet!.length).toBeLessThanOrEqual(2000);
  });

  it("getPageContextForRequest() returns merged object", () => {
    usePageContextStore.getState().setPageContext({
      page_type: "lesson", page_title: "Bài 1", course_name: "Môn A",
    });
    usePageContextStore.getState().setStudentState({ scroll_percent: 50 });
    usePageContextStore.getState().setAvailableActions([{ action: "navigate", label: "Tiếp" }]);
    const req = usePageContextStore.getState().getPageContextForRequest();
    expect(req).not.toBeNull();
    expect(req!.page_context.page_type).toBe("lesson");
    expect(req!.student_state.scroll_percent).toBe(50);
    expect(req!.available_actions).toHaveLength(1);
  });

  it("getPageContextForRequest() returns null when no context", () => {
    expect(usePageContextStore.getState().getPageContextForRequest()).toBeNull();
  });
});
