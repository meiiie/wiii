/** Workspace admission and creation of a new live provider session. */
import type { DriverFactory } from "./session-store-types";
import { isAbsoluteWorkspacePath } from "../workspace";
import { v4 as uuidv4 } from "uuid";
import type { NekoTopLevelSessionKind } from "@/neko/session-ownership";
import { createPendingNekoTaskMapping } from "../task-scope-mapping";
import { validateNekoSessionOwnership } from "@/neko/session-ownership";
import type { NekoSessionEvent } from "../session-events";
import { appendSessionEvent } from "../session-events";
import { persistSessionBeforeDispatch } from "../persistence";
import type { DriverEvent } from "../drivers/types";
import { appendRuntimeCleanupFact, observeRuntimeCleanup } from "./session-runtime-facts";
import { appendOwnedSessionEvent, removeEventById } from "./session-projections";
import type { SessionSet, SessionGet, NekoSessionState } from "./session-store-types";
import type { SessionRuntime } from "./session-runtime-lifecycle";
export function createSessionLaunchActions(set: SessionSet, get: SessionGet, runtime: SessionRuntime): Pick<NekoSessionState, "createSession" | "attachWorkspace"> {
  const { ownershipFact, defaultDriverFactory, runtimes, taskAdmissionLaunch, assertScopedRuntimeAdmitted, retainTaskAdmissionFailure, persistSessionNowOrReport, acquireHold, runtimeOperations } = runtime;
  return {
    createSession: async (agent, workspace, launchProfile = null, options = {}) => {
      const activeModeExit = runtime.modeExitOperation;
      if (activeModeExit)
        await activeModeExit;
      if (!workspace || !isAbsoluteWorkspacePath(workspace.path)) {
        throw new Error("Hãy chọn một thư mục dự án tuyệt đối trước khi bắt đầu.");
      }
      const sessionId = uuidv4();
      const now = Date.now();
      const kind: NekoTopLevelSessionKind = options.execution ? "worker" : "scratch";
      const taskScope = createPendingNekoTaskMapping({
        threadId: sessionId, providerId: agent.id, projectId: options.projectId ?? null,
        execution: options.execution ?? null, workspacePath: workspace.path,
      }, options.title?.trim() || `Công việc ${options.execution?.taskId ?? sessionId}`);
      const ownershipDiagnostics = validateNekoSessionOwnership([
        ...Object.values(get().sessions).map(ownershipFact),
        {
          sessionId,
          providerId: agent.id,
          kind,
          projectId: options.projectId ?? null,
          taskId: options.execution?.taskId ?? null,
          runId: options.execution?.runId ?? null,
          active: true,
        },
      ]);
      const conflict = ownershipDiagnostics.find((item) => item.sessionId === sessionId);
      if (conflict) {
        if (conflict.code === "multiple_task_workers") {
          throw new Error("Công việc này đã có một phiên agent đang hoạt động. Hãy tiếp tục phiên đó hoặc kết thúc nó trước khi retry.");
        }
        throw new Error(`Không thể tạo phiên Neko: ${conflict.code}.`);
      }
      const events: NekoSessionEvent[] = [];
      appendSessionEvent(events, "model", {
        type: "session-context",
        source: "created",
        agentId: agent.id,
        workspacePath: workspace.path,
        launchProfileId: launchProfile?.id ?? null,
      }, now);
      set((state) => {
        state.sessions[sessionId] = {
          id: sessionId,
          agentId: agent.id,
          agentName: agent.name,
          title: options.title?.trim() || `Phiên với ${agent.name}`,
          createdAt: now,
          updatedAt: now,
          workspace,
          launchProfile,
          kind,
          projectId: options.projectId ?? null,
          execution: options.execution ?? null,
          backendSessionId: null,
          ...(taskScope ? { taskScope } : {}),
          controls: [],
          commands: [],
          pendingControlId: null,
          lastActivityAt: now,
          status: "connecting",
          messages: [],
          events,
          eventHighWaterMark: events[events.length - 1]?.seq ?? 0,
          runtime: null,
          pendingPermission: null,
          resolvingPermissionId: null,
          cancelPending: false,
          closePending: false,
          deletePending: false,
        };
        state.activeSessionId = sessionId;
      });
      try {
        // The workspace/profile can affect the provider before the first
        // prompt, so its event must be durable before driver.start().
        await persistSessionBeforeDispatch(get().sessions[sessionId]);
        if (get().sessions[sessionId]?.status !== "connecting")
          return sessionId;
        const factory: DriverFactory = (get() as unknown as {
          _driverFactory?: DriverFactory;
        })._driverFactory ?? defaultDriverFactory;
        const pendingEvents: DriverEvent[] = [];
        let preparingRuntime = true;
        const replacement = await runtimes.replace(sessionId, agent.id, (instanceId, ownDriver) => factory(agent, sessionId, {
          workspace,
          projectId: options.projectId ?? null,
          ...(options.execution ? { execution: options.execution } : {}),
          executionId: instanceId,
          ...(launchProfile?.id ? { profileId: launchProfile.id } : {}),
          backendSessionId: null,
          ...taskAdmissionLaunch(sessionId, instanceId),
        }, (event) => {
          if (event.sessionId !== sessionId)
            return;
          if (preparingRuntime)
            pendingEvents.push(event);
          else if (runtimes.isCurrent(sessionId, instanceId))
            get().handleEvent(event);
        }, ownDriver));
        await assertScopedRuntimeAdmitted(sessionId, replacement.current);
        set((state) => {
          const session = state.sessions[sessionId];
          if (!session)
            return;
          if (replacement.previous && !replacement.cleanupFailed) {
            appendRuntimeCleanupFact(session, replacement.previous, "replacement", { failed: false });
          }
          session.runtime = replacement.current;
          session.executionProjection = undefined;
          session.backendSessionId = replacement.current.backendSessionId;
          appendOwnedSessionEvent(session, "runtime", {
            type: "runtime-attached",
            provider: replacement.current,
          });
          if (session.status === "connecting")
            session.status = "idle";
          if (replacement.cleanupFailed && replacement.previous) {
            appendRuntimeCleanupFact(session, replacement.previous, "durability-failure", { failed: true, error: replacement.cleanupError });
            session.status = "error";
            session.statusDetail = "Runtime mới đã chạy nhưng runtime cũ không đóng sạch.";
          }
        });
        preparingRuntime = false;
        for (const event of pendingEvents) {
          if (event.sessionId === sessionId && runtimes.isCurrent(sessionId, replacement.current.instanceId)) {
            get().handleEvent(event);
          }
        }
      }
      catch (err) {
        await retainTaskAdmissionFailure(sessionId, err);
        const reason = err instanceof Error ? err.message : String(err);
        set((state) => {
          const session = state.sessions[sessionId];
          if (session?.status === "connecting") {
            session.status = "error";
            session.statusDetail = reason;
            appendOwnedSessionEvent(session, "runtime", {
              type: "runtime-attach-failed",
              providerId: agent.id,
              reason,
            });
          }
        });
      }
      await persistSessionNowOrReport(sessionId, "trạng thái khởi động runtime");
      return sessionId;
    },
    attachWorkspace: async (sessionId, workspace) => {
      if (!workspace || !isAbsoluteWorkspacePath(workspace.path))
        return;
      const activeModeExit = runtime.modeExitOperation;
      if (activeModeExit)
        await activeModeExit;
      const current = get().sessions[sessionId];
      if (!current || current.workspace || current.closePending || current.deletePending)
        return;
      if (current.taskScope)
        throw new Error("Không đổi thư mục của tác vụ Neko đã liên kết. Hãy tạo một công việc rõ ràng khác.");
      const releaseOperation = acquireHold(runtimeOperations, sessionId);
      let contextEventId: string | null = null;
      try {
        set((state) => {
          const session = state.sessions[sessionId];
          if (session && !session.workspace)
            session.status = "connecting";
        });
        const provider = runtimes.get(sessionId);
        const cleanup = await observeRuntimeCleanup(runtimes.detach(sessionId));
        set((state) => {
          const session = state.sessions[sessionId];
          if (!session || session.workspace)
            return;
          session.workspace = workspace;
          session.backendSessionId = null;
          session.runtime = null;
          session.executionProjection = undefined;
          if (provider) {
            appendRuntimeCleanupFact(session, provider, "workspace-change", cleanup);
          }
          contextEventId = appendOwnedSessionEvent(session, "model", {
            type: "session-context",
            source: "workspace-attached",
            agentId: session.agentId,
            workspacePath: workspace.path,
            launchProfileId: session.launchProfile?.id ?? null,
          }).eventId!;
          session.status = cleanup.failed ? "error" : "exited";
          session.statusDetail = "Đã gắn dự án. Lượt tiếp theo sẽ khởi động một runtime mới trong thư mục này.";
          if (cleanup.failed) {
            session.statusDetail = "Đã gắn dự án nhưng runtime cũ không đóng sạch.";
          }
          session.updatedAt = Date.now();
          session.lastActivityAt = session.updatedAt;
        });
        const updated = get().sessions[sessionId];
        if (updated) {
          try {
            await persistSessionBeforeDispatch(updated);
          }
          catch (error) {
            set((state) => {
              const session = state.sessions[sessionId];
              if (session) {
                session.workspace = null;
                removeEventById(session.events as NekoSessionEvent[], contextEventId);
                session.status = "exited";
                session.statusDetail = `Không thể lưu ngữ cảnh dự án; hãy chọn lại thư mục: ${error instanceof Error ? error.message : String(error)}`;
                session.updatedAt = Date.now();
                session.lastActivityAt = session.updatedAt;
              }
            });
            await persistSessionNowOrReport(sessionId, "rollback ngữ cảnh dự án", {
              strict: true,
            });
          }
        }
      }
      finally {
        releaseOperation();
      }
    }
  };
}
