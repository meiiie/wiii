/**
 * T302 — neko-session-store: DriverEvent → ContentBlock streaming, turn
 * lifecycle, permission pass-through, cancel, process exit.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Driver, DriverEvent, PermissionDecision } from "@/neko-chill/drivers/types";
import type { DetectedAgent } from "@/neko-chill/stores/neko-agent-store";

const storage = new Map<string, unknown>();
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn(async (store: string, key: string, dflt: unknown) =>
    storage.get(`${store}:${key}`) ?? dflt),
  loadStoreStrict: vi.fn(async (store: string, key: string, dflt: unknown) => {
    const hit = storage.get(`${store}:${key}`);
    return hit === undefined ? dflt : hit;
  }),
  saveStore: vi.fn(async (store: string, key: string, value: unknown) => {
    storage.set(`${store}:${key}`, value);
  }),
  saveStoreStrict: vi.fn(async (store: string, key: string, value: unknown) => {
    storage.set(`${store}:${key}`, value);
  }),
  deleteStore: vi.fn(async (store: string, key: string) => {
    storage.delete(`${store}:${key}`);
  }),
  deleteStoreStrict: vi.fn(async (store: string, key: string) => {
    storage.delete(`${store}:${key}`);
  }),
  clearStore: vi.fn(async () => {}),
}));

import {
  useNekoSessionStore,
  _setDriverFactoryForTests,
} from "@/neko-chill/stores/neko-session-store";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useCompletionNoticeStore } from "@/neko-chill/stores/completion-notice-store";
import { saveStoreStrict } from "@/lib/storage";

const AGENT: DetectedAgent = {
  id: "neko",
  name: "Neko Core",
  version: "0.24.0",
  found: true,
  availability: "available",
  supportsProfiles: true,
};
const WORKSPACE = { path: "C:/tmp/project", name: "project" };
const detectAgents = useNekoAgentStore.getState().detect;

class FakeDriver implements Driver {
  readonly kind = "acp" as const;
  readonly backendSessionId: string;
  readonly runtime: Driver["runtime"] = {
    capabilities: ["prompt", "cancel", "permission-resolution", "session-config"],
    contextContinuity: "process",
    workspaceIsolation: "advisory",
  };
  prompts: string[] = [];
  cancelled = 0;
  disposed = 0;
  decisions: PermissionDecision[] = [];
  configChanges: Array<{ optionId: string; value: string | boolean }> = [];
  configErrors: Error[] = [];
  constructor(
    readonly sessionId: string,
    readonly emit: (event: DriverEvent) => void,
  ) {
    this.backendSessionId = `backend-${sessionId}`;
  }
  async start(): Promise<void> {}
  async prompt(text: string): Promise<void> {
    this.prompts.push(text);
  }
  async cancel(): Promise<void> {
    this.cancelled += 1;
  }
  async resolvePermission(decision: PermissionDecision): Promise<void> {
    this.decisions.push(decision);
  }
  async setConfigOption(optionId: string, value: string | boolean): Promise<void> {
    this.configChanges.push({ optionId, value });
    const error = this.configErrors.shift();
    if (error) throw error;
  }
  async dispose(): Promise<void> {
    this.disposed += 1;
  }
}

let driver: FakeDriver;
let launchConfig: {
  workspace: typeof WORKSPACE;
  executionId?: string;
  profileId?: string;
  backendSessionId?: string | null;
} | undefined;

async function setup(): Promise<string> {
  _setDriverFactoryForTests(async (agent, sessionId, launch, onEvent) => {
    launchConfig = launch;
    driver = new FakeDriver(sessionId, onEvent);
    return driver;
  });
  return useNekoSessionStore.getState().createSession(AGENT, WORKSPACE);
}

const emit = (event: DriverEvent) => useNekoSessionStore.getState().handleEvent(event);
const session = (id: string) => useNekoSessionStore.getState().sessions[id];

describe("neko-session-store", () => {
  beforeEach(() => {
    storage.clear();
    useCompletionNoticeStore.setState({ enabled: true, sound: false, notices: [] });
    useNekoSessionStore.setState({ sessions: {}, activeSessionId: null });
    useNekoAgentStore.setState({ agents: [], isLoading: false, error: null, detect: detectAgents });
    launchConfig = undefined;
    _setDriverFactoryForTests(undefined);
  });

  it("announces only a durably stored live completion, never duplicate events", async () => {
    const id = await setup();
    emit({ type: "turn-started", sessionId: id });
    emit({ type: "answer-delta", sessionId: id, text: "Kết quả đã kiểm tra." });
    emit({ type: "turn-finished", sessionId: id, stopReason: "end_turn" });
    expect(useCompletionNoticeStore.getState().notices).toEqual([]);
    await vi.waitFor(() => expect(useCompletionNoticeStore.getState().notices).toHaveLength(1));
    const result = useCompletionNoticeStore.getState().notices[0];
    expect(result.sessionId).toBe(id);
    useCompletionNoticeStore.getState().dismiss(result.id);
    emit({ type: "turn-finished", sessionId: id, stopReason: "end_turn" });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(useCompletionNoticeStore.getState().notices).toEqual([]);
  });

  it.each(["cancelled", "error", "refusal", "max_tokens", "max_turn_requests"] as const)(
    "never sends a successful completion notice for %s", async (stopReason) => {
      const id = await setup();
      emit({ type: "turn-started", sessionId: id });
      emit({ type: "answer-delta", sessionId: id, text: "Partial result" });
      emit({ type: "turn-finished", sessionId: id, stopReason });
      await new Promise((resolve) => setTimeout(resolve, 20));
      expect(useCompletionNoticeStore.getState().notices).toEqual([]);
    },
  );

  it("does not announce a completion when durable storage rejects it", async () => {
    const id = await setup();
    emit({ type: "turn-started", sessionId: id });
    emit({ type: "answer-delta", sessionId: id, text: "Result not stored" });
    vi.mocked(saveStoreStrict).mockRejectedValueOnce(new Error("disk unavailable"));
    emit({ type: "turn-finished", sessionId: id, stopReason: "end_turn" });
    await vi.waitFor(() => expect(session(id).statusDetail).toContain("disk unavailable"));
    expect(useCompletionNoticeStore.getState().notices).toEqual([]);
  });

  it("does not announce a previous turn after a new turn has started", async () => {
    const id = await setup();
    emit({ type: "turn-started", sessionId: id });
    emit({ type: "answer-delta", sessionId: id, text: "First result" });
    emit({ type: "turn-finished", sessionId: id, stopReason: "end_turn" });
    emit({ type: "turn-started", sessionId: id });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(useCompletionNoticeStore.getState().notices).toEqual([]);
  });

  it("creates a session, becomes idle, and records the user prompt", async () => {
    const id = await setup();
    expect(session(id).status).toBe("idle");
    expect(useNekoSessionStore.getState().activeSessionId).toBe(id);
    expect(session(id).workspace).toEqual(WORKSPACE);
    expect(session(id)).toMatchObject({ kind: "scratch", execution: null });
    expect(launchConfig?.workspace).toEqual(WORKSPACE);
    expect(launchConfig?.executionId).toEqual(expect.any(String));
    expect(launchConfig?.executionId).not.toBe(id);
    expect(launchConfig?.backendSessionId).toBeNull();
    expect(session(id).backendSessionId).toBe(`backend-${id}`);

    await useNekoSessionStore.getState().sendPrompt("Xin chào");
    expect(driver.prompts).toEqual(["Xin chào"]);
    expect(session(id).messages[0]).toMatchObject({ role: "user", text: "Xin chào",
    });
    expect(session(id).title).toBe("Xin chào");
  });

  it("refuses to create a session without an explicit workspace", async () => {
    await expect(
      useNekoSessionStore.getState().createSession(AGENT, undefined as never),
    ).rejects.toThrow("thư mục dự án tuyệt đối");
    await expect(
      useNekoSessionStore.getState().createSession(AGENT, {
        path: "relative/project",
        name: "project",
      }),
    ).rejects.toThrow("thư mục dự án tuyệt đối");
    expect(Object.keys(useNekoSessionStore.getState().sessions)).toHaveLength(0);
  });

  it("wraps one provider-owned session once and resumes the native identity", async () => {
    const discovered = {
      providerId: "neko",
      nativeSessionId: "native-neko-42",
      title: "Existing provider session",
      workspacePath: WORKSPACE.path,
      createdAt: "2026-08-23T10:00:00.000Z",
      updatedAt: "2026-08-24T10:00:00.000Z",
      model: "test-model",
      state: "saved",
      canResume: true,
    };
    const id = await useNekoSessionStore.getState().importProviderSession(
      discovered,
      AGENT,
      WORKSPACE,
    );
    const duplicateId = await useNekoSessionStore.getState().importProviderSession(
      discovered,
      AGENT,
      WORKSPACE,
    );

    expect(duplicateId).toBe(id);
    expect(Object.keys(useNekoSessionStore.getState().sessions)).toHaveLength(1);
    expect(session(id)).toMatchObject({
      backendSessionId: "native-neko-42",
      title: "Existing provider session",
      workspace: WORKSPACE,
      status: "exited",
      messages: [],
    });
    expect(session(id).events[0]?.data).toMatchObject({
      type: "session-context",
      source: "provider-imported",
    });

    useNekoAgentStore.setState({ agents: [AGENT] });
    _setDriverFactoryForTests(async (_agent, sessionId, launch, onEvent) => {
      launchConfig = launch;
      driver = new FakeDriver(sessionId, onEvent);
      return driver;
    });
    await useNekoSessionStore.getState().sendPrompt("Tiếp tục");
    expect(launchConfig?.backendSessionId).toBe("native-neko-42");
    expect(driver.prompts).toEqual(["Tiếp tục"]);
  });

  it("blocks a second active worker for one task before another provider starts", async () => {
    let starts = 0;
    _setDriverFactoryForTests(async (_agent, sessionId, _launch, onEvent) => {
      starts += 1;
      return new FakeDriver(sessionId, onEvent);
    });
    const first = await useNekoSessionStore.getState().createSession(
      AGENT,
      WORKSPACE,
      null,
      {
        execution: {
          taskId: "task-auth",
          runId: "run-1",
          environmentId: "env-1",
        },
      },
    );

    await expect(useNekoSessionStore.getState().createSession(
      AGENT,
      WORKSPACE,
      null,
      {
        execution: {
          taskId: "task-auth",
          runId: "run-2",
          environmentId: "env-2",
        },
      },
    )).rejects.toThrow(/đã có một phiên agent/i);
    expect(starts).toBe(1);
    expect(session(first).kind).toBe("worker");
  });

  it("stores controls, commands, session info, and routes a control change", async () => {
    const id = await setup();
    emit({
      type: "session-controls",
      sessionId: id,
      controls: [
        {
          id: "mode",
          label: "Chế độ",
          category: "mode",
          kind: "select",
          currentValue: "default",
          choices: [{ value: "default", label: "Default" }, { value: "plan", label: "Plan" }],
        },
      ],
    });
    emit({
      type: "available-commands",
      sessionId: id,
      commands: [{ name: "memory show", description: "Show memory" }],
    });
    emit({
      type: "session-info",
      sessionId: id,
      title: "Tiêu đề từ agent",
      updatedAt: "2026-08-13T12:00:00.000Z",
      continuityLevel: "recovered",
      revision: 4,
    });

    expect(session(id)).toMatchObject({
      title: "Tiêu đề từ agent",
      controls: [{ id: "mode", currentValue: "default" }],
      commands: [{ name: "memory show" }],
    });
    expect(session(id).updatedAt).toBeGreaterThanOrEqual(
      Date.parse("2026-08-13T12:00:00.000Z"),
    );
    expect(session(id).statusDetail).toContain("không tự chạy lại");
    await useNekoSessionStore.getState().setConfigOption("mode", "plan");
    expect(driver.configChanges).toEqual([{ optionId: "mode", value: "plan" }]);
    expect(session(id).pendingControlId).toBeNull();
  });

  it("rolls a failed config transaction back to the previous effective value", async () => {
    const id = await setup();
    emit({
      type: "session-controls",
      sessionId: id,
      controls: [{
        id: "model",
        label: "Model",
        category: "model",
        kind: "select",
        currentValue: "stable",
        choices: [
          { value: "stable", label: "Stable" },
          { value: "preview", label: "Preview" },
        ],
      }],
    });
    driver.configErrors.push(new Error("provider rejected preview"));

    await useNekoSessionStore.getState().setConfigOption("model", "preview");

    expect(session(id).controls[0].currentValue).toBe("stable");
    expect(session(id).pendingControlId).toBeNull();
    expect(session(id).statusDetail).toContain("provider rejected preview");
    expect(driver.configChanges).toEqual([
      { optionId: "model", value: "preview" },
      { optionId: "model", value: "stable" },
    ]);
    const phases = session(id).events.flatMap((event) =>
      event.data.type === "control-change" ? [event.data.phase] : [],
    );
    expect(phases.slice(-2)).toEqual(["requested", "rolled-back"]);
  });

  it("reports unknown effective config when an ambiguous failure cannot be compensated", async () => {
    const id = await setup();
    emit({
      type: "session-controls",
      sessionId: id,
      controls: [{
        id: "model",
        label: "Model",
        category: "model",
        kind: "select",
        currentValue: "stable",
        choices: [
          { value: "stable", label: "Stable" },
          { value: "preview", label: "Preview" },
        ],
      }],
    });
    driver.configErrors.push(
      new Error("provider response lost"),
      new Error("compensation unavailable"),
    );

    await useNekoSessionStore.getState().setConfigOption("model", "preview");

    expect(session(id).status).toBe("exited");
    expect(session(id).pendingControlId).toBeNull();
    expect(session(id).statusDetail).toContain("compensation unavailable");
    expect(session(id).runtime).toBeNull();
    expect(driver.disposed).toBe(1);
    expect(driver.configChanges).toEqual([
      { optionId: "model", value: "preview" },
      { optionId: "model", value: "stable" },
    ]);
    expect(session(id).events.at(-1)?.data).toMatchObject({
      type: "control-change",
      phase: "rollback-failed",
      reason: expect.stringContaining("provider response lost"),
    });
    expect(session(id).events).toEqual(expect.arrayContaining([
      expect.objectContaining({
        data: expect.objectContaining({
          type: "runtime-detached",
          reason: "config-uncertain",
        }),
      }),
    ]));
  });

  it("blocks prompts until a configuration transaction finishes", async () => {
    const id = await setup();
    emit({
      type: "session-controls",
      sessionId: id,
      controls: [{
        id: "mode",
        label: "Chế độ",
        category: "mode",
        kind: "select",
        currentValue: "default",
        choices: [{ value: "default", label: "Default" }, { value: "plan", label: "Plan" }],
      }],
    });

    const changing = useNekoSessionStore.getState().setConfigOption("mode", "plan");
    expect(session(id).pendingControlId).toBe("mode");
    await useNekoSessionStore.getState().sendPrompt("không được chạy giữa giao dịch");
    await changing;

    expect(driver.prompts).toEqual([]);
    expect(driver.configChanges).toEqual([{ optionId: "mode", value: "plan" }]);
    expect(session(id).pendingControlId).toBeNull();
  });

  it("attaches a workspace to a legacy transcript and restarts on the next prompt", async () => {
    const id = await setup();
    useNekoSessionStore.setState((state) => {
      state.sessions[id].workspace = null;
      state.sessions[id].messages.push({ id: "old", role: "user", text: "old turn",
      });
    });

    const attached = { path: "C:/tmp/legacy", name: "legacy" };
    await useNekoSessionStore.getState().attachWorkspace(id, attached);
    expect(driver.disposed).toBe(1);
    expect(session(id)).toMatchObject({ workspace: attached, status: "exited",
    });
  });

  it("streams interleaved thinking/answer/tool blocks in ContentBlock vocabulary", async () => {
    const id = await setup();
    emit({ type: "turn-started", sessionId: id });
    expect(session(id).status).toBe("streaming");

    emit({ type: "reasoning-delta", sessionId: id, text: "Nghĩ " });
    emit({ type: "reasoning-delta", sessionId: id, text: "đã…" });
    emit({
      type: "activity",
      sessionId: id,
      activity: { id: "t1", title: "Write(hello.txt)", kind: "file", status: "pending",
        operation: "update", locations: [{ path: "C:/tmp/project/hello.txt" }],
      },
    });
    emit({ type: "answer-delta", sessionId: id, text: "Chào " });
    emit({ type: "answer-delta", sessionId: id, text: "bạn!" });
    emit({
      type: "activity",
      sessionId: id,
      activity: {
        id: "t1",
        title: "Write(hello.txt)",
        kind: "file",
        status: "failed",
        detail: "Denied by user",
        operation: "update",
        locations: [{ path: "C:/tmp/project/hello.txt" }],
      },
    });
    emit({ type: "turn-finished", sessionId: id, stopReason: "end_turn" });

    const blocks = session(id).messages.at(-1)!.blocks!;
    expect(blocks.map((b) => b.type)).toEqual(["thinking", "tool_execution", "answer"]);
    expect(blocks[0]).toMatchObject({ content: "Nghĩ đã…" });
    // Tool upsert: one block, terminal state renders completed + detail kept.
    expect(blocks[1]).toMatchObject({
      status: "completed",
      tool: { name: "Write(hello.txt)", result: "Denied by user" },
    });
    expect(blocks[2]).toMatchObject({ content: "Chào bạn!" });
    expect(session(id).status).toBe("idle");
    expect(
      session(id).events.filter((event) => event.data.type === "workspace-activity"),
    ).toHaveLength(2);
  });

  it("presents only complete provider blocks instead of partial tokens", async () => {
    const id = await setup();
    emit({ type: "turn-started", sessionId: id });

    emit({ type: "answer-delta", sessionId: id, text: "Neko đang đọc " });
    emit({ type: "answer-delta", sessionId: id, text: "dự án và chưa xong paragraph." });
    expect(session(id).messages.at(-1)?.blocks).toEqual([]);

    emit({ type: "answer-delta", sessionId: id, text: "\n\n" });
    expect(session(id).messages.at(-1)?.blocks?.[0]).toMatchObject({
      type: "answer",
      content: "Neko đang đọc dự án và chưa xong paragraph.\n\n",
    });

    emit({ type: "answer-delta", sessionId: id, text: "Đoạn cuối không có blank line" });
    expect(session(id).messages.at(-1)?.blocks?.[0]).not.toMatchObject({
      content: expect.stringContaining("Đoạn cuối"),
    });

    emit({ type: "turn-finished", sessionId: id, stopReason: "end_turn" });
    expect(session(id).messages.at(-1)?.blocks?.[0]).toMatchObject({
      content: "Neko đang đọc dự án và chưa xong paragraph.\n\nĐoạn cuối không có blank line",
    });
  });

  it("passes permission requests through and resolves them on the driver", async () => {
    const id = await setup();
    emit({ type: "turn-started", sessionId: id });
    emit({
      type: "permission-request",
      sessionId: id,
      request: {
        requestId: "perm-1",
        title: "Write(hello.txt)",
        options: [
          { optionId: "allow_once", label: "Cho phép", kind: "allow_once" },
          { optionId: "reject_once", label: "Từ chối", kind: "reject_once" },
        ],
      },
    });
    expect(session(id).pendingPermission?.requestId).toBe("perm-1");

    const firstDecision = useNekoSessionStore.getState().resolvePermission("reject_once");
    expect(session(id).resolvingPermissionId).toBe("perm-1");
    const conflictingDecision = useNekoSessionStore.getState().resolvePermission("allow_once");
    await Promise.all([firstDecision, conflictingDecision]);
    expect(session(id).pendingPermission).toBeNull();
    expect(session(id).resolvingPermissionId).toBeNull();
    expect(driver.decisions).toEqual([{ requestId: "perm-1", optionId: "reject_once" }]);
    expect(session(id).events.filter((event) => event.data.type === "permission-decision"))
      .toHaveLength(1);
  });

  it("cancel reaches the driver; process exit marks the session honestly", async () => {
    const id = await setup();
    emit({ type: "turn-started", sessionId: id });
    await useNekoSessionStore.getState().cancelTurn();
    expect(driver.cancelled).toBe(1);

    emit({ type: "process-exited", sessionId: id, code: 1 });
    expect(session(id).status).toBe("exited");
    expect(session(id).statusDetail).toContain("mã lỗi 1");
    // Driver gone → a further prompt is a no-op, not a crash.
    await useNekoSessionStore.getState().sendPrompt("còn đó không?");
    expect(driver.prompts).toEqual([]);
  });

  it("closeSession disposes the driver but keeps the transcript (exited)", async () => {
    const id = await setup();
    await useNekoSessionStore.getState().closeSession(id);
    expect(driver.disposed).toBe(1);
    const closed = session(id);
    expect(closed.status).toBe("exited");
    expect(closed.pendingPermission).toBeNull();
  });

  it("checks a saved session's unprobed harness even when another harness is already known", async () => {
    const id = await setup();
    await useNekoSessionStore.getState().closeSession(id);
    const detect = vi.fn(async () => { useNekoAgentStore.setState({ agents: [AGENT] }); });
    useNekoAgentStore.setState({ agents: [{ ...AGENT, id: "gemini", name: "Gemini CLI" }], detect });
    useNekoSessionStore.getState().setActiveSession(id);
    await useNekoSessionStore.getState().sendPrompt("Tiếp tục bản nháp");
    expect(detect).toHaveBeenCalledExactlyOnceWith("neko");
    expect(driver.prompts).toEqual(["Tiếp tục bản nháp"]);
  });

  it.each([{ isLoading: true }, { error: "cleanup could not be proven" }])(
    "does not resume a cached harness while discovery is unresolved: %o", async (state) => {
      const id = await setup();
      await useNekoSessionStore.getState().closeSession(id);
      const factory = vi.fn(async (_agent, sessionId, _launch, onEvent) => new FakeDriver(sessionId, onEvent));
      _setDriverFactoryForTests(factory);
      useNekoAgentStore.setState({ agents: [AGENT], ...state });
      useNekoSessionStore.getState().setActiveSession(id);
      await useNekoSessionStore.getState().sendPrompt("Chưa được gửi");
      expect(factory).not.toHaveBeenCalled();
      expect(session(id).statusDetail).toContain("Quản lý harness");
    },
  );

  it("keeps a session exited when close cancels respawn preparation", async () => {
    const id = await setup();
    await useNekoSessionStore.getState().closeSession(id);
    let replacement!: FakeDriver;
    _setDriverFactoryForTests(async (_agent, sessionId, _launch, onEvent, ownDriver) => {
      replacement = new FakeDriver(sessionId, onEvent);
      let rejectStart!: (error: Error) => void;
      const starting = new Promise<Driver>((_resolve, reject) => {
        rejectStart = reject;
      });
      const dispose = replacement.dispose.bind(replacement);
      replacement.dispose = async () => {
        await dispose();
        rejectStart(new Error("client disposed")); };
      ownDriver(replacement);
      return starting;
    });
    useNekoAgentStore.setState({ agents: [AGENT], isLoading: false });
    useNekoSessionStore.getState().setActiveSession(id);

    const respawning = useNekoSessionStore.getState().sendPrompt("thử khởi động lại");
    await vi.waitFor(() => {
      expect(session(id).status).toBe("connecting");
      expect(replacement).toBeDefined();
    });
    const closing = useNekoSessionStore.getState().closeSession(id);
    expect(session(id).status).toBe("stopping");
    await closing;
    expect(session(id).status).toBe("exited");
    await respawning;

    expect(replacement.disposed).toBe(1);
    expect(replacement.prompts).toEqual([]);
    expect(session(id).status).toBe("exited");
  });

  it("marks the session as error when the driver factory fails", async () => {
    _setDriverFactoryForTests(async () => {
      throw new Error("spawn thất bại");
    });
    const id = await useNekoSessionStore.getState().createSession(AGENT, WORKSPACE);
    expect(session(id).status).toBe("error");
    expect(session(id).statusDetail).toContain("spawn thất bại");
    vi.restoreAllMocks();
  });
});
