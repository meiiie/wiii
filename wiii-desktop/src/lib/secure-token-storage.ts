/**
 * Sprint 176: Secure token storage — separates auth tokens from general settings.
 *
 * Tokens are stored in a dedicated "wiii_auth_tokens" store, separate from
 * the general auth_state store. This isolation:
 * - Prevents accidental token exposure in settings exports
 * - Enables future upgrade to OS keyring (tauri-plugin-keyring) when stable
 * - Makes token lifecycle management cleaner
 */
import { loadStore, saveStore, deleteStore } from "@/lib/storage";

const TOKEN_STORE_NAME = "wiii_auth_tokens";
const TOKEN_KEY = "tokens";

export interface SecureTokens {
  access_token: string;
  refresh_token: string;
  expires_at: number; // Unix timestamp (ms)
}

export async function storeTokens(
  accessToken: string,
  refreshToken: string,
  expiresAt: number,
): Promise<void> {
  const tokens: SecureTokens = {
    access_token: accessToken,
    refresh_token: refreshToken,
    expires_at: expiresAt,
  };
  await saveStore(TOKEN_STORE_NAME, TOKEN_KEY, tokens);
}

export async function loadTokens(): Promise<SecureTokens | null> {
  const tokens = await loadStore<SecureTokens | null>(
    TOKEN_STORE_NAME,
    TOKEN_KEY,
    null,
  );
  return tokens;
}

export async function clearTokens(): Promise<void> {
  await deleteStore(TOKEN_STORE_NAME, TOKEN_KEY);
}

// =============================================================================
// Sprint 192: Secure API Key Storage
// =============================================================================
const API_KEY_KEY = "api_key";

export async function storeApiKey(apiKey: string): Promise<void> {
  await saveStore(TOKEN_STORE_NAME, API_KEY_KEY, apiKey);
}

export async function loadApiKey(): Promise<string | null> {
  const key = await loadStore<string | null>(TOKEN_STORE_NAME, API_KEY_KEY, null);
  return key;
}

export async function clearApiKey(): Promise<void> {
  await deleteStore(TOKEN_STORE_NAME, API_KEY_KEY);
}

// =============================================================================
// Sprint 194b (H5): Secure Facebook Cookie Storage
// Moved from settings-store (plaintext localStorage) to secure token storage
// to prevent PII exposure via XSS attacks.
// =============================================================================
const FB_COOKIE_KEY = "facebook_cookie";

export async function storeFacebookCookie(cookie: string): Promise<void> {
  await saveStore(TOKEN_STORE_NAME, FB_COOKIE_KEY, cookie);
}

export async function loadFacebookCookie(): Promise<string | null> {
  const cookie = await loadStore<string | null>(TOKEN_STORE_NAME, FB_COOKIE_KEY, null);
  return cookie;
}

export async function clearFacebookCookie(): Promise<void> {
  await deleteStore(TOKEN_STORE_NAME, FB_COOKIE_KEY);
}
