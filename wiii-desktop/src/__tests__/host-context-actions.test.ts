import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useHostContextStore } from "@/stores/host-context-store";

describe("Host Context Store — Action Support (Sprint 222b)", () => {
  beforeEach(() => {
    useHostContextStore.getState().clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("requestAction creates pending action and returns promise", async () => {
    vi.useRealTimers(); // Need real timers for this test
    const store = useHostContextStore.getState();
    const promise = store.requestAction("create_course", { name: "Test" });

    const pending = useHostContextStore.getState().pendingActions;
    expect(pending.size).toBe(1);

    const [reqId] = Array.from(pending.keys());
    expect(reqId).toMatch(/^req-/);

    store.resolveAction(reqId, { success: true, data: { id: 123 } });
    const result = await promise;
    expect(result.success).toBe(true);
    expect(result.data?.id).toBe(123);
  });

  it("requestAction times out after 30s", async () => {
    const store = useHostContextStore.getState();
    const promise = store.requestAction("slow_action", {});

    vi.advanceTimersByTime(30000);

    await expect(promise).rejects.toThrow(/timeout/i);
    expect(useHostContextStore.getState().pendingActions.size).toBe(0);
  });

  it("resolveAction for unknown ID does not throw", () => {
    const store = useHostContextStore.getState();
    expect(() => store.resolveAction("unknown-id", { success: false })).not.toThrow();
  });

  it("clear removes pending actions", () => {
    vi.useRealTimers();
    const store = useHostContextStore.getState();
    store.requestAction("test", {});
    expect(useHostContextStore.getState().pendingActions.size).toBe(1);
    store.clear();
    expect(useHostContextStore.getState().pendingActions.size).toBe(0);
  });

  it("multiple concurrent actions tracked independently", async () => {
    vi.useRealTimers();
    const store = useHostContextStore.getState();
    const p1 = store.requestAction("action_a", {});
    const p2 = store.requestAction("action_b", {});

    const pending = useHostContextStore.getState().pendingActions;
    expect(pending.size).toBe(2);

    const [id1, id2] = Array.from(pending.keys());
    store.resolveAction(id1, { success: true });
    store.resolveAction(id2, { success: true });

    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r1.success).toBe(true);
    expect(r2.success).toBe(true);
  });

  it("requestAction preserves provided request id", async () => {
    vi.useRealTimers();
    const store = useHostContextStore.getState();
    const promise = store.requestAction("navigate", { url: "/lesson/1" }, "req-fixed-123");

    const pending = useHostContextStore.getState().pendingActions;
    expect(pending.has("req-fixed-123")).toBe(true);

    store.resolveAction("req-fixed-123", { success: true, data: { ok: true } });
    const result = await promise;
    expect(result.success).toBe(true);
    expect(result.data?.ok).toBe(true);
  });

  it("resolveAction stores semantic feedback for the next turn", async () => {
    vi.useRealTimers();
    const store = useHostContextStore.getState();
    const promise = store.requestAction(
      "authoring.preview_lesson_patch",
      { lesson_id: "lesson-1" },
      "req-preview-1",
    );

    store.resolveAction("req-preview-1", {
      success: true,
      data: {
        preview_token: "lesson-preview-123",
        summary: "Lesson patch preview ready.",
      },
    });

    await promise;

    const feedback = useHostContextStore.getState().getActionFeedbackForRequest();
    expect(feedback?.last_action_result?.action).toBe("authoring.preview_lesson_patch");
    expect(feedback?.last_action_result?.data?.preview_token).toBe("lesson-preview-123");
    expect(feedback?.recent_action_results?.length).toBe(1);
  });
});
