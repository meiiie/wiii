/**
 * Root App component — initializes stores, mounts layout.
 * Sprint 106: Loading screen during init.
 */
import { lazy, Suspense, useEffect } from "react";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { useSettingsStore } from "@/stores/settings-store";
import { useAuthStore } from "@/stores/auth-store";
import type { AuthUser } from "@/stores/auth-store";
import { useConnectionStore } from "@/stores/connection-store";
import { useContextStore } from "@/stores/context-store";
import { useDomainStore } from "@/stores/domain-store";
import { useOrgStore } from "@/stores/org-store";
import { useChatStore } from "@/stores/chat-store";
import { useUIStore } from "@/stores/ui-store";
import { useToastStore } from "@/stores/toast-store";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { initClient } from "@/api/client";
import { buildAuthUserFromPayload, toCompatibilitySettingsRole } from "@/lib/auth-user";

const AppShell = lazy(async () => {
  const mod = await import("@/components/layout/AppShell");
  return { default: mod.AppShell };
});

const LoginScreen = lazy(async () => {
  const mod = await import("@/components/auth/LoginScreen");
  return { default: mod.LoginScreen };
});

const CommandPalette = lazy(async () => {
  const mod = await import("@/components/common/CommandPalette");
  return { default: mod.CommandPalette };
});

const AvatarPreview = lazy(async () => {
  const mod = await import("@/components/common/AvatarPreview");
  return { default: mod.AvatarPreview };
});

function BootSplash({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-screen bg-surface">
      <div className="flex flex-col items-center gap-4">
        <WiiiAvatar state="thinking" size={48} />
        <span className="text-sm text-text-tertiary">{label}</span>
      </div>
    </div>
  );
}

export default function App() {
  // Dev tool: ?preview=avatar shows avatar preview page
  if (window.location.search.includes("preview=avatar")) {
    return (
      <Suspense fallback={<BootSplash label="Wiii dang mo ban xem truoc..." />}>
        <AvatarPreview />
      </Suspense>
    );
  }

  const { loadSettings, settings, updateSettings, isLoaded: settingsLoaded } = useSettingsStore();
  const { loadAuth, loginWithTokens, isAuthenticated, isLoaded: authLoaded, authMode, user: authUser, isTokenExpiringSoon, refreshAccessToken } = useAuthStore();
  const { startPolling, stopPolling, setOnReconnect } = useConnectionStore();
  const { startPolling: startContextPolling, stopPolling: stopContextPolling } =
    useContextStore();
  const { fetchDomains, setOrgFilter } = useDomainStore();
  const { fetchOrganizations, setActiveOrg, detectSubdomainOrg, fetchAdminContext } = useOrgStore();
  const { loadConversations, isLoaded: chatsLoaded } = useChatStore();
  const { commandPaletteOpen, closeCommandPalette } = useUIStore();
  const { addToast } = useToastStore();

  // Register global keyboard shortcuts
  useKeyboardShortcuts();

  // Sprint 193: Handle web OAuth callback (hash-based token delivery)
  // Must run BEFORE auth state is checked so tokens are available immediately.
  useEffect(() => {
    if (!window.location.hash) return;
    const params = new URLSearchParams(window.location.hash.substring(1));
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    if (!accessToken || !refreshToken) return;

    const expiresIn = parseInt(params.get("expires_in") || "900", 10);
    const user: AuthUser = buildAuthUserFromPayload({
      user_id: params.get("user_id") || "",
      email: params.get("email") || "",
      name: params.get("name") || "",
      avatar_url: params.get("avatar_url") || "",
      role: params.get("role") || "",
      legacy_role: params.get("legacy_role") || "",
      platform_role: params.get("platform_role") || "user",
      organization_role: params.get("organization_role") || "",
      host_role: params.get("host_role") || "",
      role_source: params.get("role_source") || "",
      active_organization_id: params.get("active_organization_id") || "",
      organization_id: params.get("organization_id") || "",
      connector_id: params.get("connector_id") || "",
      identity_version: params.get("identity_version") || "",
    });

    // Sprint 193b: Extract organization_id from OAuth callback
    const orgId = user.active_organization_id || params.get("organization_id") || "";

    // Login immediately, then persist settings + clear hash
    loginWithTokens(accessToken, refreshToken, expiresIn, user).then(async () => {
      updateSettings({
        user_id: user.id,
        display_name: user.name || user.email,
        user_role: toCompatibilitySettingsRole(user),
        ...(orgId ? { organization_id: orgId } : {}),
      });
      // Sprint 218: Switch chat store to new user's conversations
      await useChatStore.getState().switchUser(user.id);
      // Clear hash AFTER login succeeds to prevent token leakage in browser history
      window.history.replaceState(null, "", window.location.pathname);
    }).catch((err) => {
      console.error("[OAuth] Login failed:", err);
      addToast("error", "Đăng nhập thất bại. Vui lòng thử lại.");
      // Clear hash even on failure to prevent stale token in URL
      window.history.replaceState(null, "", window.location.pathname);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize on mount
  useEffect(() => {
    async function init() {
      // 1. Load persisted settings
      await loadSettings();
      // 2. Load persisted auth state (Sprint 157)
      await loadAuth();
      // 3. Load persisted conversations
      await loadConversations();
    }
    init();
  }, [loadSettings, loadAuth, loadConversations]);

  // When settings AND auth are loaded, initialize client and start health polling
  useEffect(() => {
    // Sprint 218: Guard on BOTH settingsLoaded AND authLoaded to prevent race condition
    // Without authLoaded, API calls fire before OAuth tokens are available → 401
    if (!settingsLoaded || !authLoaded) return;
    if (!isAuthenticated) return;
    if (settings.server_url) {
      // Sprint 192: Initialize HTTP client with dynamic header resolver
      // Headers are resolved at request time from getAuthHeaders() — always fresh
      const client = initClient(settings.server_url, {});
      client.setHeaderResolver(() => useSettingsStore.getState().getAuthHeaders());
      // Sprint 192: Wire 401 interceptor for automatic token refresh
      client.setOnUnauthorized(async () => {
        const authState = useAuthStore.getState();
        if (authState.authMode !== "oauth") return false;
        return authState.refreshAccessToken(
          useSettingsStore.getState().settings.server_url,
        );
      });

      // Start health check polling
      startPolling();

      // Register reconnection celebration
      setOnReconnect(() => addToast("success", "Wiii đã quay lại rồi nè! ✨"));

      // Fetch available domains
      fetchDomains();

      // Sprint 175: Detect org from subdomain (web deployment)
      detectSubdomainOrg();

      // Sprint 156: Fetch organizations + restore saved org
      fetchOrganizations().then(() => {
        // Sprint 181: Fetch admin context after auth/org init
        fetchAdminContext();
        // Sprint 175: If subdomain detected, use it (skip saved org)
        const subdomainOrg = useOrgStore.getState().subdomainOrgId;
        const orgToActivate = subdomainOrg || settings.organization_id;
        if (orgToActivate) {
          setActiveOrg(orgToActivate);
          const org = useOrgStore.getState().organizations.find((o) => o.id === orgToActivate);
          if (org) {
            setOrgFilter(org.allowed_domains);
          }
        }
      });
    }

    return () => {
      stopPolling();
    };
  }, [settingsLoaded, authLoaded, isAuthenticated, settings.server_url, settings.api_key, settings.user_id, settings.user_role, startPolling, stopPolling, fetchDomains, fetchOrganizations, setActiveOrg, setOrgFilter, setOnReconnect, addToast, detectSubdomainOrg, fetchAdminContext, refreshAccessToken]);

  // Start context polling when active conversation changes (handles mid-session creation)
  const activeConv = useChatStore((s) => s.activeConversation());
  const sessionId = activeConv?.session_id || activeConv?.id || "";
  useEffect(() => {
    if (sessionId && settings.server_url) {
      startContextPolling(sessionId);
    }
    return () => {
      stopContextPolling();
    };
  }, [sessionId, settings.server_url, startContextPolling, stopContextPolling]);

  // Sprint 157: Auto-refresh JWT before expiration
  useEffect(() => {
    if (authMode !== "oauth" || !isAuthenticated) return;
    const interval = setInterval(() => {
      if (isTokenExpiringSoon()) {
        refreshAccessToken(settings.server_url);
      }
    }, 60_000); // Check every minute
    return () => clearInterval(interval);
  }, [authMode, isAuthenticated, isTokenExpiringSoon, refreshAccessToken, settings.server_url]);

  // Keep settings.user_id in sync with auth.user.id in OAuth mode.
  // Fixes race condition where loadSettings() loads stale anonymous UUID from
  // localStorage before loginWithTokens() updates it — any code using
  // settings.user_id (chat requests, memory tab, etc.) stays correct.
  useEffect(() => {
    if (authMode === "oauth" && authUser?.id && settings.user_id !== authUser.id) {
      updateSettings({ user_id: authUser.id });
    }
  }, [authMode, authUser?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Loading screen while stores initialize
  if (!settingsLoaded || !authLoaded || !chatsLoaded) {
    return <BootSplash label="Wiii dang thuc day..." />;
  }

  // Sprint 157: Show login screen when not authenticated
  if (!isAuthenticated) {
    return (
      <ErrorBoundary>
        <Suspense fallback={<BootSplash label="Wiii dang mo cong dang nhap..." />}>
          <LoginScreen />
        </Suspense>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <Suspense fallback={<BootSplash label="Wiii dang mo khong gian tro chuyen..." />}>
        <AppShell />
      </Suspense>
      <Suspense fallback={null}>
        <CommandPalette open={commandPaletteOpen} onClose={closeCommandPalette} />
      </Suspense>
    </ErrorBoundary>
  );
}
