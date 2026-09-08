import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import {
  sessionCatalogKey,
  useNekoSessionCatalog,
} from "@/neko-chill/hooks/useNekoSessionCatalog";
import {
  type NekoSession,
  useNekoSessionStore,
} from "@/neko-chill/stores/neko-session-store";

function liveSession(): NekoSession {
  return {
    id: "live",
    agentId: "neko",
    agentName: "Neko Core",
    title: "Live session",
    createdAt: 1,
    updatedAt: 10,
    workspace: { path: "C:/work/wiii", name: "Wiii" },
    launchProfile: null,
    backendSessionId: null,
    controls: [],
    commands: [],
    pendingControlId: null,
    lastActivityAt: 10,
    status: "streaming",
    messages: [{ id: "answer", role: "assistant", blocks: [] }],
    events: [],
    eventHighWaterMark: 0,
    runtime: null,
    pendingPermission: null,
    resolvingPermissionId: null,
    cancelPending: false,
    closePending: false,
    deletePending: false,
  };
}

describe("Neko session catalog performance projection", () => {
  beforeEach(() => {
    useNekoSessionStore.setState({
      sessions: {},
      activeSessionId: null,
      hydrated: true,
      hydrating: false,
      hydrationError: null,
    });
  });

  it("does not invalidate navigation for streamed answer content", () => {
    const current = liveSession();
    const next: NekoSession = {
      ...current,
      updatedAt: 20,
      messages: [{
        id: "answer",
        role: "assistant",
        blocks: [{ id: "block", type: "answer", content: "Nội dung mới" }],
      }],
    };

    expect(sessionCatalogKey(next)).toBe(sessionCatalogKey(current));
    expect(sessionCatalogKey({ ...next, status: "idle" }))
      .not.toBe(sessionCatalogKey(current));
  });

  it("keeps the navigation subscription asleep across a streaming burst", () => {
    useNekoSessionStore.setState({
      sessions: { live: liveSession() },
      activeSessionId: "live",
    });
    let renders = 0;
    const { result } = renderHook(() => {
      renders += 1;
      return useNekoSessionCatalog();
    });

    expect(result.current).toHaveLength(1);
    expect(renders).toBe(1);

    act(() => {
      for (let index = 0; index < 100; index += 1) {
        const state = useNekoSessionStore.getState();
        const session = state.sessions.live;
        useNekoSessionStore.setState({
          sessions: {
            ...state.sessions,
            live: {
              ...session,
              updatedAt: 20 + index,
              messages: [{
                id: "answer",
                role: "assistant",
                blocks: [{
                  id: "block",
                  type: "answer",
                  content: `Nội dung ${index}`,
                }],
              }],
            },
          },
        });
      }
    });

    expect(renders).toBe(1);

    act(() => {
      const state = useNekoSessionStore.getState();
      useNekoSessionStore.setState({
        sessions: {
          ...state.sessions,
          live: { ...state.sessions.live, status: "idle", updatedAt: 200 },
        },
      });
    });

    expect(renders).toBe(2);
    expect(result.current[0]?.status).toBe("idle");
  });
});
