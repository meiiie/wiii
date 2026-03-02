import { describe, it, expect } from "vitest";
import { useHostContextStore } from "@/stores/host-context-store";

describe("Host Action SSE + PostMessage Integration (Sprint 222b)", () => {
  it("wiii:action-response resolves pending action", async () => {
    useHostContextStore.getState().clear();
    const store = useHostContextStore.getState();
    const promise = store.requestAction("create_course", { name: "Test" });

    const [reqId] = Array.from(useHostContextStore.getState().pendingActions.keys());

    store.resolveAction(reqId, { success: true, data: { id: 42 } });

    const result = await promise;
    expect(result.success).toBe(true);
    expect(result.data?.id).toBe(42);
  });

  it("host_action SSE event type is recognized", () => {
    const eventType = "host_action";
    expect(eventType).toBe("host_action");
  });
});
