import type { AdeGraph } from "./legacy-work-model";
import { emptyAdeGraph, loadAdeWorkSnapshot } from "./legacy-work-storage";

/**
 * Existing fixed-task sessions still require their original Work/root proof.
 * Load it on demand; normal workspace boot never reads Work. There are no
 * creation, transition, write or deletion operations for the retired feature.
 */
let state: { graph: AdeGraph; hydrated: boolean } = { graph: emptyAdeGraph(), hydrated: false };
let hydration: Promise<void> | null = null;

async function hydrate(): Promise<void> {
  if (state.hydrated) return;
  if (!hydration) {
    hydration = loadAdeWorkSnapshot().then((snapshot) => {
      state = { graph: snapshot?.graph ?? emptyAdeGraph(), hydrated: true };
    }).finally(() => { hydration = null; });
  }
  await hydration;
}

export const legacyWorkState = { getState: () => ({ ...state, hydrate }) };
