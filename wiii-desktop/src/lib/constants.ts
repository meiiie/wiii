/** App version */
export const APP_VERSION = "0.1.0";

/** App name */
export const APP_NAME = "Wiii";

/** Default server URL */
export const DEFAULT_SERVER_URL = "http://localhost:8000";

/** Default user settings */
export const DEFAULT_USER_ID = "desktop-user";
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
