/** Restore durable sessions and import provider-owned conversations. */
import type { NekoSession } from "./session-store-types";
import { loadSessionIndex, loadSessionSnapshot, persistSessionStrict } from "../persistence";
import { appendSessionEvent } from "../session-events";
import { projectAuthoritativeMessages, projectControls } from "./session-projections";
import { workspaceFromPath, isAbsoluteWorkspacePath } from "../workspace";
import { restoreNekoTaskMapping, isNekoTaskScopeMapping } from "../task-scope-mapping";
import { nativeSessionsForTask, retireAbsentNativeCheckpoints, reconcileNativeRuntime, reconcileNativeStatus } from "./session-native-recovery";
import type { NekoNativeSessionRecord } from "@/neko/control-client";
import { v4 as uuidv4 } from "uuid";
import type { NekoSessionEvent } from "../session-events";
import type { SessionSet, SessionGet, NekoSessionState } from "./session-store-types";
import type { SessionRuntime } from "./session-runtime-lifecycle";
export function createSessionHydrationActions(set: SessionSet, get: SessionGet, runtime: SessionRuntime): Pick<NekoSessionState, "hydrate" | "importProviderSession"> {
  return {
    hydrate: async () => {
      if (get().hydrated || get().hydrating)
        return;
      set((state) => {
        state.hydrating = true;
        state.hydrationError = null;
      });
      const migratedIds: string[] = [];
      try {
        let index: Awaited<ReturnType<typeof loadSessionIndex>>;
        try {
          index = await loadSessionIndex();
        }
        catch (error) {
          set((state) => {
            state.hydrating = false;
            state.hydrationError = error instanceof Error ? error.message : String(error);
          });
          return;
        }
        const restored: Record<string, NekoSession> = {};
        for (const entry of index) {
          // Live sessions in state win over their persisted snapshot.
          if (get().sessions[entry.id])
            continue;
          let snapshot: Awaited<ReturnType<typeof loadSessionSnapshot>>;
          try {
            snapshot = await loadSessionSnapshot(entry.id);
          }
          catch (error) {
            set((state) => {
              state.hydrating = false;
              state.hydrationError = error instanceof Error ? error.message : String(error);
            });
            return;
          }
          const events = [...snapshot.events];
          const needsMigration = snapshot.needsEventMigration || events.length === 0;
          if (needsMigration) {
            appendSessionEvent(events, "model", {
              type: "session-context",
              source: "legacy-migration",
              agentId: entry.agentId,
              workspacePath: entry.workspace?.path ?? null,
              launchProfileId: entry.launchProfile?.id ?? null,
            }, entry.createdAt);
            for (const [messageIndex, message] of snapshot.messages.entries()) {
              if (message.role !== "user" || typeof message.text !== "string")
                continue;
              appendSessionEvent(events, "model", {
                type: "model-input",
                source: "legacy-migration",
                messageId: message.id,
                text: message.text,
                providerInstanceId: null,
              }, entry.createdAt + messageIndex + 1);
            }
            migratedIds.push(entry.id);
          }
          const eventHighWaterMark = Math.max(snapshot.eventHighWaterMark, events[events.length - 1]?.seq ?? 0);
          const messages = projectAuthoritativeMessages(snapshot.messages, events);
          const droppedStagedMessages = messages.length !== snapshot.messages.length;
          const latestContext = [...events].reverse().find((event) => event.data.type === "session-context");
          const contextData = latestContext?.data.type === "session-context" ? latestContext.data : null;
          const workspace = contextData
            ? contextData.workspacePath === null
              ? null
              : entry.workspace?.path === contextData.workspacePath
                ? entry.workspace
                : workspaceFromPath(contextData.workspacePath)
            : (entry.workspace ?? null);
          const launchProfile = contextData
            ? contextData.launchProfileId === null
              ? null
              : entry.launchProfile?.id === contextData.launchProfileId
                ? entry.launchProfile
                : {
                  id: contextData.launchProfileId,
                  provider: "legacy",
                  model: null,
                  active: true,
                }
            : (entry.launchProfile ?? null);
          const taskDecision = restoreNekoTaskMapping(entry.taskScope, {
            threadId: entry.id, providerId: entry.agentId, projectId: entry.projectId ?? null,
            execution: entry.execution ?? null, workspacePath: workspace?.path ?? "",
          });
          restored[entry.id] = {
            id: entry.id,
            agentId: entry.agentId,
            agentName: entry.agentName,
            title: droppedStagedMessages && messages.length === 0
              ? `Phiên với ${entry.agentName}`
              : entry.title,
            createdAt: entry.createdAt,
            updatedAt: entry.updatedAt,
            workspace,
            launchProfile,
            kind: entry.kind ?? (entry.execution ? "worker" : "scratch"),
            projectId: entry.projectId ?? null,
            execution: entry.execution ?? null,
            backendSessionId: entry.backendSessionId ?? null,
            ...(taskDecision.kind !== "legacy" ? { taskScope: taskDecision.mapping } : {}),
            controls: projectControls(entry.controls ?? [], events),
            commands: entry.commands ?? [],
            pendingControlId: null,
            lastActivityAt: entry.updatedAt,
            status: needsMigration ? "connecting" : "exited",
            messages,
            events,
            eventHighWaterMark,
            runtime: null,
            pendingPermission: null,
            resolvingPermissionId: null,
            cancelPending: false,
            closePending: false,
            deletePending: false,
            statusDetail: needsMigration
              ? "Đang nâng cấp log phiên trước khi có thể khởi động lại agent…"
              : droppedStagedMessages
                ? "Đã bỏ qua prompt chưa xác nhận gửi sau lần thoát trước."
                : "Phiên đã lưu — nhắn tiếp để khởi động lại agent.",
          };
        }
        if (Object.keys(restored).length > 0) {
          const nativeReader = runtime.readNativeControl();
          const nativeSessions = await nativeReader.listSessions();
          for (const session of Object.values(restored)) {
            const natives = nativeSessionsForTask(nativeSessions, session);
            let changed = retireAbsentNativeCheckpoints(session, natives);
            const reconciled: NekoNativeSessionRecord[] = [];
            for (const native of natives) {
              const result = await reconcileNativeRuntime(session, native, nativeReader);
              changed ||= result.changed;
              reconciled.push(result.native);
            }
            reconcileNativeStatus(session, nativeSessionsForTask(reconciled, session));
            if (session.taskScope && (!isNekoTaskScopeMapping(session.taskScope)
              || session.taskScope.state === "recovery-required")) {
              session.status = "error";
              session.statusDetail = "Liên kết tác vụ Neko cần đối soát. Chưa gửi prompt hoặc chạy lại thao tác.";
            }
            // The renderer must not become usable from a reconciled read model
            // that exists only in memory. Native truth remains authoritative,
            // and this strict snapshot records the consumed replay cursor.
            if (changed)
              await persistSessionStrict(session);
          }
        }
        set((state) => {
          state.sessions = { ...restored, ...state.sessions };
          state.hydrated = true;
          state.hydrating = false;
          state.hydrationError = null;
        });
      }
      catch (error) {
        // No parser/projection bug may strand the shell in its loading state.
        set((state) => {
          state.hydrated = false;
          state.hydrating = false;
          state.hydrationError = error instanceof Error ? error.message : String(error);
        });
        return;
      }
      for (const sessionId of migratedIds) {
        const session = get().sessions[sessionId];
        if (!session)
          continue;
        try {
          // A migrated boundary log is not usable until the upgraded snapshot
          // is durable. Restored sessions must not respawn through this gate.
          await persistSessionStrict(session);
          set((state) => {
            const current = state.sessions[sessionId];
            if (!current || current.runtime || current.status !== "connecting")
              return;
            current.status = "exited";
            current.statusDetail = "Phiên đã lưu — nhắn tiếp để khởi động lại agent.";
          });
        }
        catch (error) {
          set((state) => {
            const current = state.sessions[sessionId];
            if (!current || current.runtime)
              return;
            current.status = "error";
            current.statusDetail = `Không thể lưu bản nâng cấp log phiên: ${error instanceof Error ? error.message : String(error)}`;
          });
        }
      }
    },
    importProviderSession: async (providerSession, agent, workspace) => {
      if (providerSession.providerId !== agent.id) {
        throw new Error("Phiên được phát hiện không thuộc harness đã chọn.");
      }
      if (!providerSession.canResume) {
        throw new Error("Harness không xác nhận rằng phiên này có thể tiếp tục.");
      }
      if (!isAbsoluteWorkspacePath(workspace.path)) {
        throw new Error("Hãy gắn một thư mục dự án tuyệt đối trước khi nhập phiên.");
      }
      const existing = Object.values(get().sessions).find((session) => session.agentId === agent.id &&
        session.backendSessionId === providerSession.nativeSessionId);
      if (existing) {
        set((state) => {
          state.activeSessionId = existing.id;
        });
        return existing.id;
      }
      const sessionId = uuidv4();
      const now = Date.now();
      const parsedCreatedAt = Date.parse(providerSession.createdAt ?? "");
      const parsedUpdatedAt = Date.parse(providerSession.updatedAt ?? "");
      const createdAt = Number.isFinite(parsedCreatedAt)
        ? parsedCreatedAt
        : Number.isFinite(parsedUpdatedAt)
          ? parsedUpdatedAt
          : now;
      const updatedAt = Number.isFinite(parsedUpdatedAt)
        ? parsedUpdatedAt
        : createdAt;
      const events: NekoSessionEvent[] = [];
      appendSessionEvent(events, "model", {
        type: "session-context",
        source: "provider-imported",
        agentId: agent.id,
        workspacePath: workspace.path,
        launchProfileId: null,
      }, now);
      const imported: NekoSession = {
        id: sessionId,
        agentId: agent.id,
        agentName: agent.name,
        title: providerSession.title.trim().slice(0, 120) || `Phiên với ${agent.name}`,
        createdAt,
        updatedAt,
        workspace,
        launchProfile: null,
        kind: "scratch",
        projectId: null,
        execution: null,
        backendSessionId: providerSession.nativeSessionId,
        controls: [],
        commands: [],
        pendingControlId: null,
        lastActivityAt: updatedAt,
        status: "exited",
        messages: [],
        events,
        eventHighWaterMark: events[events.length - 1]?.seq ?? 0,
        runtime: null,
        pendingPermission: null,
        resolvingPermissionId: null,
        cancelPending: false,
        closePending: false,
        deletePending: false,
        statusDetail: `Phiên do ${agent.name} sở hữu đã được gắn vào Wiii. ` +
          "Wiii không sao chép lịch sử; nhắn tiếp để harness resume bằng session gốc.",
      };
      await persistSessionStrict(imported);
      set((state) => {
        state.sessions[sessionId] = imported;
        state.activeSessionId = sessionId;
      });
      return sessionId;
    }
  };
}
