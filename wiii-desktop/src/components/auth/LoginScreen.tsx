/**
 * LoginScreen — Google OAuth login for Wiii Desktop.
 * Sprint 157: "Đăng Nhập"
 *
 * Shows a centered login card with Google OAuth button.
 * Also provides a "Developer mode" toggle for legacy API key auth.
 */
import { useState } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { useAuthStore } from "@/stores/auth-store";
import type { AuthUser } from "@/stores/auth-store";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";

// Dynamic import that bypasses Vite static analysis (plugin may not be installed)
const _oauthMod = "@fabianlars/tauri-plugin-oauth";
function loadOAuth(): Promise<{ start: (opts: { ports: number[] }) => Promise<number>; onUrl: (cb: (url: string) => void) => void; cancel: (port: number) => Promise<void> }> {
  return import(/* @vite-ignore */ _oauthMod) as Promise<any>;
}

export function LoginScreen() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDevMode, setShowDevMode] = useState(false);
  const { settings, updateSettings } = useSettingsStore();
  const { loginWithTokens, setLegacyMode } = useAuthStore();

  const handleGoogleLogin = async () => {
    setError(null);
    setIsLoading(true);

    try {
      // Try to use tauri-plugin-oauth for localhost redirect
      let port: number;
      try {
        const oauth = await loadOAuth();
        port = await oauth.start({ ports: [8765, 8766, 8767, 8768, 8769] });
      } catch {
        // Fallback: use a fixed port if plugin not available
        port = 8765;
      }

      // Open system browser to backend OAuth login
      const loginUrl = `${settings.server_url}/api/v1/auth/google/login?port=${port}`;

      try {
        const { open } = await import("@tauri-apps/plugin-shell");
        await open(loginUrl);
      } catch {
        // Browser fallback: use window.open
        window.open(loginUrl, "_blank");
      }

      // Wait for callback from the OAuth redirect to localhost
      // The tauri-plugin-oauth will capture the URL
      try {
        const oauth = await loadOAuth();
        const callbackUrl = await new Promise<string>((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error("OAuth timeout (60s)")), 60000);
          oauth.onUrl((url: string) => {
            clearTimeout(timeout);
            resolve(url);
          });
        });

        // Sprint 160b: Parse tokens from URL fragment (#) with fallback to query (?)
        // Fragments are never sent to the server — prevents token leakage to logs/proxies.
        const url = new URL(callbackUrl);
        const params = url.hash
          ? new URLSearchParams(url.hash.substring(1))
          : url.searchParams; // backward compat with pre-160b backends
        const accessToken = params.get("access_token");
        const refreshToken = params.get("refresh_token");
        const expiresIn = parseInt(params.get("expires_in") || "1800", 10);
        const userId = params.get("user_id") || "";
        const email = params.get("email") || "";
        const name = params.get("name") || "";
        const avatarUrl = params.get("avatar_url") || "";

        if (!accessToken || !refreshToken) {
          throw new Error("Missing tokens in callback");
        }

        const user: AuthUser = { id: userId, email, name, avatar_url: avatarUrl, role: "student" };
        await loginWithTokens(accessToken, refreshToken, expiresIn, user);

        // Sync user info to settings
        await updateSettings({
          user_id: userId,
          display_name: name || email,
        });

        await oauth.cancel(port);
      } catch (oauthErr) {
        // If tauri-plugin-oauth isn't available, show manual instructions
        throw new Error(
          "Không thể nhận callback từ Google. Vui lòng thử lại hoặc dùng Developer Mode."
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDevModeActivate = () => {
    setLegacyMode();
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-surface">
      <div className="w-full max-w-sm mx-auto flex flex-col items-center gap-6 px-6">
        {/* Wiii avatar */}
        <WiiiAvatar state="idle" size={56} />

        {/* Title */}
        <div className="text-center">
          <h1
            className="text-3xl font-normal text-text"
            style={{ fontFamily: '"Source Serif 4", "Noto Serif", Georgia, ui-serif, serif' }}
          >
            Chào mừng đến Wiii
          </h1>
          <p className="mt-2 text-sm text-text-tertiary">
            Trợ lý AI thông minh cho học tập và nghiên cứu
          </p>
        </div>

        {/* Google login button */}
        <button
          onClick={handleGoogleLogin}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-3 h-11 px-6 rounded-lg bg-white border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 active:bg-gray-100 transition-colors disabled:opacity-50 shadow-sm"
        >
          {isLoading ? (
            <div className="w-5 h-5 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
          )}
          <span>{isLoading ? "Đang đăng nhập..." : "Đăng nhập với Google"}</span>
        </button>

        {/* Error message */}
        {error && (
          <div className="w-full p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Divider */}
        <div className="w-full flex items-center gap-3">
          <div className="flex-1 h-px bg-border" />
          <span className="text-[11px] text-text-tertiary">hoặc</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        {/* Developer mode toggle */}
        {!showDevMode ? (
          <button
            onClick={() => setShowDevMode(true)}
            className="text-xs text-text-tertiary hover:text-text-secondary transition-colors"
          >
            Developer Mode (API Key)
          </button>
        ) : (
          <div className="w-full flex flex-col gap-3">
            <p className="text-xs text-text-tertiary text-center">
              Dành cho nhà phát triển — nhập API Key thủ công
            </p>
            <input
              type="password"
              placeholder="API Key"
              value={settings.api_key}
              onChange={(e) => updateSettings({ api_key: e.target.value })}
              className="w-full h-9 px-3 rounded-lg bg-surface-secondary border border-border text-sm text-text placeholder:text-text-tertiary focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
            <button
              onClick={handleDevModeActivate}
              disabled={!settings.api_key}
              className="w-full h-9 rounded-lg bg-surface-tertiary text-sm text-text-secondary hover:bg-surface-secondary transition-colors disabled:opacity-50"
            >
              Tiếp tục với API Key
            </button>
          </div>
        )}

        {/* Footer */}
        <p className="text-[10px] text-text-tertiary text-center mt-4">
          by The Wiii Lab
        </p>
      </div>
    </div>
  );
}
