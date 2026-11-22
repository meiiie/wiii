/** Native session store composition. Live runtime ownership and all public imports remain stable. */
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type { NekoSessionState, SessionStoreApi, DriverFactory } from "./session-store-types";
import { createSessionPresentation } from "./session-presentation";
import { createSessionRuntime } from "./session-runtime-lifecycle";
import { createSessionHydrationActions } from "./session-hydration-actions";
import { createSessionLaunchActions } from "./session-launch-actions";
import { createSessionPromptActions } from "./session-prompt-actions";
import { createSessionControlActions } from "./session-control-actions";
import { createSessionLifecycleActions } from "./session-lifecycle-actions";
import { createSessionEventActions } from "./session-event-actions";
import { createSessionRecoveryActions } from "./session-recovery-actions";

export type { NekoMessage, NekoSession, NekoSessionStatus } from "./session-store-types";

// Resolve the store only at action time: helpers never import this entry back.
const getStore = (): SessionStoreApi => useNekoSessionStore;
const runtime = createSessionRuntime(getStore, createSessionPresentation(getStore));

export const useNekoSessionStore = create<NekoSessionState>()(
  immer((set, get) => {
    const hydration = createSessionHydrationActions(set, get, runtime);
    const launch = createSessionLaunchActions(set, get, runtime);
    return {
      sessions: {},
      activeSessionId: null,
      hydrated: false,
      hydrating: false,
      hydrationError: null,
      hydrate: hydration.hydrate,
      createSession: launch.createSession,
      importProviderSession: hydration.importProviderSession,
      attachWorkspace: launch.attachWorkspace,
      ...createSessionPromptActions(set, get, runtime),
      ...createSessionControlActions(set, get, runtime),
      ...createSessionLifecycleActions(set, get, runtime),
      ...createSessionRecoveryActions(set, get, runtime),
      ...createSessionEventActions(set, get, runtime),
    };
  }),
);

export const {
  sweepIdleSessions,
  startIdleReaper,
  stopIdleReaper,
  disposeAllNekoRuntimes,
  _setNativeControlReaderForTests,
  _clearLiveDriversForTests,
} = runtime;

/** Test hook: swap the driver factory (kept off the public interface). */
export function _setDriverFactoryForTests(factory: DriverFactory | undefined): void {
  useNekoSessionStore.setState({ _driverFactory: factory } as never);
}
