/**
 * Root App component — initializes stores, mounts layout.
 * Sprint 106: Loading screen during init.
 */
import { useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { ChatView } from "@/components/chat/ChatView";
import { SettingsPage } from "@/components/settings";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { LoginScreen } from "@/components/auth/LoginScreen";
import { useSettingsStore } from "@/stores/settings-store";
import { useAuthStore } from "@/stores/auth-store";
import { useConnectionStore } from "@/stores/connection-store";
import { useContextStore } from "@/stores/context-store";
import { useDomainStore } from "@/stores/domain-store";
import { useOrgStore } from "@/stores/org-store";
import { useChatStore } from "@/stores/chat-store";
import { useUIStore } from "@/stores/ui-store";
import { useToastStore } from "@/stores/toast-store";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { CommandPalette } from "@/components/common/CommandPalette";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { initClient } from "@/api/client";
import { AvatarPreview } from "@/components/common/AvatarPreview";

export default function App() {
  // Dev tool: ?preview=avatar shows avatar preview page
  if (window.location.search.includes("preview=avatar")) {
    return <AvatarPreview />;
  }

  const { loadSettings, settings, isLoaded: settingsLoaded } = useSettingsStore();
  const { loadAuth, isAuthenticated, authMode, isTokenExpiringSoon, refreshAccessToken } = useAuthStore();
  const { startPolling, stopPolling, setOnReconnect } = useConnectionStore();
  const { startPolling: startContextPolling, stopPolling: stopContextPolling } =
    useContextStore();
  const { fetchDomains, setOrgFilter } = useDomainStore();
  const { fetchOrganizations, setActiveOrg } = useOrgStore();
  const { loadConversations, isLoaded: chatsLoaded } = useChatStore();
  const { settingsOpen, commandPaletteOpen, closeCommandPalette } = useUIStore();
  const { addToast } = useToastStore();

  // Register global keyboard shortcuts
  useKeyboardShortcuts();

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

  // When settings are loaded, initialize client and start health polling
  useEffect(() => {
    if (settings.server_url) {
      // Initialize HTTP client with current settings
      const headers: Record<string, string> = {
        "X-API-Key": settings.api_key,
        "X-User-ID": settings.user_id,
        "X-Role": settings.user_role,
      };
      if (settings.organization_id && settings.organization_id !== "personal") {
        headers["X-Organization-ID"] = settings.organization_id;
      }
      initClient(settings.server_url, headers);

      // Start health check polling
      startPolling();

      // Register reconnection celebration
      setOnReconnect(() => addToast("success", "Wiii đã quay lại rồi nè! ✨"));

      // Fetch available domains
      fetchDomains();

      // Sprint 156: Fetch organizations + restore saved org
      fetchOrganizations().then(() => {
        const savedOrgId = settings.organization_id;
        if (savedOrgId) {
          setActiveOrg(savedOrgId);
          const org = useOrgStore.getState().organizations.find((o) => o.id === savedOrgId);
          if (org) {
            setOrgFilter(org.allowed_domains);
          }
        }
      });
    }

    return () => {
      stopPolling();
    };
  }, [settings.server_url, settings.api_key, settings.user_id, settings.user_role, startPolling, stopPolling, fetchDomains, fetchOrganizations, setActiveOrg, setOrgFilter, setOnReconnect, addToast]);

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

  // Loading screen while stores initialize
  if (!settingsLoaded || !chatsLoaded) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-surface">
        <div className="flex flex-col items-center gap-4">
          <WiiiAvatar state="thinking" size={48} />
          <span className="text-sm text-text-tertiary">Wiii đang thức dậy...</span>
        </div>
      </div>
    );
  }

  // Sprint 157: Show login screen when not authenticated
  if (!isAuthenticated) {
    return (
      <ErrorBoundary>
        <LoginScreen />
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <AppShell>
        <ChatView />
      </AppShell>
      {settingsOpen && <SettingsPage />}
      <CommandPalette open={commandPaletteOpen} onClose={closeCommandPalette} />
    </ErrorBoundary>
  );
}
