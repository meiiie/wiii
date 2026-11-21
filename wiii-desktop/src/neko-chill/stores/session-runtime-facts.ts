/** Runtime cleanup outcomes and their durable lifecycle facts. */
import type { NekoSessionEventData } from "../session-events";
import type { RuntimeProviderSnapshot, RuntimeDisposalResult } from "../runtime-manager";
import type { NekoSession } from "./session-store-types";
import { appendOwnedSessionEvent } from "./session-projections";
import { nativeRuntimeIdentity } from "./session-native-recovery";
export function cleanupFailureReason(error: unknown): string {
  const fallback = "Unknown native runtime cleanup failure.";
  if (!error)
    return fallback;
  try {
    const reason = error instanceof Error ? String(error.message) : String(error);
    return (reason || fallback).slice(0, 4096);
  }
  catch {
    return fallback;
  }
}
export type RuntimeDetachReason = Extract<NekoSessionEventData, {
  type: "runtime-detached";
}>["reason"];
export type RuntimeCleanupOutcome = {
  failed: false;
} | {
  failed: true;
  error: unknown;
};
export type RuntimeDetachOutcome = {
  failed: false;
  provider: RuntimeProviderSnapshot | null;
} | {
  failed: true;
  error: unknown;
};
export async function observeRuntimeCleanup(operation: Promise<unknown>): Promise<RuntimeCleanupOutcome> {
  try {
    await operation;
    return { failed: false };
  }
  catch (error) {
    return { failed: true, error };
  }
}
export async function observeRuntimeDetach(operation: Promise<RuntimeProviderSnapshot | null>): Promise<RuntimeDetachOutcome> {
  try {
    return { failed: false, provider: await operation };
  }
  catch (error) {
    return { failed: true, error };
  }
}
export function runtimeDisposalOutcome(result: Pick<RuntimeDisposalResult, "cleanupFailed" | "error">): RuntimeCleanupOutcome {
  return result.cleanupFailed
    ? { failed: true, error: result.error }
    : { failed: false };
}
/** A detach fact is terminal only when provider cleanup returned successfully. */
export function appendRuntimeCleanupFact(session: NekoSession, provider: RuntimeProviderSnapshot, reason: RuntimeDetachReason, cleanup: RuntimeCleanupOutcome, at: number = Date.now()): void {
  if (cleanup.failed) {
    appendOwnedSessionEvent(session, "runtime", {
      type: "native-runtime-cleanup-uncertain",
      ...nativeRuntimeIdentity(provider),
      providerId: provider.providerId,
      reason: cleanupFailureReason(cleanup.error),
    }, at);
    return;
  }
  appendOwnedSessionEvent(session, "runtime", {
    type: "native-runtime-cleanup-resolved",
    ...nativeRuntimeIdentity(provider),
    providerId: provider.providerId,
  }, at);
  appendOwnedSessionEvent(session, "runtime", {
    type: "runtime-detached",
    providerId: provider.providerId,
    instanceId: provider.instanceId,
    kind: provider.kind,
    reason,
  }, at);
}
