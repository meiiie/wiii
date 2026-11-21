import { create } from "zustand";
import { loadStore, saveStore } from "@/lib/storage";
import type { WorkbenchHost } from "./host";

export type WorkbenchSurface = "local" | "managed";

const WORKBENCH_STORE = "wiii-workbench.json";
const WORKBENCH_SURFACE_KEY = "surface";
const LEGACY_MODE_STORE = "neko-chill-mode.json";
const LEGACY_MODE_KEY = "mode";
const AUTH_STORE = "auth_state";
const AUTH_KEY = "data";

function hostAllowsLocalSurface(host: WorkbenchHost): boolean {
  return host.capabilities.localProcess && host.capabilities.localWorkspace;
}

/**
 * Persisted auth files can exist without containing an account (for example
 * after logout or an older install that wrote `{}`).  File presence alone is
 * therefore not managed-account evidence.
 */
export function hasManagedAccountState(value: unknown): boolean {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const state = value as Record<string, unknown>;
  const user = state.user;
  if (user && typeof user === "object" && !Array.isArray(user)) {
    const identity = user as Record<string, unknown>;
    if (
      (typeof identity.id === "string" && identity.id.trim().length > 0) ||
      (typeof identity.email === "string" && identity.email.trim().length > 0)
    ) {
      return true;
    }
  }
  // OAuth identity is only meaningful with a persisted user; logout writes
  // `{ user: null, authMode: "oauth" }`. Legacy mode has no user object and
  // represents an API-key choice whose credential remains in settings.
  return state.authMode === "legacy";
}

/**
 * Resolve the initial surface without mutating any legacy state.
 *
 * Desktop always starts locally; Service is a native capability surface.
 * Hosted web stays on its remotely-backed surface.
 */
export function resolveInitialWorkbenchSurface(
  host: WorkbenchHost,
  _storedSurface: unknown,
  _legacyMode: unknown,
  _hasManagedAccount: boolean,
): WorkbenchSurface {
  if (!hostAllowsLocalSurface(host)) return "managed";
  return "local";
}

interface WorkbenchState {
  surface: WorkbenchSurface;
  isLoaded: boolean;
  load: (host: WorkbenchHost) => Promise<void>;
  setSurface: (
    surface: WorkbenchSurface,
    host: WorkbenchHost,
  ) => Promise<void>;
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  surface: "local",
  isLoaded: false,

  load: async (host) => {
    const [storedSurface, legacyMode, authState] = await Promise.all([
      loadStore<unknown>(WORKBENCH_STORE, WORKBENCH_SURFACE_KEY, null),
      loadStore<unknown>(LEGACY_MODE_STORE, LEGACY_MODE_KEY, null),
      loadStore<unknown>(AUTH_STORE, AUTH_KEY, null),
    ]);

    set({
      surface: resolveInitialWorkbenchSurface(
        host,
        storedSurface,
        legacyMode,
        hasManagedAccountState(authState),
      ),
      isLoaded: true,
    });
  },

  setSurface: async (surface, host) => {
    const next =
      surface === "local" && !hostAllowsLocalSurface(host)
        ? "managed"
        : surface;
    set({ surface: next });
    await saveStore(WORKBENCH_STORE, WORKBENCH_SURFACE_KEY, next);
  },
}));
