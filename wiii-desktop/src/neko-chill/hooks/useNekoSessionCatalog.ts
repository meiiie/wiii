import { useMemo } from "react";
import { useShallow } from "zustand/react/shallow";
import {
  useNekoSessionStore,
  type NekoSession,
} from "../stores/neko-session-store";

const VOLATILE_STATUSES = new Set<NekoSession["status"]>([
  "dispatching",
  "streaming",
]);

const catalogKeyCache = new WeakMap<NekoSession, string>();

export function sessionCatalogKey(session: NekoSession): string {
  return JSON.stringify([
    session.id,
    session.title,
    session.agentId,
    session.agentName,
    session.projectId ?? null,
    session.workspace?.name ?? null,
    session.workspace?.path ?? null,
    session.launchProfile?.provider ?? null,
    session.launchProfile?.model ?? null,
    session.backendSessionId ?? null,
    session.status,
    session.statusDetail ?? null,
    Boolean(session.pendingPermission),
    session.pendingControlId ?? null,
    session.cancelPending,
    session.closePending,
    session.controls.map((option) => [option.id, option.currentValue]),
    session.commands.map((command) => command.name),
    VOLATILE_STATUSES.has(session.status) ? null : session.updatedAt,
  ]);
}

function cachedSessionCatalogKey(session: NekoSession): string {
  const cached = catalogKeyCache.get(session);
  if (cached !== undefined) return cached;
  const key = sessionCatalogKey(session);
  catalogKeyCache.set(session, key);
  return key;
}

export function useNekoSessionCatalog(): NekoSession[] {
  const fingerprints = useNekoSessionStore(useShallow((state) =>
    Object.entries(state.sessions).flatMap(([recordKey, session]) => [
      recordKey,
      cachedSessionCatalogKey(session),
    ]),
  ));

  return useMemo(() => {
    const sessions = useNekoSessionStore.getState().sessions;
    const catalog: NekoSession[] = [];
    for (let index = 0; index < fingerprints.length; index += 2) {
      const recordKey = fingerprints[index];
      const session = sessions[recordKey];
      if (session) catalog.push(session);
    }
    return catalog;
  }, [fingerprints]);
}
