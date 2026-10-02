/**
 * Driver factory: resolves one provider definition, asks Neko Control to own
 * its process transport, then selects the protocol adapter. Provider launch
 * arguments and raw Tauri commands live outside this module.
 */
import { getNekoControlClient } from "@/neko/control-client";
import type { NekoExecutionBinding } from "@/neko/control-client";
import { requireProviderDefinition } from "@/neko/provider-registry";
import { AcpDriver } from "./acp/driver";
import { CodexAppServerDriver } from "./codex/driver";
import type { Driver, DriverEventHandler } from "./types";
import type { DetectedAgent } from "../stores/neko-agent-store";
import { isAbsoluteWorkspacePath, type WorkspaceRef } from "../workspace";
import { createComputerAgentBridge } from "@/neko-computer/agent-bridge";
import { useAdeWorkStore } from "@/ade/store";
import {
  assertNekoTaskBindingCurrent,
  validateNekoTaskBinding,
  type NekoTaskBindingInput,
  type NekoTrustedTaskBinding,
} from "@/neko/task-binding";
import {
  canonicalRootsEqual,
  NekoTaskProtocolError,
  validateNekoTaskReceipt,
  type NekoTaskReceipt,
} from "./acp/task-protocol";

export interface DriverLaunchConfig {
  workspace: WorkspaceRef;
  /** Stable Wiii Project identity. Computer remains unavailable for unassigned legacy sessions. */
  projectId?: string | null;
  /** Wiii-owned work identity. Omitted only for manual/legacy Neko sessions. */
  execution?: NekoExecutionBinding;
  /** One RuntimeRegistry replacement attempt; creates a fresh Neko Run. */
  executionId?: string;
  profileId?: string;
  backendSessionId?: string | null;
  /** Explicit opt-in only; absence preserves every legacy/provider lane. */
  taskScope?: { readonly label: string; readonly receipt?: NekoTaskReceipt };
  /** Durable mapping must commit before the adapter opens prompt admission. */
  onTaskAdmitted?: (
    backendSessionId: string,
    receipt: NekoTaskReceipt,
    authorizedCanonicalRoot: string,
  ) => Promise<void>;
  onTaskCloseOutcome?: (outcome: "acknowledged" | "uncertain") => Promise<void> | void;
}

export async function createDriverForAgent(
  agent: DetectedAgent,
  sessionId: string,
  launch: DriverLaunchConfig,
  onEvent: DriverEventHandler,
  ownDriver?: (driver: Driver) => void,
): Promise<Driver> {
  const provider = requireProviderDefinition(agent.id);
  if (!provider.launchable) {
    throw new Error(`${provider.name} hiện chỉ hỗ trợ xem chỉ mục phiên trong Wiii.`);
  }
  if (!isAbsoluteWorkspacePath(launch.workspace.path)) {
    throw new Error("Hãy chọn thư mục dự án trước khi bắt đầu.");
  }

  let taskBinding: NekoTrustedTaskBinding | null = null;
  let expectedTaskReceipt: NekoTaskReceipt | undefined;
  let readCurrentTaskBinding: (() => NekoTaskBindingInput) | null = null;
  if (launch.taskScope) {
    if (provider.id !== "neko" || provider.protocol !== "acp-v1"
      || !launch.execution || !launch.executionId || !launch.onTaskAdmitted) {
      throw new Error("Task scoped cần Neko, công việc rõ ràng, generation và cổng lưu mapping trước prompt.");
    }
    if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) {
      throw new Error("Task scoped cần native Wiii để xác minh root vật lý; bản xem trước không có quyền này.");
    }
    // Neko can be opened directly after a cold start without mounting Work.
    // Await the serialized existing hydration before consulting its graph.
    // A missing/invalid graph still fails the fresh binding check; no spawn,
    // receipt rewrite or legacy fallback is allowed on hydration failure.
    await useAdeWorkStore.getState().hydrate();
    readCurrentTaskBinding = () => {
      const work = useAdeWorkStore.getState();
      const task = work.graph.tasks.find((item) => item.id === launch.execution?.taskId);
      return {
        hydrated: work.hydrated,
        graph: work.graph,
        execution: launch.execution!,
        projectId: task?.projectId ?? "",
        workspacePath: launch.workspace.path,
        threadId: sessionId,
        generationId: launch.executionId!,
      };
    };
    const { invoke } = await import("@tauri-apps/api/core");
    taskBinding = await validateNekoTaskBinding(readCurrentTaskBinding(), async (path) =>
      invoke<{ path: string; name: string }>("neko_resolve_workspace", { workspace: path }));
    assertNekoTaskBindingCurrent(taskBinding, readCurrentTaskBinding());
    expectedTaskReceipt = launch.taskScope.receipt
      ? validateNekoTaskReceipt(launch.taskScope.receipt) : undefined;
    if (expectedTaskReceipt && !canonicalRootsEqual(expectedTaskReceipt.root, taskBinding.canonicalWorkspacePath)) {
      throw new NekoTaskProtocolError("root-mismatch");
    }
    if (Boolean(launch.backendSessionId) !== Boolean(expectedTaskReceipt)) {
      throw new NekoTaskProtocolError("invalid-session-id");
    }
  }
  const cwd = taskBinding?.canonicalWorkspacePath ?? launch.workspace.path;
  const control = getNekoControlClient();
  const spawned = await control.spawnProvider({
    providerId: agent.id,
    clientSessionId: sessionId,
    ...(taskBinding ? { clientRunId: taskBinding.generationId, execution: taskBinding.execution }
      : {
        ...(launch.executionId ? { clientRunId: launch.executionId } : {}),
        ...(launch.execution ? { execution: launch.execution } : {}),
      }),
    workspacePath: taskBinding?.workspacePath ?? launch.workspace.path,
    ...(launch.profileId ? { profileId: launch.profileId } : {}),
  });
  const { transport } = spawned;
  const driver: Driver = provider.protocol === "codex-app-server"
    ? new CodexAppServerDriver({
        sessionId,
        cwd,
        resumeThreadId: launch.backendSessionId,
        transport,
        onEvent,
      })
    : new AcpDriver({
        sessionId,
        cwd,
        resumeSessionId: launch.backendSessionId,
        transport,
        onEvent,
        ...(taskBinding && launch.taskScope ? {
          taskScope: {
            authorizedRoot: taskBinding.canonicalWorkspacePath,
            label: launch.taskScope.label,
            ...(expectedTaskReceipt ? { expectedReceipt: expectedTaskReceipt } : {}),
            onAdmitted: async (backendSessionId: string, receipt: NekoTaskReceipt) => {
              assertNekoTaskBindingCurrent(taskBinding!, readCurrentTaskBinding!());
              await launch.onTaskAdmitted!(backendSessionId, receipt, taskBinding!.canonicalWorkspacePath);
              assertNekoTaskBindingCurrent(taskBinding!, readCurrentTaskBinding!());
            },
            ...(launch.onTaskCloseOutcome ? { onCloseOutcome: launch.onTaskCloseOutcome } : {}),
          },
        } : {}),
        ...(launch.projectId ? {
          computerBridge: createComputerAgentBridge({
            sessionId,
            projectId: launch.projectId,
          }),
        } : {}),
      });
  driver.runtime.providerVersion = spawned.provider.version;
  driver.runtime.providerExtensions = {
    ...(driver.runtime.providerExtensions ?? {}),
    nativeAgentSessionId: spawned.agentSessionId,
    nativeRunId: spawned.runId,
  };
  try {
    // RuntimeRegistry owns the process before initialize/session-new can hang.
    ownDriver?.(driver);
    if (taskBinding) assertNekoTaskBindingCurrent(taskBinding, readCurrentTaskBinding!());
    if (taskBinding && spawned.canonicalWorkspacePath !== taskBinding.canonicalWorkspacePath) {
      // The transport is owned before this proof can fail, so replacement
      // cleanup targets only the native identity that Control already checked.
      // Historical native results deliberately provide no inferred root proof.
      throw new NekoTaskProtocolError("root-mismatch");
    }
    await driver.start();
    return driver;
  } catch (error) {
    if (!ownDriver) await driver.dispose().catch(() => {});
    throw error;
  }
}
