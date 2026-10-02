import { createContext, useContext, useEffect, type ReactNode } from "react";
import { disposeAllNekoRuntimes, startIdleReaper } from "./stores/neko-session-store";

import { startNekoOutbox } from "./stores/neko-outbox-store";

const RuntimeOwner = createContext(false);

/** One local-workbench lifetime, shared by its replaceable screens.
 * Standalone previews own themselves; nested screens inherit their host.
 * No UI is kept hidden, so navigation cannot leave duplicate shortcuts active.
 */
export function NekoRuntimeScope({ children }: { children: ReactNode }) {
  const inherited = useContext(RuntimeOwner);
  useEffect(() => {
    if (inherited) return;
    const stopReaper = startIdleReaper();
    const stopOutbox = startNekoOutbox();
    return () => {
      stopOutbox();
      stopReaper();
      void disposeAllNekoRuntimes();
    };
  }, [inherited]);
  return <RuntimeOwner.Provider value={true}>{children}</RuntimeOwner.Provider>;
}
