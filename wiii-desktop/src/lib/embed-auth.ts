/**
 * Embed authentication — parses URL hash/query params into typed config.
 * Sprint 176: Wiii Chat Embed for LMS iframe integration.
 *
 * URL format:
 *   /embed#token=JWT&refresh_token=JWT2&org=maritime-lms&domain=maritime&server=https://ai.maritime.edu&theme=light
 *
 * Supports two auth modes:
 *   1. JWT (token + optional refresh_token)
 *   2. Legacy (api_key + user_id)
 */

export interface EmbedConfig {
  // Auth (one of two modes)
  token?: string;
  refresh_token?: string;
  api_key?: string;
  user_id?: string;
  role?: string;

  // Context
  org?: string;
  domain?: string;
  server?: string;

  // UI
  theme?: "light" | "dark" | "system";
  hide_welcome?: boolean;
}

/**
 * Parse embed config from URL hash fragment.
 * Hash is preferred over query params because:
 * 1. Hash fragment is NOT sent to the server (security for JWT tokens)
 * 2. Angular/React routers don't interfere with hash params
 */
export function parseEmbedConfig(url?: string): EmbedConfig {
  const source = url || (typeof window !== "undefined" ? window.location.href : "");
  const config: EmbedConfig = {};

  // Try hash first, then query params as fallback
  let params: URLSearchParams;
  const hashIndex = source.indexOf("#");
  if (hashIndex !== -1) {
    params = new URLSearchParams(source.slice(hashIndex + 1));
  } else {
    try {
      params = new URL(source).searchParams;
    } catch {
      params = new URLSearchParams();
    }
  }

  // Auth — JWT mode
  const token = params.get("token");
  if (token) config.token = token;

  const refreshToken = params.get("refresh_token");
  if (refreshToken) config.refresh_token = refreshToken;

  // Auth — Legacy mode
  const apiKey = params.get("api_key");
  if (apiKey) config.api_key = apiKey;

  const userId = params.get("user_id");
  if (userId) config.user_id = userId;

  const role = params.get("role");
  if (role) config.role = role;

  // Context — Sprint 194c (D1): Validate formats to prevent injection
  const org = params.get("org");
  if (org && /^[a-zA-Z0-9_-]{1,64}$/.test(org)) config.org = org;

  const domain = params.get("domain");
  if (domain && /^[a-zA-Z0-9_-]{1,32}$/.test(domain)) config.domain = domain;

  // Sprint 194c (D1): Validate server URL — only allow http/https, normalize to origin
  const server = params.get("server");
  if (server) {
    try {
      const parsed = new URL(server);
      if (parsed.protocol === "https:" || parsed.protocol === "http:") {
        config.server = parsed.origin; // Strip path/query/fragment
      }
    } catch {
      // Invalid URL — silently reject
    }
  }

  // UI
  const theme = params.get("theme");
  if (theme === "light" || theme === "dark" || theme === "system") {
    config.theme = theme;
  }

  const hideWelcome = params.get("hide_welcome");
  if (hideWelcome === "true" || hideWelcome === "1") {
    config.hide_welcome = true;
  }

  return config;
}

/**
 * Validate that an embed config has sufficient auth info.
 * Returns null if valid, error message if invalid.
 */
export function validateEmbedConfig(config: EmbedConfig): string | null {
  const hasJwt = !!config.token;
  const hasLegacy = !!config.api_key && !!config.user_id;

  if (!hasJwt && !hasLegacy) {
    return "Missing auth: provide either 'token' (JWT) or 'api_key' + 'user_id' (legacy)";
  }

  return null;
}

/**
 * Determine auth mode from embed config.
 */
export function getAuthMode(config: EmbedConfig): "jwt" | "legacy" {
  return config.token ? "jwt" : "legacy";
}
