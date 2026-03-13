/** App version */
export const APP_VERSION = "0.1.0";

/** App name */
export const APP_NAME = "Wiii";

function isLocalBrowserHost(): boolean {
  if (typeof window === "undefined") return false;
  const { hostname } = window.location;
  return hostname === "localhost" || hostname === "127.0.0.1";
}

/** Default server URL — localhost in dev, same-origin in production web builds */
export const DEFAULT_SERVER_URL = (
  (typeof import.meta !== "undefined" && import.meta.env?.DEV) || isLocalBrowserHost()
    ? "http://localhost:8000"
    : typeof window !== "undefined" ? window.location.origin : ""
);

/** Default user settings */
// Sprint 194b: DEFAULT_USER_ID removed — anonymous UUID generated at runtime
export const DEFAULT_USER_ROLE = "student" as const;
export const DEFAULT_DISPLAY_NAME = "User";
export const DEFAULT_DOMAIN = "maritime";
export const DEFAULT_LANGUAGE = "vi" as const;

/** Health check interval (ms) */
export const HEALTH_CHECK_INTERVAL = 30_000;

/** SSE streaming version */
export const DEFAULT_STREAMING_VERSION = "v3" as const;

/** Maximum message length */
export const MAX_MESSAGE_LENGTH = 10_000;

/** Context info polling interval (ms) — Sprint 80 */
export const CONTEXT_POLL_INTERVAL = 30_000;

/** Sprint 156: Personal workspace org ID (no multi-tenant) */
export const PERSONAL_ORG_ID = "personal";
